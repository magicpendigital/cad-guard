import { DrawingsManager } from './drawings.js';
import { StandardsManager } from './standards.js';
import { SheetsManager } from './sheets.js';

export class ReportGenerator {
  private drawings: DrawingsManager;
  private standards: StandardsManager;
  private sheets: SheetsManager;

  constructor(drawings: DrawingsManager, standards: StandardsManager, sheets: SheetsManager) {
    this.drawings = drawings;
    this.standards = standards;
    this.sheets = sheets;
  }

  public generateJson(file: string, standardName: string) {
    const audit = this.drawings.auditFile(file, standardName);
    const sheetList = this.sheets.getSheetsForDrawing(file, standardName);

    return {
      schema: 'cg.report/1',
      tool_version: '0.1.0',
      standard: {
        name: audit.standard,
        version: audit.version,
        profile: audit.profile
      },
      generated_at: new Date().toISOString(),
      file: audit.file,
      counts: audit.counts,
      rules_run: audit.rules_run,
      sheets: sheetList.map((s) => ({
        index: s.index,
        name: s.name,
        title: s.title,
        sheet_no: s.sheet_no,
        scale: s.scale,
        counts: s.counts,
        callouts_count: s.callouts.length,
        ai_risks: s.ai_insights.length
      })),
      groups: audit.groups,
      skipped: audit.skipped
    };
  }

  public generateHtml(file: string, standardName: string): string {
    const data = this.generateJson(file, standardName);
    const errCount = data.counts.E;
    const warnCount = data.counts.W;
    const infoCount = data.counts.I;

    const rows = data.groups.flatMap((g) =>
      g.rules.map((r) => `
        <tr class="${r.severity}">
          <td><strong>${r.rule_id}</strong></td>
          <td>${r.title}</td>
          <td><span class="badge ${r.severity}">${r.severity === 'E' ? 'Lỗi' : r.severity === 'W' ? 'Cảnh báo' : 'Thông tin'}</span></td>
          <td>${r.count}</td>
          <td>${r.items.map((it) => `<div>${it.message}</div>`).join('')}</td>
        </tr>
      `)
    ).join('');

    const sheetRows = data.sheets.map((s) => `
      <tr>
        <td><strong>#${s.index}</strong></td>
        <td>${s.name}</td>
        <td>${s.sheet_no}</td>
        <td>${s.scale}</td>
        <td><span class="badge E">${s.counts.E}</span> / <span class="badge W">${s.counts.W}</span></td>
        <td>${s.ai_risks > 0 ? `<span class="badge AI">${s.ai_risks} rủi ro</span>` : '<span class="badge ok">Đạt</span>'}</td>
      </tr>
    `).join('');

    return `<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Báo cáo thẩm định bản vẽ: ${file}</title>
<style>
  :root { --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; --e: #b42318; --w: #b7791f; --ok: #2e7d4f; }
  body { font-family: var(--font); background: #f9fafb; color: #1f2421; margin: 0; padding: 32px 20px; line-height: 1.5; }
  .container { max-width: 960px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  h1 { font-size: 24px; margin-top: 0; margin-bottom: 8px; color: #0f6b62; }
  .meta { color: #6b726d; font-size: 14px; margin-bottom: 24px; }
  .summary-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }
  .card { padding: 16px; border: 1px solid #dedad2; border-radius: 6px; background: #fdfdfd; }
  .card .num { font-size: 28px; font-weight: bold; margin-top: 4px; }
  .card.E .num { color: var(--e); }
  .card.W .num { color: var(--w); }
  .card.OK .num { color: var(--ok); }
  table { width: 100%; border-collapse: collapse; margin-bottom: 32px; font-size: 14px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #dedad2; vertical-align: top; }
  th { background: #f6f5f2; font-weight: 600; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 12px; font-weight: 600; }
  .badge.E { background: #fbe3e1; color: var(--e); }
  .badge.W { background: #fcefcb; color: var(--w); }
  .badge.AI { background: #f3e8ff; color: #6b21a8; }
  .badge.ok { background: #dff3e4; color: var(--ok); }
  .footer { font-size: 13px; color: #888; border-top: 1px solid #eee; padding-top: 16px; margin-top: 32px; text-align: right; }
  @media print { body { padding: 0; background: #fff; } .container { box-shadow: none; padding: 0; } }
</style>
</head>
<body>
<div class="container">
  <h1>Báo cáo Kiểm tra & Chuẩn hoá Bản vẽ Nội thất</h1>
  <div class="meta">
    Tệp: <strong>${file}</strong> · Chuẩn áp dụng: <strong>${standardName}</strong> · Thời điểm: ${new Date().toLocaleString('vi-VN')}
  </div>

  <div class="summary-cards">
    <div class="card E">
      <div>Lỗi nghiêm trọng (Mức E)</div>
      <div class="num">${errCount}</div>
    </div>
    <div class="card W">
      <div>Cảnh báo (Mức W)</div>
      <div class="num">${warnCount}</div>
    </div>
    <div class="card OK">
      <div>Trạng thái chung</div>
      <div class="num" style="font-size: 20px;">${errCount === 0 ? 'ĐẠT XUẤT XƯỞNG' : 'CẦN CHỈNH SỬA'}</div>
    </div>
    <div class="card">
      <div>Số trang bản vẽ (Sheets)</div>
      <div class="num">${data.sheets.length}</div>
    </div>
  </div>

  <h2>1. Danh sách Khung bản vẽ / Trang duyệt (Sheets)</h2>
  <table>
    <thead><tr><th>Trang</th><th>Tên bản vẽ</th><th>Số tờ</th><th>Tỉ lệ</th><th>Lỗi (E / W)</th><th>AI Đánh giá</th></tr></thead>
    <tbody>${sheetRows}</tbody>
  </table>

  <h2>2. Chi tiết Lỗi kiểm tra theo Quy chuẩn kỹ thuật</h2>
  <table>
    <thead><tr><th>Mã luật</th><th>Tiêu đề quy chuẩn</th><th>Mức độ</th><th>Số lượng</th><th>Mô tả chi tiết</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>

  <div class="footer">
    Báo cáo xuất tự động bởi CAD Guard · Hệ thống kiểm chuẩn nội thất tất định kết hợp AI
  </div>
</div>
</body>
</html>`;
  }
}
