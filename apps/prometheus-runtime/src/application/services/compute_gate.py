"""Serialize CPU-heavy work so chat answers run ahead of background indexing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

Workload = Literal["foreground", "background"]


class ComputeGate:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._foreground_active = 0
        self._waiters = asyncio.Condition()

    @asynccontextmanager
    async def exclusive(self, workload: Workload) -> AsyncIterator[None]:
        if workload == "background":
            async with self._waiters:
                while self._foreground_active > 0:
                    await self._waiters.wait()
        else:
            async with self._waiters:
                self._foreground_active += 1
        try:
            async with self._lock:
                yield
        finally:
            if workload == "foreground":
                async with self._waiters:
                    self._foreground_active = max(0, self._foreground_active - 1)
                    self._waiters.notify_all()
