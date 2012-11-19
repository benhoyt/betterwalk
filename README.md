BetterWalk, a better and faster os.walk() for Python
====================================================

BetterWalk is a somewhat better and significantly faster version of Python's
`os.walk()`, as well as a generator version of `os.listdir()`.

This GitHub repo is where I'm developing it, but it's also available as a
[library on PyPI](TODO).


Background
----------

Python's built-in `os.walk()` is significantly slower than it needs to be,
because -- in addition to calling `listdir()` on each directory -- it calls
`stat()` on each file to determine whether the filename is a directory or not.
But both `FindFirstFile` / `FindNextFile` on Windows and `readdir` on
Linux/BSD already tell you whether the files returned are directories or not,
so no further `stat` system calls are needed. In short, you can reduce the
number of system calls from O(N) to O(log N).

In practice, removing all these extra `stat()` calls makes `os.walk()` about
5x as fast on Windows, so at least on Windows we're *not* talking about
micro-optimizations. However, in my benchmarks on Linux, the gains are much
more modest -- betterwalk.walk() is only about 10% faster than os.walk().
TODO: add OS X results

Somewhat relatedly, many people have also asked for a version of
`os.listdir()` that yields filenames as it iterates instead of returning them
as one big list.

As well as a faster `walk()`, BetterWalk adds `iterdir_stat()` and
`iterdir()`. They're pretty easy to use, but [see below](#the-api) for the
full API docs.


Why you should care
-------------------

I'd love for these incremental (but significant!) improvements to be added to
the Python standard library. BetterWalk was released to help test the concept
and get it in shape for inclusion in the standard `os` module.

There are various third-party "path" and "walk directory" libraries available,
but Python's `os` module isn't going away anytime soon. So we might as well
speed it up and add small improvements where possible.

**So I'd love it if you could help test BetterWalk, report bugs, suggest
improvement, or comment on the API.** And perhaps you'll see these speed-ups
and API additions in Python 3.4 ... :-)


The API
-------

### walk()

The API for `betterwalk.walk()` is exactly the same as `os.walk()`, so just
[read the Python docs](http://docs.python.org/2/library/os.html#os.walk).

### iterdir_stat()

The `iterdir_stat()` function is BetterWalk's main workhorse. It's defined as
follows:

```python
iterdir_stat(path='.', pattern='*', fields=None)
```

It yield tuples of (filename, stat_result) for each filename that matches
`pattern` in the directory given by `path`. Like os.listdir(), `.` and `..`
are skipped, and the values are yielded in system-dependent order.

Pattern matching is done as per fnmatch.fnmatch(), but is more efficient if
the system's directory iteration supports pattern matching (like Windows).

The `fields` parameter specifies which fields to provide in each stat_result.
If None, only the fields the operating system can get "for free" are present
in stat_result. Otherwise "fields" must be an iterable of `st_*` attribute
names that the caller wants in each stat_result. The only special attribute
name is `st_mode_type`, which means the type bits in the st_mode field.

In practice, all fields are provided for free on Windows; whereas only the
st_mode_type information is provided for free on Linux, Mac OS X, and BSD.

Here's a good usage pattern for `iterdir_stat`. This is in fact almost exactly
how the faster `os.walk()` implementation uses it:

```python
dirs = []
nondirs = []
for name, st in betterwalk.iterdir_stat(top, fields=['st_mode_type']):
    if stat.S_ISDIR(st.st_mode):
        dirs.append(name)
    else:
        nondirs.append(name)
```

### iterdir()

The `iterdir()` function is similar to iterdir_stat(), except it doesn't
provide any stat information, but simply yields a list of filenames.


Further reading
---------------

* [Thread I started on the python-ideas list about speeding up os.walk()](http://mail.python.org/pipermail/python-ideas/2012-November/017770.html)
* [Question on StackOverflow about why os.walk() is slow and pointers to fix it](http://stackoverflow.com/questions/2485719/very-quickly-getting-total-size-of-folder)
* [Question on StackOverflow asking about iterating over a directory](http://stackoverflow.com/questions/4403598/list-files-in-a-folder-as-a-stream-to-begin-process-immediately)


To-do
-----

* Finish Linux/BSD version and get it working
* Add tests (copy CPython's unit tests for `walk` and `listdir`?)
* Ensure it works in Python 3
* Consider adding `walk_stat()` to speed up things like totalling size
  of a directory tree on Windows
* Consider adding `glob=None` param to `listdir()` to take advantage of
  FindFirst/Next's wildcard matching


Flames, comments, bug reports
-----------------------------

Please send flames, comments, and questions about BetterWalk to Ben Hoyt:

http://benhoyt.com/

File bug reports or feature requests at the GitHub project page:

https://github.com/benhoyt/betterwalk
