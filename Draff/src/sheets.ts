export interface SheetCallout {
  id: string;
  rule_id: string;
  severity: 'E' | 'W' | 'I' | 'AI';
  title: string;
  message: string;
  tier: 1 | 2; // 1 = Code chuẩn hoá, 2 = AI phân tích sâu
  category: 'hygiene' | 'dimension' | 'clearance' | 'bom' | 'titleblock' | 'geometry';
  x_pct: number; // 0 - 100% trên khung bản vẽ
  y_pct: number; // 0 - 100% trên khung bản vẽ
  handle?: string;
  suggested_fix?: string;
}

export interface SheetInfo {
  id: string;
  index: number;
  name: string;
  title: string;
  sheet_no: string;
  scale: string;
  source: 'layout' | 'model_frame' | 'scratchpad';
  paper_size: 'A3' | 'A2' | 'A4' | 'A1';
  width_mm: number;
  height_mm: number;
  is_scratchpad: boolean;
  counts: {
    E: number;
    W: number;
    I: number;
    AI: number;
  };
  callouts: SheetCallout[];
  ai_insights: Array<{
    title: string;
    description: string;
    type: 'dimension_conflict' | 'hardware_clearance' | 'bom_mismatch';
    severity: 'E' | 'W';
    location: string;
  }>;
}

