# llmservice/live_metrics.py
"""
Light-weight, runtime-only metrics for BaseLLMService
====================================================

Tracks — without external deps — 

    • total requests *sent*  
    • total responses *received*  
    • requests-per-minute  (RPM)  
    • responses-per-minute (RePM)  
    • tokens-per-minute    (TPM)  
    • cumulative cost ($)

All counters use the same sliding time-window (default 60 s).  
The class is *pure Python / no I/O* so it can be unit-tested or
swapped out later for Prometheus / OTEL without touching core logic.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass




import logging

def attach_file_handler(recorder: MetricsRecorder, path: str,
                        fmt="%(asctime)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=logging.INFO) -> logging.Logger:
    """
    Convenience: create a logger named 'llmservice.metrics', attach a
    FileHandler, and return it.  Recorder itself remains I/O-free.
    """
    log = logging.getLogger("llmservice.metrics")
    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter(fmt, datefmt))
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False
    return log

# --------------------------------------------------------------------------- #
#  Public snapshot returned by .snapshot()
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class StatsSnapshot:
    total_sent:     int
    total_rcv:      int
    rpm:            float
    repm:           float
    tpm:            float
    cost:           float            # cumulative USD


# --------------------------------------------------------------------------- #
#  MetricsRecorder
# --------------------------------------------------------------------------- #

class MetricsRecorder:
    """
    Sliding-window counters used by BaseLLMService.

    Parameters
    ----------
    window : int
        Window length in seconds (default 60).  
        RPM/RePM/TPM are scaled to *per minute* regardless of window size.
    max_rpm : int | None
        Optional hard cap; helper `.is_rpm_limited()` returns True when
        current RPM >= max_rpm.
    max_tpm : int | None
        Optional hard cap on tokens-per-minute.

    All methods are **thread-safe in CPython** because they mutate `deque`
    atomically while the GIL is held.
    """

    # --------------- construction ---------------- #

    def __init__(
        self,
        *,
        window:   int,
        max_rpm:  int | None = None,
        max_tpm:  int | None = None
    ) -> None:
        self.window    = window
        self.max_rpm   = max_rpm
        self.max_tpm   = max_tpm

        self.sent_ts:  deque[float]            = deque()        # time of every req sent
        self.rcv_ts:   deque[float]            = deque()        # time of every resp rcv
        self.tok_ts:   deque[tuple[float,int]] = deque()        # (time, tokens) per resp

        self.total_sent = 0
        self.total_rcv  = 0
        self.total_cost = 0.0

    # --------------- hooks called by service ---------------- #

    def mark_sent(self) -> None:
        """Call *immediately* before you dispatch the LLM request."""
        now = time.time()
        self.total_sent += 1
        self.sent_ts.append(now)
        self._trim(self.sent_ts)

    def mark_rcv(self, *, tokens: int, cost: float) -> None:
        """Call once when the response has been parsed."""
        now = time.time()
        self.total_rcv  += 1
        self.total_cost += cost

        self.rcv_ts.append(now)
        self.tok_ts.append((now, tokens))

        self._trim(self.rcv_ts)
        self._trim_tok()

    # --------------- computed properties ---------------- #

    def rpm(self)  -> float:      # requests sent per minute
        return len(self.sent_ts) * 60 / self.window

    def repm(self) -> float:      # responses received per minute
        self._trim(self.rcv_ts)
        return len(self.rcv_ts) * 60 / self.window

    def tpm(self)  -> float:      # tokens processed per minute
        self._trim_tok()
        total = sum(tok for _, tok in self.tok_ts)
        return total * 60 / self.window

    # --------------- convenience helpers ---------------- #

    def snapshot(self) -> StatsSnapshot:
        """Return an immutable view of current counters."""
        return StatsSnapshot(
            total_sent = self.total_sent,
            total_rcv  = self.total_rcv,
            rpm        = self.rpm(),
            repm       = self.repm(),
            tpm        = self.tpm(),
            cost       = self.total_cost
        )

    def is_rpm_limited(self) -> bool:
        return self.max_rpm is not None and self.rpm() >= self.max_rpm

    def is_tpm_limited(self) -> bool:
        return self.max_tpm is not None and self.tpm() >= self.max_tpm

    # --------------- internal trimming ---------------- #

    def _cutoff(self) -> float:
        return time.time() - self.window

    def _trim(self, dq: deque[float]) -> None:
        cut = self._cutoff()
        while dq and dq[0] < cut:
            dq.popleft()

    def _trim_tok(self) -> None:
        cut = self._cutoff()
        while self.tok_ts and self.tok_ts[0][0] < cut:
            self.tok_ts.popleft()
