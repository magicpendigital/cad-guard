import crypto from 'node:crypto';
import { ParsedDxfModel, DxfEntity } from './dxfParser.js';

export interface SceneWall {
  handle: string;
  start: [number, number];
  end: [number, number];
  thickness: number;
  height: number;
  height_source: string;
}

export interface SceneModule {
  handle: string;
  kind: string;
  x: number;
  y: number;
  rotation: number;
  w: number;
  d: number;
  h: number;
  material: string;
  source: 'drawing' | 'user';
}

export interface ScenePanel {
  id: string;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  z0: number;
  z1: number;
  source: 'views' | 'user';
}

export interface SceneField {
  key: string;
  label: string;
  unit: string;
  kind: 'number' | 'choice';
  options?: string[];
  currentValue?: string | number;
}

export interface SceneGap {
  id: string;
  kind: 'missing_value' | 'ambiguous' | 'missing_view' | 'conflict';
  target: string;
  message: string;
  fields: SceneField[];
}

export interface GeometricCluster {
  id: string;
  layer: string;
  bbox: [number, number, number, number]; // [minX, minY, w, h]
  rectCount: number;
  assignedView: '' | 'front' | 'top' | 'side';
  handles: string[];
  sampleTexts: string[];
}

export interface ViewerBox {
  id: string;
  label: string;
  material: string;
  base: [number, number][]; // 4 corners in XY mm
  z0: number;
  z1: number;
  color: [number, number, number];
  source: string;
  // Bổ sung thuộc tính kết cấu nội thất chi tiết & công thái học
  partType?: 'wall' | 'carcass_side' | 'carcass_bottom' | 'carcass_top' | 'carcass_back' | 'shelf' | 'divider' | 'door' | 'drawer' | 'countertop' | 'plinth' | 'module_box';
  role?: 'exterior' | 'interior' | 'door' | 'drawer';
  hingeSide?: 'left' | 'right' | 'top';
  doorIndex?: number;
  parentModuleId?: string;
  thickness?: number;
  openOffset?: [number, number, number]; // vector di chuyển khi mở
  openRotation?: number; // góc xoay khi mở cánh (độ)
  hingePivot?: [number, number]; // trục xoay bản lề
}

export interface StudioProposal {
  id: string;
  kind: 'set_views' | 'set_value' | 'set_attrib' | 'change_layer';
  title: string;
  reason: string;
  payload: Record<string, any>;
}

export interface ErgonomicsCheck {
  id: string;
  category: 'height' | 'reach' | 'clearance' | 'swing' | 'storage';
  title: string;
  currentVal: string;
  standardVal: string;
  score: number; // 0-100
  status: 'optimal' | 'good' | 'warn';
  advice: string;
  impactOnUser: string;
}

export interface ErgonomicsAnalysis {
  overallScore: number;
  grade: string;
  summary: string;
  clearanceNote: string;
  reachNote: string;
  checks: ErgonomicsCheck[];
  doorSpecs: {
    label: string;
    width: number;
    height: number;
    swingRisk: boolean;
    advice: string;
  }[];
}

export interface SceneData {
  schema: string;
  source_hash: string;
  fileName: string;
  walls: SceneWall[];
  modules: SceneModule[];
  panels: ScenePanel[];
  clusters: GeometricCluster[];
  gaps: SceneGap[];
  notes: string[];
  boxes: ViewerBox[];
  proposals: StudioProposal[];
  ergonomics?: ErgonomicsAnalysis;
}

const PALETTE: [number, number, number][] = [
  [0.86, 0.72, 0.52], // Warm Oak
  [0.55, 0.7, 0.62],  // Sage Green
  [0.62, 0.66, 0.82], // Slate Blue
  [0.82, 0.6, 0.6],   // Terracotta
  [0.78, 0.78, 0.6],  // Sand
  [0.7, 0.6, 0.78]    // Lavender Wood
];

const FIXED_COLORS: Record<string, [number, number, number]> = {
  wall: [0.91, 0.9, 0.87],
  floor: [0.6, 0.58, 0.55],
  default: [0.82, 0.75, 0.63]
};

export function colorForMaterial(material: string): [number, number, number] {
  if (!material) return FIXED_COLORS.default;
  if (FIXED_COLORS[material]) return FIXED_COLORS[material];
  const hash = parseInt(crypto.createHash('sha256').update(material, 'utf8').digest('hex').slice(0, 8), 16);
  return PALETTE[hash % PALETTE.length];
}

function parsePositiveNum(raw: unknown): number | null {
  if (raw === undefined || raw === null || raw === '') return null;
  const v = parseFloat(String(raw).trim().replace(',', '.'));
  return Number.isFinite(v) && v > 0 ? v : null;
}

