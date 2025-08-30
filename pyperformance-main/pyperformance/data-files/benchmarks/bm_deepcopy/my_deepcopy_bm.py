import copy
import copy_fastpath
import copy_fastmemo
import copy_merged
import pyperf
from dataclasses import dataclass
import gc

# Example custom class
@dataclass
class Person:
    name: str
    age: int
    hobbies: list

def create_structures(scale=1):
    """Create 10 different complex Python structures, scaled up by 'scale'."""
    structures = []

    # 1. Nested list
    structures.append([[i for i in range(10 * scale)] for _ in range(10 * scale)])

    # 2. Nested dict
    structures.append({f"key{i}": {"val": i, "nested": [i, i+1, i+2]} for i in range(10 * scale)})

    # 3. Tuple with lists
    structures.append((list(range(5 * scale)), list(range(5 * scale, 10 * scale))))

    # 4. Set of frozensets
    structures.append({frozenset({i, i+1, i+2}) for i in range(5 * scale)})

    # 5. Dict with mixed types
    structures.append({"nums": list(range(3 * scale)), "words": tuple(f"w{j}" for j in range(3 * scale)), "flag": True})

    # 6. List of dicts
    structures.append([{"id": i, "val": i**2} for i in range(10 * scale)])

    # 7. Custom dataclass objects
    structures.append([Person(f"Person_{i}", 20 + i, [f"hobby{j}" for j in range(5 * scale)]) for i in range(2 * scale)])

    # 8. Nested combination
    structures.append({"list": list(range(2 * scale)) + [{"inner": (j, j+1)} for j in range(2 * scale)], "set": set(range(3 * scale))})

    # 9. String manipulations
    structures.append([f"string_{i}" for i in range(100 * scale)])

    # 10. Dict of lists of dicts
    structures.append({i: [{"val": j} for j in range(3 * scale)] for i in range(5 * scale)})

    return structures


def create_structures_complex(scale=1):
    """
    Create complex, deeply nested structures with lots of shared mutable sub-objects.
    These are designed to challenge the MEMO-OPT in copy_merged.py, since
    the optimization only applies to atomics/immutables, not to these mutables.
    """
    structures = []

    # 1. Deeply nested list of lists with shared sublists
    shared_sublist = [i for i in range(10 * scale)]
    nested = [shared_sublist for _ in range(10 * scale)]
    structures.append([nested for _ in range(5 * scale)])

    # 2. List of dicts, each dict shares the same tuple (mutable values)
    shared_tuple = ([i for i in range(5 * scale)], [j for j in range(5 * scale, 10 * scale)])
    structures.append([{'a': shared_tuple, 'b': [k for k in range(3 * scale)]} for _ in range(10 * scale)])

    # 3. Dict of lists, where lists contain references to the same dict
    shared_dict = {'x': 1, 'y': [1, 2, 3]}
    structures.append({i: [shared_dict for _ in range(3 * scale)] for i in range(5 * scale)})

    # 4. List of tuples, each tuple contains a list that is also shared
    shared_inner_list = [i**2 for i in range(10 * scale)]
    structures.append([(shared_inner_list, i) for i in range(10 * scale)])

    # 5. List of sets, each set contains a tuple with a shared list
    shared_list = [i for i in range(10 * scale)]
    structures.append([{(i, tuple(shared_list)) for i in range(5 * scale)} for _ in range(5 * scale)])

    # 6. Deeply nested mix: list of dicts of lists of tuples of lists
    base_list = [i for i in range(3 * scale)]
    structures.append([
        {f'k{j}': [(j, base_list)] * 2 for j in range(3 * scale)}
        for _ in range(3 * scale)
    ])

    # 7. Cyclic reference: list contains itself
    cyclic = []
    cyclic.append(cyclic)
    structures.append(cyclic)

    # 8. Dict with values that are lists of dicts, all sharing a sub-dict
    shared_subdict = {'shared': True, 'data': [1, 2, 3]}
    structures.append({i: [{'ref': shared_subdict, 'idx': j} for j in range(3 * scale)] for i in range(5 * scale)})

    # 9. List of lists, each containing the same set (mutable)
    shared_set = set(range(10 * scale))
    structures.append([[shared_set for _ in range(3 * scale)] for _ in range(5 * scale)])

    # 10. Tuple of lists, each list contains references to the same dict and set
    shared_dict2 = {'foo': 'bar', 'nums': list(range(10 * scale))}
    shared_set2 = set(range(5 * scale))
    structures.append(tuple([[shared_dict2, shared_set2] for _ in range(10 * scale)]))

    return structures

def deepcopy_bm(structures, n=10):
    """Deepcopy each structure individually"""
    dt = 0
    for ii in range(n):
        for s in structures:
            t0 = pyperf.perf_counter()
            _ = copy.deepcopy(s)
            dt += pyperf.perf_counter() - t0
    return dt

def deepcopy_fastpath_bm(structures, n=10):
    """Deepcopy each structure individually"""
    dt = 0
    for ii in range(n):
        for s in structures:
            t0 = pyperf.perf_counter()
            _ = copy_fastpath.deepcopy(s)
            dt += pyperf.perf_counter() - t0
    return dt

def deepcopy_fastmemo_bm(structures, n=10):
    """Deepcopy each structure individually"""
    dt = 0
    for ii in range(n):
        for s in structures:
            t0 = pyperf.perf_counter()
            _ = copy_fastmemo.deepcopy(s)
            dt += pyperf.perf_counter() - t0
    return dt

def deepcopy_merged_bm(structures, n=10):
    """Deepcopy each structure individually"""
    dt = 0
    for ii in range(n):
        for s in structures:
            t0 = pyperf.perf_counter()
            _ = copy_merged.deepcopy(s)
            dt += pyperf.perf_counter() - t0
    return dt

def clear_python_cache():
    """Force garbage collection and clear caches if needed."""
    gc.collect()
    # Add more cache-clearing logic here if you use any custom caches

def run_benchmark():
    runner = pyperf.Runner()
    
    for scale in [1, 2, 3]:
        # Benchmark with simpler structures
        structures = create_structures(scale=scale)
        # runner.bench_func(f"Deepcopy (scale={scale})", deepcopy_bm, structures)
        # clear_python_cache()
        # runner.bench_func(f"Deepcopy FastPath (scale={scale})", deepcopy_fastpath_bm, structures)
        # clear_python_cache()
        # runner.bench_func(f"Deepcopy FastMemo (scale={scale})", deepcopy_fastmemo_bm, structures)
        # clear_python_cache()
        runner.bench_func(f"Deepcopy Merged (scale={scale})", deepcopy_merged_bm, structures)
        clear_python_cache()
    
        # Benchmark with more complex structures
        complex_structures = create_structures_complex(scale=scale)
        # runner.bench_func(f"Deepcopy complex (scale={scale})", deepcopy_bm, complex_structures)
        # clear_python_cache()
        # runner.bench_func(f"Deepcopy FastPath complex (scale={scale})", deepcopy_fastpath_bm, complex_structures)
        # clear_python_cache()
        # runner.bench_func(f"Deepcopy FastMemo complex (scale={scale})", deepcopy_fastmemo_bm, complex_structures)
        # clear_python_cache()
        runner.bench_func(f"Deepcopy Merged complex (scale={scale})", deepcopy_merged_bm, complex_structures)
        clear_python_cache()


if __name__ == "__main__":
    run_benchmark()
