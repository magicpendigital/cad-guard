import { GoogleGenAI } from '@google/genai';
import { SheetInfo } from './sheets.js';

export interface AiAuditReport {
  sheet_id: string;
  sheet_name: string;
  summary_vi: string;
  risks_detected: number;
  checks: {
    dimension_consistency: {
      status: 'pass' | 'warning' | 'error';
      title: string;
      findings: Array<{ message: string; severity: 'E' | 'W'; location: string }>;
    };
    hardware_clearances: {
      status: 'pass' | 'warning' | 'error';
      title: string;
      findings: Array<{ message: string; severity: 'E' | 'W'; location: string }>;
    };
    bom_schedule: {
      status: 'pass' | 'warning' | 'error';
      title: string;
      findings: Array<{ message: string; severity: 'E' | 'W'; location: string }>;
    };
  };
  recommendations: string[];
}

export class AiAuditEngine {
  public async analyzeSheet(sheet: SheetInfo, drawingName: string): Promise<AiAuditReport> {
    if (sheet.is_scratchpad) {
      return {
        sheet_id: sheet.id,
        sheet_name: sheet.name,
        summary_vi: 'Đây là khu vực vẽ nháp và thử nghiệm chi tiết ngoài khung in. Không có rủi ro sản xuất trực tiếp.',
        risks_detected: 0,
        checks: {
          dimension_consistency: {
            status: 'pass',
            title: 'Khu vực nháp - Bỏ qua kiểm tra kích thước',
            findings: []
          },
          hardware_clearances: {
            status: 'pass',
            title: 'Khu vực nháp - Bỏ qua kiểm tra phụ kiện',
            findings: []
          },
          bom_schedule: {
            status: 'pass',
            title: 'Khu vực nháp - Bỏ qua bảng kê vật tư',
            findings: []
          }
        },
        recommendations: ['Nên dọn dẹp các nét cắt nháp trước khi chuyển giao bản vẽ chính thức']
      };
    }

    const hasAiInsights = sheet.ai_insights && sheet.ai_insights.length > 0;

    const dimFindings = (sheet.ai_insights || [])
      .filter((i) => i.type === 'dimension_conflict')
      .map((i) => ({ message: i.description, severity: i.severity, location: i.location }));

    const clrFindings = (sheet.ai_insights || [])
      .filter((i) => i.type === 'hardware_clearance')
      .map((i) => ({ message: i.description, severity: i.severity, location: i.location }));

    const bomFindings = (sheet.ai_insights || [])
      .filter((i) => i.type === 'bom_mismatch')
      .map((i) => ({ message: i.description, severity: i.severity, location: i.location }));

    const risksCount = dimFindings.length + clrFindings.length + bomFindings.length;

    let summary = '';
    if (risksCount > 0) {
      summary = `AI phát hiện ${risksCount} rủi ro sản xuất cần lưu ý trên trang "${sheet.name}". Cần kiểm tra đối chiếu kích thước phủ bì và khe hở phụ kiện trước khi đưa bản vẽ xuống máy cắt CNC.`;
    } else {
      summary = `Trang "${sheet.name}" đạt độ nhất quán cao về kích thước 3 hình chiếu, quy cách khe hở phụ kiện và bảng kê vật tư.`;
    }

    // Dynamic prompt if Gemini API key exists
    if (process.env.GEMINI_API_KEY && hasAiInsights) {
      try {
        const ai = new GoogleGenAI({});
        const prompt = `Bạn là chuyên gia thẩm định hồ sơ kỹ thuật sản xuất nội thất gỗ công nghiệp.
Hãy đưa ra nhận định ngắn gọn (3-4 câu) về rủi ro sản xuất trên trang: ${sheet.title} (${sheet.name}).
Các điểm lưu ý:
${sheet.ai_insights.map((i) => `- ${i.title}: ${i.description}`).join('\n')}
Trả về tiếng Việt chuyên nghiệp, trực diện, không dài dòng.`;

        const res = await ai.models.generateContent({
          model: 'gemini-2.5-flash',
          contents: prompt
        });

        if (res.text) {
          summary = res.text.trim();
        }
      } catch (err: any) {
        console.warn('Gemini summary call skipped, using local analysis:', err.message);
      }
    }

    return {
      sheet_id: sheet.id,
      sheet_name: sheet.name,
      summary_vi: summary,
      risks_detected: risksCount,
      checks: {
        dimension_consistency: {
          status: dimFindings.some((f) => f.severity === 'E') ? 'error' : dimFindings.length > 0 ? 'warning' : 'pass',
          title: 'Đối chiếu kích thước các hình chiếu (Mặt bằng - Mặt đứng - Mặt cắt)',
          findings: dimFindings
        },
        hardware_clearances: {
          status: clrFindings.some((f) => f.severity === 'E') ? 'error' : clrFindings.length > 0 ? 'warning' : 'pass',
          title: 'Khe hở kỹ thuật cánh tủ (2-3mm), ray trượt và cối bản lề',
          findings: clrFindings
        },
        bom_schedule: {
          status: bomFindings.some((f) => f.severity === 'E') ? 'error' : bomFindings.length > 0 ? 'warning' : 'pass',
          title: 'Đối chiếu bảng kê vật tư (BOM) với ghi chú trên bản vẽ',
          findings: bomFindings
        }
      },
      recommendations: [
        'Đồng bộ ghi chú độ dày nẹp dán cạnh (0.45mm / 1.0mm / 2.0mm) để người lập trình CAM trừ bì chính xác',
        'Kiểm tra lại dung sai khe hở góc chữ L tối thiểu 45mm cho tay nắm vát 45 độ',
        'Xác nhận chủng loại ray trượt (ray âm giảm chấn hay ray bi 3 tầng) để chừa khoảng hở thành hộc kéo đúng catalog'
      ]
    };
  }
}
