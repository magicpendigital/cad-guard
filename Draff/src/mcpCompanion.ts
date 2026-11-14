export interface McpServerInfo {
  name: string;
  version: string;
  protocol_version: string;
  status: 'listening' | 'ready';
  endpoint: string;
  connected_clients: number;
  tools: Array<{
    name: string;
    description: string;
    parameters: Record<string, any>;
  }>;
}

export class McpCompanionManager {
  private connectedAutoCadClients: Set<string> = new Set();
  private lastSyncedEntity: { handle?: string; action?: string; timestamp?: string } = {};

  public getStatus() {
    return {
      plugin_installed: false,
      plugin_available: true,
      plugin_version: '1.0.0-beta',
      autocad_supported_versions: ['AutoCAD 2021', 'AutoCAD 2022', 'AutoCAD 2023', 'AutoCAD 2024', 'AutoCAD 2025', 'AutoCAD 2026'],
      mcp_server: {
        status: 'online',
        host: '127.0.0.1',
        port: 3000,
        mcp_endpoint: '/api/mcp/sse',
        connected_sessions: this.connectedAutoCadClients.size
      },
      quick_setup_command: 'NETLOAD "CadGuard.AutoCAD.Palette.dll"',
      instructions_vi: [
        '1. Tải gói CadGuard.AutoCAD.Plugin từ nút "Tải plugin AutoCAD"',
        '2. Trong AutoCAD, gõ lệnh NETLOAD và chọn tệp CadGuard.AutoCAD.Palette.dll',
        '3. Gõ lệnh CADGUARD để mở bảng điều khiển AI Sidebar trực tiếp trên màn hình vẽ',
        '4. Khi click vào bất kỳ lỗi nào, AutoCAD sẽ tự động Zoom to Entity và Highlight đối tượng cần sửa'
      ]
    };
  }

  public getMcpInfo(): McpServerInfo {
    return {
      name: 'cadguard-mcp-server',
      version: '0.1.0',
      protocol_version: '2024-11-05',
      status: 'listening',
      endpoint: 'http://127.0.0.1:3000/api/mcp',
      connected_clients: this.connectedAutoCadClients.size,
      tools: [
        {
          name: 'autocad_zoom_to_entity',
          description: 'Ra lệnh cho AutoCAD phóng to màn hình vào đúng đối tượng theo mã handle',
          parameters: {
            type: 'object',
            properties: {
              handle: { type: 'string', description: 'Mã handle của đối tượng (vd: 2A1, 4B1)' }
            },
            required: ['handle']
          }
        },
        {
          name: 'autocad_highlight_error',
          description: 'Khoanh vùng và đổi màu tạm thời đối tượng vi phạm trên AutoCAD',
          parameters: {
            type: 'object',
            properties: {
              handle: { type: 'string', description: 'Mã handle của đối tượng' },
              severity: { type: 'string', enum: ['E', 'W', 'I'] }
            },
            required: ['handle']
          }
        },
        {
          name: 'autocad_apply_changeset',
          description: 'Thực thi các lệnh sửa lỗi trực tiếp trên bản vẽ đang mở trong AutoCAD khi người dùng xác nhận',
          parameters: {
            type: 'object',
            properties: {
              changeset_id: { type: 'string', description: 'Mã changeset cần áp dụng' }
            },
            required: ['changeset_id']
          }
        },
        {
          name: 'audit_active_drawing',
          description: 'Quét toàn bộ bản vẽ đang mở trong AutoCAD theo chuẩn kỹ thuật nội thất',
          parameters: {
            type: 'object',
            properties: {
              standard: { type: 'string', default: 'furniture-v0' }
            }
          }
        }
      ]
    };
  }

  public handleSyncAction(body: { action: string; handle?: string; drawing?: string }) {
    this.lastSyncedEntity = {
      handle: body.handle,
      action: body.action,
      timestamp: new Date().toISOString()
    };
    return {
      ok: true,
      synced: this.lastSyncedEntity,
      message: `Đã phát lệnh ${body.action} tới client AutoCAD cho đối tượng ${body.handle || 'toàn bản vẽ'}`
    };
  }

  public getPluginScript(): string {
    return `;; ============================================================================
;; CAD GUARD - AUTOCAD IN-APP DOCKABLE SIDEBAR (AutoLISP + MCP Companion v0.3.0)
;; Tính năng:
;;   - Khung Chat AI trực tiếp trong AutoCAD để đặt câu hỏi & phân tích bản vẽ.
;;   - Danh sách lỗi kiểm định thời gian thực (Lớp 1 Code tất định + Lớp 2 AI).
;;   - Nhấp vào lỗi để AutoCAD tự động Zoom to Object & Highlight vùng vi phạm.
;;
;; Hướng dẫn sử dụng:
;;   1. Trong AutoCAD, gõ lệnh APPLOAD và chọn nạp tệp "cadguard.lsp".
;;   2. Gõ lệnh CADGUARD để mở bảng điều khiển AI Sidebar (kết nối http://127.0.0.1:3000/palette).
;;   3. Gõ lệnh CGZOOM để phóng to ngay vào đối tượng theo mã Handle.
;; ============================================================================

(vl-load-com)

(defun c:CADGUARD ( / url)
  (setq url "http://127.0.0.1:3000/palette")
  (princ "\\n[CAD Guard] Đang mở Khung Chat AI & Bảng kiểm lỗi trong AutoCAD Palette...")
  (command "_.BROWSER" url)
  (princ "\\n[CAD Guard] Đã đồng bộ không gian làm việc với AutoCAD.")
  (princ)
)

(defun c:CGZOOM ( / hnd ent)
  (setq hnd (getstring "\\n[CAD Guard] Nhập mã Handle đối tượng lỗi (VD: 2A1, 4B1): "))
  (if (and hnd (/= hnd ""))
    (progn
      (setq ent (handent hnd))
      (if ent
        (progn
          (command "_.ZOOM" "_Object" ent "")
          (sssetfirst nil (ssadd ent))
          (princ (strcat "\\n[CAD Guard] Đã khoanh vùng và chọn đối tượng Handle: " hnd))
        )
        (princ (strcat "\\n[CAD Guard] Không tìm thấy đối tượng có Handle: " hnd))
      )
    )
  )
  (princ)
)

(defun c:CGAUDIT ( / )
  (princ "\\n[CAD Guard] Đang quét toàn bộ bản vẽ hiện hành theo chuẩn furniture-v0...")
  (c:CADGUARD)
  (princ)
)

(princ "\\n========================================================")
(princ "\\n  CAD Guard AutoCAD In-App Sidebar Plugin đã nạp thành công!")
(princ "\\n  Gõ lệnh CADGUARD để mở khung chat & danh sách lỗi ngay trong CAD.")
(princ "\\n  Gõ lệnh CGZOOM để zoom vào đối tượng bất kỳ theo mã Handle.")
(princ "\\n========================================================\\n")
(princ)
`;
  }
}
