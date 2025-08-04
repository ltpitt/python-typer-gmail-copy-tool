import time
import functools

def timing(func):
    """Decorator to measure and print the execution time of a function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        elapsed = end - start
        print(f"[Timing] {func.__name__} took {elapsed:.2f} seconds.")
        return result
    return wrapper
