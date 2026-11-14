import crypto from 'node:crypto';

export interface DxfLayer {
  name: string;
  color: number;
  linetype: string;
  flags: number;
}

export interface DxfEntity {
  handle: string;
  type: string;
  layer: string;
  space: string; // 'Model' | layout name
  pts: [number, number][];
  zValues: number[];
  closed?: boolean;
  text?: string;
  style?: string;
  height?: number;
  block?: string;
  insert?: [number, number];
  xscale?: number;
  yscale?: number;
  rotation?: number;
  radius?: number;
  startAngle?: number;
  endAngle?: number;
  color?: number; // 256 = ByLayer
  dimText?: string;
  dimMeasurement?: number;
  attribs?: Record<string, string>;
}

export interface ParsedDxfModel {
  fileName: string;
  relativePath: string;
  fileHash: string;
  sizeBytes: number;
  dxfVersion: string;
  insunits: number; // 4 = mm, 6 = m, 0 = unitless
  layers: Record<string, DxfLayer>;
  textStyles: string[];
  dimStyles: string[];
  blocks: string[];
  entities: DxfEntity[];
  layouts: string[];
  department: 'design' | 'tech' | 'viz' | 'cnc';
  bbox: { minX: number; minY: number; maxX: number; maxY: number };
}

export interface RenderedSheet {
  id: number;
  code: string;
  title: string;
  scale: string;
  type: 'layout' | 'draft';
  svgBody: string;
  entityCount: number;
  ents?: DxfEntity[];
  bbox?: { minX: number; minY: number; maxX: number; maxY: number };
}

export interface EvaluatedFinding {
  id: number;
  sheet: number;
  tier: 'code' | 'ai';
  rule: string;
  sev: 'error' | 'warn';
  title: string;
  d: string;
  count: number;
  targetLayers: string[];
  targetHandles: string[];
  fix: 'a' | 'b' | null;
  fixTxt?: string;
  need?: string;
  where: string;
  st: 'open' | 'fixed';
  m: { box: [number, number, number, number]; dot: [number, number] };
}

const ACI_COLORS: Record<number, string> = {
  1: '#D93829', // Red
  2: '#C89D14', // Yellow/Amber
  3: '#2E8540', // Green
  4: '#0E7490', // Cyan
  5: '#2563EB', // Blue
  6: '#9333EA', // Magenta
  7: 'var(--cv-line)', // White/Black
  8: '#6B726D', // Gray
  9: '#8A918C'
};

export function classifyDepartment(relativePath: string, fileName: string, layers: string[], entities: DxfEntity[]): 'design' | 'tech' | 'viz' | 'cnc' {
  const lowerPath = (relativePath + '/' + fileName).toLowerCase();
  const layerStr = layers.join(' ').toUpperCase();

  if (
    /cnc|nest|cut|cam|lap-trinh|tam-|panel|mozaik|woodwop/.test(lowerPath) ||
    layerStr.includes('FN-CNC') ||
    layerStr.includes('ABF_') ||
    layerStr.includes('CUT')
  ) {
    return 'cnc';
  }
  if (
    /3d|viz|render|studio|scene|phoi-canh|goc-may/.test(lowerPath) ||
    layerStr.includes('FN-ROOM-WALL') ||
    entities.some(e => e.type === 'INSERT' && (e.block || '').toUpperCase().startsWith('FN_MOD'))
  ) {
    return 'viz';
  }
  if (
    /thiet-ke|design|concept|mat-bang|sanh|hygiene|layout-mb/.test(lowerPath) ||
    layers.some(l => l.includes('$0$') || l.includes('|'))
  ) {
    return 'design';
  }
  return 'tech';
}

