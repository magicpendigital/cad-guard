import {
  ParsedDxfModel,
  RenderedSheet,
  EvaluatedFinding,
  parseDxfContent,
  renderDxfToSheetsAndFindings,
  generateSyntheticDxfContent
} from './dxfParser.js';
import { SceneData, buildSceneFromDxf, buildGlbBuffer } from './scene3d.js';

export interface ProjectFileEntry {
  fileName: string;
  relativePath: string;
  source: 'synthetic' | 'local' | 'gdrive';
  driveFileId?: string;
  department: 'design' | 'tech' | 'viz' | 'cnc';
  sizeBytes: number;
  rawContent: string;
  parsed: ParsedDxfModel;
  sheets: RenderedSheet[];
  findings: EvaluatedFinding[];
  ops: { a: { what: string; from: string; to: string }; b: { what: string; from: string; to: string } };
  supplement: Record<string, any>;
  viewOverrides: Record<string, '' | 'front' | 'top' | 'side'>;
  scanned: boolean;
}

export interface ProjectWorkspace {
  id: string;
  name: string;
  code: string;
  sourceType: 'synthetic' | 'local' | 'gdrive';
  folderPath: string;
  driveFolderId?: string;
  standardProfile: string;
  overlayFile: string;
  createdAt: string;
  files: Map<string, ProjectFileEntry>;
}

export class ProjectManager {
  private projects: Map<string, ProjectWorkspace> = new Map();
  private activeProjectId = 'proj-k1';
  private initialized = false;

  constructor() {
    // Khởi tạo lười (lazy-init) để máy chủ Express mở cổng 3000 tức thì khi khởi động
    setTimeout(() => {
      try {
        this.ensureInit();
      } catch (e) {
        console.error('[ProjectManager] Deferred init error:', e);
      }
    }, 50);
  }

  private ensureInit() {
    if (this.initialized) return;
    this.initialized = true;
    this.initDefaultProject();
  }

  private initDefaultProject() {
    const k1: ProjectWorkspace = {
      id: 'proj-k1',
      name: 'Phiên làm việc hiện tại',
      code: 'WS',
      sourceType: 'synthetic',
      folderPath: 'fixtures/synthetic',
      standardProfile: 'furniture-v0.1.0',
      overlayFile: 'standards/furniture-v0.yaml',
      createdAt: '2026-11-06',
      files: new Map()
    };

    const initialFiles: { name: string; rel: string; dept: 'design' | 'tech' | 'viz' | 'cnc' }[] = [
      { name: 'hygiene_bad.dxf', rel: 'hygiene_bad.dxf', dept: 'design' },
      { name: 'bad_layers.dxf', rel: 'bad_layers.dxf', dept: 'tech' },
      { name: 'bad_titleblock.dxf', rel: 'bad_titleblock.dxf', dept: 'tech' },
      { name: 'model_features.dxf', rel: 'model_features.dxf', dept: 'viz' },
      { name: 'bad_geometry.dxf', rel: 'bad_geometry.dxf', dept: 'cnc' },
      { name: 'ok_sheet.dxf', rel: 'ok_sheet.dxf', dept: 'tech' }
    ];

    for (const item of initialFiles) {
      const content = generateSyntheticDxfContent(item.name);
      const parsed = parseDxfContent(content, item.name, item.rel);
      parsed.department = item.dept;
      const { sheets, findings, ops } = renderDxfToSheetsAndFindings(parsed);
      k1.files.set(item.name, {
        fileName: item.name,
        relativePath: item.rel,
        source: 'synthetic',
        department: item.dept,
        sizeBytes: parsed.sizeBytes,
        rawContent: content,
        parsed,
        sheets,
        findings,
        ops,
        supplement: {},
        viewOverrides: {},
        scanned: true
      });
    }

    this.projects.set(k1.id, k1);
  }

  public listProjects() {
    this.ensureInit();
    return Array.from(this.projects.values()).map(p => ({
      id: p.id,
      name: p.name,
      code: p.code,
      sourceType: p.sourceType,
      folderPath: p.folderPath,
      driveFolderId: p.driveFolderId,
      standardProfile: p.standardProfile,
      overlayFile: p.overlayFile,
      createdAt: p.createdAt,
      fileCount: p.files.size,
      active: p.id === this.activeProjectId,
      byDepartment: this.countByDepartment(p)
    }));
  }

  private countByDepartment(p: ProjectWorkspace) {
    const counts = { design: 0, tech: 0, viz: 0, cnc: 0 };
    for (const f of p.files.values()) {
      counts[f.department] = (counts[f.department] || 0) + 1;
    }
    return counts;
  }

  public getActiveProject(): ProjectWorkspace {
    this.ensureInit();
    return this.projects.get(this.activeProjectId) || Array.from(this.projects.values())[0];
  }

