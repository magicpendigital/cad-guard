"""L3 — MÔ HÌNH TỦ CHUẨN `cg.cabinet/1` (thiết kế `docs/research/kien-truc-doc-ban-ve-tong-the.md`, P2).

Đích chung cho mọi cách vẽ: tấm ván, danh sách cắt, kiểm kết cấu chỉ đọc mô hình này (không đọc thẳng `Scene2`).

```
Cabinet (hạng mục)
 └─ Unit (khối / thùng): kích thước + nguồn, dạng, nhãn, hình dựng, ghi chú (khấu, vòng chú thích)
     └─ Node (khoang): khung [x0, x1] × [z0, z1] (toạ độ hạng mục)
         ├─ split "h": tấm ngang chạy suốt khoang chia trên/dưới · "v": vách chạy suốt chiều cao chia trái/phải · "" lá
         ├─ boards: các tấm tạo phép chia;  loose: tấm không chạy suốt khoang (đợt từng ô khi không vẽ vách)
         ├─ fronts: cánh / ngăn kéo gắn vào khoang NHỎ NHẤT che ≥ 85 % mặt cánh (cánh cao phủ nhiều khoang: khoang cha)
         └─ contents: thanh treo, hộc trong, thiết bị, đèn
```

`Scene2` (`cg.scene/2`) vẫn là dạng lưu và trả cho app; `from_scene` / `to_scene` chuyển hai chiều KHÔNG mất gì (thứ tự
cánh, nội thất giữ nguyên qua khoá `_o`). `Unit.fronts` / `Unit.inner` trải phẳng cây theo thứ tự gốc, nên mã tấm ván
cũ đọc được `Unit` như `Module2`.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .assemble import Front, Link, Module2, Room2, Scene2, Src, Wall2
from .build import Gap

SCHEMA = "cg.cabinet/1"
TOL_X = 40.0  # tấm chạy "suốt" bề ngang khoang: hai đầu cách hông ≤ mức này (dày hông + sai số vẽ)
TOL_Z = 120.0  # vách chạy "suốt" chiều cao khoang: hai đầu cách đáy/nóc ≤ mức này (chân + đáy)
LEVELS = ("shelf", "glass", "stone")


class Node(BaseModel):
    id: str
    x0: float
    x1: float
    z0: float
    z1: float
    split: str = ""  # "" | "h" | "v"
    boards: list[dict] = Field(default_factory=list)
    loose: list[dict] = Field(default_factory=list)
    fronts: list[dict] = Field(default_factory=list)
    contents: list[dict] = Field(default_factory=list)
    children: list["Node"] = Field(default_factory=list)

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def leaves(self) -> list["Node"]:
        return [n for n in self.walk() if not n.children]


class Unit(BaseModel):
    id: str
    kind: str
    form: str = "cabinet"
    x: float
    y: float
    z0: float
    w: float
    d: float
    h: float
    src: dict[str, Src] = Field(default_factory=dict)
    shelves: int = 0
    label: str = ""
    refs: list[str] = Field(default_factory=list)
    elevation: str = ""
    plan: str = ""
    ebox: list[float] = Field(default_factory=list)
    interior: str = ""
    annotations: list[dict] = Field(default_factory=list)  # = Module2.features
    root: Node

    @property
    def fronts(self) -> list[Front]:
        fs = sorted((f for n in self.root.walk() for f in n.fronts), key=lambda f: f["_o"])
        return [Front(**{k: v for k, v in f.items() if k != "_o"}) for f in fs]

    @property
    def inner(self) -> list[dict]:
        items = [q for n in self.root.walk() for q in (n.boards + n.loose + n.contents)]
        return [{k: v for k, v in q.items() if k != "_o"} for q in sorted(items, key=lambda q: q["_o"])]

    @property
    def features(self) -> list[dict]:
        return self.annotations

    def compartments(self) -> list[Node]:
        return self.root.leaves()


class Cabinet(BaseModel):
    schema_id: str = Field(default=SCHEMA, alias="schema")
    item: str = ""
    source_hash: str = ""
    scene_hash: str = ""
    unit: str = "mm"
    room: Room2 = Field(default_factory=Room2)
    walls: list[Wall2] = Field(default_factory=list)
    units: list[Unit] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @property
    def modules(self) -> list[Unit]:  # tên cũ: mã tấm ván / kết cấu duyệt `scene.modules`
        return self.units


# ---------------- dựng cây khoang ----------------

def _span_h(q: dict, n: Node) -> bool:
    return (q.get("kind") in LEVELS and q["x0"] <= n.x0 + TOL_X and q["x1"] >= n.x1 - TOL_X
            and n.z0 < q["z0"] and q["z1"] < n.z1)


def _span_v(q: dict, n: Node) -> bool:
    return (q.get("kind") == "partition" and q["z0"] <= n.z0 + TOL_Z and q["z1"] >= n.z1 - TOL_Z
            and n.x0 < q["x0"] and q["x1"] < n.x1)


def _split(n: Node, boards: list[dict]) -> None:
    """Cắt XY theo tấm chạy suốt khoang: tấm ngang trước (tầng), không có thì vách đứng; tấm còn lại đi theo khoang con."""
    for axis, test in (("h", _span_h), ("v", _span_v)):
        cut = [q for q in boards if test(q, n)]
        if not cut:
            continue
        cut.sort(key=lambda q: q["z0"] if axis == "h" else q["x0"])
        n.split, n.boards = axis, cut
        edges = [n.z0 if axis == "h" else n.x0] + [v for q in cut for v in ((q["z0"], q["z1"]) if axis == "h" else (q["x0"], q["x1"]))] \
            + [n.z1 if axis == "h" else n.x1]
        rest = [q for q in boards if q not in cut]
        for i, (a, b) in enumerate(zip(edges[::2], edges[1::2]), 1):
            c = Node(id=f"{n.id}.{i}", x0=n.x0 if axis == "h" else a, x1=n.x1 if axis == "h" else b,
                     z0=a if axis == "h" else n.z0, z1=b if axis == "h" else n.z1)
            mine = [q for q in rest if (a <= (q["z0"] + q["z1"]) / 2 <= b if axis == "h" else a <= (q["x0"] + q["x1"]) / 2 <= b)]
            n.children.append(c)
            _split(c, mine)
        placed = {id(q) for c in n.children for m in c.walk() for q in (m.boards + m.loose)}
        n.loose = [q for q in rest if id(q) not in placed]
        return
    n.loose = list(boards)


COVER = 0.85  # khoang "chứa" một cánh/đồ khi phủ ≥ 85 % diện tích của nó (cánh trùm qua mép tấm vẫn thuộc khoang nó che)


def _cover(q: dict, n: Node) -> float:
    a = max(1e-9, (q["x1"] - q["x0"]) * (q["z1"] - q["z0"]))
    return max(0.0, min(q["x1"], n.x1) - max(q["x0"], n.x0)) * max(0.0, min(q["z1"], n.z1) - max(q["z0"], n.z0)) / a


def _home(root: Node, q: dict) -> Node:
    """Khoang nhỏ nhất che ≥ COVER diện tích của `q` (không có thì khoang gốc)."""
    best = root
    for n in root.walk():
        if _cover(q, n) >= COVER and (n.x1 - n.x0) * (n.z1 - n.z0) <= (best.x1 - best.x0) * (best.z1 - best.z0):
            best = n
    return best


def unit_from_module(m: Module2) -> Unit:
    root = Node(id=f"{m.id}.K", x0=m.x, x1=m.x + m.w, z0=m.z0, z1=m.z0 + m.h)
    inner = [{**q, "_o": i} for i, q in enumerate(m.inner)]
    boards = [q for q in inner if q.get("kind") in LEVELS + ("partition",)]
    _split(root, boards)
    for q in inner:
        if q.get("kind") not in LEVELS + ("partition",):
            _home(root, q).contents.append(q)
    for i, f in enumerate(m.fronts):
        fd = {**f.model_dump(), "_o": i}
        _home(root, fd).fronts.append(fd)
    data = m.model_dump(exclude={"fronts", "inner", "features"})
    return Unit(**data, annotations=list(m.features), root=root)


def from_scene(sc: Scene2) -> Cabinet:
    return Cabinet(item=sc.item, source_hash=sc.source_hash, scene_hash=sc.scene_hash, room=sc.room, walls=sc.walls,
                   units=[unit_from_module(m) for m in sc.modules], links=sc.links, gaps=sc.gaps, notes=sc.notes)


def module_from_unit(u: Unit) -> Module2:
    data = u.model_dump(exclude={"root", "annotations"})
    return Module2(**data, fronts=u.fronts, inner=u.inner, features=list(u.annotations))


def to_scene(cab: Cabinet) -> Scene2:
    sc = Scene2(item=cab.item, source_hash=cab.source_hash, room=cab.room, walls=cab.walls,
                modules=[module_from_unit(u) for u in cab.units], links=cab.links, gaps=cab.gaps, notes=cab.notes)
    sc.scene_hash = cab.scene_hash
    return sc


def as_cabinet(scene) -> Cabinet:
    """Nhận `Cabinet` hoặc `Scene2`/cảnh tương tự (có `modules` kiểu Module2) và trả `Cabinet`."""
    if isinstance(scene, Cabinet):
        return scene
    if isinstance(scene, Scene2):
        return from_scene(scene)
    return scene  # cảnh khác (cg.scene/1…) giữ nguyên: mã gọi chỉ dùng `.modules`


def summary(cab: Cabinet) -> list[dict]:
    """Cây khoang gọn cho app/trợ lý: mỗi khối một cây [{id, box, split, fronts, contents, children}]."""
    def node(n: Node) -> dict:
        return {"id": n.id, "box": [round(n.x0, 1), round(n.z0, 1), round(n.x1, 1), round(n.z1, 1)], "split": n.split,
                "boards": [q["kind"] for q in n.boards], "loose": [q["kind"] for q in n.loose],
                "fronts": [f"{f['kind']}:{f['id']}" for f in n.fronts], "contents": [q["kind"] for q in n.contents],
                "children": [node(c) for c in n.children]}

    return [{"unit": u.id, "form": u.form, "compartments": len(u.compartments()), "tree": node(u.root)} for u in cab.units]


__all__ = ["Cabinet", "Node", "SCHEMA", "Unit", "as_cabinet", "from_scene", "module_from_unit", "summary", "to_scene",
           "unit_from_module"]
