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
5x as fast on Windows, and TODO as fast on Linux. So we're not talking about
micro-optimizations.

Also, and somewhat relatedly, many people have also asked for a version of
`os.listdir()` that yields filenames as it iterates instead of returning them
as one big list.

BetterWalk adds a faster `walk()`, `iterdir()`, and `iterdir_stat()`. They're
pretty easy to use, but [see below](#the-api) for more information on the API.


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

The API for `betterwalk.walk()` is exactly the same as `os.walk()`, so just
[read the Python docs](http://docs.python.org/2/library/os.html#os.walk).

Using `iterdir()` is extremely straight-forward. It's just the same as
`os.listdir()` except it yields filenames as it gets them, instead of
returning them all at once in a list. This can be nicer as well as more
efficient for processing large directories.

And `iterdir_stat()` is similar, except it yields tuples of `(filename,
stat_result)`, where `stat_result` is a tuple-like structure [as returned by
`os.stat()`](http://docs.python.org/2/library/os.html#os.stat). However, just
like `stat()`, the values returned are implementation dependent, and `st_`
fields that the system doesn't know are set to `None`.

So here's a good usage pattern for `iterdir_stat`. This is in fact very
similar to how the faster `os.walk()` implementation works:

```python
for filename, st in betterwalk.iterdir_stat(path):
    if st.st_mode is None:
        st = os.stat(os.path.join(path, filename))
    if stat.S_ISDIR(st.st_mode):
        # handle directory
    else:
        # handle file
```


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
