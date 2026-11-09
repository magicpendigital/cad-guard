// CadGuard.Acad — plugin AutoCAD cho cad-guard (hướng D, CEO mở cổng 09/11/2026).
//
//   CGBANG  mở/ẩn bảng cad-guard neo cạnh màn hình: giao diện `cadguard app` ở chế độ bảng (Lỗi, Trợ lý, Hướng dẫn)
//           cho bản vẽ đang mở. Plugin tự chạy `python -m cadguard app` (chỉ 127.0.0.1) và đọc địa chỉ có mã phiên
//           từ đầu ra của tiến trình: mã phiên KHÔNG ghi ra tệp.
//   CGGHIM  hiện/ẩn ghim số lỗi tạm thời (TransientManager): chỉ vẽ trên màn hình, KHÔNG thêm đối tượng, không lưu
//           vào DWG; số và vòng tròn tính theo điểm ảnh nên giữ cùng cỡ khi phóng/kéo; ghim gần nhau gộp thành "×n".
//
// Không sửa, không lưu bản vẽ. Mọi chỉnh sửa vẫn đi đường changeset của cad-guard (xem trước, xác nhận, tệp mới).
// Thư mục làm việc lấy từ biến CadGuardFolder (đặt bằng CGTHUMUC của cadguard.lsp).

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.GraphicsInterface;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.Windows;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: ExtensionApplication(typeof(CadGuard.Acad.Plugin))]
[assembly: CommandClass(typeof(CadGuard.Acad.Commands))]

namespace CadGuard.Acad
{
    public class Plugin : IExtensionApplication
    {
        public void Initialize()
        {
            Util.Say("Đã nạp plugin cad-guard: CGBANG (bảng cad-guard), CGGHIM (ghim lỗi). Gõ CGHELP để xem hướng dẫn.");
        }

        public void Terminate()
        {
            Marks.Clear();
            AppHost.Stop();
        }
    }

    internal static class Util
    {
        [DllImport("accore.dll", CharSet = CharSet.Unicode, CallingConvention = CallingConvention.Cdecl, EntryPoint = "acedGetEnv")]
        private static extern int acedGetEnv(string name, StringBuilder value, nuint size);

        public static void Say(string msg)
        {
            var doc = AcApp.DocumentManager.MdiActiveDocument;
            doc?.Editor.WriteMessage("\n[cad-guard] " + msg);
        }

        /// <summary>Biến môi trường AutoCAD (getenv của AutoLISP): CadGuardFolder do CGTHUMUC đặt.</summary>
        public static string? GetEnv(string name)
        {
            try
            {
                var sb = new StringBuilder(1024);
                if (acedGetEnv(name, sb, (nuint)sb.Capacity) == 5100) // RTNORM
                {
                    var v = sb.ToString().Trim();
                    return v.Length > 0 ? v : null;
                }
            }
            catch (System.Exception) { }
            return null;
        }

        public static string? Workspace()
        {
            var f = GetEnv("CadGuardFolder");
            return f != null && Directory.Exists(f) ? f : null;
        }

        public static string DwgStem(Document doc) => Path.GetFileNameWithoutExtension(doc.Name);
    }

    /// <summary>Tiến trình `cadguard app` riêng của phiên AutoCAD này (chỉ nghe 127.0.0.1).</summary>
    internal static class AppHost
    {
        private static Process? _proc;
        private static string? _url;
        private static string? _workspace;
        private static readonly Regex UrlRe = new(@"http://127\.0\.0\.1:\d+/\?t=[A-Za-z0-9_\-]+", RegexOptions.Compiled);

        private sealed class Config
        {
            public string? python { get; set; }
            public string? pythonpath { get; set; }
        }

