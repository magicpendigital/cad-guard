"""Cộng tác bằng DXF tổng hợp, danh tính giả và LLM giả; không mạng ngoài."""
import concurrent.futures
import http.client
import io
import json
import secrets
import threading
import zipfile
from pathlib import Path

import pytest
from cadguard.fixtures import make_ok_sheet
from cadguard.review.store import LOCAL, ReviewError
from cadguard.review.service import ReviewService
from cadguard.review.server import ReviewServer
from cadguard.standard import load_standard
from cadguard.studio.llm import FakeBackend

C = "customer@example.test"
D = "designer@example.test"
T = "technical@example.test"
ORIGIN = "https://cadguard.example.ts.net"

@pytest.fixture
def svc(tmp_path):
    make_ok_sheet(tmp_path / "ok.dxf")
    backend = FakeBackend(['{"reply":"Đề xuất tổng hợp"}'])
    service = ReviewService(tmp_path, backend_factory=lambda: backend)
    service.fake = backend
    for actor, role in ((C,"customer"),(D,"designer"),(T,"technical")):
        service.store.member(LOCAL, actor, role, True)
    return service


def publish(svc, **kw):
    body = dict(name="Bộ hồ sơ SYN", items=[{"file":"ok.dxf","layout":"Model"}], customers=[C], cad_checked=True, request_id=secrets.token_hex(16)) | kw
    return svc.call(LOCAL,"publish",body)["id"]


def change(svc, actor, pid, action, **kw):
    p = svc.store.get(actor,pid)
    return svc.call(actor, action, dict(id=pid,version=p["version"],request_id=secrets.token_hex(16)) | kw)


def test_snapshot_and_publish_requires_explicit_cad_check(svc):
    with pytest.raises(ReviewError):
        publish(svc,cad_checked=False)
    pid=publish(svc)
    p=svc.store.get(C,pid)
    assert len(p["items"][0]["sha256"])==64 and p["revision"]==1
    with pytest.raises(ReviewError):
        svc.store.asset(C,pid,0,"dxf")
    assert svc.call(C,"view",{"id":pid,"item":0})["svg"]
    with pytest.raises(ReviewError):
        publish(svc,items=[{"file":"../outside.dxf"}])


def test_visibility_replies_roles_and_revocation(svc):
    pid=publish(svc)
    change(svc,D,pid,"note",text="PRIVATE-SYN",visibility="internal")
    private=svc.store.get(D,pid)["notes"][0]["id"]
    assert not svc.store.get(C,pid)["notes"]
    for action in ("reply","resolve","reopen","assign"):
        with pytest.raises(ReviewError):
            change(svc,C,pid,action,note=private,text="attack")
    change(svc,C,pid,"note",text="Cần đổi phương án SYN",visibility="shared",anchor={"kind":"rect","item":0,"coords":[0,0,100,100]})
    n=svc.store.get(C,pid)["notes"][0]
    assert n["anchor"]["sha256"]==svc.store.get(C,pid)["items"][0]["sha256"]
    change(svc,D,pid,"reply",note=n["id"],text="Đã tiếp nhận")
    change(svc,D,pid,"resolve",note=n["id"])
    assert len(svc.store.get(C,pid)["notes"][0]["replies"])==1
    svc.store.member(LOCAL,C,"customer",False)
    with pytest.raises(ReviewError):
        svc.store.get(C,pid)
    with pytest.raises(ReviewError):
        svc.call(D,"member",dict(login=C,role="customer",active=True))


def test_optimistic_concurrency_and_idempotency(svc):
    pid=publish(svc)
    p=svc.store.get(D,pid)
    body=dict(id=pid,version=p["version"],request_id=secrets.token_hex(16),text="SYN",visibility="shared")
    first=svc.call(D,"note",body)
    assert svc.call(D,"note",body)==first
    assert len(svc.store.get(D,pid)["notes"])==1
    with pytest.raises(ReviewError,match="Mã yêu cầu"):
        svc.call(D,"note",body | {"text":"different"})
    version=svc.store.get(D,pid)["version"]
    def post(i):
        try:
            svc.call(D,"note",dict(id=pid,version=version,request_id=secrets.token_hex(16),text=f"SYN {i}",visibility="internal"))
            return True
        except ReviewError as e:
            assert e.status==409
            return False
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(post,[0,1]))==[False,True]
    assert len(svc.store.get(D,pid)["notes"])==2
    change(svc,D,pid,"note",text="Retry retained",visibility="internal")
    assert len(svc.store.get(D,pid)["notes"])==3


def test_independent_approvals_invalidation_and_export(svc):
    pid=publish(svc)
    with pytest.raises(ReviewError):
        change(svc,T,pid,"release")
    with pytest.raises(ReviewError):
        change(svc,D,pid,"approve")
    change(svc,C,pid,"approve")
    with pytest.raises(ReviewError,match="quét"):
        change(svc,T,pid,"release")
    change(svc,T,pid,"audit")
    p=svc.store.get(T,pid)
    assert all(r["totals"]["E"]==0 for r in p["reports"])
    decisions={w["id"]:"Đã đối chiếu SYN" for w in svc.store.warnings(p)}
    change(svc,T,pid,"release",warnings=decisions)
    data=svc.store.export(T,pid)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert "manifest.json" in z.namelist() and "drawings/0.dxf" in z.namelist()
    change(svc,D,pid,"note",text="Thay đổi SYN",visibility="shared")
    assert svc.store.get(C,pid)["status"]=="review"
    assert svc.store.get(C,pid)["approvals"]
    with pytest.raises(ReviewError):
        svc.store.export(T,pid)
    note=svc.store.get(D,pid)["notes"][0]["id"]
    change(svc,D,pid,"resolve",note=note)
    change(svc,C,pid,"approve")
    change(svc,D,pid,"reopen",note=note)
    assert svc.store.get(C,pid)["status"]=="review"


