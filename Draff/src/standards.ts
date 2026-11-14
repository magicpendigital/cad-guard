import fs from 'node:fs';
import path from 'node:path';
import yaml from 'yaml';

export interface RuleSpec {
  id: string;
  title: string;
  reads: string;
  kind: string;
  severity: 'E' | 'W' | 'I';
  false_positive_risk: string;
  source: string;
  implemented: boolean;
  enabled: boolean;
  realtime_ok: boolean;
  params?: Record<string, any>;
}

export interface StandardData {
  name: string;
  version: string;
  description: string;
  globals: Record<string, any>;
  rules: RuleSpec[];
}

export interface CompanyProfile {
  name: string;
  version: string;
  standard: string;
  description: string;
  layer_patterns?: {
    allowed?: string[];
    exempt?: string[];
    protected?: string[];
  };
  overrides?: Record<string, Record<string, any>>;
  disabled?: string[];
}

export const FIXABLE_RULES: Record<string, string[]> = {
  'VS-01': ['merge_layers', 'purge_unused'],
  'VS-02': ['purge_unused', 'replace_text_style', 'replace_dim_style'],
  'VS-03': ['move_to_layer'],
  'VS-04': ['set_bylayer'],
  'VS-06': ['clear_dim_text_override'],
  'VS-07': ['replace_text_style'],
  'LY-01': ['rename_layer', 'merge_layers'],
  'LY-03': ['move_to_layer'],
  'LY-04': ['purge_unused'],
  'LY-08': ['set_layer_noplot'],
  'LY-09': ['purge_unused'],
  'TX-01': ['replace_text_style'],
  'TX-08': ['clear_dim_text_override']
};

export const RULE_RATIONALES: Record<string, string> = {
  'VS-01': 'Các layer có chứa ký tự "|" hoặc "$0$" thường là tàn dư từ việc bind external references (XREF) trong AutoCAD. Việc để lại các layer này gây rác bản vẽ, khó quản lý layer trong sản xuất.',
  'VS-02': 'Quá nhiều kiểu chữ và kiểu kích thước trong một bản vẽ dẫn đến sự thiếu đồng bộ, xung đột định dạng hiển thị khi mở trên các máy khác nhau.',
  'VS-03': 'Layer 0 trong AutoCAD được quy ước chỉ dành cho việc tạo block định nghĩa để khi insert có thể thừa hưởng layer của điểm chèn. Vẽ trực tiếp trên layer 0 vi phạm nguyên tắc quản lý bản vẽ.',
  'VS-04': 'Đối tượng không tuân thủ ByLayer gây khó khăn lớn cho việc kiểm soát màu in, độ dày nét và xuất file sang phần mềm CNC/bóc tách vật tư.',
  'VS-05': 'WIPEOUT, IMAGE và OLE làm phình dung lượng file DXF và dễ gây lỗi hiển thị hoặc treo máy cắt CNC khi xử lý đường bao.',
  'VS-06': 'Ghi đè số đo thủ công thay vì để kích thước tự động đo là nguyên nhân hàng đầu dẫn đến sai số khi ra xưởng sản xuất thực tế.',
  'VS-07': 'Các phông chữ TCVN3 hoặc VNI không theo chuẩn Unicode gây lỗi font tiếng Việt khi chuyển đổi dữ liệu và chia sẻ giữa các phòng ban.',
  'LY-01': 'Tên layer không tuân thủ quy ước FN-<KHOA>-<LOAI> khiến hệ thống bóc tách tự động không phân loại được chi tiết gỗ, phụ kiện hoặc đường tim.',
  'LY-03': 'Đối tượng vẽ trực tiếp trên layer 0 ngoài nội dung khối.',
  'LY-04': 'Layer DEFPOINTS hoặc layer chưa khai báo chứa đối tượng hình học sản xuất.',
  'LY-08': 'Layer FN-VPRT chưa được đánh dấu không in (No Plot), có thể bị in đè lên bản vẽ kỹ thuật.',
  'LY-09': 'Layer rỗng không chứa đối tượng nào cần được dọn dẹp bằng PURGE để làm gọn file.',
  'SH-04': 'Mỗi layout sản xuất cần có đúng một khung tên chuẩn theo quy định ISO 7200.',
  'SH-05': 'Các thuộc tính trong khung tên (DWG_NO, TITLE, PROJECT, SCALE, DRAWN_BY...) không được để trống.',
  'DH-01': 'Bản vẽ 2D nhưng có đối tượng mang toạ độ Z khác 0, gây sai lệch khi đo đạc và nội suy.',
  'DH-02': 'Các đoạn thẳng hoặc polyline trùng lặp nhau gây lỗi dao cắt đi cắt lại 2 lần trên máy CNC.',
  'DH-07': 'Đối tượng Proxy Entity không rõ nguồn gốc từ phần mềm CAD bên thứ ba.',
  'DH-09': 'Đường bao chi tiết cần gia công phải là polyline khép kín, hở biên dạng sẽ không lập trình CAM được.',
  'DH-10': 'Các phân đoạn vi mô (dưới zero_tolerance) do thao tác vẽ lỗi cần được làm sạch.',
  'PR-02': 'Chi tiết cấu kiện thiếu nhãn nhận diện PART_ID.',
  'TX-01': 'Kiểu chữ sử dụng không nằm trong danh mục kiểu chữ chuẩn của công ty (STD, TITLE).',
  'TX-08': 'Kích thước bị sửa số đo tay.',
  'VW-01': 'Hình chiếu triển khai thiếu nhãn tên hình chiếu.'
};

