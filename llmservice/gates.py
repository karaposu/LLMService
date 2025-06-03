# llmservice/gates.py  (Python 3.9+)
import asyncio, logging, time
from typing import Tuple
from collections import deque

class RpmGate:
    """
    One shared instance handles:
      • counting how many coroutines are currently sleeping on the RPM gate
      • logging only once per sleep-round
      • returning (waited?, loops, waited_ms) to the caller
    """
    def __init__(self, window_seconds: float, logger: logging.Logger | None = None):
        self._window = window_seconds
        self._lock   = asyncio.Lock()          # protects _waiters_count
        self._waiters_count     = 0
        self._last_logged_round = 0
        self._logger = logger or logging.getLogger(__name__)


    @staticmethod
    def _secs_until_refresh(
        dq: deque[float],
        window: int,            # <-- add this
    ) -> float:
        """Seconds until the eldest timestamp falls out of the window."""
        if not dq:
            return 0.0
        oldest = dq[0]
        return max(0.0, window - (time.time() - oldest))

    # # -------- internal helper -------- #
    # def _secs_until_refresh(self, sent_ts: deque) -> float:
    #     """Seconds until the oldest timestamp rolls out of the window."""
    #     if not sent_ts:
    #         return 0.0
    #     oldest = sent_ts[0]
    #     elapsed = time.time() - oldest
    #     return max(0.0, self._window - elapsed)
    
    async def wait_if_rate_limited(
        self,
        metrics,
    ) -> tuple[bool, int, int]:
        """Block until metrics.rpm() < max_rpm.

        Returns
        -------
        waited          : bool  – True if we actually slept
        loop_count      : int   – how many sleep iterations
        total_waited_ms : int
        """
        waited = False
        loop_count = 0
        total_waited_ms = 0

        while metrics.is_rpm_limited():
            waited = True
            loop_count += 1

            wait_for_s = max(
                0.0,
                self._secs_until_refresh(metrics.sent_ts, metrics.window)
            )
            wait_ms = int(wait_for_s * 1000)
            total_waited_ms += wait_ms

            # --- register as a waiter ---
            async with self._lock:
                self._waiters_count += 1
                waiters = self._waiters_count

            # --- log only if the delay is meaningful (>5 ms) and once per round
            if wait_ms > 5 and loop_count > self._last_logged_round:
                self._last_logged_round = loop_count
                logging.warning(
                    "RPM ⏳  %d waiting | next window in %.2fs | round #%d",
                    waiters, wait_for_s, loop_count,
                )

            # --- sleep (0 s means just yield to the event-loop) ---
            await asyncio.sleep(wait_for_s)

            # --- done waiting ---
            async with self._lock:
                self._waiters_count -= 1

        return waited, loop_count, total_waited_ms

    # # -------- async path -------- #
    # async def wait_if_rate_limited(
    #     self,
    #     metrics     # MetricsRecorder
    # ) -> Tuple[bool, int, int]:
    #     waited = False
    #     loop_count = 0
    #     total_waited_ms = 0

    #     while metrics.is_rpm_limited():
    #         waited = True
    #         loop_count += 1

    #         sleep_s  = self._secs_until_refresh(metrics.sent_ts)
    #         sleep_ms = int(sleep_s * 1000)
    #         total_waited_ms += sleep_ms

    #         # -- register as a waiter --
    #         async with self._lock:
    #             self._waiters_count += 1
    #             current_waiters = self._waiters_count

    #         # -- log once per loop round --
    #         if loop_count > self._last_logged_round:
    #             self._last_logged_round = loop_count
    #             self._logger.warning(
    #                 "RPM cap reached. %d tasks are sleeping %.2fs (%d ms), loop #%d.",
    #                 current_waiters, sleep_s, sleep_ms, loop_count
    #             )

    #         try:
    #             await asyncio.sleep(sleep_s)
    #         finally:
    #             # always decrement, even on cancellation
    #             async with self._lock:
    #                 self._waiters_count -= 1

    #     return waited, loop_count, total_waited_ms

    # -------- sync path (optional) -------- #
    def wait_if_rate_limited_sync(
        self,
        metrics
    ) -> Tuple[bool, int, int]:
        waited = False
        loop_count = 0
        total_waited_ms = 0

        while metrics.is_rpm_limited():
            waited = True
            loop_count += 1

            sleep_s  = self._secs_until_refresh(metrics.sent_ts)
            sleep_ms = int(sleep_s * 1000)
            total_waited_ms += sleep_ms

            # no per-task counting needed in sync mode (one thread) but keep symmetry
            if loop_count == 1:
                self._logger.warning(
                    "RPM cap reached. Sleeping %.2fs (%d ms), loop #%d.",
                    sleep_s, sleep_ms, loop_count
                )
            time.sleep(sleep_s)

        return waited, loop_count, total_waited_ms




class TpmGate:
    """
    Sleeps when tokens-per-minute exceeds max_tpm.

    The MetricsRecorder keeps `tok_ts` as a deque[(timestamp, tokens_used)].
    We only need the timestamp of the *oldest* entry to know when the
    window will roll forward.
    """
    def __init__(self, window_seconds: float, logger: logging.Logger | None = None):
        self._window = window_seconds
        self._lock   = asyncio.Lock()
        self._waiters_count     = 0
        self._last_logged_round = 0
        self._logger = logger or logging.getLogger(__name__)

    # ---------- helper ---------- #
    def _secs_until_refresh(self, tok_ts: deque) -> float:
        if not tok_ts:
            return 0.0
        oldest_ts, _oldest_tokens = tok_ts[0]        # deque keeps (ts, tokens)
        elapsed = time.time() - oldest_ts
        return max(0.0, self._window - elapsed)

    # ---------- async ---------- #
    async def wait_if_token_limited(
        self,
        metrics                      # MetricsRecorder
    ) -> Tuple[bool, int, int]:
        waited = False
        loop_count = 0
        total_waited_ms = 0

        while metrics.is_tpm_limited():
            waited = True
            loop_count += 1

            sleep_s  = self._secs_until_refresh(metrics.tok_ts)
            sleep_ms = int(sleep_s * 1000)
            total_waited_ms += sleep_ms

            # register this coroutine as a waiter
            async with self._lock:
                self._waiters_count += 1
                current_waiters = self._waiters_count

            if loop_count > self._last_logged_round:
                self._last_logged_round = loop_count
                self._logger.warning(
                    "TPM cap reached. %d tasks are sleeping %.2fs (%d ms), loop #%d.",
                    current_waiters, sleep_s, sleep_ms, loop_count
                )

            try:
                await asyncio.sleep(sleep_s)
            finally:
                async with self._lock:
                    self._waiters_count -= 1

        return waited, loop_count, total_waited_ms

    # ---------- sync (optional) ---------- #
    def wait_if_token_limited_sync(
        self,
        metrics
    ) -> Tuple[bool, int, int]:
        waited = False
        loop_count = 0
        total_waited_ms = 0

        while metrics.is_tpm_limited():
            waited = True
            loop_count += 1

            sleep_s  = self._secs_until_refresh(metrics.tok_ts)
            sleep_ms = int(sleep_s * 1000)
            total_waited_ms += sleep_ms

            if loop_count == 1:
                self._logger.warning(
                    "TPM cap reached. Sleeping %.2fs (%d ms), loop #%d.",
                    sleep_s, sleep_ms, loop_count
                )
            time.sleep(sleep_s)

        return waited, loop_count, total_waited_ms
