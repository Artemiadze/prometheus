"""Tests for CPU work serialization."""

from __future__ import annotations

import asyncio

from application.services.compute_gate import ComputeGate


def test_background_waits_for_foreground() -> None:
    gate = ComputeGate()
    order: list[str] = []

    async def foreground() -> None:
        async with gate.exclusive("foreground"):
            order.append("fg-start")
            await asyncio.sleep(0.05)
            order.append("fg-end")

    async def background() -> None:
        await asyncio.sleep(0.01)
        async with gate.exclusive("background"):
            order.append("bg")

    async def run() -> None:
        await asyncio.gather(foreground(), background())

    asyncio.run(run())
    assert order.index("fg-end") < order.index("bg")
