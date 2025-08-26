# test_lazydeepcopy.py

import unittest
import copy
import threading
import timeit
from lazydeepcopy import DeepcopyBatcher

class TestCorrectness(unittest.TestCase):
    """
    Tests the functional correctness of the DeepcopyBatcher and its proxies.
    """

    def setUp(self):
        """Set up a new batcher for each test."""
        self.batcher = DeepcopyBatcher()

    def test_basic_defer_get(self):
        """Test the explicit defer() and get() cycle."""
        original = {'a': [1, 2], 'b': {'c': 3}}
        handle = self.batcher.defer(original)
        
        # Before get(), the handle should not be ready
        self.assertFalse(handle._ready)
        
        # Trigger resolution
        copied = self.batcher.get(handle)
        
        # After get(), the handle is ready
        self.assertTrue(handle._ready)
        
        # Verify it's a deep copy
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
        self.assertIsNot(original['a'], copied['a'])
        self.assertIsNot(original['b'], copied['b'])

    def test_basic_proxy(self):
        """Test the transparent proxy access."""
        original = {'a': [1, 2], 'b': 3}
        proxy = self.batcher.defer_proxy(original)
        
        # The underlying handle should not be ready yet
        self.assertFalse(proxy._handle._ready)
        
        # Access an attribute to trigger resolution
        self.assertEqual(proxy['a'], [1, 2])
        
        # Now the handle should be ready
        self.assertTrue(proxy._handle._ready)
        
        # Get the real object and verify deep copy
        copied = proxy._resolve()
        self.assertEqual(original, copied)
        self.assertIsNot(original, copied)
        self.assertIsNot(original['a'], copied['a'])

    def test_consistency_at_access(self):
        """Verify 'at_access' consistency snapshots the object state at flush time."""
        original = {'data': [10, 20]}
        handle = self.batcher.defer(original, consistency="at_access")
        
        # Mutate the original object *before* the flush/get
        original['data'].append(30)
        
        # Now, get the copy
        copied = self.batcher.get(handle)
        
        # The copy should reflect the state at access time (i.e., with the mutation)
        self.assertEqual(copied, {'data': [10, 20, 30]})

    def test_consistency_strict(self):
        """Verify 'strict' consistency snapshots the object state at defer time."""
        original = {'data': [10, 20]}
        # 'strict' performs the copy immediately and bypasses batching
        handle = self.batcher.defer(original, consistency="strict")
        
        # The handle should be ready immediately
        self.assertTrue(handle._ready)
        
        # Mutate the original object *after* the defer call
        original['data'].append(30)
        
        # Get the copy
        copied = self.batcher.get(handle)
        
        # The copy should reflect the state at defer time (i.e., without the mutation)
        self.assertEqual(copied, {'data': [10, 20]})

    def test_alias_preserve(self):
        """Verify 'preserve' alias policy creates one copy for identical inputs."""
        obj = [1, 2, 3]
        
        # Defer the *same* object twice
        h1 = self.batcher.defer(obj, alias="preserve")
        h2 = self.batcher.defer(obj, alias="preserve")
        
        self.assertIsNot(h1, h2) # Handles are distinct
        
        # Resolve both
        c1 = self.batcher.get(h1)
        c2 = self.batcher.get(h2)
        
        # They should be deep copies of the original
        self.assertEqual(c1, obj)
        self.assertIsNot(c1, obj)
        
        # But they should point to the *same* copied instance
        self.assertIs(c1, c2, "With 'preserve' alias, copies of the same object should be identical")

    def test_alias_duplicate(self):
        """Verify 'duplicate' alias policy creates distinct copies for identical inputs."""
        obj = [1, 2, 3]
        
        # Defer the same object twice, forcing duplication
        h1 = self.batcher.defer(obj, alias="duplicate")
        h2 = self.batcher.defer(obj, alias="duplicate")
        
        # Resolve both
        c1 = self.batcher.get(h1)
        c2 = self.batcher.get(h2)
        
        # They should have the same value
        self.assertEqual(c1, c2)
        
        # But they should be *different* instances
        self.assertIsNot(c1, c2, "With 'duplicate' alias, copies should be distinct")

    def test_mixed_alias_policy_in_batch(self):
        """Test a batch with both preserve and duplicate policies."""
        obj_a = [100]
        obj_b = [200]
        
        # Defer A (preserved), B (duplicated), A (preserved)
        h_a1 = self.batcher.defer(obj_a, alias="preserve")
        h_b1 = self.batcher.defer(obj_b, alias="duplicate")
        h_a2 = self.batcher.defer(obj_a, alias="preserve")
        h_b2 = self.batcher.defer(obj_b, alias="duplicate")
        
        self.batcher.flush()
        
        c_a1 = self.batcher.get(h_a1)
        c_b1 = self.batcher.get(h_b1)
        c_a2 = self.batcher.get(h_a2)
        c_b2 = self.batcher.get(h_b2)
        
        self.assertIs(c_a1, c_a2, "Preserved items should point to the same copy")
        self.assertIsNot(c_b1, c_b2, "Duplicated items should point to different copies")
        self.assertEqual(c_b1, c_b2) # But have the same value
        self.assertIsNot(c_a1, c_b1)

    def test_auto_flush_on_max_items(self):
        """Test that the batch automatically flushes when max_items is reached."""
        batcher = DeepcopyBatcher(max_items=2)
        
        original1 = [1]
        h1 = batcher.defer(original1)
        
        # The first handle is not yet ready
        self.assertFalse(h1._ready)
        
        original2 = [2]
        h2 = batcher.defer(original2) # This should trigger the flush
        
        # Now the first handle should be ready without an explicit flush/get call
        self.assertTrue(h1._ready, "Batch should have auto-flushed")
        self.assertTrue(h2._ready)
        
        # Verify the content
        self.assertEqual(batcher.get(h1), original1)
        self.assertIsNot(batcher.get(h1), original1)


