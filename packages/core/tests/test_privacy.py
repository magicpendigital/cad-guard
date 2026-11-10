"""Chế độ dữ liệu: mặc định nội bộ, ẩn danh là công tắc theo dự án (privacy.py)."""
from cadguard import privacy


def test_default_internal_and_project_toggle(tmp_path):
    assert privacy.effective(tmp_path) is False
    privacy.set_project_anonymize(tmp_path, True)
    assert privacy.project_anonymize(tmp_path) is True and privacy.effective(tmp_path) is True
    assert privacy.effective(tmp_path, flag=False) is False  # cờ dòng lệnh thắng tệp dự án
    privacy.set_project_anonymize(tmp_path, False)
    assert privacy.effective(tmp_path) is False and privacy.effective(tmp_path, flag=True) is True


def test_app_privacy_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("CADGUARD_CONFIG_DIR", str(tmp_path / "cfg"))
    from cadguard.app import AppConfig, CadGuardApp

    ws = tmp_path / "duan"
    ws.mkdir()
    app = CadGuardApp(AppConfig(workspace=ws), cli_detect=lambda name: {"installed": None})
    assert app.session()["anonymize"] is False
    res = app.set_privacy(True)
    assert res["anonymize"] is True and privacy.project_anonymize(ws) is True
    app2 = CadGuardApp(AppConfig(workspace=ws), cli_detect=lambda name: {"installed": None})
    assert app2.session()["anonymize"] is True