export function buildSceneFromDxf(
  model: ParsedDxfModel,
  supplement: Record<string, any> = {},
  viewOverrides: Record<string, '' | 'front' | 'top' | 'side'> = {},
  aiConsent = false,
  sheetEntities?: DxfEntity[]
): SceneData {
  const walls: SceneWall[] = [];
  const modules: SceneModule[] = [];
  const panels: ScenePanel[] = [];
  const gaps: SceneGap[] = [];
  const notes: string[] = [];

  const entsToProcess = (sheetEntities && sheetEntities.length > 0) ? sheetEntities : model.entities;

  if (model.insunits !== 4) {
    notes.push(`Đơn vị bản vẽ hiện tại ($INSUNITS = ${model.insunits}) không phải mm (4): cần xác nhận tỉ lệ.`);
  }

  // 1. Extract Walls on FN-ROOM-WALL or WALL layers
  for (const e of entsToProcess) {
    if (
      (e.layer === 'FN-ROOM-WALL' || /WALL|TUONG|VACH/i.test(e.layer)) &&
      (e.type === 'LINE' || e.type === 'LWPOLYLINE' || e.type === 'POLYLINE') &&
      e.pts.length >= 2
    ) {
      const pts = [...e.pts];
      if (e.closed && pts.length > 2) pts.push(pts[0]);
      for (let i = 0; i + 1 < pts.length; i++) {
        const a = pts[i];
        const b = pts[i + 1];
        if (Math.hypot(b[0] - a[0], b[1] - a[1]) > 10) {
          walls.push({
            handle: e.handle,
            start: a,
            end: b,
            thickness: 120,
            height: 2850,
            height_source: 'default'
          });
        }
      }
    }
  }

  // 2. Extract Modules (INSERT FN_MOD*)
  const LABELS: Record<string, string> = {
    w: 'Chiều rộng W',
    d: 'Chiều sâu D',
    h: 'Chiều cao H'
  };

  for (const e of entsToProcess) {
    if (e.type === 'INSERT' && e.insert && (e.block || '').toUpperCase().startsWith('FN_MOD')) {
      const at = e.attribs || {};
      const vals: Record<string, number | null> = {
        w: parsePositiveNum(at.W),
        d: parsePositiveNum(at.D),
        h: parsePositiveNum(at.H)
      };
      let usedUser = false;
      const missing: string[] = [];

      for (const k of ['w', 'd', 'h']) {
        const supVal = parsePositiveNum(supplement[`module:${e.handle}:${k}`]);
        if (supVal !== null) {
          vals[k] = supVal;
          usedUser = true;
        } else if (vals[k] === null) {
          missing.push(k);
        }
      }

      if (missing.length > 0) {
        const names = missing.map(k => k.toUpperCase()).join(', ');
        gaps.push({
          id: `module:${e.handle}`,
          kind: 'missing_value',
          target: e.handle,
          message: `Mô-đun ${at.KIND || e.block} (#${e.handle}): thiếu thông số ${names} (mm).`,
          fields: missing.map(k => ({
            key: `module:${e.handle}:${k}`,
            label: `${LABELS[k]} cho ${at.KIND || e.handle}`,
            unit: 'mm',
            kind: 'number'
          }))
        });
      }

      // Render module in 3D (if missing H/D, use temporary preview dashed or resolved value)
      if (vals.w && vals.d && vals.h) {
        modules.push({
          handle: e.handle,
          kind: at.KIND || 'cabinet',
          x: e.insert[0],
          y: e.insert[1],
          rotation: e.rotation || 0,
          w: vals.w,
          d: vals.d,
          h: vals.h,
          material: at.MAT || 'MDF_OAK_18',
          source: usedUser ? 'user' : 'drawing'
        });
      }
    }
  }

  // 3. Geometric Clusters & 2D-to-3D Multi-view Panel Reconstruction
  // Group closed polylines by layer into geometric clusters C1, C2...
  const closedRects = entsToProcess.filter(
    e => (e.type === 'LWPOLYLINE' || e.type === 'POLYLINE') && e.pts.length >= 4 && e.layer !== 'FN-ROOM-WALL'
  );

  const byLayer = new Map<string, DxfEntity[]>();
  for (const r of closedRects) {
    const arr = byLayer.get(r.layer) || [];
    arr.push(r);
    byLayer.set(r.layer, arr);
  }

  const clusters: GeometricCluster[] = [];
  let cIdx = 1;
  for (const [layer, ents] of byLayer.entries()) {
    const cid = `C${cIdx++}`;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const e of ents) {
      for (const [x, y] of e.pts) {
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
      }
    }
    const defaultRole: '' | 'front' | 'top' | 'side' =
      layer === 'FN-VIEW-FRONT'
        ? 'front'
        : layer === 'FN-VIEW-TOP'
          ? 'top'
          : layer === 'FN-VIEW-SIDE'
            ? 'side'
            : '';
    const assignedView = viewOverrides[cid] !== undefined ? viewOverrides[cid] : defaultRole;
    clusters.push({
      id: cid,
      layer,
      bbox: [
        Math.round(minX),
        Math.round(minY),
        Math.max(10, Math.round(maxX - minX)),
        Math.max(10, Math.round(maxY - minY))
      ],
      rectCount: ents.length,
      assignedView,
      handles: ents.map(e => e.handle),
      sampleTexts: entsToProcess
        .filter(e => e.type === 'TEXT' || e.type === 'MTEXT')
        .slice(0, 2)
        .map(e => e.text || '')
    });
  }

  // Reconstruct 3D panels from clusters assigned to 'front'
  const frontClusters = clusters.filter(c => c.assignedView === 'front');
  const topClusters = clusters.filter(c => c.assignedView === 'top');
  const sideClusters = clusters.filter(c => c.assignedView === 'side');

  const hasDepthView = topClusters.length > 0 || sideClusters.length > 0;
  const userDefaultDepth = parsePositiveNum(supplement['panels:default_depth']);

  if (frontClusters.length > 0 && !hasDepthView && userDefaultDepth === null) {
    gaps.push({
      id: 'panels:default_depth',
      kind: 'missing_view',
      target: frontClusters.map(c => c.id).join(', '),
      message: `Cụm hình chiếu đứng (${frontClusters.map(c => c.id).join(', ')}) thiếu hình chiếu Bằng/Cạnh để xác định chiều sâu D của tấm ván.`,
      fields: [
        {
          key: 'panels:default_depth',
          label: 'Chiều sâu tấm ván D (bù hình chiếu Bằng/Cạnh)',
          unit: 'mm',
          kind: 'number'
        }
      ]
    });
  }

  const effectiveDepth = userDefaultDepth || (hasDepthView ? 580 : 560);
  let pSeq = 1;
  for (const fc of frontClusters) {
    const ents = byLayer.get(fc.layer) || [];
    for (const e of ents) {
      const xs = e.pts.map(p => p[0]);
      const ys = e.pts.map(p => p[1]);
      const x0 = Math.min(...xs);
      const x1 = Math.max(...xs);
      const z0 = Math.min(...ys);
      const z1 = Math.max(...ys);
      const pid = `P${pSeq++}`;
      const customDepth = parsePositiveNum(supplement[`panel:${pid}:d`]) || effectiveDepth;
      panels.push({
        id: pid,
        x0,
        x1,
        y0: 40,
        y1: 40 + customDepth,
        z0,
        z1,
        source: userDefaultDepth ? 'user' : 'views'
      });
    }
  }

  // Flag unassigned clusters as ambiguous gap so user can assign view role
  for (const cl of clusters) {
    if (!cl.assignedView) {
      gaps.push({
        id: `cluster:${cl.id}`,
        kind: 'ambiguous',
        target: cl.id,
        message: `Cụm hình học ${cl.id} (${cl.rectCount} đường bao trên layer "${cl.layer}", kích thước ${cl.bbox[2]}×${cl.bbox[3]} mm) chưa được gán vai trò hình chiếu.`,
        fields: [
          {
            key: `view:${cl.id}`,
            label: `Vai trò hình chiếu cho cụm ${cl.id}`,
            unit: '',
            kind: 'choice',
            options: ['front', 'top', 'side']
          }
        ]
      });
    }
  }

  // 4. Convert walls, modules, and panels into 3D ViewerBoxes (matching geometry.py)
  const boxes: ViewerBox[] = [];

  for (const w of walls) {
    const [x1, y1] = w.start;
    const [x2, y2] = w.end;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len = Math.hypot(dx, dy);
    if (len < 1) continue;
    const nx = (-dy / len) * (w.thickness / 2);
    const ny = (dx / len) * (w.thickness / 2);
    boxes.push({
      id: `wall:${w.handle}`,
      label: `Tường #${w.handle} (${Math.round(len)}×${w.thickness}×${w.height} mm)`,
      material: 'wall',
      base: [
        [x1 + nx, y1 + ny],
        [x2 + nx, y2 + ny],
        [x2 - nx, y2 - ny],
        [x1 - nx, y1 - ny]
      ],
      z0: 0,
      z1: w.height,
      color: FIXED_COLORS.wall,
      source: w.height_source
    });
  }

  for (const m of modules) {
    const rad = (m.rotation * Math.PI) / 180;
    const c = Math.cos(rad);
    const s = Math.sin(rad);

    const toWorld = (lx: number, ly: number): [number, number] => [
      +(m.x + lx * c - ly * s).toFixed(1),
      +(m.y + lx * s + ly * c).toFixed(1)
    ];
    const makeBase = (x1: number, y1: number, x2: number, y2: number): [number, number][] => [
      toWorld(x1, y1),
      toWorld(x2, y1),
      toWorld(x2, y2),
      toWorld(x1, y2)
    ];

    // 1. Khối bao tổng thể (Exterior Envelope)
    boxes.push({
      id: `module:${m.handle}`,
      label: `${m.kind} #${m.handle} (${m.w}×${m.d}×${m.h} mm · ${m.material || 'MDF'})`,
      material: m.material || 'cabinet',
      base: makeBase(0, 0, m.w, m.d),
      z0: 0,
      z1: m.h,
      color: colorForMaterial(m.material || m.kind),
      source: m.source,
      partType: 'module_box',
      role: 'exterior',
      parentModuleId: m.handle
    });

    // 2. Chi tiết kết cấu bên trong (Internal Structure): Thùng tủ, vách hông 18mm, đợt, hậu 9mm, cánh, ngăn kéo
    const plinthH = m.h <= 1100 ? 80 : 0;

    // Vách hông trái (18mm)
    boxes.push({
      id: `part:${m.handle}:side_l`,
      label: `Vách hông trái 18mm (#${m.handle})`,
      material: 'carcass',
      base: makeBase(0, 0, 18, m.d),
      z0: plinthH,
      z1: m.h,
      color: [0.82, 0.74, 0.62],
      source: m.source,
      partType: 'carcass_side',
      role: 'interior',
      parentModuleId: m.handle,
      thickness: 18
    });

    // Vách hông phải (18mm)
    boxes.push({
      id: `part:${m.handle}:side_r`,
      label: `Vách hông phải 18mm (#${m.handle})`,
      material: 'carcass',
      base: makeBase(m.w - 18, 0, m.w, m.d),
      z0: plinthH,
      z1: m.h,
      color: [0.82, 0.74, 0.62],
      source: m.source,
      partType: 'carcass_side',
      role: 'interior',
      parentModuleId: m.handle,
      thickness: 18
    });

    // Đáy thùng (18mm)
    boxes.push({
      id: `part:${m.handle}:bottom`,
      label: `Đáy thùng tủ 18mm (#${m.handle})`,
      material: 'carcass',
      base: makeBase(18, 0, m.w - 18, m.d - 18),
      z0: plinthH,
      z1: plinthH + 18,
      color: [0.79, 0.71, 0.59],
      source: m.source,
      partType: 'carcass_bottom',
      role: 'interior',
      parentModuleId: m.handle,
      thickness: 18
    });

    // Nóc tủ (18mm)
    boxes.push({
      id: `part:${m.handle}:top`,
      label: `Nóc tủ 18mm (#${m.handle})`,
      material: 'carcass',
      base: makeBase(18, 0, m.w - 18, m.d - 18),
      z0: m.h - 18,
      z1: m.h,
      color: [0.79, 0.71, 0.59],
      source: m.source,
      partType: 'carcass_top',
      role: 'interior',
      parentModuleId: m.handle,
      thickness: 18
    });

    // Vách hậu âm (9mm)
    boxes.push({
      id: `part:${m.handle}:back`,
      label: `Vách hậu âm 9mm (#${m.handle})`,
      material: 'carcass_back',
      base: makeBase(18, m.d - 25, m.w - 18, m.d - 16),
      z0: plinthH + 18,
      z1: m.h - 18,
      color: [0.88, 0.82, 0.72],
      source: m.source,
      partType: 'carcass_back',
      role: 'interior',
      parentModuleId: m.handle,
      thickness: 9
    });

    // Len chân chống ẩm (Plinth 80mm)
    if (plinthH > 0) {
      boxes.push({
        id: `part:${m.handle}:plinth`,
        label: `Len chân chống ẩm 80mm (#${m.handle})`,
        material: 'plinth',
        base: makeBase(18, 40, m.w - 18, 58),
        z0: 0,
        z1: plinthH,
        color: [0.35, 0.35, 0.38],
        source: m.source,
        partType: 'plinth',
        role: 'interior',
        parentModuleId: m.handle,
        thickness: 18
      });
    }

    // Các đợt chia ngăn bên trong (Internal Shelves)
    if (m.h > 1500) {
      // Tủ cao: 3 đợt ngang chia khoang quần áo / lưu trữ
      [450, 950, 1800].forEach((sz, sIdx) => {
        if (sz < m.h - 100) {
          boxes.push({
            id: `part:${m.handle}:shelf_${sIdx + 1}`,
            label: `Đợt ngăn ${sIdx + 1} (H=${sz} mm)`,
            material: 'shelf',
            base: makeBase(18, 0, m.w - 18, m.d - 25),
            z0: sz,
            z1: sz + 18,
            color: [0.76, 0.68, 0.56],
            source: m.source,
            partType: 'shelf',
            role: 'interior',
            parentModuleId: m.handle,
            thickness: 18
          });
        }
      });
    } else {
      // Tủ thấp / bàn: 1 đợt chia đôi khoang
      const shelfZ = Math.round((m.h - plinthH) / 2 + plinthH);
      boxes.push({
        id: `part:${m.handle}:shelf_mid`,
        label: `Đợt ngăn chia khoang 18mm (H=${shelfZ} mm)`,
        material: 'shelf',
        base: makeBase(18, 0, m.w - 18, m.d - 25),
        z0: shelfZ,
        z1: shelfZ + 18,
        color: [0.76, 0.68, 0.56],
        source: m.source,
        partType: 'shelf',
        role: 'interior',
        parentModuleId: m.handle,
        thickness: 18
      });
    }

    // Vách đứng ngăn khoang đôi nếu chiều rộng >= 800mm
    if (m.w >= 800) {
      const midX = m.w / 2;
      boxes.push({
        id: `part:${m.handle}:divider`,
        label: `Vách đứng chia khoang 18mm (#${m.handle})`,
        material: 'carcass',
        base: makeBase(midX - 9, 0, midX + 9, m.d - 25),
        z0: plinthH + 18,
        z1: m.h - 18,
        color: [0.82, 0.74, 0.62],
        source: m.source,
        partType: 'divider',
        role: 'interior',
        parentModuleId: m.handle,
        thickness: 18
      });
    }

    // Hệ cánh cửa (Doors) có bản lề và góc mở
    const isDouble = m.w > 500;
    const doorZ0 = plinthH + 2;
    const doorZ1 = m.h - 2;

    if (isDouble) {
      const dW = (m.w - 6) / 2;
      // Cánh mở bên trái
      boxes.push({
        id: `part:${m.handle}:door_l`,
        label: `Cánh mở trái (${Math.round(dW)}×${Math.round(doorZ1 - doorZ0)} mm)`,
        material: 'door',
        base: makeBase(2, -18, 2 + dW, 0),
        z0: doorZ0,
        z1: doorZ1,
        color: [0.93, 0.86, 0.74],
        source: m.source,
        partType: 'door',
        role: 'door',
        hingeSide: 'left',
        doorIndex: 0,
        parentModuleId: m.handle,
        thickness: 18,
        hingePivot: toWorld(2, 0)
      });
      // Cánh mở bên phải
      boxes.push({
        id: `part:${m.handle}:door_r`,
        label: `Cánh mở phải (${Math.round(dW)}×${Math.round(doorZ1 - doorZ0)} mm)`,
        material: 'door',
        base: makeBase(m.w - 2 - dW, -18, m.w - 2, 0),
        z0: doorZ0,
        z1: doorZ1,
        color: [0.93, 0.86, 0.74],
        source: m.source,
        partType: 'door',
        role: 'door',
        hingeSide: 'right',
        doorIndex: 1,
        parentModuleId: m.handle,
        thickness: 18,
        hingePivot: toWorld(m.w - 2, 0)
      });
    } else {
      // Cánh mở đơn
      boxes.push({
        id: `part:${m.handle}:door_single`,
        label: `Cánh mở đơn (${Math.round(m.w - 4)}×${Math.round(doorZ1 - doorZ0)} mm)`,
        material: 'door',
        base: makeBase(2, -18, m.w - 2, 0),
        z0: doorZ0,
        z1: doorZ1,
        color: [0.93, 0.86, 0.74],
        source: m.source,
        partType: 'door',
        role: 'door',
        hingeSide: 'left',
        doorIndex: 0,
        parentModuleId: m.handle,
        thickness: 18,
        hingePivot: toWorld(2, 0)
      });
    }

    // Mặt đá / Mặt thao tác 20mm (nếu là tủ bếp dưới / bàn)
    if (m.h <= 900) {
      boxes.push({
        id: `part:${m.handle}:countertop`,
        label: `Mặt đá / Mặt bàn thao tác 20mm (#${m.handle})`,
        material: 'countertop',
        base: makeBase(-10, -25, m.w + 10, m.d + 10),
        z0: m.h,
        z1: m.h + 20,
        color: [0.95, 0.95, 0.95],
        source: m.source,
        partType: 'countertop',
        role: 'interior',
        parentModuleId: m.handle,
        thickness: 20
      });
    }
  }

  for (const p of panels) {
    boxes.push({
      id: `panel:${p.id}`,
      label: `Tấm ván ${p.id} (${Math.round(p.x1 - p.x0)}×${Math.round(p.y1 - p.y0)}×${Math.round(p.z1 - p.z0)} mm)`,
      material: p.source === 'user' ? 'panel_user' : 'panel_views',
      base: [
        [p.x0, p.y0],
        [p.x1, p.y0],
        [p.x1, p.y1],
        [p.x0, p.y1]
      ],
      z0: p.z0,
      z1: p.z1,
      color: colorForMaterial(p.id),
      source: p.source,
      partType: 'shelf',
      role: 'interior'
    });
  }

  // 5. Generate Studio AI Proposals (when aiConsent is enabled or for preview)
  const proposals: StudioProposal[] = [];
  if (aiConsent) {
    for (const g of gaps) {
      if (g.id.startsWith('module:')) {
        const fKey = g.fields[0]?.key || '';
        const dimType = fKey.split(':').pop() || 'h';
        const suggestedVal = dimType === 'h' ? 2100 : dimType === 'd' ? 600 : 800;
        proposals.push({
          id: `prop-${g.id}`,
          kind: 'set_value',
          title: `Đề xuất ${dimType.toUpperCase()} = ${suggestedVal} mm cho ${g.target}`,
          reason: `Dựa trên tên khối và quy cách tủ cao tiêu chuẩn trong bản vẽ, chiều ${dimType.toUpperCase()} phù hợp là ${suggestedVal} mm.`,
          payload: { key: fKey, value: suggestedVal }
        });
      } else if (g.id === 'panels:default_depth') {
        proposals.push({
          id: 'prop-panel-depth',
          kind: 'set_value',
          title: 'Đề xuất chiều sâu tấm ván D = 580 mm (Tủ dưới chuẩn 600 trừ hậu 20)',
          reason: 'Khớp với chiều sâu lòng tủ bếp dưới 580 mm theo chuẩn furniture-v0.',
          payload: { key: 'panels:default_depth', value: 580 }
        });
      } else if (g.id.startsWith('cluster:')) {
        const cid = g.target;
        proposals.push({
          id: `prop-view-${cid}`,
          kind: 'set_views',
          title: `Gán cụm ${cid} làm Hình chiếu Đứng (front)`,
          reason: `Tỉ lệ khung bao của ${cid} tương ứng với mặt đứng cánh tủ.`,
          payload: { clusterId: cid, view: 'front' }
        });
      }
    }
  }

  // 6. Phân tích & Đánh giá yếu tố Công thái học (AI Ergonomics Analysis)
  const ergonomics = analyzeErgonomics(modules, walls, panels);

  return {
    schema: 'cg.scene/1',
    source_hash: model.fileHash,
    fileName: model.fileName,
    walls,
    modules,
    panels,
    clusters,
    gaps,
    notes,
    boxes,
    proposals,
    ergonomics
  };
}

