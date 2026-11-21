import time
from typing import Callable, Optional

def wait_until(timeout: float, interval: float = 0.1, condition: Optional[Callable[[], bool]] = None) -> bool:
    """
    Wait until timeout or until condition becomes True.

    Args:
        timeout: max seconds to wait
        interval: sleep interval between checks
        condition: function returning True/False

    Returns:
        True if condition met, False if timeout
    """
    start = time.time()

    while time.time() - start < timeout:
        if condition and condition():
            return True
        time.sleep(interval)

    return False