        private static Config LoadConfig()
        {
            // cadguard-acad.json cạnh DLL (do scripts/build_acad_plugin.py ghi): đường dẫn Python, không có bí mật.
            var dir = Path.GetDirectoryName(typeof(AppHost).Assembly.Location) ?? ".";
            var path = Path.Combine(dir, "cadguard-acad.json");
            try
            {
                if (File.Exists(path))
                    return JsonSerializer.Deserialize<Config>(File.ReadAllText(path, Encoding.UTF8)) ?? new Config();
            }
            catch (System.Exception) { }
            return new Config();
        }

        public static string? Url(string workspace, out string? error)
        {
            error = null;
            if (_proc != null && !_proc.HasExited && _url != null &&
                string.Equals(_workspace, workspace, StringComparison.OrdinalIgnoreCase))
                return _url;
            Stop();
            var cfg = LoadConfig();
            var python = cfg.python ?? Environment.GetEnvironmentVariable("CADGUARD_PYTHON") ?? "python";
            var psi = new ProcessStartInfo(python)
            {
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            foreach (var a in new[] { "-m", "cadguard", "app", "--workspace", workspace, "--no-browser", "--port", "0" })
                psi.ArgumentList.Add(a);
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment["PYTHONIOENCODING"] = "utf-8";
            if (!string.IsNullOrEmpty(cfg.pythonpath)) psi.Environment["PYTHONPATH"] = cfg.pythonpath;
            string? found = null;
            var ready = new ManualResetEventSlim(false);
            var err = new StringBuilder();
            try
            {
                var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
                p.OutputDataReceived += (_, e) =>
                {
                    if (e.Data == null) { ready.Set(); return; }
                    var m = UrlRe.Match(e.Data);
                    if (m.Success && found == null) { found = m.Value; ready.Set(); }
                };
                p.ErrorDataReceived += (_, e) => { if (e.Data != null && err.Length < 2000) err.AppendLine(e.Data); };
                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                _proc = p;
            }
            catch (System.Exception)
            {
                error = "Không chạy được Python để mở cad-guard. Kiểm cadguard-acad.json cạnh CadGuard.Acad.dll hoặc biến CADGUARD_PYTHON.";
                return null;
            }
            if (!ready.Wait(TimeSpan.FromSeconds(45)) || found == null)
            {
                var tail = err.ToString().Trim();
                Stop();
                error = "cad-guard app không khởi động được." + (tail.Length > 0 ? " " + LastLine(tail) : "");
                return null;
            }
            _url = found;
            _workspace = workspace;
            return _url;
        }

        private static string LastLine(string s)
        {
            var lines = s.Split('\n').Select(x => x.Trim()).Where(x => x.Length > 0).ToArray();
            return lines.Length > 0 ? lines[^1] : "";
        }

        public static void Stop()
        {
            try { if (_proc != null && !_proc.HasExited) _proc.Kill(entireProcessTree: true); }
            catch (System.Exception) { }
            _proc = null;
            _url = null;
            _workspace = null;
        }
    }

    public class Commands
    {
        private static PaletteSet? _ps;
        private static string? _panelKey;

        [CommandMethod("CGBANG", CommandFlags.Session)]
        public void Bang()
        {
            var doc = AcApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return;
            var ws = Util.Workspace();
            if (ws == null) { Util.Say("Chưa đặt thư mục làm việc. Chạy CGTHUMUC trước (nạp cadguard.lsp)."); return; }
            var stem = Util.DwgStem(doc);
            var key = ws + "|" + stem;
            if (_ps != null && _ps.Visible && _panelKey == key) { _ps.Visible = false; return; }
            Util.Say("Đang mở cad-guard…");
            var url = AppHost.Url(ws, out var error);
            if (url == null) { Util.Say(error ?? "Không mở được cad-guard."); return; }
            if (_ps == null)
            {
                _ps = new PaletteSet("cad-guard", new Guid("6f1f6a52-3c1e-4c8e-9a51-0c4d2b8f7a11"))
                {
                    Style = PaletteSetStyles.ShowAutoHideButton | PaletteSetStyles.ShowCloseButton | PaletteSetStyles.ShowPropertiesMenu,
                    MinimumSize = new System.Drawing.Size(320, 400),
                };
            }
            while (_ps.Count > 0) _ps.Remove(0);
            _ps.Add("cad-guard", new Uri(url + "&panel=1&dwg=" + Uri.EscapeDataString(stem)));
            _panelKey = key;
            var first = !_ps.Visible && _ps.Dock == DockSides.None;
            _ps.Visible = true;
            if (first)
            {
                try { _ps.Dock = DockSides.Right; _ps.Size = new System.Drawing.Size(460, 800); } catch (System.Exception) { }
            }
        }

