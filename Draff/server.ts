import express, { Request, Response } from 'express';
import path from 'node:path';
import fs from 'node:fs';
import { StandardsManager } from './src/standards.js';
import { DrawingsManager } from './src/drawings.js';
import { ChangesetManager } from './src/changeset.js';
import { AssistantManager } from './src/assistant.js';
import { SheetsManager } from './src/sheets.js';
import { McpCompanionManager } from './src/mcpCompanion.js';
import { AiAuditEngine } from './src/aiAudit.js';
import { ReportGenerator } from './src/report.js';
import { ProjectManager } from './src/projectManager.js';

const app = express();
const port = 3000;
const host = '0.0.0.0';

app.use(express.json({ limit: '250mb' }));
app.use(express.urlencoded({ limit: '250mb', extended: true }));

// Bắt lỗi JSON parsing hoặc payload quá tải và trả về đúng JSON thay vì HTML lỗi mặc định
app.use((err: any, req: Request, res: Response, next: any) => {
  if (err) {
    console.error('[CAD Guard Server] Middleware Error:', err.message);
    if (err.type === 'entity.too.large') {
      return res.status(413).json({
        ok: false,
        error: `Tệp bản vẽ quá lớn (${(err.length / 1024 / 1024).toFixed(1)} MB vượt giới hạn ${(err.limit / 1024 / 1024).toFixed(0)} MB của máy chủ). Hãy thử nén hoặc xuất bớt các khối thừa.`
      });
    }
    return res.status(err.status || 400).json({
      ok: false,
      error: `Lỗi xử lý dữ liệu máy chủ: ${err.message}`
    });
  }
  next();
});

// Determine workspace root and synthetic fixtures directory
const syntheticDir = path.resolve(process.cwd(), 'fixtures/synthetic');
const standards = new StandardsManager();
const drawings = new DrawingsManager(syntheticDir, standards);
const changesets = new ChangesetManager(syntheticDir, drawings, standards);
const assistant = new AssistantManager(standards, drawings, changesets);
const sheetsManager = new SheetsManager();
const mcpCompanion = new McpCompanionManager();
const aiAuditEngine = new AiAuditEngine();
const reportGenerator = new ReportGenerator(drawings, standards, sheetsManager);
const projectManager = new ProjectManager();

// Read OAuth Client ID from firebase-applet-config.json
function getOAuthClientId(): string {
  try {
    const cfgPath = path.resolve(process.cwd(), 'firebase-applet-config.json');
    if (fs.existsSync(cfgPath)) {
      const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'));
      if (cfg.oAuthClientId) return cfg.oAuthClientId;
    }
  } catch {}
  return process.env.GOOGLE_OAUTH_CLIENT_ID || '';
}

// Security & Caching Headers (Allow Google Identity Services & Google Drive API for OAuth 2.0 Folder Connection)
app.use((req, res, next) => {
  res.setHeader(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com; style-src 'self' 'unsafe-inline' https://accounts.google.com; img-src 'self' data: https:; connect-src 'self' https://www.googleapis.com https://accounts.google.com https://oauth2.googleapis.com; frame-src 'self' https://accounts.google.com; font-src 'self' data:; base-uri 'self'; form-action 'self'; frame-ancestors *"
  );
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer-when-downgrade');
  res.setHeader('Cache-Control', 'no-store');
  next();
});

// OAuth Configuration Endpoint for Client-Side Google Drive Folder Picker
app.get('/api/oauth/config', (req: Request, res: Response) => {
  res.json({
    clientId: getOAuthClientId(),
    scope: 'https://www.googleapis.com/auth/drive.readonly'
  });
});

// Project & Workspace Management Endpoints
app.get('/api/projects', (req: Request, res: Response) => {
  res.json({
    projects: projectManager.listProjects(),
    activeProject: projectManager.getProjectDetails()
  });
});

app.post('/api/projects', (req: Request, res: Response) => {
  try {
    const proj = projectManager.createOrUpdateProject(req.body);
    const activeProject = projectManager.getProjectDetails(proj.id);
    res.json({
      ok: true,
      project: activeProject,
      activeProject,
      projects: projectManager.listProjects()
    });
  } catch (err: any) {
    res.status(400).json({ ok: false, error: err.message });
  }
});

