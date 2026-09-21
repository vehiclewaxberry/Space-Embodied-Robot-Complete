"""Pre-registered vNext runner surface; no success path exists in this freeze."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DENIAL = "NO_DIRECT_OWNER_SOURCE_R2_RAW_ADAPTER_EXECUTION_PATH_NOT_IMPLEMENTED"


class RunnerAuthorizationError(RuntimeError):
    pass


def consume_authorization(*args: Any, **kwargs: Any) -> None:
    raise RunnerAuthorizationError(DENIAL)


def authorized_lazy_imports(*args: Any, **kwargs: Any) -> None:
    raise RunnerAuthorizationError(DENIAL)


def create_output_root_after_authorization(output_root: Path, *args: Any, **kwargs: Any) -> None:
    raise RunnerAuthorizationError(DENIAL)


def run_registered_vnext(*args: Any, **kwargs: Any) -> None:
    raise RunnerAuthorizationError(DENIAL)


__all__ = [
    "DENIAL", "RunnerAuthorizationError", "authorized_lazy_imports",
    "consume_authorization", "create_output_root_after_authorization",
    "run_registered_vnext",
]
