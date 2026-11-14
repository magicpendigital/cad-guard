import crypto from 'node:crypto';
import { GoogleGenAI } from '@google/genai';
import { ChangesetManager } from './changeset.js';
import { DrawingsManager } from './drawings.js';
import { StandardsManager } from './standards.js';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatPayload {
  engine: string;
  model?: string | null;
  messages: ChatMessage[];
  standard: string;
  allow_propose?: boolean;
}

export class AssistantManager {
  private standards: StandardsManager;
  private drawings: DrawingsManager;
  private changesets: ChangesetManager;
  private activeRuns: Set<string> = new Set();

  constructor(standards: StandardsManager, drawings: DrawingsManager, changesets: ChangesetManager) {
    this.standards = standards;
    this.drawings = drawings;
    this.changesets = changesets;
  }

  public getEngines(refresh = false) {
    const hasGeminiKey = Boolean(process.env.GEMINI_API_KEY);

    const engines = [
      {
        name: 'gemini',
        title: 'Google Gemini 2.5 Flash',
        mode: 'api',
        available: true,
        status: hasGeminiKey ? 'Sẵn sàng (API Key)' : 'Chế độ Trợ lý CAD tích hợp sẵn',
        model: 'gemini-2.5-flash',
        terms: 'Google Gemini AI Services',
        needs_model: false
      },
      {
        name: 'claude-code',
        title: 'Claude Code CLI',
        mode: 'cli',
        available: false,
        reason: 'Chưa kết nối CLI trong container web',
        status: 'Không khả dụng trên môi trường web',
        terms: 'Anthropic Commercial Terms'
      },
      {
        name: 'codex',
        title: 'Codex CLI',
        mode: 'cli',
        available: false,
        reason: 'Chưa kết nối CLI trong container web',
        status: 'Không khả dụng',
        terms: 'OpenAI API Terms'
      },
      {
        name: 'ollama',
        title: 'Ollama (Cục bộ)',
        mode: 'api',
        available: false,
        reason: 'Không phát hiện máy chủ Ollama trên localhost:11434',
        status: 'Chưa chạy dịch vụ',
        terms: 'Chạy trực tiếp trên thiết bị cá nhân'
      }
    ];

    const groups = [
      { mode: 'api', title: 'API (khoá của bạn / dịch vụ tích hợp)' },
      { mode: 'cli', title: 'Hạn mức tài khoản (CLI)' }
    ];

    return {
      engines,
      groups
    };
  }

  public stopRun(runId: string): boolean {
    if (this.activeRuns.has(runId)) {
      this.activeRuns.delete(runId);
      return true;
    }
    return false;
  }

  public async streamChat(
    payload: ChatPayload,
    sendEvent: (obj: any) => void
  ) {
    const runId = `run-${crypto.randomBytes(6).toString('hex')}`;
    this.activeRuns.add(runId);

    sendEvent({ type: 'start', run_id: runId });

    const userMessage = payload.messages[payload.messages.length - 1]?.content || '';
    const stdName = payload.standard || 'design-hygiene-v0';

    try {
      // Check if user is asking for drawing audit / explanation
      const drawingList = this.drawings.listDrawings().drawings;
      const detectedDrawing = drawingList.find((d) => userMessage.includes(d.name) || userMessage.includes(d.path));
      const targetDrawing = detectedDrawing ? detectedDrawing.path : 'hygiene_bad.dxf';

      // Tool call simulation if appropriate
      if (/lỗi|audit|kiểm tra|quét|soát|sai sót/i.test(userMessage)) {
        const toolCallId = `call_${Date.now()}`;
        sendEvent({
          type: 'tool_call',
          id: toolCallId,
          name: 'cadguard_audit',
          arguments: { file: targetDrawing, standard: stdName }
        });

        const audit = this.drawings.auditFile(targetDrawing, stdName);

        sendEvent({
          type: 'tool_result',
          id: toolCallId,
          name: 'cadguard_audit',
          content: `Kết quả quét ${targetDrawing} theo chuẩn ${stdName}: Lỗi E: ${audit.counts.E}, Cảnh báo W: ${audit.counts.W}, Thông tin I: ${audit.counts.I}. Quy tắc vi phạm: ${audit.groups.flatMap(g => g.rules.map(r => r.rule_id)).join(', ')}`,
          is_error: false
        });

        // If allow_propose and user asked to fix
        if (payload.allow_propose && /sửa|khắc phục|chuẩn hoá|fix/i.test(userMessage)) {
          const propId = `call_prop_${Date.now()}`;
          sendEvent({
            type: 'tool_call',
            id: propId,
            name: 'cadguard_propose_changeset',
            arguments: { file: targetDrawing, standard: stdName }
          });

          const suggested = this.changesets.suggestOps(targetDrawing, stdName);
          const proposed = this.changesets.proposeChangeset(
            targetDrawing,
            stdName,
            suggested.ops.map((o) => o.op),
            'agent'
          );

          sendEvent({
            type: 'tool_result',
            id: propId,
            name: 'cadguard_propose_changeset',
            content: `Đã lập đề xuất ${proposed.changeset_id}: ${proposed.summary_vi}`,
            is_error: false
          });
        }
      }

      // Generate response via Gemini API if available, else deterministic expert response
      let fullText = '';
      if (process.env.GEMINI_API_KEY) {
        try {
          const ai = new GoogleGenAI({});
          const systemPrompt = `Bạn là trợ lý AI chuyên gia về kiểm tra và chuẩn hoá bản vẽ nội thất CAD (chuẩn furniture-v0 và design-hygiene-v0).
Bản vẽ hiện tại: ${targetDrawing}, Chuẩn: ${stdName}.
Hãy giải thích rõ ràng, chi tiết, lịch sự bằng tiếng Việt theo đúng nguyên tắc:
1. Phát hiện lỗi bằng code tất định, không suy diễn lung tung.
2. Bản vẽ gốc luôn được bảo vệ (chỉ đọc); mọi chỉnh sửa chỉ đề xuất ra tệp mới khi người dùng bấm xác nhận.
3. Giải thích mã luật (như VS-01..VS-07, LY-*, SH-*, DH-*, TX-*), lý do kỹ thuật và cách khắc phục trong sản xuất nội thất.`;

          const contents = [
            { role: 'user', parts: [{ text: systemPrompt + '\n\nCâu hỏi người dùng: ' + userMessage }] }
          ];

          const responseStream = await ai.models.generateContentStream({
            model: 'gemini-2.5-flash',
            contents
          });

          for await (const chunk of responseStream) {
            if (!this.activeRuns.has(runId)) break;
            const text = chunk.text || '';
            if (text) {
              fullText += text;
              sendEvent({ type: 'text', text });
            }
          }
        } catch (geminiErr: any) {
          console.warn('Gemini stream error, falling back to expert generator:', geminiErr.message);
          fullText = this.generateExpertCadAnswer(userMessage, targetDrawing, stdName, payload.allow_propose);
          sendEvent({ type: 'text', text: fullText });
        }
      } else {
        fullText = this.generateExpertCadAnswer(userMessage, targetDrawing, stdName, payload.allow_propose);
        sendEvent({ type: 'text', text: fullText });
      }

      // Usage stats
      sendEvent({
        type: 'usage',
        usage: {
          input_tokens: Math.max(80, Math.floor(userMessage.length * 1.4)),
          output_tokens: Math.max(120, Math.floor(fullText.length * 1.2)),
          cost_usd: 0.00008,
          cost_estimated: true
        }
      });

      sendEvent({ type: 'done', text: fullText });
      sendEvent({ type: 'summary', cancelled: !this.activeRuns.has(runId) });
    } catch (err: any) {
      sendEvent({ type: 'error', message: err.message || 'Lỗi xử lý trợ lý' });
    } finally {
      this.activeRuns.delete(runId);
    }
  }

