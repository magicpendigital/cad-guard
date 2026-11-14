// ==============================================================================
// CAD GUARD AUTOCAD DOCKABLE PALETTE (.NET C# Plugin for AutoCAD 2021-2026)
// Sử dụng Autodesk.AutoCAD.Windows.PaletteSet và Microsoft.Web.WebView2
// Ghim trực tiếp Khung Chat AI và Danh sách lỗi cạnh màn hình vẽ AutoCAD.
// ==============================================================================

using System;
using System.IO;
using System.Windows.Forms;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Windows;
using Microsoft.Web.WebView2.WinForms;

[assembly: ExtensionApplication(typeof(CadGuard.AutoCadPlugin.CadGuardApp))]
[assembly: CommandClass(typeof(CadGuard.AutoCadPlugin.CadGuardCommands))]

namespace CadGuard.AutoCadPlugin
{
    public class CadGuardApp : IExtensionApplication
    {
        public static PaletteSet CadGuardPaletteSet = null;
        public static WebView2 BrowserControl = null;

        public void Initialize()
        {
            var doc = Autodesk.AutoCAD.ApplicationServices.Application.DocumentManager.MdiActiveDocument;
            doc?.Editor.WriteMessage("\n[CAD Guard] Plugin đã nạp thành công! Gõ lệnh CADGUARD để mở bảng điều khiển AI Sidebar.\n");
        }

        public void Terminate()
        {
            if (CadGuardPaletteSet != null)
            {
                CadGuardPaletteSet.Dispose();
                CadGuardPaletteSet = null;
            }
        }
    }

    public class CadGuardCommands
    {
        private const string LocalPaletteUrl = "http://127.0.0.1:3000/palette";

        [CommandMethod("CADGUARD")]
        public void ShowCadGuardPalette()
        {
            if (CadGuardApp.CadGuardPaletteSet == null)
            {
                CadGuardApp.CadGuardPaletteSet = new PaletteSet("CAD Guard · Trợ lý AI & Kiểm lỗi", new Guid("8E307DC6-11AE-4D05-A13D-86D315E4CA62"))
                {
                    Style = PaletteSetStyles.ShowAutoHideButton |
                            PaletteSetStyles.ShowCloseButton |
                            PaletteSetStyles.ShowPropertiesMenu,
                    MinimumSize = new System.Drawing.Size(320, 480),
                    Dock = DockSides.Right
                };

                var userControl = new UserControl { Dock = DockStyle.Fill };
                CadGuardApp.BrowserControl = new WebView2 { Dock = DockStyle.Fill };
                userControl.Controls.Add(CadGuardApp.BrowserControl);

                CadGuardApp.BrowserControl.EnsureCoreWebView2Async().ContinueWith(task =>
                {
                    if (task.IsCompletedSuccessfully)
                    {
                        CadGuardApp.BrowserControl.Invoke(new Action(() =>
                        {
                            CadGuardApp.BrowserControl.Source = new Uri(LocalPaletteUrl);
                        }));
                    }
                });

                CadGuardApp.CadGuardPaletteSet.Add("CAD Guard Sidebar", userControl);
            }

            CadGuardApp.CadGuardPaletteSet.Visible = true;
        }

        [CommandMethod("CGZOOM")]
        public void ZoomToEntity()
        {
            var doc = Autodesk.AutoCAD.ApplicationServices.Application.DocumentManager.MdiActiveDocument;
            if (doc == null) return;
            var ed = doc.Editor;

            var pso = new PromptStringOptions("\n[CAD Guard] Nhập mã Handle của đối tượng lỗi: ");
            var res = ed.GetString(pso);
            if (res.Status != PromptStatus.OK || string.IsNullOrWhiteSpace(res.StringResult)) return;

            long hVal = Convert.ToInt64(res.StringResult, 16);
            var handle = new Handle(hVal);

            using (var tr = doc.TransactionManager.StartTransaction())
            {
                if (doc.Database.TryGetObjectId(handle, out ObjectId objId))
                {
                    var ent = tr.GetObject(objId, OpenMode.ForRead) as Entity;
                    if (ent != null)
                    {
                        ed.SetImpliedSelection(new ObjectId[] { objId });
                        ed.Command("_.ZOOM", "_Object", objId, "");
                        ed.WriteMessage($"\n[CAD Guard] Đã phóng to và chọn đối tượng Handle: {res.StringResult}\n");
                    }
                }
                tr.Commit();
            }
        }
    }
}
