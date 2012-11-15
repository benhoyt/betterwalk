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
import sys

# TODO: Reparse points / Win32 symbolic links need testing. From Random832:
# http://mail.python.org/pipermail/python-ideas/2012-November/017794.html

# In the presence of reparse points (i.e. symbolic links) on win32, I 
# believe information about whether the destination is meant to be a 
# directory is still provided (I haven't confirmed this, but I know you're 
# required to provide it when making a symlink). This is discarded when 
# the st_mode field is populated with the information that it is a 
# symlink. If the goal is "speed up os.walk", it might be worth keeping 
# this information and using it in os.walk(..., followlinks=True) - maybe 
# the windows version of the stat result has a field for the windows 
# attributes?

# It's arguable, though, that symbolic links on windows are rare enough 
# not to matter.


__version__ = '0.5'
__all__ = ['iterdir', 'iterdir_stat', 'walk']

# Windows implementation
if sys.platform == 'win32':
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
        """See iterdir_stat.__doc__ below for docstring."""
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
                name = data.cFileName
                if name not in ('.', '..'):
                    st = find_data_to_stat(data)
                    yield (name, st)

                success = FindNextFile(handle, data_p)
                if not success:
                    error = ctypes.GetLastError()
                    if error == ERROR_NO_MORE_FILES:
                        break
                    raise ctypes.WinError()
        finally:
            if not FindClose(handle):
                raise ctypes.WinError()


# Linux, OS X, and BSD implementation
elif sys.platform.startswith(('linux', 'darwin', 'freebsd')):
    import ctypes
    import ctypes.util

    DIR_p = ctypes.c_void_p

    # TODO: Linux version -- may be different on OS X etc?
    class dirent(ctypes.Structure):
        _fields_ = (
            ('d_ino', ctypes.c_ulong),
            ('d_off', ctypes.c_long),
            ('d_reclen', ctypes.c_ushort),
            ('d_type', ctypes.c_byte),
            ('d_name', ctypes.c_char * 256),
        )
    dirent_p = ctypes.POINTER(dirent)
    dirent_pp = ctypes.POINTER(dirent_p)

    # TODO: test with unicode filenames
    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    opendir = libc.opendir
    opendir.argtypes = [ctypes.c_char_p]
    opendir.restype = DIR_p

    readdir = libc.readdir_r
    readdir.argtypes = [DIR_p, dirent_p, dirent_pp]
    readdir.restype = ctypes.c_int

    closedir = libc.closedir
    closedir.argtypes = [DIR_p]
    closedir.restype = ctypes.c_int

    DT_DIR = 4

    def type_to_stat(d_type):
        if d_type == DT_DIR:
            st_mode = stat.S_IFDIR | 0o111
        else:
            st_mode = stat.S_IFREG
        st = os.stat_result((st_mode, None, None, None, None, None,
                             None, None, None, None))
        return st

    def iterdir_stat(path='.'):
        """See iterdir_stat.__doc__ below for docstring."""
        dir_p = opendir(path)
        if not dir_p:
            raise OSError('TODO: opendir error: {0}'.format(ctypes.get_errno()))
        try:
            entry = dirent()
            result = dirent_p()
            while True:
                if readdir_r(dir_p, entry, result):
                    raise OSError('TODO: readdir_r error: {0}'.format(ctypes.get_errno()))
                if not result:
                    break
                name = entry.contents.d_name
                if name not in ('.', '..'):
                    st = type_to_stat(p.contents.d_type)
                    yield (name, st)
        finally:
            if closedir(dir_p):
                raise OSError('TODO: closedir error: {0}'.format(ctypes.get_errno()))


# Some other system -- have to fall back to using os.listdir() and os.stat()
else:
    def iterdir_stat(path='.'):
        for name in os.listdir(path):
            st = os.stat(os.path.join(path, name))
            yield (name, st)


iterdir_stat.__doc__ = \
"""Yield tuples of (filename, stat_result) for each filename in directory
given by "path". Like listdir(), '.' and '..' are skipped. The values are
yielded in system-dependent order.

Each stat_result is an object like you'd get by calling os.stat() on that
file, but not all information is present on all systems, and st_* fields that
are not available will be None.

In practice, stat_result is a full os.stat() on Windows, but only the "is
type" bits of the st_mode field are available on Linux/OS X/BSD.
"""


def iterdir(path='.'):
    """Like os.listdir(), but yield filenames from given path as we get them,
    instead of returning them all at once in a list.
    """
    for filename, stat_result in iterdir_stat(path):
        yield filename


def walk(top, topdown=True, onerror=None, followlinks=False):
    """Just like os.walk(), but faster, as it uses iterdir_stat internally."""
    # The structure of this function is copied directly from Python 2.7's
    # version of os.walk()

    # First get a list of all filenames/stat_results in the directory. We
    # could try to keep this an iterator, but error handling gets messy.
    try:
        names_stats = list(iterdir_stat(top))
    except OSError as err:
        if onerror is not None:
            onerror(err)
        return

    # Determine which are files and which are directories
    dirs = []
    dir_stats = []
    nondirs = []
    for name, st in names_stats:
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