def test_old_revision_snapshot_integrity_and_package_access(svc):
    old=publish(svc)
    newer=publish(svc,previous=old)
    assert svc.store.get(C,newer)["revision"]==2
    with pytest.raises(ReviewError,match="Phiên bản cũ"):
        change(svc,C,old,"approve")
    svc.store.member(LOCAL,"other@example.test","customer",True)
    with pytest.raises(ReviewError):
        svc.store.get("other@example.test",newer)
    (svc.store.dir/newer/"0.dxf").write_bytes(b"tamper synthetic")
    with pytest.raises(ReviewError,match="Snapshot"):
        change(svc,C,newer,"approve")


def test_agent_consent_isolated_context_and_revocation(svc):
    pid=publish(svc)
    change(svc,D,pid,"note",text="Ghi chú SYN",visibility="internal")
    note=svc.store.get(D,pid)["notes"][0]["id"]
    with pytest.raises(ReviewError):
        svc.call(C,"agent-open",dict(id=pid,note=note))
    sess=svc.call(D,"agent-open",dict(id=pid,note=note))
    body=dict(id=pid,session=sess["session"],message="Giải thích")
    with pytest.raises(ReviewError):
        svc.call(D,"agent-ask",body)
    assert not svc.fake.calls
    svc.call(D,"agent-consent",body | dict(consent=True,context_hash=sess["context_hash"]))
    assert svc.call(D,"agent-ask",body)["reply"]=="Đề xuất tổng hợp"
    sent=json.loads(svc.fake.calls[0][1][0]["content"].split("\nCâu hỏi:")[0])
    assert sent==sess["context"]
    with pytest.raises(ReviewError):
        svc.call(LOCAL,"agent-ask",body)
    svc.call(D,"agent-consent",body | dict(consent=False))
    with pytest.raises(ReviewError):
        svc.call(D,"agent-ask",body)
    assert len(svc.fake.calls)==1


def test_gateway_rejects_host_origin_csrf_identity_and_admin(svc):
    srv=ReviewServer(svc,ORIGIN,0)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    def req(path="/api/review/state",body=None,**headers):
        c=http.client.HTTPConnection("127.0.0.1",srv.server_address[1],timeout=10)
        h={"Host":"cadguard.example.ts.net","Tailscale-User-Login":C}|headers
        raw=None
        if body is not None:
            h["Content-Type"]="application/json";raw=json.dumps(body)
        c.request("POST" if body is not None else "GET",path,raw,h)
        r=c.getresponse();data=r.read();code=r.status;c.close();return code,data
    try:
        assert req(**{"Host":"evil.test"})[0]==403
        assert req(**{"Tailscale-User-Login":""})[0] in (400,403)
        code,data=req();assert code==200
        csrf=json.loads(data)["csrf"]
        assert req("/api/review/action",dict(action="member"),Origin=ORIGIN)[0]==403
        assert req("/api/review/action",dict(action="member"),Origin="https://evil.test",**{"X-Review-CSRF":csrf})[0]==403
        assert req("/api/review/action",dict(action="member",login=D,role="designer",active=True),Origin=ORIGIN,**{"X-Review-CSRF":csrf})[0]==403
        assert req("/api/ai/key")[0]==404
        svc.store.member(LOCAL,C,"customer",False)
        assert req()[0]==403
    finally:
        srv.shutdown();srv.server_close()


def test_cached_approval_is_not_used_after_customer_revoked(svc):
    pid=publish(svc)
    change(svc,C,pid,"approve")
    assert svc.store.get(T,pid)["status"]=="client-approved"
    svc.store.member(LOCAL,C,"customer",False)
    assert svc.store.get(T,pid)["status"]=="review"
    with pytest.raises(ReviewError):
        change(svc,T,pid,"release")


def test_local_app_does_not_list_review_snapshots(svc):
    publish(svc)
    files=svc.state(LOCAL)["drawings"]
    assert [x["path"] for x in files] == ["ok.dxf"]


def test_agent_session_reopens_after_revision_or_note_changes(svc):
    pid=publish(svc)
    change(svc,D,pid,"note",text="SYN",visibility="internal")
    note=svc.store.get(D,pid)["notes"][0]["id"]
    sess=svc.call(D,"agent-open",dict(id=pid,note=note))
    change(svc,D,pid,"reply",note=note,text="Ý mới SYN")
    with pytest.raises(ReviewError,match="thay đổi"):
        svc.call(D,"agent-consent",dict(id=pid,session=sess["session"],consent=True,context_hash=sess["context_hash"]))
    assert not svc.fake.calls


def test_review_modules_import_as_fresh_entrypoints():
    import subprocess
    import sys
    proc=subprocess.run([sys.executable,"-c","from cadguard.review.store import ReviewStore; from cadguard.review.server import ReviewServer"],capture_output=True,timeout=20)
    assert proc.returncode==0, proc.stderr.decode("utf-8",errors="replace")
