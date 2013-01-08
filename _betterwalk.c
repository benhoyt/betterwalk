// Betterwalk C speedups
//
// There's a fair bit of PY_MAJOR_VERSION boilerplate to support both Python 2
// and Python 3 -- the structure of this is taken from here:
// http://docs.python.org/3.3/howto/cporting.html

#include <Python.h>
#include <windows.h>
#include <osdefs.h>

#if PY_MAJOR_VERSION >= 3
#define INITERROR return NULL
#else
#define INITERROR return
#endif

static PyObject *
win32_error_unicode(char* function, Py_UNICODE* filename)
{
    errno = GetLastError();
    if (filename)
        return PyErr_SetFromWindowsErrWithUnicodeFilename(errno, filename);
    else
        return PyErr_SetFromWindowsErr(errno);
}

/* Below, we *know* that ugo+r is 0444 */
#if _S_IREAD != 0400
#error Unsupported C library
#endif
static int
attributes_to_mode(DWORD attr)
{
    int m = 0;
    if (attr & FILE_ATTRIBUTE_DIRECTORY)
        m |= _S_IFDIR | 0111; /* IFEXEC for user,group,other */
    else
        m |= _S_IFREG;
    if (attr & FILE_ATTRIBUTE_READONLY)
        m |= 0444;
    else
        m |= 0666;
    return m;
}

double
filetime_to_time(FILETIME *filetime)
{
    const double SECONDS_BETWEEN_EPOCHS = 11644473600.0;

    unsigned long long total = (unsigned long long)filetime->dwHighDateTime << 32 |
                               (unsigned long long)filetime->dwLowDateTime;
    return (double)total / 10000000.0 - SECONDS_BETWEEN_EPOCHS;
}

static PyObject *
find_data_to_stat(WIN32_FIND_DATAW *data)
{
    PY_LONG_LONG size = (PY_LONG_LONG)data->nFileSizeHigh << 32 |
                        (PY_LONG_LONG)data->nFileSizeLow;

    PyObject* result = Py_BuildValue("(iiiiiiKddd)",
        attributes_to_mode(data->dwFileAttributes), // st_mode
        0,                                          // st_ino
        0,                                          // st_dev
        0,                                          // st_nlink
        0,                                          // st_uid
        0,                                          // st_gid
        size,                                       // st_size
        filetime_to_time(&data->ftLastAccessTime),  // st_atime,
        filetime_to_time(&data->ftLastWriteTime),   // st_mtime,
        filetime_to_time(&data->ftCreationTime));   // st_ctime,
    return result;
}

static PyObject *
listdir(PyObject *self, PyObject *args)
{
    PyObject *d, *v;
    HANDLE hFindFile;
    BOOL result;
    WIN32_FIND_DATAW wFileData;
    Py_UNICODE *wnamebuf;
    Py_ssize_t len;
    PyObject *po;
    PyObject *name_stat;

    if (!PyArg_ParseTuple(args, "U:listdir", &po))
        return NULL;

    /* Overallocate for \\*.*\0 */
    len = PyUnicode_GET_SIZE(po);
    wnamebuf = malloc((len + 5) * sizeof(wchar_t));
    if (!wnamebuf) {
        PyErr_NoMemory();
        return NULL;
    }
    wcscpy(wnamebuf, PyUnicode_AS_UNICODE(po));
    if (len > 0) {
        Py_UNICODE wch = wnamebuf[len-1];
        if (wch != L'/' && wch != L'\\' && wch != L':')
            wnamebuf[len++] = L'\\';
        wcscpy(wnamebuf + len, L"*.*");
    }
    if ((d = PyList_New(0)) == NULL) {
        free(wnamebuf);
        return NULL;
    }
    Py_BEGIN_ALLOW_THREADS
    hFindFile = FindFirstFileW(wnamebuf, &wFileData);
    Py_END_ALLOW_THREADS
    if (hFindFile == INVALID_HANDLE_VALUE) {
        int error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND) {
            free(wnamebuf);
            return d;
        }
        Py_DECREF(d);
        win32_error_unicode("FindFirstFileW", wnamebuf);
        free(wnamebuf);
        return NULL;
    }
    do {
        /* Skip over . and .. */
        if (wcscmp(wFileData.cFileName, L".") != 0 &&
            wcscmp(wFileData.cFileName, L"..") != 0) {
            v = PyUnicode_FromUnicode(wFileData.cFileName, wcslen(wFileData.cFileName));
            if (v == NULL) {
                Py_DECREF(d);
                d = NULL;
                break;
            }
            name_stat = PyTuple_Pack(2, v, find_data_to_stat(&wFileData));
            if (name_stat == NULL) {
                Py_DECREF(v);
                Py_DECREF(d);
                d = NULL;
                break;
            }
            if (PyList_Append(d, name_stat) != 0) {
                Py_DECREF(v);
                Py_DECREF(d);
                Py_DECREF(name_stat);
                d = NULL;
                break;
            }
            Py_DECREF(v);
        }
        Py_BEGIN_ALLOW_THREADS
        result = FindNextFileW(hFindFile, &wFileData);
        Py_END_ALLOW_THREADS
        /* FindNextFile sets error to ERROR_NO_MORE_FILES if
           it got to the end of the directory. */
        if (!result && GetLastError() != ERROR_NO_MORE_FILES) {
            Py_DECREF(d);
            win32_error_unicode("FindNextFileW", wnamebuf);
            FindClose(hFindFile);
            free(wnamebuf);
            return NULL;
        }
    } while (result == TRUE);

    if (FindClose(hFindFile) == FALSE) {
        Py_DECREF(d);
        win32_error_unicode("FindClose", wnamebuf);
        free(wnamebuf);
        return NULL;
    }
    free(wnamebuf);
    return d;
}

static PyMethodDef betterwalk_methods[] = {
    {"listdir", (PyCFunction)listdir, METH_VARARGS, NULL},
    {NULL, NULL, NULL, NULL},
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "_betterwalk",
        NULL,
        0,
        betterwalk_methods,
        NULL,
        NULL,
        NULL,
        NULL,
};
#endif

#if PY_MAJOR_VERSION >= 3
PyObject *
PyInit__betterwalk(void)
{
    PyObject *module = PyModule_Create(&moduledef);
#else
void
init_betterwalk(void)
{
    PyObject *module = Py_InitModule("_betterwalk", betterwalk_methods);
#endif
    if (module == NULL) {
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}