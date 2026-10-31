// AI 智能伴侣 —— 极简窗口宿主（WebView2）
//
// 为什么要有这个文件：
//   pywebview（pythonnet）在 PyInstaller 打包后会加载 .NET 运行时失败，
//   Edge 的 --app 窗口在部分机器上会开出白窗口。于是干脆自己写一个最小的
//   WinForms + WebView2 宿主：它就是一个 exe，参数给「地址」，就显示一个
//   没有地址栏、没有标签页的窗口，标题和图标都是我们自己的。
//
// 编译（.NET Framework 4.x 自带 csc，不用装 VS）：
//   csc /target:winexe /out:AI伴侣窗口.exe /r:Microsoft.Web.WebView2.Core.dll ^
//       /r:Microsoft.Web.WebView2.WinForms.dll /r:System.Windows.Forms.dll ^
//       /r:System.Drawing.dll WindowHost.cs
//   并把 WebView2Loader.dll（runtimes\win-x64\native）放到同一个目录。
//
// 用法：AI伴侣窗口.exe http://localhost:8501 AI智能伴侣 app.ico
// 退出码：0 正常关闭；2 没装 WebView2 运行时；3 其它错误。

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace AiPartnerWindow
{
    internal static class Program
    {
        private const string DefaultUrl = "http://localhost:8501";
        private const string DefaultTitle = "AI智能伴侣";

        [STAThread]
        private static int Main(string[] args)
        {
            string url = args.Length > 0 && !string.IsNullOrEmpty(args[0]) ? args[0] : DefaultUrl;
            string title = args.Length > 1 && !string.IsNullOrEmpty(args[1]) ? args[1] : DefaultTitle;
            string iconPath = args.Length > 2 ? args[2] : null;

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // WebView2 运行时没装的话，CoreWebView2Environment 会抛这个异常，
            // 让父进程（launcher）据此退回浏览器，而不是弹一个看不懂的错误框。
            if (CoreWebView2Environment.GetAvailableBrowserVersionString() == null)
            {
                return 2;
            }

            try
            {
                var form = new Form
                {
                    Text = title,
                    Width = 1200,
                    Height = 900,
                    MinimumSize = new Size(900, 620),
                    StartPosition = FormStartPosition.CenterScreen,
                    BackColor = Color.White
                };
                TrySetIcon(form, iconPath);

                var web = new WebView2 { Dock = DockStyle.Fill };
                form.Controls.Add(web);

                form.Load += async (sender, e) =>
                {
                    try
                    {
                        // 用程序自己的目录当 user data folder：不碰用户浏览器配置，
                        // 也就不会被"以管理员权限运行的 Edge"挡住。
                        // 程序目录不可写时（装在 Program Files 之类）退到 LOCALAPPDATA。
                        // 注意：C# 5 不允许在 catch 里 await，所以先探路径再 await。
                        string exeDir = Path.GetDirectoryName(Application.ExecutablePath) ?? ".";
                        string dataDir = Path.Combine(exeDir, "webview-data");
                        if (!CanWriteTo(dataDir))
                        {
                            dataDir = Path.Combine(
                                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                "AI智能伴侣",
                                "webview-data");
                            Directory.CreateDirectory(dataDir);
                        }
                        var env = await CoreWebView2Environment.CreateAsync(null, dataDir, null);
                        await web.EnsureCoreWebView2Async(env);
                        web.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
                        web.CoreWebView2.Settings.IsStatusBarEnabled = false;
                        web.CoreWebView2.Navigate(url);
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show(
                            "界面初始化失败：" + ex.Message,
                            title,
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error);
                        form.Close();
                    }
                };

                Application.Run(form);
                return 0;
            }
            catch (Exception ex)
            {
                MessageBox.Show("窗口启动失败：" + ex.Message, title, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 3;
            }
        }

        private static bool CanWriteTo(string dir)
        {
            try
            {
                Directory.CreateDirectory(dir);
                string probe = Path.Combine(dir, ".writable");
                File.WriteAllText(probe, "ok");
                File.Delete(probe);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private static void TrySetIcon(Form form, string iconPath)
        {
            try
            {
                if (!string.IsNullOrEmpty(iconPath) && File.Exists(iconPath))
                {
                    form.Icon = new Icon(iconPath);
                }
            }
            catch
            {
                // 图标只是好看，失败不影响用
            }
        }
    }
}
