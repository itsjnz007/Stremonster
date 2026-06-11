import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, Iterable, List, Any

class MultiThreading:
    def __init__(self, logger: Any, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logger

    # Added: This helper wraps any function to inject a delay
    def _delayed_task(self, task: Callable[[], Any], delay: float) -> Callable[[], Any]:
        def wrapper():
            time.sleep(delay)
            return task()
        return wrapper

    def get_all(self, tasks: Iterable[Callable[[], Any]], delay_between: float = 2.0) -> List[Any]:
        # Wrap each task with a cumulative delay
        delayed_tasks = [
            self._delayed_task(task, i * delay_between) 
            for i, task in enumerate(tasks)
        ]
        
        futures: List[Future[Any]] = [self.executor.submit(task) for task in delayed_tasks]
        results: List[Any] = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                self.logger.error(f"Task failed: {e}")
        return results

    def get_first(self, tasks: Iterable[Callable[[], Any]], delay_between: float = 2.0) -> Any:
        # Wrap each task with a cumulative delay
        delayed_tasks = [
            self._delayed_task(task, i * delay_between) 
            for i, task in enumerate(tasks)
        ]
        
        futures: List[Future[Any]] = [self.executor.submit(task) for task in delayed_tasks]
        
        for completed in as_completed(futures):
            try:
                result = completed.result()
                if result is not None:
                    # Cancel pending tasks
                    for pending in futures:
                        if pending is not completed and not pending.done():
                            pending.cancel()
                    return result
            except Exception as e:
                self.logger.error(f"Task failed: {e}")
        return None