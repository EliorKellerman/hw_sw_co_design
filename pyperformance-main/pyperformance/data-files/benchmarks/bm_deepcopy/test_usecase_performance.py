# test_usecase_performance.py (Upgraded)

import unittest
import copy
import timeit
from lazydeepcopy import DeepcopyBatcher

class TestUsecasePerformance(unittest.TestCase):
    """
    Benchmarks that model more specific, realistic use cases and stress tests.
    """

    def test_ab_variant_generation_performance(self):
        """
        Benchmark 4 (Upgraded): A/B Test Variant Generation.

        This models a realistic web development scenario where multiple test
        variants are created from a single base page layout. The initial creation
        of all variants is independent and can be batched, followed by a phase
        of applying specific modifications to each copy.
        """
        base_page_layout = {
            'header': {
                'title': 'Generic Welcome!',
                'cta_button': {'text': 'Sign Up', 'color': 'blue'}
            },
            'body': {
                'headline': 'Discover Our Amazing Product',
                'image': 'default.jpg',
                'paragraphs': [
                    'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
                    'Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
                ]
            },
            'footer': {'links': ['About', 'Contact', 'Privacy Policy']}
        }
        
        # Define the unique modifications for each A/B test variant
        variants_to_create = {
            'variant_red_button': lambda p: p['header']['cta_button'].__setitem__('color', 'red'),
            'variant_new_headline': lambda p: p['body'].__setitem__('headline', 'Your New Favorite Tool is Here'),
            'variant_alt_image': lambda p: p['body'].__setitem__('image', 'alt_image.jpg'),
            'variant_short_footer': lambda p: p.__setitem__('footer', {'links': ['Help']}),
            'variant_green_button': lambda p: p['header']['cta_button'].__setitem__('color', 'green'),
        }
        num_runs = 100

        # --- Traditional Method ---
        def run_traditional_ab_test():
            final_variants = {}
            for name, modification_func in variants_to_create.items():
                # The copy and modification happen together for each variant
                variant_copy = copy.deepcopy(base_page_layout)
                modification_func(variant_copy)
                final_variants[name] = variant_copy
            return final_variants

        # --- Lazy/Proxy Method ---
        def run_lazy_ab_test():
            batcher = DeepcopyBatcher()
            proxies = {}
            
            # Phase 1: Defer all copy requests. This is extremely fast and fully batchable.
            for name in variants_to_create:
                proxies[name] = batcher.defer_proxy(base_page_layout)

            # Phase 2: Apply modifications. The first access to any proxy
            # triggers a single deepcopy for the entire batch.
            final_variants = {}
            for name, modification_func in variants_to_create.items():
                proxy = proxies[name]
                modification_func(proxy) # This resolves the proxy if not already resolved
                final_variants[name] = proxy._resolve() # Store the final object
            return final_variants

        # --- Timing ---
        traditional_time = timeit.timeit(run_traditional_ab_test, number=num_runs)
        lazy_time = timeit.timeit(run_lazy_ab_test, number=num_runs)

        print("\n\n--- Benchmark 4 (Upgraded): A/B Variant Generation Performance ---")
        print("Scenario: Creates multiple independent A/B test variants from a base template.")
        print("This workflow has a distinct phase for batchable copy creation.")
        print(f"Number of variants created per run: {len(variants_to_create)}")
        print(f"Number of full runs: {num_runs}")
        print(f"Traditional `copy.deepcopy` time: {traditional_time:.6f} seconds")
        print(f"Lazy `defer_proxy` time:          {lazy_time:.6f} seconds")

        if lazy_time < traditional_time:
            percentage_gain = ((traditional_time - lazy_time) / traditional_time) * 100
            speedup = traditional_time / lazy_time
            print(f"Result: Batched version was {speedup:.2f}x faster (~{percentage_gain:.1f}% gain).")
        else:
            percentage_loss = ((lazy_time - traditional_time) / lazy_time) * 100
            print(f"Result: Batched version was ~{percentage_loss:.1f}% slower.")

    def test_large_data_batch_performance(self):
        """
        Benchmark 5: Synthetic Large Data Batch.

        This stress test creates a very large object and copies it multiple
        times. The goal is to see how the library performs when the raw time
        spent copying memory is very high, potentially dwarfing the savings
        from reducing Python function call overhead.
        """
        
        def _create_large_object(num_records=1000, sublist_size=100):
            """Creates a large, memory-intensive object."""
            return [{
                'id': i,
                'name': f'record_{i}',
                'payload': list(range(sublist_size)),
                'metadata': { 'active': i % 2 == 0, 'tags': ('tagA', 'tagB', 'tagC')}
            } for i in range(num_records)]

        large_object = _create_large_object()
        num_copies = 20
        num_runs = 3

        # --- Traditional Method ---
        def run_traditional_large_batch():
            copies = [copy.deepcopy(large_object) for _ in range(num_copies)]
            return copies

        # --- Lazy/Batched Method ---
        def run_lazy_large_batch():
            batcher = DeepcopyBatcher(max_items=num_copies + 1)
            handles = [batcher.defer(large_object) for _ in range(num_copies)]
            batcher.flush()
            copies = [batcher.get(h) for h in handles]
            return copies
        
        # --- Timing ---
        traditional_time = timeit.timeit(run_traditional_large_batch, number=num_runs)
        lazy_time = timeit.timeit(run_lazy_large_batch, number=num_runs)

        print("\n\n--- Benchmark 5: Large Data Batch Performance ---")
        print("Scenario: Stress test with batch copies of a single, very large object.")
        print(f"Object size: 1000 records, each with a 100-element list.")
        print(f"Copies per run: {num_copies}")
        print(f"Number of test runs: {num_runs}")
        print(f"Traditional `copy.deepcopy` time: {traditional_time:.6f} seconds")
        print(f"Lazy `lazydeepcopy` time:       {lazy_time:.6f} seconds")

        if lazy_time < traditional_time:
            percentage_gain = ((traditional_time - lazy_time) / traditional_time) * 100
            speedup = traditional_time / lazy_time
            print(f"Result: Batched version was {speedup:.2f}x faster (~{percentage_gain:.1f}% gain).")
        else:
            percentage_loss = ((lazy_time - traditional_time) / lazy_time) * 100
            print(f"Result: Batched version was ~{percentage_loss:.1f}% slower.")


if __name__ == '__main__':
    unittest.main()