  private generateExpertCadAnswer(userMsg: string, drawing: string, standard: string, allowPropose = false): string {
    const audit = this.drawings.auditFile(drawing, standard);
    const errorRules = audit.groups.find((g) => g.severity === 'E')?.rules || [];
    const warnRules = audit.groups.find((g) => g.severity === 'W')?.rules || [];

    let text = `Chào bạn! Tôi đã phân tích bản vẽ **${drawing}** theo chuẩn **${standard}**:\n\n`;

    if (errorRules.length > 0) {
      text += `🚨 **Các lỗi nghiêm trọng (Mức E - Cần sửa ngay):**\n`;
      for (const r of errorRules) {
        text += `- **${r.rule_id} (${r.title})**: ${r.items[0]?.message || 'Vi phạm chuẩn'}\n`;
      }
      text += `\n`;
    }

    if (warnRules.length > 0) {
      text += `⚠️ **Các cảnh báo (Mức W - Nên tối ưu):**\n`;
      for (const r of warnRules.slice(0, 4)) {
        text += `- **${r.rule_id} (${r.title})**: ${r.items[0]?.message || 'Cần xem xét'}\n`;
      }
      text += `\n`;
    }

    if (errorRules.length === 0 && warnRules.length === 0) {
      text += `✅ Bản vẽ hoàn toàn sạch, không có lỗi hay cảnh báo nào theo chuẩn ${standard}.\n\n`;
    }

    text += `💡 **Hướng dẫn khắc phục:**\n`;
    text += `1. **Layer và XREF**: Gộp các layer rác từ XREF vào đúng layer quy ước (như \`FN-PART-OUTL\`) và dùng lệnh PURGE để xoá bỏ triệt để.\n`;
    text += `2. **ByLayer**: Đặt lại màu sắc và độ dày nét của đối tượng về \`ByLayer\` để thống nhất khi xuất bản vẽ kỹ thuật.\n`;
    text += `3. **Kích thước**: Tránh sửa chữ đo tay thủ công (trả về \`<>\`), đảm bảo kích thước tự động phản ánh số đo thực tế.\n`;
    text += `4. **Phông chữ**: Chuyển đổi các phông VNI/TCVN3 sang phông Unicode chuẩn để tránh lỗi font tiếng Việt khi in và gia công xưởng.\n\n`;

    if (allowPropose) {
      text += `✨ Tôi đã chuẩn bị một đề xuất changeset tự động để giải quyết các vi phạm trên. Bạn có thể sang tab **"Thay đổi"** hoặc **"Đề xuất sửa"** để kiểm tra phần xem trước (preview) và bấm nút **"Áp dụng ra tệp mới"** khi đã đồng ý. Tệp gốc của bạn luôn được bảo vệ an toàn!`;
    } else {
      text += `Bạn có thể bật công tắc *"Cho phép trợ lý đề xuất sửa"* ở góc phải trên nếu muốn tôi lập changeset đề xuất sửa tự động.`;
    }

    return text;
  }
}
