# rate_test.py

# python -m llmservice.rate_test

# to run pytest rate_test.py

import time
import pytest
from collections import deque

from llmservice.base_service import BaseLLMService

class DummyResult:
    def __init__(self, total_tokens):
        self.meta = {"total_tokens": total_tokens}

class DummyService(BaseLLMService):
    """Expose internals for testing."""
    def __init__(self, default_model_name="gpt-4o-mini", **kwargs):
        super().__init__(default_model_name=default_model_name, **kwargs)
        # override deques for isolation
        self.request_timestamps = deque()
        self.token_timestamps = deque()

    def simulate_usage(self, tokens, at_time):
        """Simulate a GenerationResult being stored."""
        # wrap tokens in dummy result
        dummy = DummyResult(tokens)
        # manually set current time
        self._store_usage(dummy)

        # but _store_usage uses time.time(); we override
        # so instead, directly append to deques:
        # (we assume _store_usage already appended at real now,
        # so clear and append our controlled timestamp)
        self.request_timestamps.clear()
        self.token_timestamps.clear()
        self.request_timestamps.append(at_time)
        self.token_timestamps.append((at_time, tokens))

@pytest.fixture(autouse=True)
def freeze_time(monkeypatch):
    """Freeze time at a known point."""
    now = 1_000_000.0
    monkeypatch.setattr(time, 'time', lambda: now)
    return now

def test_rpm_empty():
    svc = DummyService()
    assert svc.get_current_rpm() == 0

def test_tpm_empty():
    svc = DummyService()
    assert svc.get_current_tpm() == 0

def test_rpm_counts_only_within_window(freeze_time):
    svc = DummyService()
    now = freeze_time
    window = svc.rpm_window_seconds

    # one event just inside window, one just outside
    svc.request_timestamps.extend([now - window + 1, now - window - 1])
    assert svc.get_current_rpm() == 1  # only the one inside

def test_tpm_sum_only_within_window(freeze_time):
    svc = DummyService()
    now = freeze_time
    window = svc.rpm_window_seconds

    # tokens at two timestamps
    svc.token_timestamps.extend([
        (now - window + 1,  150),
        (now - window - 1,  200)
    ])
    # expect only 150 counted
    assert svc.get_current_tpm() == pytest.approx(150.0)

def test_tpm_scales_when_window_changed(monkeypatch, freeze_time):
    svc = DummyService(rpm_window_seconds=30)  # 30 s window
    now = freeze_time

    svc.token_timestamps.extend([
        (now - 10, 60),    # within
        (now - 40, 100)    # outside
    ])
    # sum=60, scaling factor=60/30=2 → TPM=120
    assert svc.get_current_tpm() == pytest.approx(120.0)