export function parseDxfContent(content: string, fileName: string, relativePath = fileName): ParsedDxfModel {
  const fileHash = crypto.createHash('sha256').update(content, 'utf8').digest('hex').slice(0, 16);
  const sizeBytes = Buffer.byteLength(content, 'utf8');
  // Parse (code, val) pairs efficiently without allocating millions of intermediate line strings
  const pairs: [number, string][] = [];
  const len = content.length;
  let lineStart = 0;
  let pendingCode: number | null = null;

  while (lineStart < len) {
    let lineEnd = content.indexOf('\n', lineStart);
    if (lineEnd === -1) lineEnd = len;

    let endPos = lineEnd;
    if (endPos > lineStart && content.charCodeAt(endPos - 1) === 13) {
      endPos--;
    }

    const line = content.substring(lineStart, endPos).trim();
    lineStart = lineEnd + 1;

    if (!line && pendingCode === null) continue;

    if (pendingCode === null) {
      const codeNum = parseInt(line, 10);
      if (!Number.isNaN(codeNum)) {
        pendingCode = codeNum;
      }
    } else {
      pairs.push([pendingCode, line]);
      pendingCode = null;
    }
  }

  let section = '';
  let dxfVersion = 'AC1032 (R2018)';
  let insunits = 4; // Default mm if not specified, or parsed from $INSUNITS
  const layers: Record<string, DxfLayer> = {
    '0': { name: '0', color: 7, linetype: 'CONTINUOUS', flags: 0 }
  };
  const textStyles = new Set<string>(['Standard']);
  const dimStyles = new Set<string>(['ISO-25']);
  const blocks = new Set<string>();
  const layouts = new Set<string>(['Model']);
  const entities: DxfEntity[] = [];

  let i = 0;
  let handleSeq = 100;

  while (i < pairs.length) {
    const [code, val] = pairs[i];
    if (code === 0 && val === 'SECTION') {
      if (i + 1 < pairs.length && pairs[i + 1][0] === 2) {
        section = pairs[i + 1][1].toUpperCase();
        i += 2;
        continue;
      }
    } else if (code === 0 && val === 'ENDSEC') {
      section = '';
      i++;
      continue;
    }

    if (section === 'HEADER') {
      if (code === 9 && val === '$ACADVER' && i + 1 < pairs.length) {
        dxfVersion = pairs[i + 1][1];
      } else if (code === 9 && val === '$INSUNITS' && i + 1 < pairs.length) {
        const u = parseInt(pairs[i + 1][1], 10);
        if (!Number.isNaN(u)) insunits = u;
      }
      i++;
      continue;
    }

    if (section === 'TABLES') {
      if (code === 0 && val === 'LAYER') {
        let name = '0';
        let color = 7;
        let linetype = 'CONTINUOUS';
        let flags = 0;
        i++;
        while (i < pairs.length && pairs[i][0] !== 0) {
          const [c, v] = pairs[i];
          if (c === 2) name = v;
          else if (c === 62) color = Math.abs(parseInt(v, 10) || 7);
          else if (c === 6) linetype = v;
          else if (c === 70) flags = parseInt(v, 10) || 0;
          i++;
        }
        layers[name] = { name, color, linetype, flags };
        continue;
      } else if (code === 0 && val === 'STYLE') {
        i++;
        while (i < pairs.length && pairs[i][0] !== 0) {
          if (pairs[i][0] === 2 && pairs[i][1]) textStyles.add(pairs[i][1]);
          i++;
        }
        continue;
      } else if (code === 0 && val === 'DIMSTYLE') {
        i++;
        while (i < pairs.length && pairs[i][0] !== 0) {
          if (pairs[i][0] === 2 && pairs[i][1]) dimStyles.add(pairs[i][1]);
          i++;
        }
        continue;
      }
      i++;
      continue;
    }

    if (section === 'BLOCKS') {
      if (code === 0 && val === 'BLOCK') {
        i++;
        while (i < pairs.length && pairs[i][0] !== 0) {
          if (pairs[i][0] === 2 && pairs[i][1]) blocks.add(pairs[i][1]);
          i++;
        }
        continue;
      }
      i++;
      continue;
    }

    if (section === 'ENTITIES') {
      if (code === 0) {
        const entType = val.toUpperCase();
        if (
          ['LINE', 'LWPOLYLINE', 'POLYLINE', 'CIRCLE', 'ARC', 'TEXT', 'MTEXT', 'DIMENSION', 'INSERT'].includes(
            entType
          )
        ) {
          const ent: DxfEntity = {
            handle: `H${handleSeq++}`,
            type: entType,
            layer: '0',
            space: 'Model',
            pts: [],
            zValues: [],
            color: 256,
            attribs: {}
          };
          let x1: number | null = null;
          let y1: number | null = null;
          let x2: number | null = null;
          let y2: number | null = null;
          let pendingX: number | null = null;

          i++;
          while (i < pairs.length && pairs[i][0] !== 0) {
            const [c, v] = pairs[i];
            if (c === 5) ent.handle = v;
            else if (c === 8) ent.layer = v || '0';
            else if (c === 67 && parseInt(v, 10) === 1) ent.space = 'Layout1';
            else if (c === 410 && v) {
              ent.space = v;
              layouts.add(v);
            } else if (c === 62) ent.color = parseInt(v, 10) || 256;
            else if (c === 10) {
              const num = parseFloat(v) || 0;
              if (entType === 'LWPOLYLINE') {
                pendingX = num;
              } else {
                x1 = num;
              }
            } else if (c === 20) {
              const num = parseFloat(v) || 0;
              if (entType === 'LWPOLYLINE' && pendingX !== null) {
                ent.pts.push([pendingX, num]);
                pendingX = null;
              } else {
                y1 = num;
              }
            } else if (c === 11) {
              x2 = parseFloat(v) || 0;
            } else if (c === 21) {
              y2 = parseFloat(v) || 0;
            } else if (c === 30 || c === 31 || c === 38) {
              const z = parseFloat(v) || 0;
              ent.zValues.push(z);
            } else if (c === 70) {
              const flag = parseInt(v, 10) || 0;
              if (entType === 'LWPOLYLINE' || entType === 'POLYLINE') {
                ent.closed = (flag & 1) === 1;
              }
            } else if (c === 40) {
              const num = parseFloat(v) || 0;
              if (entType === 'CIRCLE' || entType === 'ARC') ent.radius = num;
              else if (entType === 'TEXT' || entType === 'MTEXT') ent.height = num;
            } else if (c === 41) {
              ent.xscale = parseFloat(v) || 1;
            } else if (c === 42) {
              if (entType === 'DIMENSION') ent.dimMeasurement = parseFloat(v) || 0;
              else ent.yscale = parseFloat(v) || 1;
            } else if (c === 50) {
              if (entType === 'ARC') ent.startAngle = parseFloat(v) || 0;
              else ent.rotation = parseFloat(v) || 0;
            } else if (c === 51) {
              ent.endAngle = parseFloat(v) || 0;
            } else if (c === 1) {
              if (entType === 'DIMENSION') ent.dimText = v;
              else ent.text = (ent.text ? ent.text + ' ' : '') + v;
            } else if (c === 3 && entType === 'MTEXT') {
              ent.text = (ent.text || '') + v;
            } else if (c === 7) {
              ent.style = v;
              textStyles.add(v);
            } else if (c === 2 && entType === 'INSERT') {
              ent.block = v;
              blocks.add(v);
            }
            i++;
          }

          if (entType === 'LINE' && x1 !== null && y1 !== null && x2 !== null && y2 !== null) {
            ent.pts = [
              [x1, y1],
              [x2, y2]
            ];
          } else if (entType !== 'LWPOLYLINE' && x1 !== null && y1 !== null) {
            ent.pts = [[x1, y1]];
            if (x2 !== null && y2 !== null) ent.pts.push([x2, y2]);
            if (entType === 'INSERT') ent.insert = [x1, y1];
          }

          // Parse ATTRIB entities immediately following an INSERT
          if (entType === 'INSERT') {
            while (i < pairs.length && pairs[i][0] === 0 && pairs[i][1].toUpperCase() === 'ATTRIB') {
              i++;
              let tag = '';
              let valStr = '';
              while (i < pairs.length && pairs[i][0] !== 0) {
                if (pairs[i][0] === 2) tag = pairs[i][1].toUpperCase();
                else if (pairs[i][0] === 1) valStr = pairs[i][1];
                i++;
              }
              if (tag && ent.attribs) ent.attribs[tag] = valStr;
            }
            if (i < pairs.length && pairs[i][0] === 0 && pairs[i][1].toUpperCase() === 'SEQEND') {
              i++;
              while (i < pairs.length && pairs[i][0] !== 0) i++;
            }
          }

          if (!layers[ent.layer]) {
            layers[ent.layer] = { name: ent.layer, color: 7, linetype: 'CONTINUOUS', flags: 0 };
          }
          entities.push(ent);
          continue;
        }
      }
      i++;
      continue;
    }

    i++;
  }

  // Compute overall bounding box
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const e of entities) {
    for (const [px, py] of e.pts) {
      const r = e.radius || 0;
      if (px - r < minX) minX = px - r;
      if (py - r < minY) minY = py - r;
      if (px + r > maxX) maxX = px + r;
      if (py + r > maxY) maxY = py + r;
    }
    if (e.type === 'INSERT' && e.insert) {
      const w = parseFloat(e.attribs?.W || '600') || 600;
      const d = parseFloat(e.attribs?.D || '600') || 600;
      if (e.insert[0] + w > maxX) maxX = e.insert[0] + w;
      if (e.insert[1] + d > maxY) maxY = e.insert[1] + d;
    }
  }

  if (!Number.isFinite(minX)) {
    minX = 0;
    minY = 0;
    maxX = 800;
    maxY = 500;
  }

  const department = classifyDepartment(relativePath, fileName, Object.keys(layers), entities);

  return {
    fileName,
    relativePath,
    fileHash,
    sizeBytes,
    dxfVersion,
    insunits,
    layers,
    textStyles: Array.from(textStyles),
    dimStyles: Array.from(dimStyles),
    blocks: Array.from(blocks),
    entities,
    layouts: Array.from(layouts),
    department,
    bbox: { minX, minY, maxX, maxY }
  };
}

