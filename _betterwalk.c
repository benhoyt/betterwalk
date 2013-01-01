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
win32_error(char* function, char* filename)
{
    /* XXX We should pass the function name along in the future.
       (_winreg.c also wants to pass the function name.)
       This would however require an additional param to the
       Windows error object, which is non-trivial.
    */
    errno = GetLastError();
    if (filename)
        return PyErr_SetFromWindowsErrWithFilename(errno, filename);
    else
        return PyErr_SetFromWindowsErr(errno);
}

static PyObject *
win32_error_unicode(char* function, Py_UNICODE* filename)
{
    /* XXX - see win32_error for comments on 'function' */
    errno = GetLastError();
    if (filename)
        return PyErr_SetFromWindowsErrWithUnicodeFilename(errno, filename);
    else
        return PyErr_SetFromWindowsErr(errno);
}

static PyObject *
listdir(PyObject *self, PyObject *args)
{
    PyObject *d, *v;
    HANDLE hFindFile;
    BOOL result;
    WIN32_FIND_DATA FileData;
    char namebuf[MAX_PATH+5]; /* Overallocate for \\*.*\0 */
    char *bufptr = namebuf;
    Py_ssize_t len = sizeof(namebuf)-5; /* only claim to have space for MAX_PATH */

    PyObject *po;
    if (PyArg_ParseTuple(args, "U:listdir", &po)) {
        WIN32_FIND_DATAW wFileData;
        Py_UNICODE *wnamebuf;
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
                if (PyList_Append(d, v) != 0) {
                    Py_DECREF(v);
                    Py_DECREF(d);
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
    /* Drop the argument parsing error as narrow strings
       are also valid. */
    PyErr_Clear();

    if (!PyArg_ParseTuple(args, "et#:listdir",
                          Py_FileSystemDefaultEncoding, &bufptr, &len))
        return NULL;
    if (len > 0) {
        char ch = namebuf[len-1];
        if (ch != SEP && ch != ALTSEP && ch != ':')
            namebuf[len++] = '/';
        strcpy(namebuf + len, "*.*");
    }

    if ((d = PyList_New(0)) == NULL)
        return NULL;

    Py_BEGIN_ALLOW_THREADS
    hFindFile = FindFirstFile(namebuf, &FileData);
    Py_END_ALLOW_THREADS
    if (hFindFile == INVALID_HANDLE_VALUE) {
        int error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND)
            return d;
        Py_DECREF(d);
        return win32_error("FindFirstFile", namebuf);
    }
    do {
        /* Skip over . and .. */
        if (strcmp(FileData.cFileName, ".") != 0 &&
            strcmp(FileData.cFileName, "..") != 0) {
            v = PyString_FromString(FileData.cFileName);
            if (v == NULL) {
                Py_DECREF(d);
                d = NULL;
                break;
            }
            if (PyList_Append(d, v) != 0) {
                Py_DECREF(v);
                Py_DECREF(d);
                d = NULL;
                break;
            }
            Py_DECREF(v);
        }
        Py_BEGIN_ALLOW_THREADS
        result = FindNextFile(hFindFile, &FileData);
        Py_END_ALLOW_THREADS
        /* FindNextFile sets error to ERROR_NO_MORE_FILES if
           it got to the end of the directory. */
        if (!result && GetLastError() != ERROR_NO_MORE_FILES) {
            Py_DECREF(d);
            win32_error("FindNextFile", namebuf);
            FindClose(hFindFile);
            return NULL;
        }
    } while (result == TRUE);

    if (FindClose(hFindFile) == FALSE) {
        Py_DECREF(d);
        return win32_error("FindClose", namebuf);
    }

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