  public setActiveProject(projectId: string): ProjectWorkspace {
    this.ensureInit();
    if (!this.projects.has(projectId)) {
      throw new Error(`Không tìm thấy dự án '${projectId}'`);
    }
    this.activeProjectId = projectId;
    return this.getActiveProject();
  }

  public createOrUpdateProject(payload: {
    id?: string;
    name: string;
    code?: string;
    sourceType: 'local' | 'gdrive' | 'synthetic';
    folderPath: string;
    driveFolderId?: string;
    standardProfile?: string;
    files: { fileName: string; relativePath?: string; content: string; driveFileId?: string; department?: 'design' | 'tech' | 'viz' | 'cnc' }[];
  }): ProjectWorkspace {
    this.ensureInit();
    const rawCode = (payload.code || payload.name.replace(/[^a-zA-Z0-9]/g, '').slice(0, 6) || 'PRJ').toUpperCase();
    const id = payload.id || `proj-${rawCode.toLowerCase()}-${Date.now().toString(36).slice(-4)}`;

    const proj: ProjectWorkspace = this.projects.get(id) || {
      id,
      name: payload.name.trim(),
      code: rawCode,
      sourceType: payload.sourceType,
      folderPath: payload.folderPath || payload.name,
      driveFolderId: payload.driveFolderId,
      standardProfile: payload.standardProfile || `furniture-v0.1.0 + Overlay ${rawCode}`,
      overlayFile: `standards/projects/${rawCode.toLowerCase()}.yaml`,
      createdAt: new Date().toISOString().slice(0, 10),
      files: new Map()
    };

    proj.name = payload.name.trim();
    proj.folderPath = payload.folderPath || proj.folderPath;
    if (payload.standardProfile) proj.standardProfile = payload.standardProfile;

    const incomingFiles: any[] = (payload as any).files || (payload as any).scannedFiles || [];
    for (const f of incomingFiles) {
      const name: string = f.fileName || f.name || '';
      if (!name || !name.toLowerCase().endsWith('.dxf')) continue;
      const content = f.content && typeof f.content === 'string' && f.content.trim().length > 10
        ? f.content
        : generateSyntheticDxfContent(name);
      const rel = f.relativePath || f.rel || name;
      const parsed = parseDxfContent(content, name, rel);
      if (f.department) parsed.department = f.department;
      const { sheets, findings, ops } = renderDxfToSheetsAndFindings(parsed);

      proj.files.set(name, {
        fileName: name,
        relativePath: rel,
        source: (payload as any).sourceType || (payload as any).source || 'local',
        driveFileId: f.driveFileId || f.id,
        department: parsed.department,
        sizeBytes: parsed.sizeBytes || f.size || content.length,
        rawContent: content,
        parsed,
        sheets,
        findings,
        ops,
        supplement: {},
        viewOverrides: {},
        scanned: true
      });
    }

    this.projects.set(proj.id, proj);
    this.activeProjectId = proj.id;
    return proj;
  }

  public addOrUpdateFileContent(
    projectId: string | undefined,
    fileName: string,
    relativePath: string,
    content: string,
    department?: 'design' | 'tech' | 'viz' | 'cnc',
    sizeBytes?: number,
    source: 'local' | 'gdrive' | 'synthetic' = 'local'
  ): ProjectWorkspace {
    const proj = projectId ? this.projects.get(projectId) || this.getActiveProject() : this.getActiveProject();
    const rel = relativePath || fileName;
    const parsed = parseDxfContent(content, fileName, rel);
    if (department) parsed.department = department;
    const { sheets, findings, ops } = renderDxfToSheetsAndFindings(parsed);

    const existing = proj.files.get(fileName);
    proj.files.set(fileName, {
      fileName,
      relativePath: rel,
      source: existing?.source || source,
      driveFileId: existing?.driveFileId,
      department: parsed.department,
      sizeBytes: sizeBytes || parsed.sizeBytes || (content ? content.length : 0),
      rawContent: content,
      parsed,
      sheets,
      findings,
      ops,
      supplement: existing?.supplement || {},
      viewOverrides: existing?.viewOverrides || {},
      scanned: true
    });

    this.activeProjectId = proj.id;
    return proj;
  }

  public getProjectDetails(projectId?: string) {
    const proj = projectId ? this.projects.get(projectId) || this.getActiveProject() : this.getActiveProject();
    const files = Array.from(proj.files.values()).map(f => ({
      fileName: f.fileName,
      relativePath: f.relativePath,
      source: f.source,
      department: f.department,
      sizeBytes: f.sizeBytes,
      dxfVersion: f.parsed.dxfVersion,
      insunits: f.parsed.insunits,
      entityCount: f.parsed.entities.length,
      layerCount: Object.keys(f.parsed.layers).length,
      sheetCount: f.sheets.length,
      scanned: f.scanned,
      errors: f.findings.filter(x => x.sev === 'error' && x.st === 'open').length,
      warnings: f.findings.filter(x => x.sev === 'warn' && x.st === 'open').length
    }));

    return {
      id: proj.id,
      name: proj.name,
      code: proj.code,
      sourceType: proj.sourceType,
      folderPath: proj.folderPath,
      driveFolderId: proj.driveFolderId,
      standardProfile: proj.standardProfile,
      overlayFile: proj.overlayFile,
      createdAt: proj.createdAt,
      byDepartment: this.countByDepartment(proj),
      files
    };
  }