        [CommandMethod("CGGHIM")]
        public void Ghim()
        {
            var doc = AcApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return;
            if (Marks.IsOn(doc)) { Marks.Clear(); Util.Say("Đã ẩn ghim lỗi."); return; }
            var ws = Util.Workspace();
            if (ws == null) { Util.Say("Chưa đặt thư mục làm việc. Chạy CGTHUMUC trước."); return; }
            var report = Path.Combine(ws, ".cadguard", "reports", Util.DwgStem(doc) + ".json");
            if (!File.Exists(report))
            {
                Util.Say("Chưa có báo cáo cho bản vẽ này. Chạy CGXUAT và kiểm `cadguard watch` đang chạy.");
                return;
            }
            Marks.Show(doc, report);
        }
    }

    /// <summary>Ghim lỗi tạm thời: chỉ vẽ trên màn hình (TransientManager), không đụng cơ sở dữ liệu bản vẽ.</summary>
    internal static class Marks
    {
        private sealed record Group(int No, string RuleId, string Severity, List<Extents3d> Boxes);

        private static readonly List<Drawable> Drawn = new();
        private static Document? _doc;
        private static List<Group> _groups = new();
        private static (double size, Point3d ctr) _view;
        private static bool _hooked;
#if CGDEV
        private static bool _dbgIdle;
#endif

        private const double R = 11, GAP = 16, MERGE = 30, MIN_RING = 14; // điểm ảnh màn hình

        // Document là lớp bọc: mỗi lần lấy có thể là đối tượng khác, nên so theo con trỏ gốc.
        private static bool Same(Document? a, Document? b) => a != null && b != null && a.UnmanagedObject == b.UnmanagedObject;

        public static bool IsOn(Document doc) => Same(_doc, doc) && Drawn.Count > 0;

        public static void Show(Document doc, string reportPath)
        {
            Clear();
            List<Group> groups;
            int noBox;
            try { groups = Load(doc, reportPath, out noBox); }
            catch (System.Exception) { Util.Say("Báo cáo hỏng hoặc sai dạng. Chạy CGXUAT lại."); return; }
            _doc = doc;
            _groups = groups;
            if (!_hooked) { AcApp.Idle += OnIdle; AcApp.DocumentManager.DocumentToBeDeactivated += (_, _) => Clear(); _hooked = true; }
            Draw();
            var ed = doc.Editor;
            ed.WriteMessage("\n[cad-guard] Ghim lỗi (gõ CGGHIM lần nữa để ẩn; ghim không lưu vào bản vẽ):");
            foreach (var g in groups.Where(g => g.Boxes.Count > 0))
                ed.WriteMessage($"\n  {g.No,3}  {g.RuleId}  {(g.Severity == "E" ? "Lỗi" : g.Severity == "W" ? "Cảnh báo" : "Gợi ý")}  {g.Boxes.Count} vị trí");
            if (noBox > 0) ed.WriteMessage($"\n  {noBox} nhóm lỗi không có vị trí (theo layer, kiểu chữ…): xem bảng cad-guard (CGBANG).");
        }

