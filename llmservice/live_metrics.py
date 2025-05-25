# llmservice/live_metrics.py
"""
Light-weight, runtime-only metrics for BaseLLMService
====================================================

Tracks — without any external dependency —  

    • total requests *sent*  
    • total responses *received*  
    • requests-per-minute   (RPM)  
    • responses-per-minute  (RePM)  
    • tokens-per-minute     (TPM)  
    • cumulative cost (USD)

All counters share the same sliding time-window (default 60 s).  
The class is pure-Python and **self-synchronised**: a single internal
`threading.Lock` protects every mutation *and* every read, so callers
don’t need to worry about atomicity.
"""

from __future__ import annotations

import logging
import time
import threading
from collections import deque
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
#  Helper: optional file logger                                               #
# --------------------------------------------------------------------------- #
def attach_file_handler(
    recorder: "MetricsRecorder",
    path: str,
    *,
    fmt: str      = "%(asctime)s %(message)s",
    datefmt: str  = "%Y-%m-%d %H:%M:%S",
    level: int    = logging.INFO,
) -> logging.Logger:
    """
    Convenience helper that returns a **dedicated** logger named
    ``llmservice.metrics`` with a `FileHandler` attached.
    Useful for ``tail -f``-style monitoring.

    Notes
    -----
    • This function is completely optional; `MetricsRecorder`
      itself contains **no I/O**.  
    • Caller may add extra handlers (e.g. `StreamHandler`) later.
    """
    log = logging.getLogger("llmservice.metrics")
    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter(fmt, datefmt))
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False
    return log

# --------------------------------------------------------------------------- #
#  Public immutable snapshot                                                  #
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class StatsSnapshot:
    total_sent: int
    total_rcv:  int
    rpm:        float
    repm:       float
    tpm:        float
    cost:       float  # cumulative USD

# --------------------------------------------------------------------------- #
#  MetricsRecorder                                                            #
# --------------------------------------------------------------------------- #
class MetricsRecorder:
    """
    Sliding-window counters used by `BaseLLMService`.

    Parameters
    ----------
    window : int
        Window length in *seconds* (default 60).  
        RPM/RePM/TPM are scaled to **per-minute** regardless of window size.
    max_rpm : int | None
        Optional hard cap. `is_rpm_limited()` returns *True* when
        current RPM ≥ max_rpm.
    max_tpm : int | None
        Optional hard cap on tokens-per-minute.

    Thread-safety
    -------------
    A single internal `threading.Lock` (`self._lock`) guards:

        • totals (`total_sent`, `total_rcv`, `total_cost`)  
        • deques (`sent_ts`, `rcv_ts`, `tok_ts`)  
        • every computed read (`snapshot`, `rpm`, `repm`, `tpm`)

    Therefore **all public methods are atomic** even when called from
    multiple asyncio tasks or threads.
    """

    # ---------------- construction ---------------- #
    def __init__(
        self,
        *,
        window:  int,
        max_rpm: int | None = None,
        max_tpm: int | None = None,
    ) -> None:
        self.window    = window
        self.max_rpm   = max_rpm
        self.max_tpm   = max_tpm

        self.sent_ids = deque()   # NEW
        self.rcv_ids  = deque()   # NEW

        self.sent_ts: deque[float]            = deque()        # request send times
        self.rcv_ts:  deque[float]            = deque()        # response recv times
        self.tok_ts:  deque[tuple[float,int]] = deque()        # (time, tokens) pairs

        self.total_sent = 0
        self.total_rcv  = 0
        self.total_cost = 0.0

        self._lock = threading.Lock()

    # ---------------- mutation hooks ---------------- #
    def mark_sent(self, req_id: int) -> None:
        """Call **immediately before** dispatching the LLM request."""
        now = time.time()
       
        with self._lock:
            self.total_sent += 1
            self.sent_ts.append(now)
            self.sent_ids.append(req_id)
            # self._trim_times(self.sent_ts, now)
            self._trim_times(self.sent_ts, now, self.window)

    def mark_rcv(self, req_id: int, *, tokens: int, cost: float) -> None:
        """Call **once** after the response is parsed."""
        now = time.time()
        
        with self._lock:
            self.total_rcv  += 1
            self.total_cost += cost
            self.rcv_ts.append(now)
            self.rcv_ids.append(req_id)
            self.tok_ts.append((now, tokens))
            # self._trim_times(self.rcv_ts,  now)
            self._trim_times(self.rcv_ts,  now, self.window)
            self._trim_tokens(now)
     
    # ---------------- computed properties ---------------- #
    def rpm(self) -> float:
        with self._lock:
            return self._rpm_unlocked(time.time())

    def repm(self) -> float:
        with self._lock:
            return self._repm_unlocked(time.time())

    def tpm(self) -> float:
        with self._lock:
            return self._tpm_unlocked(time.time())

    # ---------------- snapshot (atomic read) ---------------- #
    def snapshot(self) -> StatsSnapshot:
        now = time.time()
        with self._lock:
            return StatsSnapshot(
                total_sent = self.total_sent,
                total_rcv  = self.total_rcv,
                rpm        = self._rpm_unlocked(now),
                repm       = self._repm_unlocked(now),
                tpm        = self._tpm_unlocked(now),
                cost       = self.total_cost,
            )

    # ---------------- limit helpers ---------------- #
    def is_rpm_limited(self) -> bool:
        return self.max_rpm is not None and self.rpm() >= self.max_rpm

    def is_tpm_limited(self) -> bool:
        return self.max_tpm is not None and self.tpm() >= self.max_tpm

    # ------------------------------------------------------------------ #
    #  Internal helpers  (lock *must* be held)                           #
    # ------------------------------------------------------------------ #
    def _cutoff(self, now: float) -> float:
        return now - self.window

    @staticmethod
    def _trim_times(dq: deque[float], now: float, window: int | None = None) -> None:
        """Pop old timestamps from a *timestamps* deque."""
        if window is None:                         # caller passes correct window
            return
        cutoff = now - window
        while dq and dq[0] < cutoff:
            dq.popleft()

    def _trim_tokens(self, now: float) -> None:
        cutoff = now - self.window
        while self.tok_ts and self.tok_ts[0][0] < cutoff:
            self.tok_ts.popleft()

    # ---- unlocked calculations (lock already held) ---- #
    def _rpm_unlocked(self, now: float) -> float:
        self._trim_times(self.sent_ts, now, self.window)
        return len(self.sent_ts) * 60 / self.window

    def _repm_unlocked(self, now: float) -> float:
        self._trim_times(self.rcv_ts,  now, self.window)
        return len(self.rcv_ts) * 60 / self.window

    def _tpm_unlocked(self, now: float) -> float:
        self._trim_tokens(now)
        total = sum(tok for _, tok in self.tok_ts)
        return total * 60 / self.window