class TestPerformance(unittest.TestCase):
    """
    A simple performance comparison. This is not a rigorous benchmark, but it
    demonstrates the potential speedup from batching.
    """
    def test_performance_comparison(self):
        """Compares batched deepcopy vs. traditional deepcopy."""
        # A moderately complex object to copy, similar to pyperformance's workload
        complex_object = {
            'id': 123,
            'user': 'test',
            'data': [i for i in range(50)],
            'nested': {'a': True, 'b': None, 'c': (1, 2, 3), 'd': [4, 5, 6]}
        }
        num_copies = 10000  # Increased for a more stable measurement
        num_runs = 10

        # --- Traditional Method ---
        def run_traditional_deepcopy():
            # Performs N individual deepcopy operations.
            copies = [copy.deepcopy(complex_object) for _ in range(num_copies)]
            return copies

        # --- Lazy/Batched Method (Corrected) ---
        def run_lazy_deepcopy():
            batcher = DeepcopyBatcher(max_items=num_copies + 1) # Prevent auto-flush
            handles = [batcher.defer(complex_object) for _ in range(num_copies)]

            # --- FAIRNESS CORRECTION ---
            # 1. Flushing does the heavy lifting (the single deepcopy call).
            batcher.flush()
            # 2. We must also account for the cost of retrieving the results,
            #    which is what a real application would do. This makes the
            #    comparison fair.
            copies = [batcher.get(h) for h in handles]
            return copies

        # Time the executions
        # We run once before timing to warm up any caches etc.
        run_traditional_deepcopy()
        run_lazy_deepcopy()
        
        traditional_time = timeit.timeit(run_traditional_deepcopy, number=num_runs)
        lazy_time = timeit.timeit(run_lazy_deepcopy, number=num_runs)
        
        print("\n\n--- Corrected Performance Comparison ---")
        print(f"A fair test measures the total time to produce and retrieve all copies.")
        print(f"Number of copies per run: {num_copies}")
        print(f"Number of test runs: {num_runs}")
        print(f"Traditional `copy.deepcopy` time: {traditional_time:.6f} seconds")
        print(f"Batched `lazydeepcopy` time:      {lazy_time:.6f} seconds")
        
        # We expect lazy_time to be less than traditional_time, but not by 20x.
        # A 20-50% improvement (1.25x to 2.0x faster) is a realistic gain.
        self.assertLess(lazy_time, traditional_time, 
                        "Expected lazy deepcopy to be faster for this workload.")

        if lazy_time < traditional_time:
            percentage_gain = ((traditional_time - lazy_time) / traditional_time) * 100
            speedup = traditional_time / lazy_time
            print(f"Result: Batched version was {speedup:.2f}x faster (~{percentage_gain:.1f}% gain).")
        else:
            slowdown = (lazy_time / traditional_time)
            print(f"Result: Batched version was unexpectedly slower.")
        
        print("Note: This gain comes from reducing Python's function call overhead.\n")


class TestThreading(unittest.TestCase):
    """
    Tests basic thread safety of the DeepcopyBatcher.
    """
    def test_concurrent_defer_calls(self):
        """Ensure multiple threads can defer items without corrupting the queue."""
        num_threads = 10
        items_per_thread = 100
        total_items = num_threads * items_per_thread
        
        batcher = DeepcopyBatcher(max_items=total_items + 1) # Prevent auto-flush
        handles = []
        lock = threading.Lock()

        def worker():
            local_handles = []
            for i in range(items_per_thread):
                local_handles.append(batcher.defer([i]))
            
            with lock:
                handles.extend(local_handles)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # At this point, all deferrals should be in the queue
        self.assertEqual(len(batcher._queue), total_items)
        self.assertEqual(len(handles), total_items)
        
        # Now, flush everything
        batcher.flush()
        
        # All handles should now be ready
        self.assertTrue(all(h._ready for h in handles))
        
        # Verify a few copies to be sure
        first_copy = batcher.get(handles[0])
        last_copy = batcher.get(handles[-1])
        self.assertIsInstance(first_copy, list)
        self.assertIsInstance(last_copy, list)


if __name__ == '__main__':
    unittest.main()