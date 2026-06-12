import time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, Iterable, List, Any

class MultiThreading:
    def __init__(self, logger: Any, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logger
        self.stop_event: threading.Event = threading.Event()


    # Added: This helper wraps any function to inject a delay
    def _delayed_task(self, task: Callable[[threading.Event], Any], delay: float) -> Callable[[threading.Event], Any]:
        def wrapper() -> Any:
            start_time = time.time()
            while time.time() - start_time < delay:
                if self.stop_event.is_set():
                    return None
                time.sleep(0.1)  # Check every 100ms
            if self.stop_event.is_set(): return None
            return task(self.stop_event) # type: ignore
        return wrapper # type: ignore

    def get_all(self, tasks: Iterable[Callable[[threading.Event], Any]], delay_between: float = 2.0) -> List[Any]:
        # Wrap each task with a cumulative delay
        delayed_tasks = [
            self._delayed_task(task, i * delay_between) 
            for i, task in enumerate(tasks)
        ]
        
        futures: List[Future[Any]] = [self.executor.submit(task) for task in delayed_tasks] # type: ignore
        results: List[Any] = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                self.logger.error(f"Task failed: {e}")
        return results

    def get_first(self, tasks: Iterable[Callable[[threading.Event], Any]], delay_between: float = 2.0) -> Any:
        self.stop_event.clear()
        # Wrap each task with a cumulative delay
        delayed_tasks = [
            self._delayed_task(task, i * delay_between) 
            for i, task in enumerate(tasks)
        ]
        
        futures: List[Future[Any]] = [self.executor.submit(task) for task in delayed_tasks] # type: ignore
        
        for completed in as_completed(futures):
            try:
                result = completed.result()
                if result is not None:
                    self.stop_event.set()
                    # Cancel pending tasks
                    for pending in futures:
                        if pending is not completed and not pending.done():
                            pending.cancel()
                    return result
            except Exception as e:
                self.logger.error(f"Task failed: {e}")
        return None