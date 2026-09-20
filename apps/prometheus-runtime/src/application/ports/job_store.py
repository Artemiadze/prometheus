"""Background-job persistence application port."""

from typing import Protocol

from application.dto.job import Job, JobId, JobKind
from domain.value_objects.vault_id import VaultId


class JobStore(Protocol):
    """Persist and retrieve background-job state."""

    def create(self, vault_id: VaultId, kind: JobKind) -> Job: ...

    def get(self, job_id: JobId) -> Job | None: ...

    def update(self, job: Job) -> None: ...

    def delete(self, job_id: JobId) -> None: ...

    def find_active(self, vault_id: VaultId) -> Job | None: ...

    def recover_interrupted(self) -> int: ...