        private static List<Group> Load(Document doc, string reportPath, out int noBox)
        {
            using var js = JsonDocument.Parse(File.ReadAllText(reportPath, Encoding.UTF8));
            var file = js.RootElement.GetProperty("files")[0];
            var order = new[] { "E", "W", "I" };
            var byRule = new Dictionary<string, (string sev, List<string> handles)>();
            var seq = new List<string>();
            foreach (var f in file.GetProperty("findings").EnumerateArray())
            {
                var rid = f.GetProperty("rule_id").GetString() ?? "";
                var sev = f.GetProperty("severity").GetString() ?? "W";
                if (!byRule.TryGetValue(rid, out var v)) { v = (sev, new List<string>()); byRule[rid] = v; seq.Add(rid); }
                foreach (var h in f.GetProperty("handles").EnumerateArray())
                    if (h.GetString() is string s && v.handles.Count < 200) v.handles.Add(s);
            }
            // đánh số như giao diện cad-guard: theo mức (Lỗi, Cảnh báo, Gợi ý) rồi theo thứ tự xuất hiện
            var rules = seq.OrderBy(r => Array.IndexOf(order, byRule[r].sev)).ToList();
            var db = doc.Database;
            var groups = new List<Group>();
            noBox = 0;
            using var tr = db.TransactionManager.StartOpenCloseTransaction();
            for (int i = 0; i < rules.Count; i++)
            {
                var (sev, handles) = byRule[rules[i]];
                var boxes = new List<Extents3d>();
                foreach (var h in handles)
                {
                    try
                    {
                        var id = db.GetObjectId(false, new Handle(long.Parse(h, NumberStyles.HexNumber, CultureInfo.InvariantCulture)), 0);
                        if (id.IsNull || id.IsErased) continue;
                        if (tr.GetObject(id, OpenMode.ForRead) is Entity ent) boxes.Add(ent.GeometricExtents);
                    }
                    catch (System.Exception) { }
                }
                if (boxes.Count == 0) noBox++;
                groups.Add(new Group(i + 1, rules[i], sev, boxes));
            }
            return groups;
        }

        private static (double size, Point3d ctr) CurrentView()
        {
            var size = Convert.ToDouble(AcApp.GetSystemVariable("VIEWSIZE"), CultureInfo.InvariantCulture);
            var ctr = (Point3d)AcApp.GetSystemVariable("VIEWCTR");
            return (size, ctr);
        }

        private static void OnIdle(object? sender, EventArgs e)
        {
            if (_doc == null || Drawn.Count == 0 || !Same(AcApp.DocumentManager.MdiActiveDocument, _doc)) return;
            try
            {
                var v = CurrentView();
#if CGDEV
                if (!_dbgIdle) { _dbgIdle = true; Util.Say($"[dev] idle: {v.size:0.##} vs {_view.size:0.##}"); }
#endif
                if (Math.Abs(v.size - _view.size) > 1e-9 * Math.Max(1, v.size) || v.ctr.DistanceTo(_view.ctr) > 1e-9 * Math.Max(1, v.size))
                    Draw();
            }
            catch (System.Exception) { }
        }

