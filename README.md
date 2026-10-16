# Desktop Timezone Clock Overlay | 桌面多时区时钟覆盖工具

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

这是一个专为 Windows 10/11 设计的轻量化桌面工具，旨在解决系统时区与显示时间不一致的需求。


### 此分支的默认行为

- **系统时区保持原样**：例如美国太平洋时间 `Pacific Standard Time`，程序不会修改系统时钟、时区或区域设置。
- **右下角显示北京时间**：默认时区为 `Asia/Shanghai`（UTC+8）。设置页同时显示系统本地时间，方便核对美国时间与北京时间。
- **简体中文**：中文界面、时区名称、安装选项、源码注释和说明文档统一使用简体中文，保留英文界面。
- **Windows 时间格式**：默认使用 Windows 当前用户的短时间和短日期格式（包括 12/24 小时制、日期顺序和分隔符）。设置里的“跟随 Windows 时间格式”可以关闭，继续使用配置中的自定义格式。
- **旧配置兼容**：原项目默认的繁体字体／时间日期格式组合会迁移为 Windows 样式（已选北京时间的旧配置也适用）；默认香港时区改为北京时间，其他自定义时区、字体、颜色和时间格式保留。

若旧版正在运行，请先从托盘菜单退出旧版，再启动此版本；原有开机启动项仍指向安装位置时，也需要在替换版本后重新设置。

### 🚀 解决的核心问题
本工具特别适合以下族群：
1. **频繁外游的用家**：需要电脑底层运行特定时区（如工作需要的美国时间），但想在桌面上快速查看当地或家乡时间。
2. **长期使用 VPN 的用家**：解决因使用 VPN 导致电脑系统时间与实际身处时区不符，或不方便修改系统底层时间的问题。

### ✨ 功能特点
- **按原生区域覆盖**：Windows 10 使用原生时钟窗口；Windows 11 通过 UI Automation 识别 XAML 时钟区域并覆盖，跟随实际位置和 DPI 缩放。
- **接近 Windows 原生样式**：默认使用 Segoe UI、上方时间／下方日期的两行布局，时间和短日期格式跟随 Windows 区域设置，背景色自动采样任务栏；也支持自定义颜色和字号。
- **内建日历 popup**：点击时钟即弹出自家设计的日历窗口（显示完整日期、所选时区当前时间，并可浏览前后月份），不依赖 Windows 原生日历触发机制，稳定可靠。
- **全球时区支持**：内建完整时区资料库，可自由切换全球任何城市时间。
- **中英双语界面**：设置窗口支持简体中文与英文，可在设置中即时切换。
- **现代化设置 UI**：采用 CustomTkinter 打造的深色科技风格界面，支持深色标题列。
- **轻量与开源**：基于 Python 开发，占用资源极低，且完全透明公开。

### 🛠️ 安装与使用
1. **环境需求**：安装 [Python 3.9+](https://www.python.org/)。
2. **安装依赖包**：
   ```bash
   python -m pip install -r requirements.txt
   ```
3. **启动程序**：执行 `python main.py`；已有 EXE 时可直接运行 `dist/DesktopTimezoneClock.exe`。
4. **设置时区**：在右下角系统托盘图示点击右键，选择 **「设置」** 即可自定义时区。
5. **切换语言**：在设置窗口的「语言」列选择 **中文** 或 **EN**，界面即时切换。

### 📦 打包与发布（Windows 安装程序）
若你要发布到 GitHub Releases，建议用以下流程：

1. 安装 Inno Setup 6（需有 `ISCC.exe`）。
2. 先创建 exe + 安装程序：
   ```bash
   python build_installer.py
   ```
3. 产物位置：
   - `dist/DesktopTimezoneClock.exe`
   - `dist/DesktopTimezoneClock-Setup.exe`

安装器特性（`installer.iss`）：
- 默认安装到用户目录（不需系统管理员权限）。
- 安装时默认勾选「开机自动启动」。
- 写入 `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`。
- 可在安装完成后立即启动程序。

### 🌐 语言支持
| 语言 | 状态 |
|------|------|
| 简体中文 | ✅ 完整支持 |
| English | ✅ 完整支持 |

### ☕ 支持作者
如果你觉得这个工具对你有帮助，欢迎支持我的持续开发：
- **GitHub Sponsors**: [https://github.com/sponsors/Kanaoda](https://github.com/sponsors/Kanaoda)
- **Buy Me a Coffee**: [https://buymeacoffee.com/kanaoda](https://buymeacoffee.com/kanaoda)

**作者**: Kanaoda  
**版权**: © 2026 Kanaoda. Licensed under the MIT License.

---

## English

A lightweight desktop utility for Windows 10/11 designed to bridge the gap between system-level timezone settings and your desired display time.

### 🚀 Who is this for?
This tool is specifically built for:
1. **Frequent Travelers**: Keep your system on a specific timezone (e.g., US time for work) while displaying local or home time on your taskbar.
2. **Long-term VPN Users**: Solve the issue where system time doesn't match your actual location due to VPN usage, without messing with low-level system settings.

### ✨ Key Features
- **Taskbar Overlay**: Uses the native clock window on Windows 10 and the XAML clock bounds via UI Automation on Windows 11, including DPI scaling.
- **Windows-style Display**: Segoe UI, two lines for time and date, user-specific Windows short time/date formats, and a sampled taskbar background. Colors and font size remain configurable.
- **Built-in Calendar Popup**: Clicking the clock opens a self-rendered calendar popup (full date, target-timezone time, and month navigation). No reliance on Windows' native calendar flyout — works consistently on Windows 10 and 11.
- **Global Timezone Support**: Full timezone database support for any city worldwide.
- **Bilingual Interface**: Settings window supports both Simplified Chinese and English, switchable at runtime.
- **Modern Settings UI**: Dark tech-style interface built with CustomTkinter, with dark title bar support.
- **Lightweight & Open Source**: Built with Python, minimal resource usage, and fully transparent code.

### 🛠️ Installation & Usage
1. **Prerequisites**: Install [Python 3.9+](https://www.python.org/).
2. **Install Dependencies**:
   ```bash
   pip install pywin32 pystray Pillow tzdata requests customtkinter
   ```
3. **Run Application**: Execute `python main.py`.
4. **Configure**: Right-click the system tray icon and select **"Settings"** to choose your target timezone.
5. **Switch Language**: In the Settings window, select **中文** or **EN** in the Language row to switch the interface instantly.

### 📦 Packaging for GitHub Release (Windows Installer)
For publishing to GitHub Releases, use this flow:

1. Install Inno Setup 6 (must provide `ISCC.exe`).
2. Build EXE + installer:
   ```bash
   python build_installer.py
   ```
3. Output files:
   - `dist/DesktopTimezoneClock.exe`
   - `dist/DesktopTimezoneClock-Setup.exe`

Installer behavior (`installer.iss`):
- Per-user install (no admin required).
- "Launch on Startup" is enabled by default at install time.
- Writes to `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`.
- Optionally launches the app immediately after installation.

### 🌐 Language Support
| Language | Status |
|----------|--------|
| Simplified Chinese (简体中文) | ✅ Full support |
| English | ✅ Full support |

### ☕ Support the Developer
If you find this tool useful, feel free to support my work:
- **GitHub Sponsors**: [https://github.com/sponsors/Kanaoda](https://github.com/sponsors/Kanaoda)
- **Buy Me a Coffee**: [https://buymeacoffee.com/kanaoda](https://buymeacoffee.com/kanaoda)

**Author**: Kanaoda  
**Copyright**: © 2026 Kanaoda. Licensed under the MIT License.
