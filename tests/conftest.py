"""Shared test setup."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _connector_scratch_in_pytest_temp(tmp_path_factory):
    """Database connectors copy tables to a scratch folder (STRATA_SCRATCH,
    default the system temp folder). Tests used to leave hundreds of them in
    %TEMP%; pytest's own temp folder is cleaned up after a few runs."""
    mp = pytest.MonkeyPatch()
    mp.setenv("STRATA_SCRATCH", str(tmp_path_factory.mktemp("connector-scratch")))
    yield
    mp.undo()
