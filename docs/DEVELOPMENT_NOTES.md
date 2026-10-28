# 继续开发的技术入口

当前事实与未验收项以 [CURRENT_BASELINE](CURRENT_BASELINE_20261028.md) 为准。这里只保留后续直接需要的索引；长篇旧诊断与操作历史从 [历史标签](HISTORY.md) 查询。

当前鼠标入口已按用户反馈改为 [Select 单独长按 2 秒后松开](RG34XXSP_SELECT_HOLD_20261028.md)，不依赖肩键或摇杆。按原计划排序的下一步与先前的电源/音频盘点、模拟器初测、小型回退记录见 [输入、电源与模拟器记录](RG34XXSP_INPUT_POWER_EMULATORS_20261028.md)，其 v6 三键组合已由 v7 替代。

应用侧后续见 [720×480 小屏筛选](RG34XXSP_SMALL_SCREEN_APPS_20261028.md)：KOReader 的 HAT/字号用户补丁、Nova 的 TV/mdpi 预配置，以及尚未解决的音乐布局、图形设置焦点、Kodi/Vanilla 启动问题。不得把安装成功或片段播放成功当作完整应用验收。

## 设备与输入

- 当前是用户提供的 H700/2GB/双摇杆样机，Android 产品名仍为 `RGSP H700`。每次操作先核对实际序列号及 ADB transport，真实会话参数见本地保全目录。
- 原输入证明主要来自无摇杆 RGSP。输入节点编号不是稳定接口，应按设备名称和能力重新枚举；新的四轴附加模块、明确的单机启用配置及验收状态见 [RG34XXSP 开发记录](RG34XXSP_DEVELOPMENT_20261028.md)。
- 已保留的 `tools/settings_nav_probe/` 包含被动观察器、通用辅助代码和 29 项安全测试。其控制后端仍绑定旧 RGSP/COM4，不能直接用于新机器；不会因本轮清理自动变成通用控制工具。
- Java 方向、指针几何、回收控件身份测试保存在 `tools/navigation_tests/`，通过 `tools/test_navigation_geometry.ps1` 运行；只生成主机 class，不构建或安装试验 APK。

## 显示与系统

- 现有 H700 路径为厂商 framebuffer/disp/ION/Mali 栈。当前 HWC 使用测得几何的分数软件周期，旧实测周期为 16904379ns；硬件 VSYNC 事件未恢复。
- 已有副屏电源隔离与 SurfaceFlinger 启动异常缓冲隔离。新机亮暗表现仍需实体观察，日志零错误不能代替肉眼验收。
- 主要源码入口在冻结覆盖层的 `hardware/aw/hwc2/`、`frameworks/native/services/surfaceflinger/`，以及产品 `graphics/`；图形周期主机回归为 `tools/tests/rgsp_frame_period_test.cpp`。
- `tools/flicker/` 和 `tools/analyze_rgsp_flicker_video.py` 保留用于后续定位。后者依赖现有 `out/video-analysis-tools/`，该依赖本轮保留。
- 可选教学视频关闭、通用硬解与 FTRACE 限制沿用当前基线，不因清理而改变。

## 单卡与存储保护

单卡固定 system/vendor/data/ROMS 的分区边界见当前基线 `image-manifest.json`。运行中 system 挂载为 `/`，vendor 为 `/vendor`，最后核验均只读。

vold 对启动卡的格式化、重分区和 whole-device fallback 有明确保护；p8 ROMS 对普通应用可见，但不是可采纳内部存储。不要为让设置页显示容量而放开启动卡保护。

保留 `test_rgsp_roms.py`、`test_rgsp_auto_grow.py`、`test_rgsp_dirty_fat.py` 和增长 helper 源码。`build_rgsp_compact_image.py` 仅因测试复用其 boot/init 策略及历史恢复参考而保留，不是当前封装入口；它的旧 seed 也不应被视作已存在。

## 源码与构建

以 [恢复文档](REPRODUCE_BASELINE_20261028.md) 的 364 文件锁和私有输入锁恢复基线。历史 prepare 链已移出当前分支，不要重新按旧日期串行施工。

日常产品配置位于 `android/h700-android10/device/roc/`，实际完整 AOSP 树在 WSL。新的原生改动必须纳入新的 Git 源码覆盖与证明，不能只留在不完整 Git 元数据的 WSL 树里。当前冻结快照的字节和哈希保持不变。

构建继续使用低压力入口。清理之后的新开发已构建 APK 和输入附加模块、在实机安装并重启验证；没有重封装或刷卡。未来封装仍需先解决已记录的 v5f seed 缺口，再完整校验。
