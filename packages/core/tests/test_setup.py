"""Cài đặt một lần (setup.py) và trình mở `cadguard open` (app/launcher.py), không đụng máy thật."""
from pathlib import Path

import pytest

from cadguard import fixtures, setup

TTF = b"\x00\x01\x00\x00" + b"\x00" * 64


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(setup, "_register_font", lambda p: None)  # không ghi sổ đăng ký thật
    monkeypatch.setattr(setup, "install_plugin", lambda build=None: "plugin (giả)")  # không build .NET, không ghi registry
    monkeypatch.setattr(setup, "uninstall_plugin", lambda: None)
    monkeypatch.setattr(setup, "plugin_registered", lambda: False)
    sup = tmp_path / "roaming" / "AutoCAD 2027" / "R26.0" / "enu" / "Support"
    sup.mkdir(parents=True)
    monkeypatch.setattr(setup, "autocad_profiles", lambda: [{"name": "AutoCAD 2027", "release": "R26.0", "support": sup}])
    return tmp_path, sup


def test_font_install_from_download_and_remove(home):
    urls = []
    st = setup.install_font(fetch=lambda u: urls.append(u) or TTF)
    assert st["done"] and len(urls) == len(setup.FONT_FILES)
    assert all(u.startswith("https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/") for u in urls)
    assert setup.install_font(fetch=lambda u: pytest.fail("không tải lại"))["done"]
    with pytest.raises(setup.SetupError):
        setup.uninstall_font()
        setup.install_font(fetch=lambda u: b"<html>")
    assert not setup.font_status()["done"]


def test_autocad_link_keeps_user_acaddoc(home):
    _tmp, sup = home
    (sup / "acaddoc.lsp").write_text('(princ "cua nguoi dung")\n', encoding="utf-8")
    st = setup.install_autocad()
    assert st["done"]
    txt = (sup / "acaddoc.lsp").read_text(encoding="utf-8")
    assert '(princ "cua nguoi dung")' in txt and txt.count(setup.MARK_BEGIN) == 1 and "cg:*home*" in txt
    setup.install_autocad()  # cài lại không nhân đôi khối
    assert (sup / "acaddoc.lsp").read_text(encoding="utf-8").count(setup.MARK_BEGIN) == 1
    runner = (setup.addon_dir() / "cadguard-run.cmd").read_text(encoding="utf-8")
    assert "-m cadguard" in runner and '"%1"=="open"' in runner
    setup.uninstall_autocad()
    assert (sup / "acaddoc.lsp").read_text(encoding="utf-8").strip() == '(princ "cua nguoi dung")'


def test_autocad_link_removes_file_it_created(home):
    _tmp, sup = home
    setup.install_autocad()
    setup.uninstall_autocad()
    assert not (sup / "acaddoc.lsp").exists()


def test_lisp_has_single_command():
    lsp = (Path(setup.__file__).with_name("autocad") / "cadguard.lsp").read_text(encoding="utf-8")
    assert "(defun c:CADGUARD" in lsp and " open --workspace " in lsp


def test_open_reuses_running_app_and_switches_project(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    from cadguard.app import AppConfig, CadGuardApp
    from cadguard.app.launcher import open_app, write_instance
    from cadguard.app.server import start_in_thread, url_of

    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    fixtures.make_ok_sheet(b / "ban-ve.dxf")
    app = CadGuardApp(AppConfig(workspace=a), cli_detect=lambda name: {"installed": None})
    srv, _t = start_in_thread(app)
    try:
        write_instance(url_of(app), app.token, app.port)
        opened = []
        url = open_app(b, "ban-ve", browser=opened.append)
        assert opened == [url] and "dwg=ban-ve" in url and "open=1" in url and app.token in url
        assert app.d().ws.root == b.resolve()
    finally:
        srv.shutdown()
        srv.server_close()


def test_setup_api(home):
    from cadguard.app import AppConfig, CadGuardApp

    app = CadGuardApp(AppConfig(), cli_detect=lambda name: {"installed": None})
    steps = {s["id"]: s for s in app.setup_status()["steps"]}
    assert set(steps) == {"font", "autocad", "shortcut"} and not steps["autocad"]["done"]
    out = {s["id"]: s for s in app.setup_run("autocad", False)["steps"]}
    assert out["autocad"]["done"]