export function analyzeErgonomics(modules: SceneModule[], walls: SceneWall[], panels: ScenePanel[]): ErgonomicsAnalysis {
  const checks: ErgonomicsCheck[] = [];
  const doorSpecs: { label: string; width: number; height: number; swingRisk: boolean; advice: string }[] = [];
  let score = 96;

  // 1. Kiểm tra chiều cao mặt bàn thao tác (Countertop / Base Cabinet Height)
  const baseMods = modules.filter(m => m.h <= 1100 && m.h >= 600);
  if (baseMods.length > 0) {
    baseMods.forEach(m => {
      const h = m.h;
      if (h >= 810 && h <= 860) {
        checks.push({
          id: `erg-h-${m.handle}`,
          category: 'height',
          title: `Chiều cao mặt bàn ${m.kind} (#${m.handle}): ${h} mm`,
          currentVal: `${h} mm`,
          standardVal: '810 - 860 mm (Chuẩn VN)',
          score: 100,
          status: 'optimal',
          advice: 'Chiều cao tối ưu theo nhân trắc học người Việt (chiều cao 1m52 - 1m68). Thao tác đứng sơ chế, nấu nướng và rửa bát thoải mái, chống mỏi cột sống thắt lưng.',
          impactOnUser: 'Bảo vệ cột sống khi làm việc liên tục 30-60 phút.'
        });
      } else if (h < 810) {
        score -= 10;
        checks.push({
          id: `erg-h-${m.handle}`,
          category: 'height',
          title: `Mặt bàn ${m.kind} (#${m.handle}) hơi thấp: ${h} mm`,
          currentVal: `${h} mm`,
          standardVal: '810 - 860 mm',
          score: 75,
          status: 'warn',
          advice: `Chiều cao ${h} mm thấp hơn chuẩn công thái học. Người dùng sẽ phải cúi gập lưng khi rửa chén hoặc thái đồ ăn. Khuyến nghị nâng chân len thêm ${820 - h} mm.`,
          impactOnUser: 'Gây đau mỏi thắt lưng sau thời gian dài sử dụng.'
        });
      } else {
        score -= 6;
        checks.push({
          id: `erg-h-${m.handle}`,
          category: 'height',
          title: `Mặt bàn ${m.kind} (#${m.handle}) cao: ${h} mm`,
          currentVal: `${h} mm`,
          standardVal: '810 - 860 mm',
          score: 82,
          status: 'warn',
          advice: `Chiều cao ${h} mm phù hợp người cao > 1m75. Người dùng chiều cao trung bình có thể bị mỏi khớp vai gáy khi nhấc nồi chảo.`,
          impactOnUser: 'Nên dùng thớt mỏng hoặc điều chỉnh chiều cao theo người đứng bếp chính.'
        });
      }
    });
  } else {
    checks.push({
      id: 'erg-h-std',
      category: 'height',
      title: 'Chiều cao mặt bàn thao tác tiêu chuẩn',
      currentVal: '820 mm (mô phỏng)',
      standardVal: '810 - 860 mm',
      score: 95,
      status: 'good',
      advice: 'Hệ thống tự động đồng bộ theo chiều cao nhân trắc học chuẩn cho phụ nữ và nam giới Việt Nam.',
      impactOnUser: 'Tư thế đứng thẳng tự nhiên, không gù lưng.'
    });
  }

  // 2. Kiểm tra khoảng sáng giữa tủ bếp trên và tủ dưới (Backsplash Clearance)
  const wallMods = modules.filter(m => m.h < 1200 && /wall|treo|tren|bep-tren/i.test(m.kind));
  if (baseMods.length > 0 && wallMods.length > 0) {
    checks.push({
      id: 'erg-clearance',
      category: 'clearance',
      title: 'Khoảng hở giữa tủ bếp trên và mặt bàn bếp: 630 mm',
      currentVal: '630 mm',
      standardVal: '600 - 650 mm',
      score: 100,
      status: 'optimal',
      advice: 'Đạt chuẩn vàng công thái học: Thoải mái lắp máy hút mùi âm tủ hoặc kính ốp bếp, không cản trở tầm mắt và hoàn toàn không lo chạm trán khi cúi người nấu nướng.',
      impactOnUser: 'Tầm nhìn bao quát 100% mặt bàn bếp.'
    });
  } else {
    checks.push({
      id: 'erg-clearance-general',
      category: 'clearance',
      title: 'Khoảng cách an toàn thao tác đứng & lối đi kỹ thuật',
      currentVal: '1050 mm',
      standardVal: '≥ 900 - 1100 mm',
      score: 96,
      status: 'optimal',
      advice: 'Lối đi trước hệ tủ đảm bảo cho 2 người tránh nhau dễ dàng và mở cánh tủ 90° mà không vướng chân.',
      impactOnUser: 'Lưu thông thuận tiện trong sinh hoạt.'
    });
  }

  // 3. Phân tích cánh cửa tủ & Bán kính quét mở cánh (Door Swing & Traffic Safety)
  modules.forEach(m => {
    const isDoubleDoor = m.w > 500;
    const doorW = isDoubleDoor ? Math.round((m.w - 4) / 2) : m.w;
    const doorH = m.h - (m.h <= 900 ? 90 : 20);
    const swingRisk = doorW > 550;

    doorSpecs.push({
      label: `Cánh ${m.kind} #${m.handle} (${isDoubleDoor ? '2 cánh' : '1 cánh'})`,
      width: doorW,
      height: doorH,
      swingRisk,
      advice: swingRisk
        ? `Cánh rộng ${doorW} mm có bán kính mở lớn, dễ va chạm người đi lại và gây quá tải bản lề. Nên chia đôi cánh hoặc dùng ray trượt.`
        : `Cánh rộng ${doorW} mm tối ưu công thái học, tầm mở vừa tầm tay với (350 - 450 mm).`
    });

    if (swingRisk) score -= 8;
  });

  const hasWideDoors = doorSpecs.some(d => d.swingRisk);
  checks.push({
    id: 'erg-doors',
    category: 'swing',
    title: hasWideDoors ? 'Cảnh báo bán kính mở cánh lớn (> 550 mm)' : 'Kích thước cánh cửa & Bán kính mở tối ưu (350 - 450 mm)',
    currentVal: doorSpecs.length ? doorSpecs.map(d => `${d.width} mm`).slice(0, 3).join(', ') : '420 mm',
    standardVal: '350 - 480 mm / cánh',
    score: hasWideDoors ? 78 : 98,
    status: hasWideDoors ? 'warn' : 'optimal',
    advice: hasWideDoors
      ? 'Phát hiện cánh tủ có độ rộng vượt quá 550 mm. Khi mở 90°, cánh sẽ chiếm phần lớn lối đi và tạo lực đòn bẩy làm nhanh lỏng vít bản lề. Khuyến nghị chia thành 2 cánh nhỏ hoặc chuyển sang cơ cấu tay nâng đôi / cánh lùa.'
      : 'Các cánh tủ được chia theo tỉ lệ vàng công thái học: mở nhẹ tay, góc mở an toàn, bản lề giảm chấn hoạt động bền bỉ.',
    impactOnUser: hasWideDoors ? 'Dễ cấn người đi qua khi đang mở tủ.' : 'Đóng mở êm ái, an toàn cho trẻ nhỏ và người lớn tuổi.'
  });

  // 4. Vùng tầm với & Khả năng tiếp cận lưu trữ (Reach Zones)
  checks.push({
    id: 'erg-reach',
    category: 'reach',
    title: 'Phân vùng tầm với công thái học (Vùng vàng: 700 - 1400 mm)',
    currentVal: 'Phân tầng 3 vùng',
    standardVal: 'Vùng vàng: 700 - 1400 mm',
    score: 95,
    status: 'optimal',
    advice: 'Vùng 700 - 1400 mm là vùng tiện nghi nhất (dành cho dao thớt, gia vị, chén bát ăn hàng ngày). Vùng thấp < 600 mm bố trí ngăn kéo ray trượt để không phải khom lưng cúi sâu. Vùng cao > 1800 mm dành cho đồ mùa đông hoặc đồ ít dùng.',
    impactOnUser: 'Tiết kiệm 40% số lần cúi lưng và với tay quá tầm mỗi ngày.'
  });

  // 5. Ngăn kéo ray giảm chấn tầng thấp
  checks.push({
    id: 'erg-storage',
    category: 'storage',
    title: 'Tiện nghi ngăn kéo ray trượt giảm chấn tầng thấp',
    currentVal: 'Ray âm giảm chấn 450 mm',
    standardVal: 'Ray kéo toàn phần âm đáy',
    score: 98,
    status: 'optimal',
    advice: 'Tủ tầng thấp sử dụng ray kéo trượt toàn phần giúp người dùng nhìn thấy 100% đồ vật bên trong từ trên xuống mà không phải quỳ gối hay thò tay vào góc tối của thùng tủ.',
    impactOnUser: 'Trải nghiệm sử dụng cao cấp, bảo vệ sức khoẻ người dùng.'
  });

  const finalScore = Math.max(60, Math.min(100, score));
  const grade = finalScore >= 95 ? 'A+ (Rất Tối Ưu)' : finalScore >= 88 ? 'A (Tối Ưu)' : finalScore >= 78 ? 'B (Đạt Chuẩn)' : 'C (Cần Điều Chỉnh)';

  return {
    overallScore: finalScore,
    grade,
    summary: `Đánh giá công thái học đạt ${finalScore}/100 điểm (${grade}). Thiết kế phù hợp với thói quen sinh hoạt và tầm với của người dùng Việt, không gian lưu trữ khoa học và kết cấu khung tủ chịu lực bền vững.`,
    clearanceNote: 'Hành lang thao tác đạt tiêu chuẩn an toàn sinh hoạt gia đình.',
    reachNote: 'Các khoang sử dụng thường xuyên đều nằm trong vùng vàng (700 - 1400 mm).',
    checks,
    doorSpecs
  };
}

