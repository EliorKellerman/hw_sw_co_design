# test_advanced_performance.py (Corrected)

import unittest
import copy
import timeit
from lazydeepcopy import DeepcopyBatcher

class TestAdvancedPerformance(unittest.TestCase):
    """
    More complex and realistic performance benchmarks for lazydeepcopy.
    These tests model specific usage patterns like data dependencies and
    heavy proxy interaction.
    """

    def setUp(self):
        """Reusable complex object for tests."""
        self.base_object = {
            'config': {'setting1': True, 'setting2': 12.34},
            'data_points': list(range(100)),
            'metadata': {'source': 'A', 'timestamps': []}
        }
        self.num_ops = 200 # Number of sequential operations or objects
        self.num_runs = 5   # Number of times to run the whole test for timeit

    def test_chained_copy_performance(self):
        """
        Benchmark 2: Chained/Dependent Copies.

        This simulates a state evolution workflow where each step depends on the
        result of the previous copy and modification. This pattern prevents
        large-scale batching, highlighting per-operation overhead.
        """
        
        # --- Traditional Method ---
        def run_traditional_chained():
            current_obj = self.base_object
            for i in range(self.num_ops):
                # Create a copy of the current state
                next_obj = copy.deepcopy(current_obj)
                # Mutate it
                next_obj['metadata']['timestamps'].append(i)
                # The next iteration depends on this new object
                current_obj = next_obj
            return current_obj

        # --- Lazy/Proxy Method (Corrected) ---
        def run_lazy_chained():
            batcher = DeepcopyBatcher()
            current_proxy = batcher.defer_proxy(self.base_object)
            for i in range(self.num_ops):
                # Any access to current_proxy will resolve it. The copy is made here.
                # Then we mutate the resolved object.
                current_proxy['metadata']['timestamps'].append(i)
                
                # --- FIX IS HERE ---
                # We defer a copy of the *resolved data*, not the proxy itself.
                current_proxy = batcher.defer_proxy(current_proxy._resolve())
            
            # Final resolution
            return current_proxy._resolve()

        # --- Timing ---
        traditional_time = timeit.timeit(run_traditional_chained, number=self.num_runs)
        lazy_time = timeit.timeit(run_lazy_chained, number=self.num_runs)

        print("\n\n--- Benchmark 2: Chained/Dependent Copy Performance ---")
        print("Scenario: Simulates state evolution (copy -> mutate -> copy -> ...).")
        print("This prevents effective batching, testing single-operation overhead.")
        print(f"Operations per run: {self.num_ops}")
        print(f"Number of test runs: {self.num_runs}")
        print(f"Traditional `copy.deepcopy` time: {traditional_time:.6f} seconds")
        print(f"Lazy `defer_proxy` time:          {lazy_time:.6f} seconds")
        
        if lazy_time < traditional_time:
            percentage_gain = ((traditional_time - lazy_time) / traditional_time) * 100
            print(f"Result: Lazy version was ~{percentage_gain:.1f}% faster.")
        else:
            percentage_loss = ((lazy_time - traditional_time) / lazy_time) * 100
            print(f"Result: Lazy version was ~{percentage_loss:.1f}% slower due to overhead.")

    def test_proxy_access_performance(self):
        """
        Benchmark 3: Proxy Object Access.

        This measures the overhead of accessing data through the proxy layer.
        It first creates a batch of objects and then accesses an attribute
        on each of them repeatedly.
        """
        access_count = 10

        # --- Traditional Method ---
        def run_traditional_access():
            # 1. Create all copies up front
            copies = [copy.deepcopy(self.base_object) for _ in range(self.num_ops)]
            # 2. Access data on the real objects
            total = 0
            for obj in copies:
                for _ in range(access_count):
                    total += len(obj['data_points'])
            return total

        # --- Lazy/Proxy Method ---
        def run_lazy_access():
            batcher = DeepcopyBatcher(max_items=self.num_ops + 1)
            # 1. Defer all copies (very fast)
            proxies = [batcher.defer_proxy(self.base_object) for _ in range(self.num_ops)]
            
            # The first access to any proxy will trigger the single batch flush.
            
            # 2. Access data through the proxies
            total = 0
            for proxy in proxies:
                for _ in range(access_count):
                    # __getattr__ overhead is incurred here on every access
                    total += len(proxy['data_points'])
            return total

        # --- Timing ---
        traditional_time = timeit.timeit(run_traditional_access, number=self.num_runs)
        lazy_time = timeit.timeit(run_lazy_access, number=self.num_runs)
        
        print("\n\n--- Benchmark 3: Proxy Access Performance ---")
        print("Scenario: Creates a batch of objects, then accesses their attributes repeatedly.")
        print("This measures the performance difference between direct access and proxy delegation.")
        print(f"Objects created: {self.num_ops}, Accesses per object: {access_count}")
        print(f"Number of test runs: {self.num_runs}")
        print(f"Traditional (create then access) time: {traditional_time:.6f} seconds")
        print(f"Lazy Proxy (defer then access) time:   {lazy_time:.6f} seconds")

        if lazy_time < traditional_time:
            percentage_gain = ((traditional_time - lazy_time) / traditional_time) * 100
            print(f"Result: Lazy version was ~{percentage_gain:.1f}% faster overall.")
        else:
            percentage_loss = ((lazy_time - traditional_time) / lazy_time) * 100
            print(f"Result: Lazy version was ~{percentage_loss:.1f}% slower overall.")


if __name__ == '__main__':
    unittest.main()