function escapeXml(str: string): string {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function computeEntityBbox(
  ents: DxfEntity[],
  lowPct = 0.02,
  highPct = 0.98
): { minX: number; minY: number; maxX: number; maxY: number } {
  const xs: number[] = [];
  const ys: number[] = [];

  for (const e of ents) {
    // Ưu tiên toạ độ hình học thực tế (LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, INSERT)
    for (const [px, py] of e.pts) {
      if (Number.isFinite(px) && Number.isFinite(py)) {
        xs.push(px);
        ys.push(py);
      }
    }
    if (e.type === 'INSERT' && e.insert) {
      if (Number.isFinite(e.insert[0]) && Number.isFinite(e.insert[1])) {
        xs.push(e.insert[0]);
        ys.push(e.insert[1]);
      }
    }
  }

  if (xs.length === 0 || ys.length === 0) {
    return { minX: 0, minY: 0, maxX: 800, maxY: 500 };
  }

  xs.sort((a, b) => a - b);
  ys.sort((a, b) => a - b);

  // Loại bỏ các điểm ngoại lai (Percentile Bounding Box 2% -> 98%) khi có nhiều điểm
  const usePercentile = xs.length >= 20;
  const xLowIdx = usePercentile ? Math.floor(xs.length * lowPct) : 0;
  const xHighIdx = usePercentile ? Math.min(xs.length - 1, Math.ceil(xs.length * highPct) - 1) : xs.length - 1;
  const yLowIdx = usePercentile ? Math.floor(ys.length * lowPct) : 0;
  const yHighIdx = usePercentile ? Math.min(ys.length - 1, Math.ceil(ys.length * highPct) - 1) : ys.length - 1;

  let minX = xs[xLowIdx];
  let maxX = xs[xHighIdx];
  let minY = ys[yLowIdx];
  let maxY = ys[yHighIdx];

  if (maxX - minX < 1) {
    minX = xs[0];
    maxX = xs[xs.length - 1];
  }
  if (maxY - minY < 1) {
    minY = ys[0];
    maxY = ys[ys.length - 1];
  }

  return { minX, minY, maxX, maxY };
}

export function renderDxfToSheetsAndFindings(model: ParsedDxfModel): {
  sheets: RenderedSheet[];
  findings: EvaluatedFinding[];
  ops: { a: { what: string; from: string; to: string }; b: { what: string; from: string; to: string } };
} {
  const modelEntities = model.entities.filter(e => e.space === 'Model' || !e.space);
  const validModelEnts = modelEntities.filter(e => e.pts.length > 0 || (e.type === 'INSERT' && e.insert));
  const primaryEnts = validModelEnts.length > 0 ? validModelEnts : model.entities;

  // Tính Percentile Bounding Box (2% -> 98%) cho toàn bộ các nét vẽ hình học thực tế
  const percentileBbox = computeEntityBbox(primaryEnts, 0.02, 0.98);

  const sheetGroups: {
    code: string;
    title: string;
    scale: string;
    type: 'layout' | 'draft';
    ents: DxfEntity[];
    customBbox: { minX: number; minY: number; maxX: number; maxY: number };
  }[] = [
    {
      code: 'MAIN',
      title: model.fileName,
      scale: model.department === 'cnc' ? '1:5' : '1:20',
      type: 'layout',
      ents: primaryEnts,
      customBbox: percentileBbox
    }
  ];

  const renderedSheets: RenderedSheet[] = [];
  // Lưu toạ độ SVG [x, y, w, h] cho từng handle đối tượng để tự động Pan/Zoom tới đúng vùng lỗi thật
  const entitySvgBoxes = new Map<string, [number, number, number, number]>();

  sheetGroups.forEach((sg, idx) => {
    const bbox = sg.customBbox || computeEntityBbox(sg.ents, 0.02, 0.98);
    const minX = bbox.minX;
    const minY = bbox.minY;
    const maxX = bbox.maxX;
    const maxY = bbox.maxY;

    const w = Math.max(10, maxX - minX);
    const h = Math.max(10, maxY - minY);
    // Lề nhỏ (6% mỗi bên -> bản vẽ lấp đầy ~88% diện tích khung nhìn trung tâm)
    const padX = 28;
    const padY = 24;
    const availW = 820 - padX * 2;
    const availH = 540 - padY * 2;
    const scale = Math.min(availW / w, availH / h);
    const offsetX = padX + (availW - w * scale) / 2;
    const offsetY = padY + (availH - h * scale) / 2;

    const tx = (x: number) => +(offsetX + (x - minX) * scale).toFixed(1);
    const ty = (y: number) => +(540 - (offsetY + (y - minY) * scale)).toFixed(1);

    // Lọc bỏ các đối tượng rác nằm quá xa vùng Percentile Bounding Box để không kéo lệch khung nhìn
    const marginX = w * 0.35;
    const marginY = h * 0.35;
    const inBoundsEnts = sg.ents.filter(e => {
      const pt = e.pts[0] || e.insert;
      if (!pt) return false;
      return (
        pt[0] >= minX - marginX &&
        pt[0] <= maxX + marginX &&
        pt[1] >= minY - marginY &&
        pt[1] <= maxY + marginY
      );
    });
    const renderList = inBoundsEnts.length > 0 ? inBoundsEnts : sg.ents;

    const sortedEnts = [...renderList]
      .sort((a, b) => {
        const p = (t: string) =>
          t === 'LWPOLYLINE' || t === 'POLYLINE' ? 1 : t === 'LINE' ? 2 : t === 'INSERT' ? 3 : t === 'CIRCLE' || t === 'ARC' ? 4 : 5;
        return p(a.type) - p(b.type);
      })
      .slice(0, 6500);

    const svgParts: string[] = [];

    for (const e of sortedEnts) {
      const layerObj = model.layers[e.layer];
      const aci = e.color && e.color !== 256 ? e.color : layerObj?.color || 7;
      const strokeColor = e.layer === '0' ? 'var(--cv-l0)' : ACI_COLORS[aci] || 'var(--cv-line)';
      const isDimLayer = /DIM/i.test(e.layer) || e.type === 'DIMENSION';
      const dataAttrs = `class="dxf-ent" data-layer="${escapeXml(e.layer)}" data-handle="${escapeXml(e.handle)}"`;

      if (e.type === 'LINE' && e.pts.length >= 2) {
        const x1 = tx(e.pts[0][0]);
        const y1 = ty(e.pts[0][1]);
        const x2 = tx(e.pts[1][0]);
        const y2 = ty(e.pts[1][1]);
        svgParts.push(
          `<line ${dataAttrs} x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${strokeColor}" stroke-width="${e.layer === 'FN-ROOM-WALL' ? 2.0 : 1.15}" fill="none"/>`
        );
        entitySvgBoxes.set(e.handle, [
          Math.min(x1, x2),
          Math.min(y1, y2),
          Math.max(4, Math.abs(x2 - x1)),
          Math.max(4, Math.abs(y2 - y1))
        ]);
      } else if ((e.type === 'LWPOLYLINE' || e.type === 'POLYLINE') && e.pts.length >= 2) {
        const mapped = e.pts.map(([px, py]) => [tx(px), ty(py)] as [number, number]);
        const dPath =
          mapped.map(([px, py], i) => `${i === 0 ? 'M' : 'L'}${px},${py}`).join(' ') + (e.closed ? ' Z' : '');
        const xs = mapped.map(p => p[0]);
        const ys = mapped.map(p => p[1]);
        const bx = Math.min(...xs);
        const by = Math.min(...ys);
        const bw = Math.max(4, Math.max(...xs) - bx);
        const bh = Math.max(4, Math.max(...ys) - by);
        entitySvgBoxes.set(e.handle, [bx, by, bw, bh]);
        svgParts.push(
          `<path ${dataAttrs} d="${dPath}" stroke="${strokeColor}" stroke-width="${e.closed ? 1.25 : 1.1}" fill="${e.closed ? 'var(--cv-fill)' : 'none'}" fill-opacity="0.22"/>`
        );
      } else if (e.type === 'CIRCLE' && e.pts.length >= 1) {
        const cx = tx(e.pts[0][0]);
        const cy = ty(e.pts[0][1]);
        const r = Math.max(1.5, +((e.radius || 10) * scale).toFixed(1));
        entitySvgBoxes.set(e.handle, [cx - r, cy - r, r * 2, r * 2]);
        svgParts.push(
          `<circle ${dataAttrs} cx="${cx}" cy="${cy}" r="${r}" stroke="${strokeColor}" stroke-width="1.1" fill="none"/>`
        );
      } else if (e.type === 'ARC' && e.pts.length >= 1) {
        const cx = tx(e.pts[0][0]);
        const cy = ty(e.pts[0][1]);
        const r = Math.max(2, +((e.radius || 20) * scale).toFixed(1));
        const a0 = ((e.startAngle || 0) * Math.PI) / 180;
        const a1 = ((e.endAngle || 90) * Math.PI) / 180;
        const sx = +(cx + r * Math.cos(a0)).toFixed(1);
        const sy = +(cy - r * Math.sin(a0)).toFixed(1);
        const ex = +(cx + r * Math.cos(a1)).toFixed(1);
        const ey = +(cy - r * Math.sin(a1)).toFixed(1);
        entitySvgBoxes.set(e.handle, [cx - r, cy - r, r * 2, r * 2]);
        svgParts.push(
          `<path ${dataAttrs} d="M${sx},${sy} A${r},${r} 0 0 0 ${ex},${ey}" stroke="${strokeColor}" stroke-width="1.1" fill="none"/>`
        );
      } else if ((e.type === 'TEXT' || e.type === 'MTEXT') && e.pts.length >= 1) {
        const x = tx(e.pts[0][0]);
        const y = ty(e.pts[0][1]);
        const cleanTxt = (e.text || '').replace(/\\P/g, ' ').replace(/\{|\}/g, '').trim().slice(0, 60);
        if (cleanTxt) {
          const naturalH = e.height || 120;
          const fontH = +(naturalH * scale).toFixed(1);
          const clampedFs = Math.max(2.6, Math.min(10.5, fontH > 0 ? fontH : 7.5));
          if (clampedFs >= 2.8 || sg.ents.length < 600) {
            entitySvgBoxes.set(e.handle, [x, y - clampedFs, Math.max(18, cleanTxt.length * clampedFs * 0.55), clampedFs + 2]);
            svgParts.push(
              `<text ${dataAttrs} x="${x}" y="${y}" font-size="${clampedFs}" fill="${strokeColor}" opacity="0.82">${escapeXml(cleanTxt)}</text>`
            );
          }
        }
      } else if (e.type === 'DIMENSION' && e.pts.length >= 1) {
        const x1 = tx(e.pts[0][0]);
        const y1 = ty(e.pts[0][1]);
        const x2 = e.pts[1] ? tx(e.pts[1][0]) : x1 + 40;
        const y2 = e.pts[1] ? ty(e.pts[1][1]) : y1;
        const mx = +((x1 + x2) / 2).toFixed(1);
        const my = +((y1 + y2) / 2 - 3).toFixed(1);
        const label =
          e.dimText && e.dimText !== '<>'
            ? e.dimText
            : e.dimMeasurement
              ? String(Math.round(e.dimMeasurement))
              : 'DIM';
        entitySvgBoxes.set(e.handle, [
          Math.min(x1, x2),
          Math.min(y1, y2) - 10,
          Math.max(24, Math.abs(x2 - x1)),
          18
        ]);
        svgParts.push(
          `<g ${dataAttrs}><line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${isDimLayer ? 'var(--cv-dim)' : strokeColor}" stroke-width="0.9" stroke-dasharray="3 2"/><text x="${mx}" y="${my}" text-anchor="middle" font-size="7.5" fill="var(--cv-dim)">${escapeXml(label)}</text></g>`
        );
      } else if (e.type === 'INSERT' && e.insert) {
        const x = tx(e.insert[0]);
        const y = ty(e.insert[1]);
        const rawW = parseFloat(e.attribs?.W || '400') || 400;
        const rawD = parseFloat(e.attribs?.D || '300') || 300;
        const modW = Math.max(2, rawW * scale);
        const modD = Math.max(2, rawD * scale);
        const by = y - modD;
        entitySvgBoxes.set(e.handle, [x, by, Math.max(8, modW), Math.max(8, modD)]);
        svgParts.push(
          `<rect ${dataAttrs} x="${x}" y="${by}" width="${Math.max(2, modW).toFixed(1)}" height="${Math.max(2, modD).toFixed(1)}" stroke="${strokeColor}" stroke-width="1.0" fill="none"/>`
        );
      }
    }

    renderedSheets.push({
      id: idx,
      code: sg.code,
      title: sg.title,
      scale: sg.scale,
      type: sg.type,
      svgBody: svgParts.join('\n'),
      entityCount: sg.ents.length,
      ents: sg.ents,
      bbox: { minX, minY, maxX, maxY }
    });
  });

  // Tính hộp bao SVG (Percentile 5%–95%) của một tập các đối tượng vi phạm để Pan/Zoom chính xác vào vùng nét vẽ thật
  const computeGroupSvgBox = (ents: DxfEntity[]): { box: [number, number, number, number]; dot: [number, number] } => {
    const boxes: [number, number, number, number][] = [];
    for (const e of ents) {
      const b = entitySvgBoxes.get(e.handle);
      if (b) boxes.push(b);
    }
    if (boxes.length === 0) {
      return { box: [120, 90, 580, 360], dot: [410, 270] };
    }
    const x1s = boxes.map(b => b[0]).sort((a, b) => a - b);
    const y1s = boxes.map(b => b[1]).sort((a, b) => a - b);
    const x2s = boxes.map(b => b[0] + b[2]).sort((a, b) => a - b);
    const y2s = boxes.map(b => b[1] + b[3]).sort((a, b) => a - b);

    const low = boxes.length > 10 ? Math.floor(boxes.length * 0.05) : 0;
    const high = boxes.length > 10 ? Math.min(boxes.length - 1, Math.ceil(boxes.length * 0.95) - 1) : boxes.length - 1;

    const minBx = Math.max(10, Math.round(x1s[low]));
    const minBy = Math.max(10, Math.round(y1s[low]));
    const maxBx = Math.min(810, Math.round(x2s[high]));
    const maxBy = Math.min(530, Math.round(y2s[high]));
    const bw = Math.max(24, maxBx - minBx);
    const bh = Math.max(24, maxBy - minBy);
    return {
      box: [minBx, minBy, bw, bh],
      dot: [Math.round(minBx + bw / 2), Math.round(minBy + bh / 2)]
    };
  };

  const findings: EvaluatedFinding[] = [];
  let fid = 1;

  // 1. Kiểm tra đối tượng vẽ trực tiếp trên Layer "0" (LY-03 / VS-03)
  const layer0Ents = model.entities.filter(e => e.layer === '0' && e.type !== 'INSERT');
  if (layer0Ents.length > 0) {
    const ratio = ((layer0Ents.length / Math.max(1, model.entities.length)) * 100).toFixed(1);
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: model.department === 'design' ? 'VS-03' : 'LY-03',
      sev: 'error',
      title: `Có ${layer0Ents.length} đối tượng (${ratio}%) vẽ trực tiếp trên layer "0"`,
      d: `${layer0Ents.length} nét vẽ hình học nằm trực tiếp trên layer "0" thay vì layer chuyên trách.`,
      count: layer0Ents.length,
      targetLayers: ['0'],
      targetHandles: layer0Ents.slice(0, 600).map(e => e.handle),
      fix: 'a',
      fixTxt: `Chuyển ${layer0Ents.length} đối tượng trên layer "0" sang layer chuẩn`,
      where: `Layer "0" (${layer0Ents.length} đối tượng)`,
      st: 'open',
      m: computeGroupSvgBox(layer0Ents)
    });
  }

  // 2. Kiểm tra Layer dư từ Xref hoặc chưa chuẩn quy ước đặt tên (VS-01 / LY-01)
  const layerNames = Object.keys(model.layers).filter(l => l !== '0' && l !== 'DEFPOINTS');
  const xrefLayers = layerNames.filter(l => l.includes('$') || l.includes('|'));
  const nonFnLayers = layerNames.filter(l => !l.startsWith('FN-') && !l.startsWith('A3'));

  if (xrefLayers.length > 0) {
    const xrefEnts = model.entities.filter(e => xrefLayers.includes(e.layer));
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: 'VS-01',
      sev: 'warn',
      title: `${xrefLayers.length} layer dư từ Xref (${xrefEnts.length} đối tượng)`,
      d: `Các layer [${xrefLayers.slice(0, 4).join(', ')}] chứa ký tự "$" hoặc "|" sinh ra khi bind Xref.`,
      count: xrefEnts.length || xrefLayers.length,
      targetLayers: xrefLayers,
      targetHandles: xrefEnts.slice(0, 600).map(e => e.handle),
      fix: 'b',
      fixTxt: `Gộp ${xrefLayers.length} layer Xref dư về layer chuẩn`,
      where: `Layer: ${xrefLayers.slice(0, 2).join(', ')}`,
      st: 'open',
      m: computeGroupSvgBox(xrefEnts)
    });
  } else if (nonFnLayers.length > 0) {
    const nonFnEnts = model.entities.filter(e => nonFnLayers.includes(e.layer));
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: 'LY-01',
      sev: 'warn',
      title: `${nonFnLayers.length} layer chưa đặt tên theo quy ước FN-* (${nonFnEnts.length} đối tượng)`,
      d: `Các layer [${nonFnLayers.slice(0, 4).join(', ')}] chưa theo chuẩn FN-<NHÓM>-<LOẠI>.`,
      count: nonFnEnts.length || nonFnLayers.length,
      targetLayers: nonFnLayers.slice(0, 12),
      targetHandles: nonFnEnts.slice(0, 400).map(e => e.handle),
      fix: 'b',
      fixTxt: `Chuẩn hoá tên ${nonFnLayers.length} layer theo quy ước FN-*`,
      where: `Layer: ${nonFnLayers.slice(0, 2).join(', ')}`,
      st: 'open',
      m: computeGroupSvgBox(nonFnEnts)
    });
  }

  // 3. Kiểm tra đường bao LWPOLYLINE hở mạch (DH-03)
  const openPolys = model.entities.filter(
    e => (e.type === 'LWPOLYLINE' || e.type === 'POLYLINE') && !e.closed && !/WALL|DIM/i.test(e.layer)
  );
  if (openPolys.length > 0) {
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: 'DH-03',
      sev: 'error',
      title: `${openPolys.length} đường bao LWPOLYLINE chưa khép kín`,
      d: `${openPolys.length} đường bao chi tiết có thuộc tính closed=false, cần khép kín để gia công CNC.`,
      count: openPolys.length,
      targetLayers: [],
      targetHandles: openPolys.slice(0, 600).map(e => e.handle),
      fix: findings.some(f => f.fix === 'a') ? null : 'a',
      fixTxt: `Khép kín tự động ${openPolys.length} đường bao LWPOLYLINE`,
      need: 'Kiểm tra điểm đầu/cuối của đường bao trước khi xuất CNC.',
      where: `${openPolys.length} đường bao trên layer ${openPolys[0].layer}`,
      st: 'open',
      m: computeGroupSvgBox(openPolys)
    });
  }

  // 4. Kiểm tra cao độ Z != 0 hoặc đơn vị bản vẽ (DH-10 / DH-09)
  const nonZeroZ = model.entities.filter(e => e.zValues.some(z => Math.abs(z) > 0.001));
  if (nonZeroZ.length > 0) {
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: 'DH-10',
      sev: 'warn',
      title: `${nonZeroZ.length} đối tượng có cao độ Z ≠ 0 trong bản vẽ 2D`,
      d: `Đối tượng #${nonZeroZ[0].handle} có Z ≠ 0 mm, dễ gây lệch phép đo chiều dài trên mặt phẳng 2D.`,
      count: nonZeroZ.length,
      targetLayers: [],
      targetHandles: nonZeroZ.slice(0, 600).map(e => e.handle),
      fix: null,
      need: 'Xác nhận làm phẳng (Flatten Z=0) cho các đối tượng 2D.',
      where: `${nonZeroZ.length} đối tượng có Z ≠ 0`,
      st: 'open',
      m: computeGroupSvgBox(nonZeroZ)
    });
  } else if (model.insunits !== 4) {
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: 'DH-09',
      sev: 'error',
      title: `Đơn vị bản vẽ ($INSUNITS = ${model.insunits}) khác chuẩn milimét (4)`,
      d: 'Chuẩn sản xuất nội thất yêu cầu đơn vị bản vẽ là mm ($INSUNITS = 4).',
      count: 1,
      targetLayers: [],
      targetHandles: model.entities.slice(0, 50).map(e => e.handle),
      fix: null,
      need: 'Đặt lại biến hệ thống $INSUNITS = 4.',
      where: 'Biến HEADER $INSUNITS',
      st: 'open',
      m: computeGroupSvgBox(model.entities.slice(0, 50))
    });
  }

  // 5. Kiểm tra kích thước bị sửa chữ bằng tay (TX-08)
  const overriddenDims = model.entities.filter(e => e.type === 'DIMENSION' && e.dimText && e.dimText !== '<>');
  if (overriddenDims.length > 0) {
    findings.push({
      id: fid++,
      sheet: 0,
      tier: 'code',
      rule: 'TX-08',
      sev: 'error',
      title: `${overriddenDims.length} kích thước bị ghi đè số đo thủ công`,
      d: `Kích thước hiển thị "${overriddenDims[0].dimText}" thay vì giá trị đo hình học thực tế.`,
      count: overriddenDims.length,
      targetLayers: [],
      targetHandles: overriddenDims.map(e => e.handle),
      fix: null,
      need: 'Đối chiếu số đo thực tế và xoá Text Override.',
      where: `${overriddenDims.length} đối tượng DIMENSION`,
      st: 'open',
      m: computeGroupSvgBox(overriddenDims)
    });
  }

  const ops = {
    a: {
      what: layer0Ents.length
        ? `Chuyển ${layer0Ents.length} đối tượng khỏi layer "0"`
        : `Khép kín ${openPolys.length || 1} đường bao chi tiết`,
      from: layer0Ents.length ? `${layer0Ents.length} đối tượng · layer: "0"` : 'Đường bao hở mạch (closed = false)',
      to: `Layer chuẩn FN-${model.department.toUpperCase()}-MAIN`
    },
    b: {
      what: xrefLayers.length
        ? `Gộp ${xrefLayers.length} layer Xref dư (${xrefLayers.slice(0, 2).join(', ')})`
        : `Chuẩn hoá ${Math.max(1, nonFnLayers.length)} layer về quy ước FN-*`,
      from: xrefLayers.length ? xrefLayers.slice(0, 3).join(', ') : nonFnLayers.slice(0, 3).join(', ') || 'Layer tự do',
      to: 'Hệ layer chuẩn FN-* & kiểu chữ STD cao 2.5mm'
    }
  };

  return { sheets: renderedSheets, findings, ops };
}