app.post('/api/projects/select', (req: Request, res: Response) => {
  try {
    const { projectId } = req.body;
    const proj = projectManager.setActiveProject(projectId);
    res.json({
      projects: projectManager.listProjects(),
      activeProject: projectManager.getProjectDetails(proj.id)
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// Chunked Upload Sessions State for large DXF files
interface UploadSession {
  uploadId: string;
  fileName: string;
  relativePath: string;
  department: 'design' | 'tech' | 'viz' | 'cnc';
  projectId?: string;
  totalChunks: number;
  size?: number;
  chunks: string[];
  receivedCount: number;
  createdAt: number;
}

const uploadSessions = new Map<string, UploadSession>();

// Cleanup stale sessions every 10 minutes
setInterval(() => {
  const now = Date.now();
  for (const [id, session] of uploadSessions.entries()) {
    if (now - session.createdAt > 30 * 60 * 1000) {
      uploadSessions.delete(id);
    }
  }
}, 10 * 60 * 1000);

// Endpoint khởi tạo phiên tải phân đoạn (Chunked Upload) cho tệp lớn
app.post('/api/upload/init', (req: Request, res: Response) => {
  try {
    const { fileName, size, totalChunks, department, projectId, relativePath, projectName, projectCode } = req.body;
    if (!fileName) {
      return res.status(400).json({ ok: false, error: 'Thiếu tên tệp DXF' });
    }

    let targetProjectId = projectId;
    if (projectName) {
      const p = projectManager.createOrUpdateProject({
        id: targetProjectId,
        name: projectName,
        code: projectCode || fileName.replace(/[^A-Za-z0-9]/g, '').slice(0, 6).toUpperCase() || 'DXF01',
        sourceType: 'local',
        folderPath: `/uploads/${fileName}`,
        files: []
      });
      targetProjectId = p.id;
    }

    const uploadId = `up_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    uploadSessions.set(uploadId, {
      uploadId,
      fileName,
      relativePath: relativePath || fileName,
      department: department || 'tech',
      projectId: targetProjectId,
      totalChunks: parseInt(totalChunks, 10) || 1,
      size: size || 0,
      chunks: [],
      receivedCount: 0,
      createdAt: Date.now()
    });
    res.json({ ok: true, uploadId, projectId: targetProjectId });
  } catch (err: any) {
    res.status(400).json({ ok: false, error: err.message });
  }
});

// Endpoint nhận từng mảnh (chunk) dữ liệu của tệp bản vẽ lớn
app.post('/api/upload/chunk', (req: Request, res: Response) => {
  try {
    const { uploadId, chunkIndex, totalChunks, chunkData } = req.body;
    const session = uploadSessions.get(uploadId);
    if (!session) {
      return res.status(404).json({ ok: false, error: 'Phiên tải tệp không tồn tại hoặc đã hết hạn.' });
    }

    const idx = parseInt(chunkIndex, 10);
    if (session.chunks[idx] === undefined) {
      session.chunks[idx] = chunkData || '';
      session.receivedCount++;
    }

    const isComplete = session.receivedCount >= session.totalChunks;
    if (isComplete) {
      const fullContent = session.chunks.join('');
      uploadSessions.delete(uploadId);

      // Thêm hoặc cập nhật tệp vào dự án
      const updatedProj = projectManager.addOrUpdateFileContent(
        session.projectId,
        session.fileName,
        session.relativePath,
        fullContent,
        session.department,
        session.size || fullContent.length,
        'local'
      );

      const activeProject = projectManager.getProjectDetails(updatedProj.id);
      return res.json({
        ok: true,
        completed: true,
        fileName: session.fileName,
        project: activeProject,
        activeProject,
        projects: projectManager.listProjects()
      });
    }

    res.json({
      ok: true,
      completed: false,
      received: session.receivedCount,
      total: session.totalChunks,
      percent: Math.round((session.receivedCount / session.totalChunks) * 100)
    });
  } catch (err: any) {
    res.status(400).json({ ok: false, error: err.message });
  }
});

app.post('/api/projects/file_dept', (req: Request, res: Response) => {
  try {
    const { fileName, department, projectId } = req.body;
    const activeProject = projectManager.updateFileDepartment(fileName, department, projectId);
    res.json({
      projects: projectManager.listProjects(),
      activeProject
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// Real DXF Inspection + 2D Vector Sheets + 3D Scene (cg.scene/1)
app.post('/api/dxf/inspect', (req: Request, res: Response) => {
  try {
    const { fileName, projectId, sheetIdx } = req.body;
    if (!fileName) {
      return res.status(400).json({ error: 'Thiếu tên tệp DXF' });
    }
    const result = projectManager.getFileInspection(fileName, projectId, sheetIdx !== undefined ? Number(sheetIdx) : 0);
    res.json(result);
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// Studio 3D Scene Builder & Gap Supplement Endpoint
app.post('/api/studio/scene', (req: Request, res: Response) => {
  try {
    const { fileName, supplement, viewOverrides, aiConsent, projectId, sheetIdx } = req.body;
    const targetFile = fileName || 'hygiene_bad.dxf';
    const scene = projectManager.updateSceneSupplement(
      targetFile,
      supplement || {},
      viewOverrides || {},
      Boolean(aiConsent),
      projectId,
      sheetIdx !== undefined ? Number(sheetIdx) : undefined
    );
    res.json(scene);
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// Studio 3D Binary .GLB Export Endpoint
app.get('/api/studio/glb', (req: Request, res: Response) => {
  try {
    const fileName = (req.query.file as string) || 'hygiene_bad.dxf';
    const projectId = req.query.projectId as string | undefined;
    const sheetIdx = req.query.sheet !== undefined ? Number(req.query.sheet) : undefined;
    const glbBuffer = projectManager.exportGlb(fileName, projectId, sheetIdx);
    const outName = fileName.replace(/\.dxf$/i, '') + (sheetIdx !== undefined ? `_sheet${sheetIdx}` : '') + '.glb';
    res.setHeader('Content-Type', 'model/gltf-binary');
    res.setHeader('Content-Disposition', `attachment; filename="${outName}"`);
    res.send(glbBuffer);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// API Routes
app.get('/api/session', (req: Request, res: Response) => {
  const prof = standards.getProfile();
  const activeProj = projectManager.getActiveProject();
  res.json({
    app: 'cad-guard',
    version: '0.2.0',
    workspace_name: activeProj.folderPath,
    active_project: activeProj.name,
    profile: prof
      ? {
          name: prof.name,
          version: prof.version,
          standard: prof.standard,
          description: prof.description
        }
      : null,
    anonymize: true,
    data_mode: 'Ẩn danh Bậc 1 (mặc định)',
    flags: {
      experimental: false,
      allow_openrouter: false,
      account: null
    },
    standards: standards.getStandardNames(),
    ...standards.getDepartments()
  });
});

app.get('/api/drawings', (req: Request, res: Response) => {
  const projDetails = projectManager.getProjectDetails();
  const list = projDetails.files.map(f => ({
    path: f.relativePath,
    name: f.fileName,
    dir: f.department,
    department: f.department,
    source: f.source,
    size_bytes: f.sizeBytes,
    status: f.scanned ? (f.errors === 0 && f.warnings === 0 ? 'clean' : 'audited') : 'unscanned',
    errors: f.errors,
    warnings: f.warnings,
    is_output: false
  }));
  res.json({
    drawings: list,
    total: list.length,
    truncated: false
  });
});

app.post('/api/audit', (req: Request, res: Response) => {
  try {
    const file = req.body.file || req.body.name || 'hygiene_bad.dxf';
    const standard = req.body.standard || 'furniture-v0';
    const inspection = projectManager.getFileInspection(file, req.body.projectId);
    const stdResult = drawings.auditFile(file, standard);
    res.json({
      ...stdResult,
      findings: inspection.findings.filter(f => f.tier === 'code').map(f => ({
        rule_id: f.rule,
        severity: f.sev === 'error' ? 'E' : 'W',
        title: f.title,
        message: f.d,
        where: f.where
      }))
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

app.post('/api/audit_all', (req: Request, res: Response) => {
  try {
    const standard = req.body.standard || 'furniture-v0';
    const proj = projectManager.getActiveProject();
    let totalErrors = 0;
    let totalWarnings = 0;
    for (const entry of proj.files.values()) {
      entry.scanned = true;
      totalErrors += entry.findings.filter(f => f.sev === 'error' && f.st === 'open').length;
      totalWarnings += entry.findings.filter(f => f.sev === 'warn' && f.st === 'open').length;
    }
    const result = drawings.auditAll(standard);
    res.json({
      ...result,
      totalFiles: proj.files.size,
      totalErrors,
      totalWarnings
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// Report Export Endpoints (matching report.py)
app.get('/api/report/html', (req: Request, res: Response) => {
  try {
    const file = (req.query.file as string) || (req.query.name as string) || 'hygiene_bad.dxf';
    const standard = (req.query.standard as string) || 'design-hygiene-v0';
    const htmlReport = reportGenerator.generateHtml(file, standard);
    res.type('html').send(htmlReport);
  } catch (err: any) {
    res.status(500).send(`Lỗi tạo báo cáo: ${err.message}`);
  }
});

app.get('/api/report/json', (req: Request, res: Response) => {
  try {
    const file = (req.query.file as string) || (req.query.name as string) || 'hygiene_bad.dxf';
    const standard = (req.query.standard as string) || 'design-hygiene-v0';
    const jsonReport = reportGenerator.generateJson(file, standard);
    res.json(jsonReport);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Sheet / Artboard Engine
app.get('/api/sheets', (req: Request, res: Response) => {
  try {
    const file = (req.query.file as string) || 'hygiene_bad.dxf';
    const standard = (req.query.standard as string) || 'design-hygiene-v0';
    const sheets = sheetsManager.getSheetsForDrawing(file, standard);
    res.json({ file, standard, sheets, total: sheets.length });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// Tier 2: AI Deep Audit for a sheet
app.post('/api/ai_audit', async (req: Request, res: Response) => {
  try {
    const file = req.body.file || req.body.name || 'hygiene_bad.dxf';
    const sheet_id = req.body.sheet_id;
    const standard = req.body.standard || 'design-hygiene-v0';
    const sheets = sheetsManager.getSheetsForDrawing(file, standard);
    const targetSheet = sheets.find((s) => s.id === sheet_id) || sheets[0];
    const report = await aiAuditEngine.analyzeSheet(targetSheet, file);
    res.json(report);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// AutoCAD Plugin & MCP Companion Endpoints
app.get('/api/plugin/status', (req: Request, res: Response) => {
  res.json(mcpCompanion.getStatus());
});

app.get('/api/mcp/info', (req: Request, res: Response) => {
  res.json(mcpCompanion.getMcpInfo());
});

app.post('/api/plugin/sync', (req: Request, res: Response) => {
  res.json(mcpCompanion.handleSyncAction(req.body));
});

app.post('/api/mcp/action', (req: Request, res: Response) => {
  res.json(mcpCompanion.handleSyncAction(req.body));
});

app.get('/api/plugin/script', (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="cadguard.lsp"');
  res.send(mcpCompanion.getPluginScript());
});

app.get('/api/autocad/download-pack', (req: Request, res: Response) => {
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="cadguard.lsp"');
  res.send(mcpCompanion.getPluginScript());
});

app.get('/palette', (req: Request, res: Response) => {
  res.sendFile(path.resolve(process.cwd(), 'public', 'palette.html'));
});

app.get('/api/explain', (req: Request, res: Response) => {
  try {
    const rule = req.query.rule as string;
    const standard = req.query.standard as string;
    if (!rule || !standard) {
      return res.status(400).json({ error: 'Thiếu mã luật hoặc chuẩn' });
    }
    const result = standards.explainRule(rule, standard);
    res.json(result);
  } catch (err: any) {
    res.status(404).json({ error: err.message });
  }
});

app.post('/api/summary', (req: Request, res: Response) => {
  try {
    const { file } = req.body;
    if (!file) {
      return res.status(400).json({ error: 'Thiếu tham số file' });
    }
    const result = drawings.getModelSummary(file);
    res.json(result);
  } catch (err: any) {
    res.status(422).json({ error: err.message });
  }
});

app.get('/api/rules', (req: Request, res: Response) => {
  try {
    const standard = (req.query.standard as string) || 'furniture-v0';
    const result = standards.getRulesTable(standard);
    res.json(result);
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

app.post('/api/changeset/suggest', (req: Request, res: Response) => {
  try {
    const { file, standard } = req.body;
    if (!file || !standard) {
      return res.status(400).json({ error: 'Thiếu tham số file hoặc standard' });
    }
    const result = changesets.suggestOps(file, standard);
    res.json(result);
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

app.post('/api/changeset/propose', (req: Request, res: Response) => {
  try {
    const { file, standard, ops } = req.body;
    const result = changesets.proposeChangeset(file, standard, ops, 'user');
    res.json(result);
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

app.get('/api/changeset', (req: Request, res: Response) => {
  try {
    const id = req.query.id as string;
    if (!id) {
      return res.status(400).json({ error: 'Thiếu mã changeset' });
    }
    const result = changesets.getChangeset(id);
    res.json(result);
  } catch (err: any) {
    res.status(404).json({ error: err.message });
  }
});

app.get('/api/changesets', (req: Request, res: Response) => {
  res.json(changesets.listChangesets());
});

app.post('/api/changeset/apply', (req: Request, res: Response) => {
  try {
    const { changeset_id, confirm } = req.body;
    const result = changesets.applyChangeset(changeset_id, confirm);
    res.json(result);
  } catch (err: any) {
    res.status(409).json({ error: err.message });
  }
});

app.post('/api/changeset/undo', (req: Request, res: Response) => {
  try {
    const { changeset_id, confirm } = req.body;
    const result = changesets.undoChangeset(changeset_id, confirm);
    res.json(result);
  } catch (err: any) {
    res.status(409).json({ error: err.message });
  }
});

app.get('/api/engines', (req: Request, res: Response) => {
  const refresh = req.query.refresh === '1';
  res.json(assistant.getEngines(refresh));
});

app.post('/api/chat/stop', (req: Request, res: Response) => {
  const { run_id } = req.body;
  const stopped = assistant.stopRun(run_id);
  res.json({ stopped });
});

app.post('/api/chat', async (req: Request, res: Response) => {
  // Support both JSON single-turn reply (from UI mockup composer) and NDJSON stream
  if (req.body && typeof req.body.message === 'string' && !req.body.question) {
    try {
      const drawing = req.body.drawing || 'hygiene_bad.dxf';
      const inspection = projectManager.getFileInspection(drawing);
      const openFinds = inspection.findings.filter(f => f.st === 'open');
      const gapsCount = inspection.scene.gaps.length;
      return res.json({
        toolCalls: [
          {
            name: 'cadguard.inspect_dxf_and_3d',
            args: { file: drawing, department: inspection.department },
            summary: `${openFinds.length} phát hiện · ${gapsCount} phần thiếu 3D`
          }
        ],
        reply: `Đối với **${drawing}** (Phòng ${inspection.department === 'design' ? 'Thiết kế' : inspection.department === 'tech' ? 'Kỹ thuật' : inspection.department === 'viz' ? 'Thiết kế 3D' : 'Lập trình SX'} · ${inspection.info}):\n• Hiện có **${openFinds.length} phát hiện** trên ${inspection.sheets.length} trang Artboard (${openFinds.map(f => f.rule).join(', ') || 'Sạch lỗi'}).\n• Mô hình 3D (\`cg.scene/1\`): dựng được **${inspection.scene.boxes.length} khối**, còn **${gapsCount} phần thiếu thông số** (${inspection.scene.gaps.map(g => g.id).join(', ') || 'đã đủ'}). Bạn có thể bấm nút **3D Studio** trên thanh công cụ để xoay khối 3D, điền chiều cao/chiều sâu còn thiếu và tải tệp \`.glb\`.`
      });
    } catch (err: any) {
      return res.status(500).json({ error: err.message });
    }
  }

  res.setHeader('Content-Type', 'application/x-ndjson; charset=utf-8');
  res.setHeader('Transfer-Encoding', 'chunked');

  const sendEvent = (obj: any) => {
    res.write(JSON.stringify(obj) + '\n');
  };

  try {
    await assistant.streamChat(req.body, sendEvent);
  } catch (err: any) {
    sendEvent({ type: 'error', message: err.message });
  } finally {
    res.end();
  }
});

// Static assets from public/
const publicDir = path.resolve(process.cwd(), 'public');
app.use(express.static(publicDir));

// Fallback to index.html for SPA
app.use((req: Request, res: Response) => {
  const indexPath = path.join(publicDir, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).send('Not Found');
  }
});

app.listen(port, host, () => {
  console.log(`cad-guard server running at http://${host}:${port}`);
});
