"""Simple benchmark to compare the speed of BetterWalk with os.walk()."""

import os
import sys
import timeit

import betterwalk

def benchmark(path):
    def do_os_walk():
        for root, dirs, files in os.walk(path):
            pass

    def do_betterwalk():
        for root, dirs, files in betterwalk.walk(path):
            pass

    print('Benchmarking walks on {0}'.format(path))
    os_walk_time = timeit.timeit(do_os_walk, number=1)
    betterwalk_time = timeit.timeit(do_betterwalk, number=1)
    print('os.walk took {0:.3}s, BetterWalk took {1:.3}s -- {2:.2}x as fast'.format(
          os_walk_time, betterwalk_time, os_walk_time / betterwalk_time))

if __name__ == '__main__':
    benchmark(sys.argv[1] if len(sys.argv) > 1 else '.')
