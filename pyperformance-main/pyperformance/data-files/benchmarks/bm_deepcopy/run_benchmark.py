"""
Benchmark to measure performance of the python builtin method copy.deepcopy

Performance is tested on a nested dictionary and a dataclass

Author: Pieter Eendebak

"""
import copy
import copy_fastpath
import copy_fastmemo
import copy_merged  
import pyperf
from dataclasses import dataclass


@dataclass
class A:
    string: str
    lst: list
    boolean: bool


def benchmark_reduce(n, deepcopy_func):
    """ 
    Benchmark where the __reduce__ functionality is used.

    This benchmark creates a custom class C that implements the __reduce__ and __setstate__ methods,
    which are used by the copy module for pickling and copying objects. The benchmark measures the time
    it takes to perform n deep copies of an instance of C, thus testing the performance of deepcopy
    when __reduce__ is involved.
    """
    class C(object):
        def __init__(self):
            self.a = 1
            self.b = 2

        def __reduce__(self):
            return (C, (), self.__dict__)

        def __setstate__(self, state):
            self.__dict__.update(state)
    c = C()

    t0 = pyperf.perf_counter()
    for ii in range(n):
        _ = deepcopy_func(c)
    dt = pyperf.perf_counter() - t0
    return dt


def benchmark_memo(n, deepcopy_func):
    """ 
    Benchmark where the memo functionality is used.

    This benchmark creates a data structure with shared references (the same list object appears multiple times).
    It measures the time to perform n deep copies of this structure, which exercises the memoization logic in
    copy.deepcopy (to avoid copying the same object multiple times).
    """
    A = [1] * 100
    data = {'a': (A, A, A), 'b': [A] * 100}

    t0 = pyperf.perf_counter()
    for ii in range(n):
        _ = deepcopy_func(data)
    dt = pyperf.perf_counter() - t0
    return dt


def benchmark(n, deepcopy_func):
    """ 
    Benchmark on some standard data types.

    This benchmark measures the time to deepcopy a variety of standard Python data types, including
    dictionaries, lists, tuples, strings, and a dataclass instance. It performs multiple deep copies
    of these objects in nested loops to simulate typical usage patterns and to get a stable timing.
    """
    a = {
        'list': [1, 2, 3, 43],
        't': (1 ,2, 3),
        'str': 'hello',
        'subdict': {'a': True}
    }
    dc = A('hello', [1, 2, 3], True)

    dt = 0
    for ii in range(n):
        for jj in range(30):
            t0 = pyperf.perf_counter()
            _ = deepcopy_func(a)
            dt += pyperf.perf_counter() - t0
        for s in ['red', 'blue', 'green']:
            dc.string = s
            for kk in range(5):
                dc.lst[0] = kk
                for b in [True, False]:
                    dc.boolean = b
                    t0 = pyperf.perf_counter()
                    _ = deepcopy_func(dc)
                    dt += pyperf.perf_counter() - t0
    return dt

if __name__ == "__main__":
    runner = pyperf.Runner()
    runner.metadata['description'] = "deepcopy benchmark"

    # # Regular deepcopy
    # runner.bench_time_func('deepcopy', lambda n: benchmark(n, copy.deepcopy))
    # runner.bench_time_func('deepcopy_reduce', lambda n: benchmark_reduce(n, copy.deepcopy))
    # runner.bench_time_func('deepcopy_memo', lambda n: benchmark_memo(n, copy.deepcopy))

    # # Fastpath deepcopy
    # runner.bench_time_func('deepcopy_fastpath', lambda n: benchmark(n, copy_fastpath.deepcopy))
    # runner.bench_time_func('deepcopy_fastpath_reduce', lambda n: benchmark_reduce(n, copy_fastpath.deepcopy))
    # runner.bench_time_func('deepcopy_fastpath_memo', lambda n: benchmark_memo(n, copy_fastpath.deepcopy))

    # # Fastmemo deepcopy
    # runner.bench_time_func('deepcopy_fastmemo', lambda n: benchmark(n, copy_fastmemo.deepcopy))
    # runner.bench_time_func('deepcopy_fastmemo_reduce', lambda n: benchmark_reduce(n, copy_fastmemo.deepcopy))
    # runner.bench_time_func('deepcopy_fastmemo_memo', lambda n: benchmark_memo(n, copy_fastmemo.deepcopy))

    # Merged deepcopy
    runner.bench_time_func('deepcopy_merged', lambda n: benchmark(n, copy_merged.deepcopy))
    runner.bench_time_func('deepcopy_merged_reduce', lambda n: benchmark_reduce(n, copy_merged.deepcopy))
    runner.bench_time_func('deepcopy_merged_memo', lambda n: benchmark_memo(n, copy_merged.deepcopy))
