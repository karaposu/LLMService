# telemetry.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json, logging

class TelemetryClient(ABC):
    """
    Backends implement **synchronous** record/flush.
    The async helpers delegate to the same sync methods
    so you write the logic once and call it from either context.
    """

    # --------  core sync interface  --------
    @abstractmethod
    def record(self, payload: Dict[str, Any]) -> None: ...
    @abstractmethod
    def flush(self) -> None: ...

    # --------  helpers for async callers  --------
    async def arecord(self, payload: Dict[str, Any]) -> None:
        self.record(payload)

    async def aflush(self) -> None:
        self.flush()


# ------------------------------------------------------------------
# Default backend: one JSON line per log entry
# ------------------------------------------------------------------
class JSONLoggerTelemetry(TelemetryClient):
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.log = logger or logging.getLogger("llmservice.telemetry")

    # sync versions
    def record(self, payload: Dict[str, Any]) -> None:
        self.log.info(json.dumps(payload, separators=(",", ":")))

    def flush(self) -> None:
        pass  # nothing buffered
