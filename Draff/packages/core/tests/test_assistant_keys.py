"""`cadguard keys` với kho khoá GIẢ (không đụng kho khoá thật của máy), không bao giờ ghi tệp."""
from __future__ import annotations

import sys
import types

import pytest

from cadguard.assistant import keys
from cadguard.cli import main as cli_main

FAKE_KEY = "test-fake-key-abcdefghijklmnop"


@pytest.fixture
def fake_keyring(monkeypatch):
    store: dict = {}
    mod = types.ModuleType("keyring")
    mod.get_password = lambda service, user: store.get((service, user))
    mod.set_password = lambda service, user, pw: store.__setitem__((service, user), pw)

    def delete(service, user):
        if (service, user) not in store:
            raise KeyError(user)
        del store[(service, user)]

    mod.delete_password = delete
    monkeypatch.setitem(sys.modules, "keyring", mod)
    for env in keys.KEY_ENV.values():
        monkeypatch.delenv(env, raising=False)
    return store


def _files(root):
    return sorted(str(p) for p in root.rglob("*"))


def test_keys_set_status_delete_without_files(fake_keyring, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    before = _files(tmp_path)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": FAKE_KEY)
    assert cli_main(["keys", "set", "anthropic"]) == 0
    assert fake_keyring[("cad-guard", "anthropic")] == FAKE_KEY
    assert keys.get_key("anthropic") == FAKE_KEY
    assert cli_main(["keys", "status", "anthropic"]) == 0
    assert cli_main(["engines", "--no-detect"]) == 0
    assert cli_main(["keys", "delete", "anthropic"]) == 0
    assert keys.get_key("anthropic") is None
    out = capsys.readouterr()
    assert FAKE_KEY not in out.out + out.err
    assert "kho khoá hệ điều hành: có" in out.out
    assert _files(tmp_path) == before  # không ghi tệp nào (kể cả CADGUARD_HOME nằm trong tmp_path)


def test_env_var_wins_over_keyring(fake_keyring, monkeypatch):
    fake_keyring[("cad-guard", "openai")] = "test-from-keyring-123456"
    monkeypatch.setenv("OPENAI_API_KEY", "test-from-env-123456")
    assert keys.get_key("openai") == "test-from-env-123456"
    assert keys.key_status("openai") == {"provider": "openai", "env_var": "OPENAI_API_KEY", "env": True, "keyring": True}


def test_no_keyring_is_vietnamese_and_writes_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "keyring", None)  # import keyring -> ImportError
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": FAKE_KEY)
    before = _files(tmp_path)
    assert cli_main(["keys", "set", "gemini"]) == 2
    err = capsys.readouterr().err
    assert "keyring" in err and "không ghi khoá ra tệp" in err and FAKE_KEY not in err
    assert _files(tmp_path) == before
    assert not any(FAKE_KEY in p.read_text(encoding="utf-8", errors="ignore") for p in tmp_path.rglob("*") if p.is_file())
    assert keys.key_status("gemini")["keyring"] is None


def test_keys_rejects_unknown_provider():
    with pytest.raises(keys.KeyStoreError):
        keys.set_key("ollama", "x")