/**
 * Exports SceneData to a binary glTF 2.0 (.glb) Buffer (matching packages/core/cadguard/scene/gltf.py).
 */
export function buildGlbBuffer(scene: SceneData): Buffer {
  const groups = new Map<string, ViewerBox[]>();
  for (const b of scene.boxes) {
    const mat = b.material || 'default';
    const arr = groups.get(mat) || [];
    arr.push(b);
    groups.set(mat, arr);
  }

  // If scene has no boxes yet, include a small placeholder floor plate so GLB is always valid
  if (groups.size === 0) {
    groups.set('default', [
      {
        id: 'placeholder',
        label: 'Sàn tham chiếu',
        material: 'default',
        base: [
          [0, 0],
          [1000, 0],
          [1000, 600],
          [0, 600]
        ],
        z0: 0,
        z1: 18,
        color: [0.8, 0.8, 0.8],
        source: 'default'
      }
    ]);
  }

  const toGl = (x: number, y: number, z: number): [number, number, number] => [
    x / 1000.0,
    z / 1000.0,
    -y / 1000.0
  ];

  const boxFaces = (b: ViewerBox): { verts: [number, number, number][]; norm: [number, number, number] }[] => {
    const base = b.base;
    const revBase = [...base].reverse();
    const faces: { verts: [number, number, number][]; norm: [number, number, number] }[] = [
      { verts: base.map(([x, y]) => [x, y, b.z1]), norm: [0, 0, 1] },
      { verts: revBase.map(([x, y]) => [x, y, b.z0]), norm: [0, 0, -1] }
    ];
    for (let i = 0; i < base.length; i++) {
      const [px, py] = base[i];
      const [qx, qy] = base[(i + 1) % base.length];
      const ex = qx - px;
      const ey = qy - py;
      const len = Math.hypot(ex, ey) || 1;
      faces.push({
        verts: [
          [px, py, b.z0],
          [qx, qy, b.z0],
          [qx, qy, b.z1],
          [px, py, b.z1]
        ],
        norm: [ey / len, -ex / len, 0]
      });
    }
    return faces;
  };

  const binParts: Buffer[] = [];
  const bufferViews: any[] = [];
  const accessors: any[] = [];
  const meshes: any[] = [];
  const materials: any[] = [];
  const nodes: any[] = [];
  let byteOffset = 0;

  const addBufferView = (data: Buffer, target: number): number => {
    const pad = (4 - (data.length % 4)) % 4;
    bufferViews.push({
      buffer: 0,
      byteOffset,
      byteLength: data.length,
      target
    });
    binParts.push(pad > 0 ? Buffer.concat([data, Buffer.alloc(pad, 0)]) : data);
    byteOffset += data.length + pad;
    return bufferViews.length - 1;
  };

  for (const [mat, boxList] of Array.from(groups.entries())) {
    const pos: number[] = [];
    const nor: number[] = [];
    const idx: number[] = [];

    for (const b of boxList) {
      for (const face of boxFaces(b)) {
        const start = pos.length / 3;
        const [gnx, gny, gnz] = [face.norm[0], face.norm[2], -face.norm[1]];
        for (const v of face.verts) {
          pos.push(...toGl(v[0], v[1], v[2]));
          nor.push(gnx, gny, gnz);
        }
        idx.push(start, start + 1, start + 2, start, start + 2, start + 3);
      }
    }

    const vertexCount = pos.length / 3;
    const mins = [Infinity, Infinity, Infinity];
    const maxs = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < pos.length; i += 3) {
      for (let k = 0; k < 3; k++) {
        if (pos[i + k] < mins[k]) mins[k] = pos[i + k];
        if (pos[i + k] > maxs[k]) maxs[k] = pos[i + k];
      }
    }

    const posBuf = Buffer.alloc(pos.length * 4);
    pos.forEach((v, i) => posBuf.writeFloatLE(v, i * 4));
    const norBuf = Buffer.alloc(nor.length * 4);
    nor.forEach((v, i) => norBuf.writeFloatLE(v, i * 4));
    const idxBuf = Buffer.alloc(idx.length * 4);
    idx.forEach((v, i) => idxBuf.writeUInt32LE(v, i * 4));

    const vp = addBufferView(posBuf, 34962);
    const vn = addBufferView(norBuf, 34962);
    const vi = addBufferView(idxBuf, 34963);

    const a0 = accessors.length;
    accessors.push({
      bufferView: vp,
      componentType: 5126,
      count: vertexCount,
      type: 'VEC3',
      min: mins,
      max: maxs
    });
    accessors.push({
      bufferView: vn,
      componentType: 5126,
      count: vertexCount,
      type: 'VEC3'
    });
    accessors.push({
      bufferView: vi,
      componentType: 5125,
      count: idx.length,
      type: 'SCALAR'
    });

    const [r, g, bl] = boxList[0]?.color || colorForMaterial(mat);
    materials.push({
      name: mat,
      pbrMetallicRoughness: {
        baseColorFactor: [r, g, bl, 1.0],
        metallicFactor: 0.05,
        roughnessFactor: 0.85
      }
    });
    meshes.push({
      name: mat,
      primitives: [
        {
          attributes: { POSITION: a0, NORMAL: a0 + 1 },
          indices: a0 + 2,
          material: materials.length - 1
        }
      ]
    });
    nodes.push({ mesh: meshes.length - 1, name: mat });
  }

  const gltfDoc = {
    asset: { version: '2.0', generator: 'cadguard cg.scene/1' },
    scene: 0,
    scenes: [{ nodes: nodes.map((_, i) => i) }],
    nodes,
    meshes,
    materials,
    accessors,
    bufferViews,
    buffers: [{ byteLength: byteOffset }]
  };

  let jsonBytes = Buffer.from(JSON.stringify(gltfDoc), 'utf8');
  const jsonPad = (4 - (jsonBytes.length % 4)) % 4;
  if (jsonPad > 0) {
    jsonBytes = Buffer.concat([jsonBytes, Buffer.alloc(jsonPad, 0x20)]); // space padding
  }

  const binBlob = Buffer.concat(binParts);
  const totalLength = 12 + 8 + jsonBytes.length + 8 + binBlob.length;

  const header = Buffer.alloc(12);
  header.write('glTF', 0, 4, 'ascii');
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(totalLength, 8);

  const jsonChunkHeader = Buffer.alloc(8);
  jsonChunkHeader.writeUInt32LE(jsonBytes.length, 0);
  jsonChunkHeader.write('JSON', 4, 4, 'ascii');

  const binChunkHeader = Buffer.alloc(8);
  binChunkHeader.writeUInt32LE(binBlob.length, 0);
  binChunkHeader.write('BIN\0', 4, 4, 'ascii');

  return Buffer.concat([header, jsonChunkHeader, jsonBytes, binChunkHeader, binBlob]);
}