        private static void Draw()
        {
            Erase();
            if (_doc == null) return;
            _view = CurrentView();
            var screen = (Point2d)AcApp.GetSystemVariable("SCREENSIZE");
            var k = _view.size / Math.Max(1, screen.Y); // đơn vị bản vẽ trên một điểm ảnh
            var db = _doc.Database;
            // 1) vòng khoanh từng vị trí + điểm neo nhãn (góc trên phải)
            var anchors = new List<(Point3d at, Group g)>();
            foreach (var g in _groups)
            {
                foreach (var b in g.Boxes.Take(60))
                {
                    double pad = 6 * k, min = MIN_RING * k;
                    double x0 = b.MinPoint.X - pad, y0 = b.MinPoint.Y - pad, x1 = b.MaxPoint.X + pad, y1 = b.MaxPoint.Y + pad;
                    if (x1 - x0 < min) { var c = (x0 + x1) / 2; x0 = c - min / 2; x1 = c + min / 2; }
                    if (y1 - y0 < min) { var c = (y0 + y1) / 2; y0 = c - min / 2; y1 = c + min / 2; }
                    var ring = new Autodesk.AutoCAD.DatabaseServices.Polyline();
                    ring.AddVertexAt(0, new Point2d(x0, y0), 0, 0, 0);
                    ring.AddVertexAt(1, new Point2d(x1, y0), 0, 0, 0);
                    ring.AddVertexAt(2, new Point2d(x1, y1), 0, 0, 0);
                    ring.AddVertexAt(3, new Point2d(x0, y1), 0, 0, 0);
                    ring.Closed = true;
                    ring.ColorIndex = Color(g.Severity);
                    Add(ring);
                    anchors.Add((new Point3d(x1, y1, 0), g));
                }
            }
            // 2) gộp nhãn gần nhau trên màn hình
            var clusters = new List<(Point3d at, List<Group> gs)>();
            foreach (var a in anchors)
            {
                var near = clusters.FindIndex(c => c.at.DistanceTo(a.at) < MERGE * k);
                if (near >= 0) { if (!clusters[near].gs.Contains(a.g)) clusters[near].gs.Add(a.g); continue; }
                clusters.Add((a.at, new List<Group> { a.g }));
            }
            // 3) đặt nhãn ở chỗ trống (8 hướng, 2 vòng khoảng cách)
            var dirs = new (double x, double y)[] { (1, 1), (-1, 1), (1, -1), (-1, -1), (1.4, 0), (-1.4, 0), (0, 1.4), (0, -1.4) };
            var placed = new List<(Point3d p, double r)>();
            foreach (var c in clusters)
            {
                var multi = c.gs.Count > 1;
                var r = (multi ? R + 3 : R) * k;
                Point3d? best = null;
                foreach (var dist in new[] { GAP, GAP * 2.2 })
                {
                    foreach (var d in dirs)
                    {
                        var p = new Point3d(c.at.X + d.x * dist * k, c.at.Y + d.y * dist * k, 0);
                        if (placed.All(o => o.p.DistanceTo(p) > o.r + r + 2 * k)) { best = p; break; }
                    }
                    if (best != null) break;
                }
                var at = best ?? new Point3d(c.at.X + GAP * k, c.at.Y + GAP * k, 0);
                placed.Add((at, r));
                var worst = c.gs.Any(g => g.Severity == "E") ? "E" : c.gs.Any(g => g.Severity == "W") ? "W" : "I";
                var col = Color(worst);
                Add(new Line(c.at, at) { ColorIndex = col });
                Add(new Circle(at, Vector3d.ZAxis, r) { ColorIndex = col });
                Add(new Circle(at, Vector3d.ZAxis, r * 0.86) { ColorIndex = col });
                var label = multi ? "×" + c.gs.Count : c.gs[0].No.ToString(CultureInfo.InvariantCulture);
                var h = 11 * k;
                var w = 0.62 * h * label.Length;
                var t = new DBText
                {
                    TextString = label,
                    Height = h,
                    Position = new Point3d(at.X - w / 2, at.Y - h / 2, 0),
                    ColorIndex = col,
                    TextStyleId = db.Textstyle,
                };
                Add(t);
            }
        }

        private static short Color(string sev) => sev == "E" ? (short)1 : sev == "W" ? (short)30 : (short)8;

        private static void Add(Drawable d)
        {
            TransientManager.CurrentTransientManager.AddTransient(d, TransientDrawingMode.DirectTopmost, 128, new IntegerCollection());
            Drawn.Add(d);
        }

        private static void Erase()
        {
            var tm = TransientManager.CurrentTransientManager;
            foreach (var d in Drawn)
            {
                try { tm.EraseTransient(d, new IntegerCollection()); } catch (System.Exception) { }
                d.Dispose();
            }
            Drawn.Clear();
        }

        public static void Clear()
        {
            Erase();
            _doc = null;
            _groups = new List<Group>();
        }
    }
}
