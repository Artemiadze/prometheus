"""Remove ``<think>…</think>`` reasoning traces from model output, including streams."""

from __future__ import annotations

_OPEN = "<think>"
_CLOSE = "</think>"


class ReasoningFilter:
    """Incrementally drop reasoning blocks whose tags may be split across fragments."""

    def __init__(self) -> None:
        self._buffer = ""
        self._inside = False
        self._started = False

    def feed(self, piece: str) -> str:
        self._buffer += piece
        output: list[str] = []
        while True:
            if self._inside:
                index = self._buffer.find(_CLOSE)
                if index < 0:
                    self._buffer = self._buffer[-(len(_CLOSE) - 1) :]
                    break
                self._buffer = self._buffer[index + len(_CLOSE) :]
                self._inside = False
                continue
            index = self._buffer.find(_OPEN)
            if index >= 0:
                output.append(self._buffer[:index])
                self._buffer = self._buffer[index + len(_OPEN) :]
                self._inside = True
                continue
            keep = _partial_tag_suffix(self._buffer)
            output.append(self._buffer[: len(self._buffer) - keep])
            self._buffer = self._buffer[len(self._buffer) - keep :]
            break
        return self._emit("".join(output))

    def flush(self) -> str:
        """Return held-back text; an unterminated reasoning block is discarded."""

        remainder = "" if self._inside else self._buffer
        self._buffer = ""
        return self._emit(remainder)

    def _emit(self, text: str) -> str:
        if not self._started:
            text = text.lstrip()
            self._started = bool(text)
        return text


def strip_reasoning(text: str) -> str:
    reasoning_filter = ReasoningFilter()
    return reasoning_filter.feed(text) + reasoning_filter.flush()


def _partial_tag_suffix(text: str) -> int:
    for length in range(min(len(_OPEN) - 1, len(text)), 0, -1):
        if _OPEN.startswith(text[-length:]):
            return length
    return 0
