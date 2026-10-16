# ISSUE LOG - Desktop Timezone Clock Overlay

此文件记录了在 Windows 10/11 开发桌面时间覆盖工具时遇到的技术挑战、失败原因及目前的解决方案。

## 1. 设置窗口无反应 (Settings Not Responding)
- **问题描述**：点击系统托盘选单中的 "Settings" 后，窗口未出现或出现后立即卡死。
- **原因分析**：Tkinter 是一个单执行绪的 UI 框架。之前的程序码试图在 `pystray` 的回调执行绪（子执行绪）中创建并运行 `SettingsWindow`。这会导致 Tcl/Tk 核心崩溃或无法响应。
- **解决方法**：使用 `root.after()` 或队列机制，将设置窗口的创建请求转发给主 UI 执行绪执行。

## 2. 透明度失效与「黑盒」现象 (Transparency/Black Box Issue)
- **问题描述**：时钟背景显示为纯黑色块，无法看到下方的任务栏。
- **原因分析**：
    - Windows 11 的 DWM (Desktop Window Manager) 渲染机制对 `WS_EX_LAYERED` 的属性处理非常严格。
    - Tkinter 的 `-transparentcolor` 在处理非纯色边缘（反锯齿）时会失败。
- **解决方法**：
    - 强制使用 `win32gui.SetLayeredWindowAttributes` 并指定 `LWA_COLORKEY`。
    - 设置 `-alpha` 为 0.99 触发 DWM 重新渲染。

## 3. 点击穿透与原生日历弹出 (Click-through & Calendar Popup)
- **问题描述**：点击小工具时无法开启 Windows 日历，或原生时钟会短暂跳出。
- **原因分析**：
    - `WS_EX_TRANSPARENT` 会让窗口完全失去事件感应，无法进行任何交互。
    - 转发 `WM_LBUTTONDOWN` 讯息给 `TrayClockWClass` 在 Win11 下经常被拦截。
- **解决方法**：
    - 移除 `WS_EX_TRANSPARENT`，让小工具拦截点击。
    - 使用 `pyautogui` 模拟 `Win + N` (Win11 日历热键) 或模拟点击底层坐标。

## 4. 时区切换不生效 (Timezone Sync Issue)
- **问题描述**：在设置页面修改时区并保存后，桌面时钟没有变化。
- **原因分析**：`main.py` 与 `ClockOverlay` 之间的配置对象引用不一致，且 `update_clock` 循环中未正确重新加载配置。
- **解决方法**：在 `update_config` 中执行深度复制，并在 `ClockOverlay` 中显式重置时区相关变量。

## 5. 按下任务栏时跳回本机时间 (Jumping to Local Time)
- **问题描述**：当点击任务栏其他区域时，原生时钟会浮现覆盖小工具。
- **原因分析**：Windows 任务栏在获得焦点时会强制执行重绘，其层级可能暂时高于普通置顶窗口。
- **解决方法**：增加一个极高频率（如 500ms）的 `force_topmost` 校准循环。

---
**Status**: 修复中 (Fixing...)
**Author**: Kanaoda
**Date**: 2026-04-25
