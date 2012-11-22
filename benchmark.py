"""Simple benchmark to compare the speed of BetterWalk with os.walk()."""

import optparse
import os
import sys
import timeit

import betterwalk

# TODO: run each benchmark a couple of times (in different orders), take the min, then compare
# TODO: better printing out of results

DEPTH = 4
NUM_DIRS = 5
NUM_FILES = 50

def create_tree(path, depth=DEPTH):
    """Create a directory tree at path with given depth, and NUM_DIRS and
    NUM_FILES at each level.
    """
    os.mkdir(path)
    for i in range(NUM_FILES):
        filename = os.path.join(path, 'file{0:03}.txt'.format(i))
        with open(filename, 'wb') as f:
            line = 'The quick brown fox jumps over the lazy dog.\n'
            if i == 0:
                # So we have at least one big file per directory
                f.write(line * 20000)
            else:
                f.write(line * i * 10)
    if depth <= 1:
        return
    for i in range(NUM_DIRS):
        dirname = os.path.join(path, 'dir{0:03}'.format(i))
        create_tree(dirname, depth - 1)

def benchmark(path):
    def do_os_walk():
        for root, dirs, files in os.walk(path):
            pass

    def do_betterwalk():
        for root, dirs, files in betterwalk.walk(path):
            pass

    # Run this once first to cache things, so we're not benchmarking I/O
    do_betterwalk()

    print('Benchmarking walks on {0}'.format(path))
    os_walk_time = timeit.timeit(do_os_walk, number=1)
    betterwalk_time = timeit.timeit(do_betterwalk, number=1)
    print('os.walk took {0:.3}s, BetterWalk took {1:.3}s -- {2:.2}x as fast'.format(
          os_walk_time, betterwalk_time, os_walk_time / betterwalk_time))

def main():
    """Usage: benchmark.py [-h] [tree_dir]

Create 230MB directory tree named "benchtree" (relative to this script) and
benchmark os.walk() versus betterwalk.walk(). If tree_dir is specified,
benchmark using it instead of creating a tree.
"""
    parser = optparse.OptionParser(usage=main.__doc__.rstrip())
    options, args = parser.parse_args()

    if args:
        tree_dir = args[0]
    else:
        tree_dir = os.path.join(os.path.dirname(__file__), 'benchtree')
        if not os.path.exists(tree_dir):
            print 'Creating tree at {0}: depth={1}, num_dirs={2}, num_files={3}'.format(
                tree_dir, DEPTH, NUM_DIRS, NUM_FILES)
            create_tree(tree_dir)

    benchmark(tree_dir)

if __name__ == '__main__':
    main()
