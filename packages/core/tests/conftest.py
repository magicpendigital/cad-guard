from pathlib import Path

import pytest

from cadguard import fixtures
from cadguard.standard import load_standard

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def standard():
    return load_standard("furniture-v0", REPO / "standards")


@pytest.fixture(scope="session")
def hygiene():
    return load_standard("design-hygiene-v0", REPO / "standards")


@pytest.fixture(scope="session")
def synthetic(tmp_path_factory):
    d = tmp_path_factory.mktemp("synthetic")
    fixtures.make_all(d)
    return d


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_HOME", str(tmp_path / "home"))
