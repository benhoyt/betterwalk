"""BetterWalk, a better and faster os.walk() for Python.

BetterWalk is a somewhat better and significantly faster version of Python's
os.walk(), as well as a generator version of os.listdir(). See README.md or
https://github.com/benhoyt/betterwalk for rationale and documentation.

BetterWalk is released under the new BSD 3-clause license. See LICENSE.txt for
the full license text.

"""

import ctypes
import os
import stat

__version__ = '0.5'
__all__ = ['iterdir', 'iterdir_stat', 'walk']

# Windows implementation
if os.name == 'nt':
    from ctypes import wintypes

    # Various constants from windows.h
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    ERROR_FILE_NOT_FOUND = 2
    ERROR_NO_MORE_FILES = 18
    FILE_ATTRIBUTE_READONLY = 1
    FILE_ATTRIBUTE_DIRECTORY = 16
    FILE_ATTRIBUTE_REPARSE_POINT = 1024

    # Numer of seconds between 1601-01-01 and 1970-01-01
    SECONDS_BETWEEN_EPOCHS = 11644473600

    kernel32 = ctypes.windll.kernel32

    # ctypes wrappers for (wide string versions of) FindFirstFile,
    # FindNextFile, and FindClose
    FindFirstFile = kernel32.FindFirstFileW
    FindFirstFile.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.WIN32_FIND_DATAW),
    ]
    FindFirstFile.restype = wintypes.HANDLE

    FindNextFile = kernel32.FindNextFileW
    FindNextFile.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.WIN32_FIND_DATAW),
    ]
    FindNextFile.restype = wintypes.BOOL

    FindClose = kernel32.FindClose
    FindClose.argtypes = [wintypes.HANDLE]
    FindClose.restype = wintypes.BOOL

    # The conversion functions below are taken more or less straight from
    # CPython's Modules/posixmodule.c

    def attributes_to_mode(attributes):
        """Convert Win32 dwFileAttributes to st_mode."""
        mode = 0
        if attributes & FILE_ATTRIBUTE_DIRECTORY:
            mode |= stat.S_IFDIR | 0o111
        else:
            mode |= stat.S_IFREG
        if attributes & FILE_ATTRIBUTE_READONLY:
            mode |= 0o444
        else:
            mode |= 0o666
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            mode |= stat.S_IFLNK
        return mode

    def filetime_to_time(filetime):
        """Convert Win32 FILETIME to time since Unix epoch in seconds."""
        total = filetime.dwHighDateTime << 32 | filetime.dwLowDateTime
        return total / 10000000.0 - SECONDS_BETWEEN_EPOCHS

    def find_data_to_stat(data):
        """Convert Win32 FIND_DATA struct to stat_result."""
        st_mode = attributes_to_mode(data.dwFileAttributes)
        st_ino = 0
        st_dev = 0
        st_nlink = 0
        st_uid = 0
        st_gid = 0
        st_size = data.nFileSizeHigh << 32 | data.nFileSizeLow
        st_atime = filetime_to_time(data.ftLastAccessTime)
        st_mtime = filetime_to_time(data.ftLastWriteTime)
        st_ctime = filetime_to_time(data.ftCreationTime)
        st = os.stat_result((st_mode, st_ino, st_dev, st_nlink, st_uid,
                             st_gid, st_size, st_atime, st_mtime, st_ctime))
        return st

    def iterdir_stat(path='.'):
        """Yield tuples of (filename, stat_result) for each filename in
        directory given by "path". Like listdir(), '.' and '..' are skipped.
        The values are yielded in system-dependent order.
        
        Each stat_result is an object like you'd get by calling os.stat() on
        that file, but not all information is present on all systems, and st_*
        fields that are not available will be None.

        In practice, stat_result is a full os.stat() on Windows, but only the
        "is type" bits of the st_mode field are available on Linux/BSD/OS X.
        """
        # Note that Windows doesn't need *.* anymore, just *
        filename = os.path.join(path, '*')

        # Call FindFirstFile and errors
        data = wintypes.WIN32_FIND_DATAW()
        data_p = ctypes.byref(data)
        handle = FindFirstFile(filename, data_p)
        if handle == INVALID_HANDLE_VALUE:
            error = ctypes.GetLastError()
            if error == ERROR_FILE_NOT_FOUND:
                # No files, don't yield anything
                return
            raise ctypes.WinError()

        # Call FindNextFile in a loop, stopping when no more files
        try:
            while True:
                # Skip '.' and '..' (current and parent directory), but
                # otherwise yield (filename, stat_result) tuple
                if data.cFileName not in ('.', '..'):
                    st = find_data_to_stat(data)
                    yield (data.cFileName, st)

                success = FindNextFile(handle, data_p)
                if not success:
                    error = ctypes.GetLastError()
                    if error == ERROR_NO_MORE_FILES:
                        break
                    raise ctypes.WinError()
        finally:
            if not FindClose(handle):
                raise ctypes.WinError()


