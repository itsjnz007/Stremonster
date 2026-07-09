import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, Iterable, List, Any, Dict
from app.core.logger import Logger
from typing import Optional, Tuple

logger = Logger("multithreading")

class MultiThreading:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logger
        self.stop_event: threading.Event = threading.Event()


    # Added: This helper wraps any function to inject a delay
    def _delayed_task(self, task: Callable[[threading.Event], Any], delay: float) -> Callable[[], Any]:
        def wrapper() -> Any:
            start_time = time.time()
            while time.time() - start_time < delay:
                if self.stop_event.is_set():
                    return None
                time.sleep(0.1)  # Check every 100ms
            if self.stop_event.is_set(): return None
            return task(self.stop_event)
        return wrapper

    def run_in_background(self, task: Callable[[Any], Any], delay: float = 0.0) -> Future[Any]:
        """Run a single task in the background and return its Future immediately."""
        self.stop_event.clear()
        delayed_task = self._delayed_task(task, delay)
        return self.executor.submit(delayed_task)

    def get_all(self, tasks: Iterable[Callable[[Any], Any]], delay_between: float = 2.0):
        self.stop_event.clear()
        delayed_tasks = [
            self._delayed_task(task, i * delay_between)
            for i, task in enumerate(tasks)
        ]

        futures: List[Future[Any]] = [self.executor.submit(task) for task in delayed_tasks]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    yield result
            except Exception as e:
                self.logger.error(f"Task failed: {e}")

    def get_first(
        self, 
        tasks: Iterable[Tuple[Callable[[threading.Event], Any], str]], 
        delay_between: float = 2.0
    ) -> Optional[Tuple[Any, str]]: # Returns (result, task_name)
        
        self.stop_event.clear()
        
        # Map the Future to the task name string directly
        future_to_name: Dict[Future[Any], str] = {}
        futures: List[Future[Any]] = []
        
        for i, (task, task_name) in enumerate(tasks):
            delayed_task = self._delayed_task(task, i * delay_between)
            future = self.executor.submit(delayed_task)
            futures.append(future)
            future_to_name[future] = task_name
        
        for completed in as_completed(futures):
            try:
                result = completed.result()
                if result is not None:
                    # Retrieve the name associated with this future
                    task_name = future_to_name[completed]
                    
                    self.stop_event.set()
                    # Cancel remaining tasks
                    for pending in futures:
                        if not pending.done():
                            pending.cancel()
                            
                    # Return result and the name
                    return (result, task_name)
            except Exception as e:
                self.logger.error(f"Task failed: {e}")
                
        return None
    

if __name__ == "__main__":
    # Test conditions
    pool: MultiThreading = MultiThreading(max_workers=3)
    
    def dummy_task(event: threading.Event, name: str, delay: float) -> Optional[str]:
        time.sleep(delay)
        return f"Result from {name}"

    print("--- Testing get_first ---")
    # Define tasks with explicit typing
    test_tasks: Iterable[Tuple[Callable[[threading.Event], Any], str]] = [
        (lambda e: dummy_task(e, "Task A", 1.0), 'task1'),
        (lambda e: dummy_task(e, "Task B", 0.2), 'task2'), # This should win
        (lambda e: dummy_task(e, "Task C", 2.0), 'task3'),
    ]
    
    start_time: float = time.time()
    response: Optional[Tuple[Any, str]] = pool.get_first(test_tasks, delay_between=0.1)
    
    if response:
        val: Any
        idx: str
        val, idx = response
        print(f"Winner: Taskname {idx} ({val}) in {time.time() - start_time:.2f}s")
    
    print("\n--- Testing get_all ---")
    tasks_all: List[Callable[[threading.Event], Optional[str]]] = [
        lambda e: dummy_task(e, "Fast", 0.1),
        lambda e: dummy_task(e, "Slow", 0.5),
    ]
    print("Streaming results as they arrive:")
    for result in pool.get_all(tasks_all, delay_between=0.1):
        print(result)

    print("\n--- Testing run_in_background ---")
    future = pool.run_in_background(lambda e: dummy_task(e, "Background", 0.2), delay=0.1)
    print("Returned immediately. Waiting for result...")
    print(future.result())

    pool.executor.shutdown(wait=True)