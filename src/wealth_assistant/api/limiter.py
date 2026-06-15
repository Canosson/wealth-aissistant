"""Shared rate-limiter instance for decorator annotations.

The decorator (@limiter.limit) only attaches metadata to the route function.
Actual enforcement uses the limiter stored on app.state.limiter, which is
created fresh inside create_app() so each test's app has isolated storage.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