# Linux/BSD -- this is only half-tested and doesn't work at the moment, but
# leaving here for future use
else:
    import ctypes
    import ctypes.util

    class DIR(ctypes.Structure):
        pass
    DIR_p = ctypes.POINTER(DIR)

    class dirent(ctypes.Structure):
        _fields_ = (
            ('d_ino', ctypes.c_long),
            ('d_off', ctypes.c_long),
            ('d_reclen', ctypes.c_ushort),
            ('d_type', ctypes.c_byte),
            ('d_name', ctypes.c_char * 256)
        )
    dirent_p = ctypes.POINTER(dirent)

    _libc = ctypes.CDLL(ctypes.util.find_library('c'))
    _opendir = _libc.opendir
    _opendir.argtypes = [ctypes.c_char_p]
    _opendir.restype = DIR_p

    _readdir = _libc.readdir
    _readdir.argtypes = [DIR_p]
    _readdir.restype = dirent_p

    _closedir = _libc.closedir
    _closedir.argtypes = [DIR_p]
    _closedir.restype = ctypes.c_int

    DT_DIR = 4

    def _type_to_stat(d_type):
        if d_type == DT_DIR:
            st_mode = stat.S_IFDIR | 0o111
        else:
            st_mode = stat.S_IFREG
        st = os.stat_result((st_mode, None, None, None, None, None,
                             None, None, None, None))
        return st

    def listdir_stat(dirname='.', glob=None):
        dir_p = _opendir(dirname)
        try:
            while True:
                p = _readdir(dir_p)
                if not p:
                    break
                name = p.contents.d_name
                if name not in ('.', '..'):
                    st = _type_to_stat(p.contents.d_type)
                    yield (name, st)
        finally:
            _closedir(dir_p)


def iterdir(path='.'):
    """Like os.listdir(), but yield filenames as we get them, instead of
    returning them all at once in a list.
    """
    for filename, stat_result in iterdir_stat(path):
        yield filename


def walk(top, topdown=True, onerror=None, followlinks=False):
    """Just like os.walk(), but faster, as it uses iterdir_stat internally."""
    # First get an iterator over the directory using iterdir_stat
    try:
        names_stats_iter = iterdir_stat(top)
    except OSError, err:
        if onerror is not None:
            onerror(err)
        return

    # Determine which are files and which are directories
    dirs = []
    dir_stats = []
    nondirs = []
    for name, st in names_stats_iter:
        if st.st_mode is None:
            st = os.stat(os.path.join(top, name))
        if stat.S_ISDIR(st.st_mode):
            dirs.append(name)
            dir_stats.append(st)
        else:
            nondirs.append(name)

    # Yield before recursion if going top down
    if topdown:
        yield top, dirs, nondirs

    # Recurse into sub-directories, following symbolic links if "followlinks"
    for name, st in zip(dirs, dir_stats):
        new_path = os.path.join(top, name)
        if followlinks or not stat.S_ISLNK(st.st_mode):
            for x in walk(new_path, topdown, onerror, followlinks):
                yield x

    # Yield before recursion if going bottom up
    if not topdown:
        yield top, dirs, nondirs


if __name__ == '__main__':
    import datetime
    import sys
    import time

    path = sys.argv[1] if len(sys.argv) > 1 else '.'

    time0 = time.clock()
    for root, dirs, files in walk(path):
        pass
    elapsed1 = time.clock() - time0
    print('our walk', elapsed1)

    time0 = time.clock()
    for root, dirs, files in os.walk(path):
        pass
    elapsed2 = time.clock() - time0
    print('os.walk', elapsed2)

    print('ours was', elapsed2 / elapsed1, 'times faster')
