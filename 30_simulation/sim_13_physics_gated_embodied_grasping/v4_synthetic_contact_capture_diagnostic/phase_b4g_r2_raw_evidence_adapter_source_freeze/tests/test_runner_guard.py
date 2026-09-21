from __future__ import annotations

from pathlib import Path

import pytest

from r2_raw_adapter.runner_guard import (
    DENIAL,
    RunnerAuthorizationError,
    authorized_lazy_imports,
    consume_authorization,
    create_output_root_after_authorization,
    run_registered_vnext,
)


@pytest.mark.parametrize(
    "call",
    [
        lambda: consume_authorization({"owner": True}),
        lambda: authorized_lazy_imports(object()),
        lambda: create_output_root_after_authorization(Path("never-created")),
        lambda: run_registered_vnext(),
    ],
)
def test_every_vnext_execution_success_path_is_unconditionally_absent(call) -> None:
    with pytest.raises(RunnerAuthorizationError, match=DENIAL):
        call()
    assert not Path("never-created").exists()
