"""Vault identifier value object."""

import re
from dataclasses import dataclass

from domain.errors import InvalidIdentifierError

_VAULT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{5,63}$")


@dataclass(frozen=True, slots=True)
class VaultId:
    """A stable, path-segment-safe Vault identifier."""

    value: str

    def __post_init__(self) -> None:
        if not _VAULT_ID.fullmatch(self.value):
            raise InvalidIdentifierError()

    def __str__(self) -> str:
        return self.value