export class StandardsManager {
  private standards: Map<string, StandardData> = new Map();
  private companyProfile: CompanyProfile | null = null;
  private departmentsData: any = null;

  constructor() {
    this.loadData();
  }

  private loadData() {
    try {
      const standardsDir = path.resolve(process.cwd(), 'standards');
      if (fs.existsSync(standardsDir)) {
        const files = fs.readdirSync(standardsDir);
        for (const file of files) {
          if (file.endsWith('.yaml') && !file.startsWith('company-profile')) {
            const content = fs.readFileSync(path.join(standardsDir, file), 'utf-8');
            const parsed = yaml.parse(content) as StandardData;
            if (parsed && parsed.name) {
              this.standards.set(parsed.name, parsed);
            }
          }
        }
      }

      const profilePath = path.resolve(standardsDir, 'company-profile.example.yaml');
      if (fs.existsSync(profilePath)) {
        const content = fs.readFileSync(profilePath, 'utf-8');
        this.companyProfile = yaml.parse(content) as CompanyProfile;
      }
    } catch (err) {
      console.warn('Lỗi khi nạp thư mục standards:', err);
    }

    // Nạp departments.json
    try {
      const depPath = path.resolve(process.cwd(), 'packages/core/cadguard/app/departments.json');
      if (fs.existsSync(depPath)) {
        this.departmentsData = JSON.parse(fs.readFileSync(depPath, 'utf-8'));
      }
    } catch {
      // fallback departments
      this.departmentsData = {
        default: 'thiet-ke',
        departments: [
          {
            id: 'thiet-ke',
            name: 'Thiết kế',
            standard: 'design-hygiene-v0',
            description: 'Vệ sinh và nhất quán bản vẽ trước khi giao Kỹ thuật.',
            next: 'ky-thuat'
          },
          {
            id: 'ky-thuat',
            name: 'Kỹ thuật',
            standard: 'furniture-v0',
            description: 'Bản vẽ triển khai: khung tên, layer, chữ, kích thước, chi tiết.',
            next: 'lap-trinh-san-xuat'
          },
          {
            id: 'lap-trinh-san-xuat',
            name: 'Lập trình sản xuất',
            standard: 'furniture-v0',
            description: 'Kiểm trước khi xuất cho máy và xưởng.',
            next: null
          }
        ]
      };
    }
  }

  public getStandardNames(): string[] {
    return Array.from(this.standards.keys()).sort();
  }

  public getStandard(name: string): StandardData | undefined {
    return this.standards.get(name);
  }

  public getProfile(): CompanyProfile | null {
    return this.companyProfile;
  }

  public getDepartments() {
    const list = this.departmentsData?.departments || [];
    const validStandards = this.getStandardNames();
    const formatted = list.map((d: any) => ({
      ...d,
      standard_ok: Boolean(d.standard && validStandards.includes(d.standard))
    }));
    return {
      default: this.departmentsData?.default || 'thiet-ke',
      departments: formatted
    };
  }

