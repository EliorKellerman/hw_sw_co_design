"""
Benchmark to measure performance of the python builtin method copy.deepcopy

Performance is tested on a nested dictionary and a dataclass

Author: Pieter Eendebak

"""
from lazydeepcopy import DeepcopyBatcher
import copy
import pyperf
from dataclasses import dataclass


@dataclass
class A:
    string: str
    lst: list
    boolean: bool


def benchmark_reduce(n):
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
        _ = copy.deepcopy(c)
    dt = pyperf.perf_counter() - t0
    return dt


def benchmark_memo(n):
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
        _ = copy.deepcopy(data)
    dt = pyperf.perf_counter() - t0
    return dt


def benchmark(n):
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
            _ = copy.deepcopy(a)
            dt += pyperf.perf_counter() - t0
        for s in ['red', 'blue', 'green']:
            dc.string = s
            for kk in range(5):
                dc.lst[0] = kk
                for b in [True, False]:
                    dc.boolean = b
                    t0 = pyperf.perf_counter()
                    _ = copy.deepcopy(dc)
                    dt += pyperf.perf_counter() - t0
    return dt

def benchmark_batched(n):
    a = {
        'list': [1, 2, 3, 43],
        't': (1 ,2, 3),
        'str': 'hello',
        'subdict': {'a': True}
    }
    dc = A('hello', [1, 2, 3], True)

    dt = 0
    for ii in range(n):
        # ---- a case (30 copies) ----
        batch_a = [a.copy() for _ in range(30)]  # shallow distinct tops
        t0 = pyperf.perf_counter()
        _ = copy.deepcopy(batch_a)
        dt += pyperf.perf_counter() - t0

        # ---- dc case (30 copies) ----
        variants = []
        for s in ['red','blue','green']:
            dc.string = s
            for kk in range(5):
                dc.lst[0] = kk
                for b in [True, False]:
                    dc.boolean = b
                    variants.append(copy.copy(dc))  # shallow copy for distinct tops
        # variants has 30 entries
        t0 = pyperf.perf_counter()
        _ = copy.deepcopy(variants)
        dt += pyperf.perf_counter() - t0

    return dt

def benchmark_batched_lazy(n):
    a = {
        'list': [1, 2, 3, 43],
        't': (1 ,2, 3),
        'str': 'hello',
        'subdict': {'a': True}
    }
    dc = A('hello', [1,2,3], True)
    batcher = DeepcopyBatcher(max_items=999999)  # let get() drive flush

    dt = 0.0
    for ii in range(n):
        # 30 copies of 'a'
        for _ in range(30):
            _ = batcher.defer(a.copy())    # distinct tops
        t0 = pyperf.perf_counter()
        batcher.flush()                     # one deepcopy for those 30
        dt += pyperf.perf_counter() - t0

        # 30 copies of 'dc' variants
        variants = []
        for s in ['red','blue','green']:
            dc.string = s
            for kk in range(5):
                dc.lst[0] = kk
                for b in [True, False]:
                    dc.boolean = b
                    variants.append(copy.copy(dc))  # distinct tops
        for v in variants:
            _ = batcher.defer(v)
        t0 = pyperf.perf_counter()
        batcher.flush()                     # one deepcopy for those 30
        dt += pyperf.perf_counter() - t0
    return dt


if __name__ == "__main__":
    runner = pyperf.Runner()
    runner.metadata['description'] = "deepcopy benchmark"

    runner.bench_time_func('deepcopy', benchmark)
    # runner.bench_time_func('deepcopy', benchmark_batched)
    # runner.bench_time_func('deepcopy', benchmark_batched_lazy)
    # runner.bench_time_func('deepcopy_reduce', benchmark_reduce)
    # runner.bench_time_func('deepcopy_memo', benchmark_memo)
