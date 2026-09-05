"""Thread-safe runtime state, metrics, caching, and admission controls."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Hashable

MISSING = object()


class BoundedTTLCache:
    def __init__(self, max_entries: int = 128, ttl_seconds: float = 300):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._values: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any:
        now = time.monotonic()
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return MISSING
            expires_at, value = item
            if expires_at <= now:
                del self._values[key]
                return MISSING
            self._values.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> Any:
        with self._lock:
            self._values[key] = (time.monotonic() + self.ttl_seconds, value)
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)
        return value

    def get_or_set(self, key: Hashable, loader: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not MISSING:
            return cached
        return self.set(key, loader())

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, identity: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[identity]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


@dataclass
class RuntimeState:
    status: str = "starting"
    startup_error: str | None = None
    started_at: float = field(default_factory=time.time)
    ready_at: float | None = None
    request_count: int = 0
    rejected_count: int = 0
    error_count: int = 0
    total_request_seconds: float = 0.0
    routes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def mark_loading(self) -> None:
        with self._lock:
            self.status = "loading"
            self.startup_error = None

    def mark_ready(self) -> None:
        with self._lock:
            self.status = "ready"
            self.ready_at = time.time()

    def mark_failed(self, error: BaseException) -> None:
        with self._lock:
            self.status = "failed"
            self.startup_error = type(error).__name__

    def record_request(self, route: str, elapsed: float, status_code: int) -> None:
        with self._lock:
            self.request_count += 1
            self.routes[route] += 1
            self.total_request_seconds += elapsed
            if status_code >= 500:
                self.error_count += 1

    def record_rejection(self) -> None:
        with self._lock:
            self.rejected_count += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            average_ms = (
                self.total_request_seconds / self.request_count * 1000
                if self.request_count
                else 0.0
            )
            return {
                "status": self.status,
                "startupError": self.startup_error,
                "uptimeSeconds": round(time.time() - self.started_at, 3),
                "requestCount": self.request_count,
                "rejectedCount": self.rejected_count,
                "errorCount": self.error_count,
                "averageRequestMs": round(average_ms, 3),
                "routes": dict(self.routes),
            }
