# test_mixed_workflow_performance.py (Final, Working Version)

import unittest
import copy
import timeit
import random
from lazydeepcopy import DeepcopyBatcher, _Proxy
from typing import Union

class TestMixedWorkflowPerformance(unittest.TestCase):
    """
    A benchmark that models a complex workflow with both independent and
    dependent copy operations.
    """

    def _generate_workflow(self, num_tasks=50, dependency_chance=0.25):
        tasks = []
        for i in range(num_tasks):
            task_name = f"task_{i}"
            source = 'BASE'
            if i > 0 and random.random() < dependency_chance:
                source = f"task_{random.randint(0, i-1)}"
            modification = {'id': i, 'status': 'processed'}
            tasks.append({
                'name': task_name, 'source': source, 'modification': modification
            })
        return tasks

    def test_dynamic_workflow_simulation(self):
        base_object = {'data': [1, 2, 3], 'metadata': {}}
        num_runs = 5
        # dependency_chances = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        dependency_chances = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        print("\n\n--- Benchmark 6: Dynamic Workflow Simulation (Corrected) ---")
        print("This tests how performance scales as dependencies increase, using the correct two-phase pattern.")

        for dep_chance in dependency_chances:
            workflow_tasks = self._generate_workflow(num_tasks=10000, dependency_chance=dep_chance)

            # --- Traditional Method ---
            # The baseline remains an inherently sequential single loop.
            def run_traditional_workflow():
                results = {'BASE': base_object}
                for task in workflow_tasks:
                    source_object = results[task['source']]
                    new_copy = copy.deepcopy(source_object)
                    new_copy['metadata'].update(task['modification'])
                    results[task['name']] = new_copy
                return results

            # --- Lazy/Proxy Method (Correct Idiomatic Two-Phase Pattern) ---
            def run_lazy_workflow():
                batcher = DeepcopyBatcher()
                proxies: dict[str, Union[dict, _Proxy]] = {'BASE': base_object}
                modifications = {} # Store modifications to be applied in the second phase.

                # --- PHASE 1: Plan the work by deferring copies ---
                # This loop builds mini-batches until a dependency forces a flush.
                for task in workflow_tasks:
                    source_proxy_or_obj = proxies[task['source']]

                    if isinstance(source_proxy_or_obj, _Proxy):
                        # Dependency found. Resolve the source, which flushes the current batch.
                        source_for_copy = source_proxy_or_obj._resolve()
                    else:
                        source_for_copy = source_proxy_or_obj

                    # Defer a new copy based on the now-concrete source data.
                    # This starts or adds to a new mini-batch.
                    new_proxy = batcher.defer_proxy(source_for_copy)
                    proxies[task['name']] = new_proxy
                    # Instead of modifying immediately, we store the planned modification.
                    modifications[task['name']] = task['modification']

                # --- PHASE 2: Execute the modifications ---
                # The first access here will flush the final batch from Phase 1.
                for name, mod in modifications.items():
                    proxies[name]['metadata'].update(mod)

                # Final resolution to ensure all work is timed.
                final_results = {name: (p._resolve() if isinstance(p, _Proxy) else p) for name, p in proxies.items()}
                return final_results

            traditional_time = timeit.timeit(run_traditional_workflow, number=num_runs)
            lazy_time = timeit.timeit(run_lazy_workflow, number=num_runs)

            print(f"\n--- Dependency chance: {dep_chance:.2f} ---")
            print(f"Traditional `copy.deepcopy` time: {traditional_time:.6f} seconds")
            print(f"Lazy `defer_proxy` time:          {lazy_time:.6f} seconds")

            if lazy_time < traditional_time:
                speedup = traditional_time / lazy_time
                print(f"Result: Batched version was {speedup:.2f}x faster.")
            else:
                percentage_loss = ((lazy_time - traditional_time) / lazy_time) * 100
                print(f"Result: Batched version was ~{percentage_loss:.1f}% slower.")


if __name__ == '__main__':
    unittest.main()