"""Simple in-memory sliding-window rate limiter, keyed by client IP.

Good for a single-process app and for learning. With several workers/servers
you'd move the counters to Redis (or use a gateway), because each process
keeps its own counts here.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.database import get_db


class RateLimiter:
    def __init__(self, name: str, limit: int, window_seconds: int):
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request, db: Session = Depends(get_db)) -> None:
        ip = client_ip(request) or "unknown"
        now = time.monotonic()
        with self._lock:
            q = self._hits[ip]
            while q and now - q[0] > self.window:
                q.popleft()
            exceeded = len(q) >= self.limit
            if not exceeded:
                q.append(now)
        if exceeded:
            security_event(db, "RATE_LIMIT_EXCEEDED", "Medium",
                           f"Rate limit '{self.name}' exceeded ({self.limit}/{self.window}s)", ip=ip)
            audit(db, "RATE_LIMIT_EXCEEDED", ip=ip, details=self.name)
            db.commit()
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.",
                                headers={"Retry-After": str(self.window)})
