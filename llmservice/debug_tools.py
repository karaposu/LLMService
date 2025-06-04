# debug_tools.py  ────────────────────────────────────────────────────────────
import time, functools, logging, threading, asyncio, inspect

def timed(name: str):
    """
    Decorator that logs wall-clock runtime and which thread / task executed it.
    Usage:
        @timed("execute_generation_async")
        async def execute_generation_async(...):
            ...
    """
    log = logging.getLogger("llmservice.timer")

    def decorator(fn):
        is_coroutine = inspect.iscoroutinefunction(fn)

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):          # async path
            t0 = time.perf_counter()
            task = asyncio.current_task()
            task_name = task.get_name() if task else "n/a"
            log.debug(f"[{name}] START  task={task_name}")
            try:
                return await fn(*args, **kwargs)
            finally:
                dt = (time.perf_counter() - t0) * 1000
                log.debug(f"[{name}] END    task={task_name}  Δ={dt:.1f} ms")

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):                 # sync path
            t0 = time.perf_counter()
            tid = threading.get_ident()
            log.debug(f"[{name}] START  thread={tid}")
            try:
                return fn(*args, **kwargs)
            finally:
                dt = (time.perf_counter() - t0) * 1000
                log.debug(f"[{name}] END    thread={tid}  Δ={dt:.1f} ms")

        return async_wrapper if is_coroutine else sync_wrapper
    return decorator