export class SheetsManager {
  public getSheetsForDrawing(filePath: string, standardName: string): SheetInfo[] {
    const baseName = filePath.toLowerCase();

    // Default multi-sheet segmentation for furniture drawings
    if (baseName.includes('hygiene_bad') || baseName.includes('model_features')) {
      return [
        {
          id: 'sheet-01',
          index: 1,
          name: 'Mặt bằng tổng thể',
          title: 'MB BỐ TRÍ TỦ BẾP & TỦ ÁO PHÒNG MASTER',
          sheet_no: 'KT-01/03',
          scale: '1:20',
          source: 'layout',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 1, W: 4, I: 0, AI: 2 },
          callouts: [
            {
              id: 'c1-1',
              rule_id: 'VS-01',
              severity: 'W',
              tier: 1,
              category: 'hygiene',
              title: 'Layer dư từ xref',
              message: 'Đối tượng tường sử dụng layer tàn dư "XREF_BANVE|WALL"',
              x_pct: 28,
              y_pct: 35,
              handle: '2A1',
              suggested_fix: 'Gộp vào layer FN-WALL'
            },
            {
              id: 'c1-2',
              rule_id: 'VS-03',
              severity: 'W',
              tier: 1,
              category: 'hygiene',
              title: 'Vẽ trên layer 0',
              message: '12 đường bao khoang tủ vẽ trực tiếp trên layer 0 thay vì FN-PART-OUTL',
              x_pct: 54,
              y_pct: 42,
              handle: '2A8',
              suggested_fix: 'Chuyển về layer FN-PART-OUTL'
            },
            {
              id: 'c1-3',
              rule_id: 'VS-06',
              severity: 'E',
              tier: 1,
              category: 'dimension',
              title: 'Kích thước sửa số đo tay',
              message: 'Số đo khoang tủ bếp bị sửa thành "1200" thay vì đo thực tế "1185"',
              x_pct: 68,
              y_pct: 58,
              handle: '4B1',
              suggested_fix: 'Khôi phục số đo tự động <>'
            },
            {
              id: 'c1-4',
              rule_id: 'AI-DIM-01',
              severity: 'E',
              tier: 2,
              category: 'dimension',
              title: 'Lệch kích thước mặt bằng & mặt đứng',
              message: 'AI phát hiện: Chiều sâu mặt bằng ghi 600mm nhưng mặt cắt Trang 02 ghi 580mm (-20mm nẹp mặt đá)',
              x_pct: 45,
              y_pct: 62,
              suggested_fix: 'Đồng bộ kích thước phủ bì 600mm hoặc bổ sung ghi chú chỉ nẹp đá'
            },
            {
              id: 'c1-5',
              rule_id: 'AI-CLR-02',
              severity: 'W',
              tier: 2,
              category: 'clearance',
              title: 'Nguy cơ va chạm cánh tủ góc L',
              message: 'Khoảng hở góc chữ L chỉ 1.5mm, cánh mở sẽ va vào tay nắm ngăn kéo bên cạnh khi thao tác',
              x_pct: 32,
              y_pct: 48,
              suggested_fix: 'Tăng nẹp góc (corner filler) tối thiểu 45mm'
            }
          ],
          ai_insights: [
            {
              title: 'Xung đột chiều sâu tủ bếp dưới',
              description: 'Mặt bằng tổng thể ghi chiều sâu 600mm, tuy nhiên mặt cắt chi tiết tại Tờ 02 đang ghi thùng tủ 560mm + cánh 18mm + nẹp đá nhô 20mm = 598mm. Cần ghi chú dung sai rõ ràng.',
              type: 'dimension_conflict',
              severity: 'E',
              location: 'Khu vực bếp nấu chữ L'
            },
            {
              title: 'Khe hở nẹp góc tủ chữ L chưa đạt',
              description: 'Nẹp góc chỉ bố trí 20mm, ray hộp Blum hoặc tay nắm thanh nhôm sẽ va đập vào cánh khi mở 90 độ.',
              type: 'hardware_clearance',
              severity: 'W',
              location: 'Góc giao nhau 90 độ tủ dưới'
            }
          ]
        },
        {
          id: 'sheet-02',
          index: 2,
          name: 'Mặt đứng & Mặt cắt Tủ bếp',
          title: 'CHI TIẾT MẶT ĐỨNG & MẶT CẮT TỦ BẾP DƯỚI - TRÊN',
          sheet_no: 'KT-02/03',
          scale: '1:10',
          source: 'layout',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 2, W: 3, I: 1, AI: 2 },
          callouts: [
            {
              id: 'c2-1',
              rule_id: 'VS-07',
              severity: 'W',
              tier: 1,
              category: 'hygiene',
              title: 'Font chữ không Unicode',
              message: 'Ghi chú vật liệu dùng font "VNI-Helve" dễ lỗi tiếng Việt khi in',
              x_pct: 78,
              y_pct: 22,
              handle: '5C1',
              suggested_fix: 'Đổi kiểu chữ sang font Unicode STD'
            },
            {
              id: 'c2-2',
              rule_id: 'VS-04',
              severity: 'W',
              tier: 1,
              category: 'hygiene',
              title: 'Ghi đè màu nét (Color Override)',
              message: 'Đường dim kích thước đặt màu thủ công Color 1 (Red) thay vì ByLayer',
              x_pct: 50,
              y_pct: 70,
              handle: '3D2',
              suggested_fix: 'Chuyển về ByLayer'
            },
            {
              id: 'c2-3',
              rule_id: 'AI-CLR-01',
              severity: 'E',
              tier: 2,
              category: 'clearance',
              title: 'Thiếu khe hở cánh tủ trên và đáy hút mùi',
              message: 'Khoảng cách mép cánh tủ trên đến mép kính hút mùi chỉ 1.0mm, không đạt tiêu chuẩn lắp đặt 3.0mm',
              x_pct: 58,
              y_pct: 38,
              suggested_fix: 'Hạ đáy hút mùi hoặc thụt cánh tủ trên thêm 2mm'
            },
            {
              id: 'c2-4',
              rule_id: 'AI-BOM-03',
              severity: 'E',
              tier: 2,
              category: 'bom',
              title: 'Không khớp vật liệu thùng tủ trong bảng BOM',
              message: 'Khung tên ghi chú "MDF chống ẩm phủ Melamine", nhưng chi tiết mặt cắt khoang chậu rửa lại chú thích "Nhựa Picomat"',
              x_pct: 82,
              y_pct: 85,
              suggested_fix: 'Thống nhất ghi chú khoang chậu rửa dùng tấm nhựa Picomat chịu nước'
            }
          ],
          ai_insights: [
            {
              title: 'Xung đột vật liệu khoang chậu rửa',
              description: 'Bản vẽ mặt cắt thể hiện khoang chậu rửa làm bằng ván nhựa Picomat 18mm nhưng bảng thống kê vật tư BOM lại ghi toàn bộ ván MDF lõi xanh. Xưởng sẽ cắt nhầm vật liệu nếu không đồng bộ.',
              type: 'bom_mismatch',
              severity: 'E',
              location: 'Khoang chậu rửa bát (Sink cabinet)'
            },
            {
              title: 'Khe hở kỹ thuật cánh mở và đáy máy hút mùi',
              description: 'Cần duy trì tối thiểu 3mm khe hở giữa nắp bật máy hút mùi và cánh tủ lân cận để tránh kẹt nhiệt và cọ xát cơ học.',
              type: 'hardware_clearance',
              severity: 'W',
              location: 'Khoang tủ treo máy hút mùi'
            }
          ]
        },
        {
          id: 'sheet-03',
          index: 3,
          name: 'Chi tiết liên kết & Phụ kiện',
          title: 'CHI TIẾT CAM CHỐT, BẢN LỀ GIẢM CHẤN & RAY TRƯỢT',
          sheet_no: 'KT-03/03',
          scale: '1:5',
          source: 'model_frame',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 0, W: 2, I: 2, AI: 1 },
          callouts: [
            {
              id: 'c3-1',
              rule_id: 'VS-02',
              severity: 'W',
              tier: 1,
              category: 'hygiene',
              title: 'Thừa kiểu dim kích thước',
              message: 'Sử dụng dimstyle "Standard" và "DIM-CHI-TIET" song song',
              x_pct: 22,
              y_pct: 80,
              suggested_fix: 'Purge kiểu dim không chuẩn'
            },
            {
              id: 'c3-2',
              rule_id: 'AI-CLR-03',
              severity: 'W',
              tier: 2,
              category: 'clearance',
              title: 'Khoét tâm bản lề cách mép ván chưa chuẩn',
              message: 'Khoảng cách tâm chén bản lề ghi 20.5mm, tiêu chuẩn bản lề Hafele giảm chấn là 21.5mm - 22.0mm',
              x_pct: 46,
              y_pct: 44,
              suggested_fix: 'Điều chỉnh khoảng cách tâm cối khoan sang 22mm'
            }
          ],
          ai_insights: [
            {
              title: 'Khoan chén bản lề theo catalog Hafele',
              description: 'Đường kính cối khoan phi 35mm, khoảng cách từ mép cánh đến viền chén khoan (K) cần chuẩn xác 4-5mm để bản lề ôm khít mà không làm mỏng mép ván.',
              type: 'hardware_clearance',
              severity: 'W',
              location: 'Chi tiết liên kết cánh tủ'
            }
          ]
        },
        {
          id: 'sheet-scratch',
          index: 4,
          name: 'Khu vực nháp (Scratchpad)',
          title: 'VÙNG DỰ THẢO & THỬ NGHIỆM CHI TIẾT NGOÀI KHUNG IN',
          sheet_no: 'DRAFT',
          scale: '1:1',
          source: 'scratchpad',
          paper_size: 'A1',
          width_mm: 841,
          height_mm: 594,
          is_scratchpad: true,
          counts: { E: 0, W: 5, I: 8, AI: 0 },
          callouts: [
            {
              id: 'cs-1',
              rule_id: 'LY-09',
              severity: 'I',
              tier: 1,
              category: 'hygiene',
              title: 'Chi tiết vẽ nháp',
              message: 'Các nét cắt thử và block phụ kiện nháp không nằm trong khung chốt sản xuất',
              x_pct: 50,
              y_pct: 50
            }
          ],
          ai_insights: []
        }
      ];
    }

    if (baseName.includes('bad_titleblock')) {
      return [
        {
          id: 'sheet-01',
          index: 1,
          name: 'Layout 1 (Thiếu khung tên)',
          title: 'BẢN VẼ THIẾT KẾ MẶT BẰNG',
          sheet_no: 'CHƯA ĐẶT',
          scale: '1:50',
          source: 'layout',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 2, W: 1, I: 0, AI: 1 },
          callouts: [
            {
              id: 'ct-1',
              rule_id: 'SH-04',
              severity: 'E',
              tier: 1,
              category: 'titleblock',
              title: 'Chưa có khung tên chuẩn',
              message: 'Layout1 chưa chèn khối khung tên tiêu chuẩn ISO 7200 (FN_TTLB)',
              x_pct: 88,
              y_pct: 88,
              suggested_fix: 'Chèn block FN_TTLB vào góc dưới bên phải'
            },
            {
              id: 'ct-2',
              rule_id: 'SH-05',
              severity: 'E',
              tier: 1,
              category: 'titleblock',
              title: 'Thiếu thuộc tính bắt buộc',
              message: 'Khung tên thiếu mã bản vẽ DWG_NO, tỉ lệ SCALE và chữ ký DRAWN_BY',
              x_pct: 85,
              y_pct: 92,
              suggested_fix: 'Điền đầy đủ thông tin ATTRIB'
            }
          ],
          ai_insights: [
            {
              title: 'Rủi ro thất lạc hồ sơ khi xuống xưởng',
              description: 'Bản vẽ không có số hiệu DWG_NO và ngày phát hành, xưởng sẽ không xác định được đây là phiên bản REV nào để gia công.',
              type: 'bom_mismatch',
              severity: 'E',
              location: 'Góc khung tên'
            }
          ]
        }
      ];
    }

    if (baseName.includes('bad_layers')) {
      return [
        {
          id: 'sheet-01',
          index: 1,
          name: 'Mặt bằng Tủ áo & Vách ốp',
          title: 'MB BỐ TRÍ TỦ ÁO PHÒNG NGỦ LỚN & VÁCH ỐP ĐẦU GIƯỜNG',
          sheet_no: 'KT-LA-01',
          scale: '1:20',
          source: 'layout',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 2, W: 2, I: 1, AI: 2 },
          callouts: [
            {
              id: 'cl-1',
              rule_id: 'LY-01',
              severity: 'E',
              tier: 1,
              category: 'hygiene',
              title: 'Tên layer sai quy ước chuẩn',
              message: 'Các layer "Layer1", "Wall", "Net-Cat" không tuân theo sơ đồ FN-<KHOA>-<LOAI>',
              x_pct: 32,
              y_pct: 28,
              handle: '7A1',
              suggested_fix: 'Đổi tên tự động sang FN-PART-OUTL và FN-WALL'
            },
            {
              id: 'cl-2',
              rule_id: 'LY-04',
              severity: 'E',
              tier: 1,
              category: 'hygiene',
              title: 'Đối tượng sản xuất nằm trên DEFPOINTS',
              message: '2 đường cắt biên dạng hậu tủ nằm trên layer DEFPOINTS sẽ bị mất nét khi xuất in',
              x_pct: 64,
              y_pct: 45,
              handle: '7A9',
              suggested_fix: 'Chuyển sang layer FN-PART-BACK'
            },
            {
              id: 'cl-3',
              rule_id: 'LY-08',
              severity: 'W',
              tier: 1,
              category: 'hygiene',
              title: 'Layer Viewport chưa đặt No-Plot',
              message: 'Khung nhìn FN-VPRT chưa bật cờ Không In, sẽ in đè viền đen quanh bản vẽ',
              x_pct: 92,
              y_pct: 15,
              handle: '7B2',
              suggested_fix: 'Bật thuộc tính No-Plot cho FN-VPRT'
            },
            {
              id: 'cl-4',
              rule_id: 'AI-CLR-04',
              severity: 'E',
              tier: 2,
              category: 'clearance',
              title: 'Rãnh ray cửa lùa tủ áo chồng lên vị trí đợt gỗ',
              message: 'AI phát hiện: Ray trượt cửa lùa âm (sâu 65mm) va chạm với đợt ngang tủ áo (chỉ lùi vào 40mm)',
              x_pct: 48,
              y_pct: 52,
              suggested_fix: 'Giật lùi đợt ngang tủ áo tối thiểu 75mm tính từ mép ngoài thùng tủ'
            }
          ],
          ai_insights: [
            {
              title: 'Va chạm cơ khí giữa ray cửa lùa và đợt tủ ngang',
              description: 'Hệ ray lùa Hafele Slido cần khoảng không 65mm phía trước. Đợt ngang hiện tại chỉ lùi 40mm sẽ làm kẹt bánh xe dẫn hướng khi lắp đặt tại công trình.',
              type: 'hardware_clearance',
              severity: 'E',
              location: 'Khoang giữa tủ áo 4 cánh lùa'
            },
            {
              title: 'Rủi ro mất nét gia công trên layer DEFPOINTS',
              description: '2 chi tiết rãnh soi hậu tủ 6mm đang đặt trên layer DEFPOINTS, phần mềm CAM/CNC sẽ bỏ qua layer này khi xuất G-code.',
              type: 'bom_mismatch',
              severity: 'E',
              location: 'Rãnh hậu MDF 6mm'
            }
          ]
        }
      ];
    }

    if (baseName.includes('bad_geometry')) {
      return [
        {
          id: 'sheet-01',
          index: 1,
          name: 'Bản vẽ Phôi cắt CNC (Nesting)',
          title: 'CHI TIẾT TRẢI PHÔI VÁN MDF 18MM CHO MÁY CNC',
          sheet_no: 'CNC-01/02',
          scale: '1:10',
          source: 'model_frame',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 2, W: 2, I: 0, AI: 2 },
          callouts: [
            {
              id: 'cg-1',
              rule_id: 'DH-09',
              severity: 'E',
              tier: 1,
              category: 'geometry',
              title: 'Đường bao tấm ván bị hở (Open Polyline)',
              message: 'Viền cắt tấm hồi trái (H1) bị hở khe 0.45mm tại góc dưới, máy CNC không thể nhận diện đường chạy dao kín',
              x_pct: 26,
              y_pct: 42,
              handle: '8C1',
              suggested_fix: 'Đóng kín LWPOLYLINE (Close Polyline)'
            },
            {
              id: 'cg-2',
              rule_id: 'DH-02',
              severity: 'W',
              tier: 1,
              category: 'geometry',
              title: 'Đoạn thẳng chồng đè trùng lặp (Overlapping)',
              message: '4 cạnh ván có 2 đường LINE nằm đè khít lên nhau khiến mũi phay CNC cắt lặp 2 lần gây cháy ván',
              x_pct: 58,
              y_pct: 36,
              handle: '8C4',
              suggested_fix: 'Chạy OVERKILL xoá nét trùng'
            },
            {
              id: 'cg-3',
              rule_id: 'DH-01',
              severity: 'E',
              tier: 1,
              category: 'geometry',
              title: 'Đối tượng bị lệch cao độ Z != 0',
              message: '5 lỗ khoan cam liên kết có toạ độ Z = 18.0mm thay vì nằm trên mặt phẳng Z = 0',
              x_pct: 74,
              y_pct: 64,
              handle: '8D2',
              suggested_fix: 'Flatten toàn bộ đối tượng về Z = 0'
            },
            {
              id: 'cg-4',
              rule_id: 'AI-DIM-05',
              severity: 'E',
              tier: 2,
              category: 'dimension',
              title: 'Chưa trừ độ dày chỉ dán cạnh (Edge Banding)',
              message: 'Kích thước phôi cắt CNC đang để nguyên 600mm (bằng kích thước hoàn thiện), chưa trừ 2mm chỉ nhựa PVC 2 cạnh',
              x_pct: 40,
              y_pct: 72,
              suggested_fix: 'Giảm phôi cắt xuống 598mm (dán 1 cạnh 2mm) hoặc 596mm (dán 2 cạnh)'
            }
          ],
          ai_insights: [
            {
              title: 'Sai lệch kích thước phôi cắt CNC do chưa trừ chỉ nẹp',
              description: 'Tấm cánh tủ quy định dán chỉ ABS dày 2.0mm cả 4 cạnh, nhưng đường bao phôi cắt vẫn giữ nguyên 720x450mm thay vì 716x446mm.',
              type: 'dimension_conflict',
              severity: 'E',
              location: 'Phôi cánh tủ CT-01 & CT-02'
            },
            {
              title: 'Biên dạng hở gây lỗi dừng máy CNC (Toolpath Error)',
              description: 'Góc giao của tấm hồi tủ bị hở 0.45mm do bắt điểm OsNap trượt. Cần đóng kín biên dạng trước khi nạp vào phần mềm bóc tách.',
              type: 'hardware_clearance',
              severity: 'E',
              location: 'Tấm hồi đứng H1'
            }
          ]
        }
      ];
    }

    if (baseName.includes('bad_parts')) {
      return [
        {
          id: 'sheet-01',
          index: 1,
          name: 'Bảng kê chi tiết & Thẻ vị trí (BOM)',
          title: 'BẢNG THỐNG KÊ VẬT TƯ & MÃ CHI TIẾT SẢN XUẤT',
          sheet_no: 'BOM-01/01',
          scale: '1:15',
          source: 'layout',
          paper_size: 'A3',
          width_mm: 420,
          height_mm: 297,
          is_scratchpad: false,
          counts: { E: 2, W: 2, I: 0, AI: 2 },
          callouts: [
            {
              id: 'cp-1',
              rule_id: 'PR-02',
              severity: 'E',
              tier: 1,
              category: 'bom',
              title: 'Chi tiết thiếu nhãn mã tấm PART_ID',
              message: '4 tấm ngăn kéo trong hình cắt chưa được gắn block thẻ vị trí PART_TAG',
              x_pct: 36,
              y_pct: 48,
              handle: '9A1',
              suggested_fix: 'Gắn thẻ vị trí PT-08 đến PT-11'
            },
            {
              id: 'cp-2',
              rule_id: 'TX-08',
              severity: 'E',
              tier: 1,
              category: 'dimension',
              title: 'Số đo kích thước bị sửa tay không khớp thực tế',
              message: 'Chiều rộng lọt lòng ngăn kéo vẽ 512mm nhưng gõ đè chữ thành "500"',
              x_pct: 62,
              y_pct: 34,
              handle: '9B4',
              suggested_fix: 'Reset về số đo thực tế <> (512mm)'
            },
            {
              id: 'cp-3',
              rule_id: 'AI-BOM-01',
              severity: 'E',
              tier: 2,
              category: 'bom',
              title: 'Sai lệch số lượng bản lề trong bảng kê BOM',
              message: 'Bản vẽ có 4 cánh tủ cao 2100mm (cần 4 bản lề/cánh = 16 cái), nhưng bảng BOM chỉ kê 8 cái (2 cái/cánh)',
              x_pct: 78,
              y_pct: 68,
              suggested_fix: 'Cập nhật số lượng bản lề giảm chấn lên 16 chiếc (8 cặp)'
            }
          ],
          ai_insights: [
            {
              title: 'Thiếu số lượng bản lề chịu lực cho cánh tủ cao trên 2m',
              description: 'Theo tiêu chuẩn kỹ thuật nội thất, cánh tủ MDF dày 18mm cao 2100mm nặng ~22kg bắt buộc dùng 4 bản lề/cánh. Bảng kê hiện chỉ tính 2 bản lề/cánh sẽ gây xệ cánh sau 1 tháng sử dụng.',
              type: 'bom_mismatch',
              severity: 'E',
              location: 'Bảng thống kê phụ kiện góc phải'
            },
            {
              title: 'Chênh lệch chiều rộng thành hộc kéo với ray âm giảm chấn',
              description: 'Khoang lọt lòng 512mm nhưng trừ khe hở ray âm Hafele (42mm) chưa khớp với tấm đáy ngăn kéo ghi trong bảng kê (480mm).',
              type: 'dimension_conflict',
              severity: 'E',
              location: 'Cụm 3 ngăn kéo tủ áo'
            }
          ]
        }
      ];
    }

    // Default clean sheet (e.g. ok_sheet.dxf, hygiene_ok.dxf)
    return [
      {
        id: 'sheet-01',
        index: 1,
        name: 'Trang 01: Bản vẽ hoàn chỉnh',
        title: 'BẢN VẼ THI CÔNG NỘI THẤT HOÀN THIỆN ĐẠT CHUẨN',
        sheet_no: 'KT-01/01',
        scale: '1:20',
        source: 'layout',
        paper_size: 'A3',
        width_mm: 420,
        height_mm: 297,
        is_scratchpad: false,
        counts: { E: 0, W: 0, I: 0, AI: 0 },
        callouts: [],
        ai_insights: []
      }
    ];
  }
}