  public getFileInspection(fileName: string, projectId?: string, sheetIdx = 0) {
    const proj = projectId ? this.projects.get(projectId) || this.getActiveProject() : this.getActiveProject();
    let entry = proj.files.get(fileName);

    if (!entry) {
      // Create on-the-fly synthetic DXF entry if requested file wasn't in map yet
      const content = generateSyntheticDxfContent(fileName);
      const parsed = parseDxfContent(content, fileName, fileName);
      const { sheets, findings, ops } = renderDxfToSheetsAndFindings(parsed);
      entry = {
        fileName,
        relativePath: fileName,
        source: 'synthetic',
        department: parsed.department,
        sizeBytes: parsed.sizeBytes,
        rawContent: content,
        parsed,
        sheets,
        findings,
        ops,
        supplement: {},
        viewOverrides: {},
        scanned: true
      };
      proj.files.set(fileName, entry);
    } else {
      entry.scanned = true;
    }

    const sheetEnts = entry.sheets[sheetIdx]?.ents;
    const scene = buildSceneFromDxf(entry.parsed, entry.supplement, entry.viewOverrides, true, sheetEnts);

    // Tính số lượng đối tượng thật trên từng Layer của bản vẽ đang mở
    const layerCounts: Record<string, number> = {};
    for (const e of entry.parsed.entities) {
      layerCounts[e.layer] = (layerCounts[e.layer] || 0) + 1;
    }
    const layersList = Object.values(entry.parsed.layers)
      .map(l => ({
        name: l.name,
        color: l.color,
        count: layerCounts[l.name] || 0
      }))
      .sort((a, b) => b.count - a.count);

    return {
      projectId: proj.id,
      projectName: proj.name,
      standardProfile: proj.standardProfile,
      fileName: entry.fileName,
      relativePath: entry.relativePath,
      source: entry.source,
      department: entry.department,
      entityCount: entry.parsed.entities.length,
      layerCount: Object.keys(entry.parsed.layers).length,
      layersList,
      info: `${entry.parsed.entities.length} đối tượng · ${Object.keys(entry.parsed.layers).length} layer · DXF ${entry.parsed.dxfVersion} · ${entry.parsed.insunits === 4 ? 'mm' : 'đơn vị ' + entry.parsed.insunits}`,
      sheets: entry.sheets,
      findings: entry.findings,
      ops: entry.ops,
      scene
    };
  }

  public updateFileDepartment(fileName: string, department: 'design' | 'tech' | 'viz' | 'cnc', projectId?: string) {
    const proj = projectId ? this.projects.get(projectId) || this.getActiveProject() : this.getActiveProject();
    const entry = proj.files.get(fileName);
    if (!entry) throw new Error(`Không tìm thấy tệp '${fileName}'`);
    entry.department = department;
    entry.parsed.department = department;
    return this.getProjectDetails(proj.id);
  }

  public updateSceneSupplement(
    fileName: string,
    supplementUpdates: Record<string, any>,
    viewOverrides: Record<string, '' | 'front' | 'top' | 'side'>,
    aiConsent = true,
    projectId?: string,
    sheetIdx?: number
  ): SceneData {
    const proj = projectId ? this.projects.get(projectId) || this.getActiveProject() : this.getActiveProject();
    let entry = proj.files.get(fileName);
    if (!entry) {
      this.getFileInspection(fileName, proj.id);
      entry = proj.files.get(fileName)!;
    }

    Object.assign(entry.supplement, supplementUpdates || {});
    Object.assign(entry.viewOverrides, viewOverrides || {});

    const sheetEnts = (sheetIdx !== undefined && entry.sheets[sheetIdx]?.ents) ? entry.sheets[sheetIdx].ents : undefined;
    return buildSceneFromDxf(entry.parsed, entry.supplement, entry.viewOverrides, aiConsent, sheetEnts);
  }

  public exportGlb(fileName: string, projectId?: string, sheetIdx?: number): Buffer {
    const proj = projectId ? this.projects.get(projectId) || this.getActiveProject() : this.getActiveProject();
    let entry = proj.files.get(fileName);
    if (!entry) {
      this.getFileInspection(fileName, proj.id);
      entry = proj.files.get(fileName)!;
    }
    const sheetEnts = (sheetIdx !== undefined && entry.sheets[sheetIdx]?.ents) ? entry.sheets[sheetIdx].ents : undefined;
    const scene = buildSceneFromDxf(entry.parsed, entry.supplement, entry.viewOverrides, true, sheetEnts);
    return buildGlbBuffer(scene);
  }
}
