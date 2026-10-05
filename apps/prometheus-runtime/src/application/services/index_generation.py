"""Monotonic counter bumped when vault index content changes (invalidates answer cache)."""


class IndexGeneration:
    def __init__(self) -> None:
        self._value = 0

    @property
    def value(self) -> int:
        return self._value

    def bump(self) -> None:
        self._value += 1