export function generateSyntheticDxfContent(fileName: string): string {
  const lower = fileName.toLowerCase();
  const isHygieneBad = lower.includes('hygiene_bad') || lower.includes('sanh');
  const isCnc = lower.includes('geometry') || lower.includes('tam-') || lower.includes('cnc');
  const is3d = lower.includes('model_features') || lower.includes('ky-thuat');

  const lines: string[] = [
    '0', 'SECTION',
    '2', 'HEADER',
    '9', '$ACADVER',
    '1', 'AC1032',
    '9', '$INSUNITS',
    '70', '4',
    '0', 'ENDSEC',
    '0', 'SECTION',
    '2', 'TABLES',
    '0', 'TABLE',
    '2', 'LAYER',
    '0', 'LAYER', '2', '0', '62', '7', '6', 'CONTINUOUS', '70', '0',
    '0', 'LAYER', '2', 'FN-ROOM-WALL', '62', '8', '6', 'CONTINUOUS', '70', '0',
    '0', 'LAYER', '2', 'FN-VIEW-FRONT', '62', '3', '6', 'CONTINUOUS', '70', '0',
    '0', 'LAYER', '2', 'FN-VIEW-TOP', '62', '5', '6', 'CONTINUOUS', '70', '0',
    '0', 'LAYER', '2', 'FN-VIEW-SIDE', '62', '6', '6', 'CONTINUOUS', '70', '0',
    '0', 'LAYER', '2', 'FN-DIM-N', '62', '4', '6', 'CONTINUOUS', '70', '0',
    '0', 'LAYER', '2', 'FN-CNC-OUT', '62', '1', '6', 'CONTINUOUS', '70', '0'
  ];

  if (isHygieneBad) {
    lines.push('0', 'LAYER', '2', 'XREF_NEN$0$WALL', '62', '9', '6', 'CONTINUOUS', '70', '0');
  }

  lines.push(
    '0', 'ENDTAB',
    '0', 'ENDSEC',
    '0', 'SECTION',
    '2', 'ENTITIES'
  );

  // Room walls (for 3D scene & 2D plan)
  lines.push(
    '0', 'LWPOLYLINE',
    '5', 'W101',
    '8', 'FN-ROOM-WALL',
    '70', '0',
    '10', '0', '20', '0',
    '10', '0', '20', '2400',
    '10', '3200', '20', '2400',
    '10', '3200', '20', '0'
  );

  // Cabinet module 1 (complete W, D, H)
  lines.push(
    '0', 'INSERT',
    '5', 'M201',
    '8', 'FN-VIEW-TOP',
    '2', 'FN_MOD_BASE',
    '10', '200', '20', '1750',
    '0', 'ATTRIB', '2', 'KIND', '1', 'Tu bep duoi M1',
    '0', 'ATTRIB', '2', 'W', '1', '1200',
    '0', 'ATTRIB', '2', 'D', '1', '600',
    '0', 'ATTRIB', '2', 'H', '1', '810',
    '0', 'ATTRIB', '2', 'MAT', '1', 'MDF_OAK_18',
    '0', 'SEQEND'
  );

  // Cabinet module 2 (missing H so Studio 3D demonstrates missing height gap!)
  lines.push(
    '0', 'INSERT',
    '5', 'M202',
    '8', 'FN-VIEW-TOP',
    '2', 'FN_MOD_UPPER',
    '10', '1450', '20', '1750',
    '0', 'ATTRIB', '2', 'KIND', '1', 'Tu cao khoang tu lanh M2',
    '0', 'ATTRIB', '2', 'W', '1', '900',
    '0', 'ATTRIB', '2', 'D', '1', '600',
    '0', 'ATTRIB', '2', 'MAT', '1', 'MDF_WHITE_18',
    '0', 'SEQEND'
  );

  // Front view panels (2D multi-view projection for cabinet panels)
  // Left side panel
  lines.push(
    '0', 'LWPOLYLINE', '5', 'P301', '8', 'FN-VIEW-FRONT', '70', '1',
    '10', '200', '20', '200',
    '10', '218', '20', '200',
    '10', '218', '20', '920',
    '10', '200', '20', '920'
  );
  // Right side panel
  lines.push(
    '0', 'LWPOLYLINE', '5', 'P302', '8', 'FN-VIEW-FRONT', '70', '1',
    '10', '982', '20', '200',
    '10', '1000', '20', '200',
    '10', '1000', '20', '920',
    '10', '982', '20', '920'
  );
  // Top & Bottom horizontal panels
  lines.push(
    '0', 'LWPOLYLINE', '5', 'P303', '8', 'FN-VIEW-FRONT', '70', '1',
    '10', '218', '20', '902',
    '10', '982', '20', '902',
    '10', '982', '20', '920',
    '10', '218', '20', '920'
  );
  lines.push(
    '0', 'LWPOLYLINE', '5', 'P304', '8', 'FN-VIEW-FRONT', '70', '1',
    '10', '218', '20', '280',
    '10', '982', '20', '280',
    '10', '982', '20', '298',
    '10', '218', '20', '298'
  );
  // Middle shelf panel
  lines.push(
    '0', 'LWPOLYLINE', '5', 'P305', '8', 'isCnc ? "0" : "FN-VIEW-FRONT"'.replace('isCnc ? "0" : "FN-VIEW-FRONT"', isCnc ? '0' : 'FN-VIEW-FRONT'), '70', isCnc ? '0' : '1',
    '10', '218', '20', '580',
    '10', '982', '20', '580',
    '10', '982', '20', '598',
    '10', '218', '20', '598'
  );

  // Unassigned cluster C2 on layer 0 (to demonstrate cluster assignment in 3D Studio)
  lines.push(
    '0', 'LWPOLYLINE', '5', 'C401', '8', '0', '70', '1',
    '10', '2200', '20', '300',
    '10', '2800', '20', '300',
    '10', '2800', '20', '860',
    '10', '2200', '20', '860'
  );

  // Dimensions & Text annotations
  lines.push(
    '0', 'DIMENSION', '5', 'D501', '8', 'FN-DIM-N',
    '10', '200', '20', '140',
    '11', '1000', '21', '140',
    '42', '800',
    '1', isHygieneBad ? '805 (sua tay)' : '<>',
    '0', 'TEXT', '5', 'T601', '8', 'FN-DIM-N',
    '10', '200', '20', '90', '40', '28',
    '1', `BAN VE: ${fileName.toUpperCase()} - DAN CANH ABS 1MM`
  );

  if (is3d) {
    lines.push(
      '0', 'INSERT',
      '5', 'M203',
      '8', 'FN-VIEW-TOP',
      '2', 'FN_MOD_ISLAND',
      '10', '900', '20', '700',
      '0', 'ATTRIB', '2', 'KIND', '1', 'Ban dao trung tam M3',
      '0', 'ATTRIB', '2', 'W', '1', '1400',
      '0', 'ATTRIB', '2', 'D', '1', '750',
      '0', 'ATTRIB', '2', 'H', '1', '850',
      '0', 'ATTRIB', '2', 'MAT', '1', 'STONE_MARBLE',
      '0', 'SEQEND'
    );
  }

  lines.push('0', 'ENDSEC', '0', 'EOF');
  return lines.join('\n');
}
