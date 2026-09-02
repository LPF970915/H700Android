# 无触摸 Android 参考材料

本目录保存 H700 适用的交互规范和待实现模板。它不是 Android TV 固件，也不包含可刷镜像。

## 采用原则

- 交互模型参考 Android TV/Leanback：DPAD 焦点、确认、返回、主页。
- 代码实现优先原生 Java/Kotlin View；Flutter 项目只作为视觉/交互参考。
- 外部输入使用标准 USB/Bluetooth HID；厂商扫描码放入独立 `.kl`，不写进业务 UI。
- H700 自有 kernel/DTB/input 能力必须优先于 R36S/RK3326 的实现。

## 本目录文件

- `RGSPNoTouchLauncher-SPEC.md`：启动器最小产品规格。
- `keylayout/Generic_RGSP_H700.kl.template`：待实机事件确认后安装的 `.kl` 模板。
- `keylayout/Generic_RGSP_H700.kcm.template`：可选字符映射模板。
- `tools/capture_input_events.sh`：在 Android alpha 上采集事件的命令脚本。

## 外部官方入口

- Android TV navigation：<https://developer.android.com/training/tv/start/navigation>
- Android TV quality：<https://developer.android.com/docs/quality-guidelines/tv-app-quality>
- AOSP TvSettings：<https://android.googlesource.com/platform/packages/apps/TvSettings/>
- Android KeyEvent：<https://developer.android.com/reference/android/view/KeyEvent>

下载完整 AOSP/SDK 前先完成 UART、`dumpsys input` 和实际按键事件确认；这样可以避免把数百 GB 源码和不匹配的投影仪 SDK 放进项目。
