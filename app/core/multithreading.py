import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable, Iterable, List, Any
from app.core.logger import Logger


class MultiThreading:
    def __init__(self, logger: Logger, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.logger = logger

    def get_all(self, tasks: Iterable[Callable[[], Any]]) -> List[Any]:
        futures: List[Future[Any]] = [self.executor.submit(task) for task in tasks]
        results: List[Any] = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                self.logger.error(f"Task failed with error: {e}")
        return results
    
    def get_first(self, tasks: Iterable[Callable[[], Any]]) -> Any:
        futures: List[Future[Any]] = [self.executor.submit(task) for task in tasks]
        completed_count = 0
        for completed in as_completed(futures):
            completed_count += 1
            try:
                result = completed.result()
                # Ignore unsuccessful results and keep waiting for other tasks
                if result is not None:
                    for pending in futures:
                        if pending is not completed and not pending.done():
                            pending.cancel()
                    return result
            except Exception as e:
                self.logger.error(f"Task failed with error: {e}")

        # No task returned a valid value
        self.logger.warning("get_first: no task returned a valid result")
        return None
    

if __name__ == "__main__":
    logger = Logger("multithreading_test")
    mt = MultiThreading(logger, max_workers=2)
    import time

    start_time = time.time()

    # Example tasks
    def task1():
        while time.time() - start_time < 5:
            pass
        return "Result from task 1"

    def task2():
        while time.time() - start_time < 3:
            pass
        return "Result from task 2"

    results = mt.get_first([task1, task2])
    print(results)
    print(f"Total time taken: {time.time() - start_time:.2f} seconds")