  public getRulesTable(standardName: string) {
    const std = this.getStandard(standardName);
    if (!std) {
      throw new Error(`Không tìm thấy chuẩn '${standardName}'`);
    }

    const prof = this.companyProfile;
    const isProfileApplicable = prof && prof.standard === std.name;

    const rows = std.rules.map((rule) => {
      const defaultParams = rule.params || {};
      let effectiveParams = { ...defaultParams };
      let enabled = rule.enabled;

      if (isProfileApplicable && prof) {
        if (prof.overrides && prof.overrides[rule.id]) {
          effectiveParams = { ...effectiveParams, ...prof.overrides[rule.id] };
        }
        if (prof.disabled && prof.disabled.includes(rule.id)) {
          enabled = false;
        }
      }

      const paramsChanged = Object.keys(effectiveParams).filter(
        (k) => JSON.stringify(effectiveParams[k]) !== JSON.stringify(defaultParams[k])
      );

      return {
        id: rule.id,
        title: rule.title,
        severity: rule.severity,
        kind: rule.kind,
        false_positive_risk: rule.false_positive_risk,
        source: rule.source,
        reads: rule.reads,
        implemented: rule.implemented,
        realtime_ok: rule.realtime_ok,
        enabled_default: rule.enabled,
        enabled,
        params_default: defaultParams,
        params_effective: effectiveParams,
        params_changed: paramsChanged,
        fix_ops: FIXABLE_RULES[rule.id] || []
      };
    });

    const globalsDefault = std.globals || {};
    let globalsEffective = { ...globalsDefault };
    if (isProfileApplicable && prof && prof.layer_patterns) {
      if (prof.layer_patterns.allowed) {
        globalsEffective.allowed_layer_patterns = prof.layer_patterns.allowed;
      }
      if (prof.layer_patterns.exempt) {
        globalsEffective.exempt_layer_patterns = prof.layer_patterns.exempt;
      }
    }

    const globalsChanged = Object.keys(globalsEffective).filter(
      (k) => JSON.stringify(globalsEffective[k]) !== JSON.stringify(globalsDefault[k])
    );

    return {
      standard: std.name,
      version: std.version,
      description: std.description,
      profile: isProfileApplicable ? prof?.name : null,
      profile_note: prof && !isProfileApplicable
        ? `Hồ sơ công ty '${prof.name}' viết cho chuẩn ${prof.standard}, không áp cho chuẩn này.`
        : null,
      globals_default: globalsDefault,
      globals_effective: globalsEffective,
      globals_changed: globalsChanged,
      rules: rows,
      counts: {
        total: rows.length,
        implemented: rows.filter((r) => r.implemented).length,
        running: rows.filter((r) => r.implemented && r.enabled).length,
        disabled_by_profile: rows.filter((r) => r.enabled_default && !r.enabled).length,
        params_changed: rows.filter((r) => r.params_changed.length > 0).length
      },
      read_only: true
    };
  }

  public explainRule(ruleId: string, standardName: string) {
    const std = this.getStandard(standardName);
    if (!std) {
      throw new Error(`Không có chuẩn '${standardName}'`);
    }

    const rule = std.rules.find((r) => r.id === ruleId);
    if (!rule) {
      throw new Error(`Mã luật '${ruleId}' không tồn tại trong chuẩn ${standardName}.`);
    }

    const prof = this.companyProfile;
    const isProfileApplicable = prof && prof.standard === std.name;
    const defaultParams = rule.params || {};
    let effectiveParams = { ...defaultParams };
    let profileAdjusted = false;

    if (isProfileApplicable && prof && prof.overrides && prof.overrides[rule.id]) {
      effectiveParams = { ...effectiveParams, ...prof.overrides[rule.id] };
      profileAdjusted = true;
    }

    const fixOps = FIXABLE_RULES[rule.id] || [];

    return {
      rule_id: rule.id,
      standard: std.name,
      title: rule.title,
      severity: rule.severity,
      kind: rule.kind,
      source: rule.source,
      reads: rule.reads,
      rationale: RULE_RATIONALES[rule.id] || `Quy định kiểm soát chất lượng bản vẽ theo tiêu chuẩn ${rule.source}.`,
      default_params: defaultParams,
      effective_params: effectiveParams,
      profile_adjusted: profileAdjusted,
      fixable: fixOps.length > 0,
      fix_ops: fixOps,
      fix_notes: fixOps.length > 0
        ? `Có thể đề xuất thao tác sửa: ${fixOps.join(', ')}.`
        : 'Chưa có thao tác sửa tự động cho luật này; hãy sửa trực tiếp trong phần mềm CAD.'
    };
  }
}
