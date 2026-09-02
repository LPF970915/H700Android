# H700 Android 10 主线总控文档

日期：2026-09-02  
状态：生效，取代此前以 R36S Android 11 为运行基线的路线

2026-09-02 基线进展：完整 H616 Android+Longan 源码已在 D 盘 WSL2 落盘；原厂
`cupid_perf1-eng` 和新 `h700_rgsp-eng` 均已通过 `lunch` 与 `m nothing`。当前进入
首轮实际镜像编译阶段，详见 `docs/H700_ANDROID10_BASELINE_STATUS_20260902.md`。

## 1. 固化决策

项目正式切换为以下层级：

```text
主线实现：H616 Android 10 完整源码和官方镜像
硬件事实：RGSP 原厂 H700 kernel/DTB/Linux 行为和实机日志
运行佐证：H21S-700-V3.0 H700 Android 10 冷启动日志
诊断档案：R36S LineageOS 18.1 / Android 11 fix1-fix58
备份对照：H618 Android 12 精选源码和 vendor 参考集
```

H618 不进入主线。它面向 Android 12、较新的 HAL/内存/图形体系和更高内存设备，
只能用于接口演进、服务命名和实现差异对照。

## 2. Android 10 产品定义

- Android 10 / API 29；
- H616 `sun50iw9p1` / `cupid` HAL 代际；
- RGSP 自有 H700 Linux 4.9.170 kernel 和 DTB；
- 初期 ARM32 用户空间、64 位 Binder、flattened APEX；
- `ro.config.low_ram=true`、Go 风格裁剪、无 GMS；
- TF1 保留 Linux 和恢复能力，TF2 承载 system/vendor/data；
- 第一目标为稳定 Launcher、按键和 PPSSPP，不先追求 DRM 高清或完整电视功能。

后续可评估双 ABI 产品，但只能在 32 位主线稳定后进行，不能让 64 位应用兼容性再次
破坏 1 GiB 内存基线。

## 3. 可以继承的 Android 11 成果

- TF1 handoff、一次性启动标记和自动 Linux 回退；
- TF2 分区、PARTUUID 和 system/vendor/data 挂载事实；
- boot/env/CID 哈希校验与写后只读复核；
- UART、logdw、logcat、kmsg、tombstone 和 DropBox 采集；
- Binder 节点、ION、Mali、disp、fb0 和 ALSA 设备事实；
- H616 图形 fix51-fix56 和音频 fix58 的 ABI/运行证据；
- RGSP 720x480、AXP2202、按键、Hall、RTL8821CS 等硬件资料。

## 4. 禁止继承的 Android 11 内容

- `r36s`、`rk3326`、`rk30board` 产品和硬件身份；
- Rockchip Gralloc、HWC、GPU、Vulkan、音频和媒体二进制；
- Android 11 `framework.jar`、`services.jar` 的 headless/bypass 修改；
- 为混合 APEX、linkerconfig、VNDK 或 HAL 代际而建立的永久产品补丁；
- 把 diagnostic fix 编号继续当作 Android 10 产品版本。

Android 10 必须从未修改的 framework 启动。出现 framework 崩溃时先修正 device、HAL、
VINTF、权限和资源配置，不能先删除 SystemServer 服务。

## 5. H616 使用边界

直接复用或编译：

- Android 10 framework/build system；
- Mali-G31 r20p0 用户态、Gralloc、HWC2、ION；
- Audio HAL 5.0、audio policy、tinyalsa；
- Allwinner init、ueventd、VINTF、power/health/lights 实现框架；
- low-RAM、Go、flattened APEX 和 dexpreopt 配置。

必须替换：

- Orange Pi bootloader、GPT、DTS、HDMI/TV 产品层；
- AXP806 等开发板 PMIC 配置；
- AC107、摄像头、CEC、DRM 和不属于掌机的服务；
- eMMC/dynamic-partition fstab；
- 板级 LCD、GPIO、无线、电池、音频路由和输入映射。

## 6. 当前文件入口

- 主线 overlay：`android/h700-android10/`
- Android 11 档案：`android/legacy-android11/`
- H616 源码分析：`work/h700-source-analysis/h616/`
- H616 来源与校验：`docs/H616_ANDROID10_PROVENANCE_20260902.md`
- H618 精选集：`work/h700-source-analysis/h618/selected/`
- H700 投影仪日志：`out/logs/uart/projector-h21s700/`
- fix58 音频结论：`docs/fix58-h616-audio-analysis-20260902.md`

## 7. 后续开发阶段

### A10-P0：可重复构建

1. 完整解出 H616 `android.tar.gz` 和 `longan.tar.gz` 到同一个独立构建目录。
2. 固定 Ubuntu/WSL、JDK、Python、repo/build 工具版本。
3. 将 `android/h700-android10/device/roc` 接入源码树。
4. 先构建原始 `cupid_perf1`，确认 H616 源码本身可重现。
5. 再构建 `h700_rgsp-eng`。

当前完成度：步骤 1-3 已完成；步骤 4-5 已完成产品解析和全量构建图验证，实际镜像
编译尚未开始。

源码准备使用 `tools/prepare_h616_android10_source.ps1`。目标必须位于 WSL2
Linux 文件系统，避免在 NTFS 上构建 AOSP 时丢失大小写、权限或符号链接语义。
本项目的 Ubuntu VHDX 固定在 `D:/Works/H700Android/.wsl/Ubuntu/`，不得把完整
源码或构建输出放回 C 盘默认 WSL 目录。

退出条件：两次干净构建生成一致的关键文件清单，失败与环境问题均记录。

### A10-P1：init 和存储

1. 复用 RGSP kernel、DTB 和已验证 handoff boot header。
2. 使用 Android 10 原生 init、flattened APEX 和 linker 配置。
3. 按真实 PARTUUID 挂载 TF2 system/vendor/data。
4. 保留 Binder 权限和持久日志能力，但不移植 Android 11 framework patch。

退出条件：连续 10 次到达 ADB、zygote、未修改的 system_server。

### A10-P2：第一幅画面

1. 编译 H616 arm32/arm64 Mali-G31 库和 Gralloc/HWC2 组合。
2. 核对 `/dev/ion` heap、private handle、`/dev/disp` ioctl 结构。
3. 固定 RGSP 720x480、32 bpp、stride、旋转和 vsync。
4. 启动 SurfaceFlinger、bootanimation 和最小 Launcher。

退出条件：稳定显示 60 分钟，连续重启无黑屏。

### A10-P3：掌机基本功能

1. 输入和无触摸鼠标/按键导航；
2. H616 Audio HAL 5.0 对接 `audiocodec` card 0/device 0；
3. AXP2202 电量、充电、亮度、关机和 Hall；
4. 振动、RTL8821CS Wi-Fi 和蓝牙；
5. low-RAM、zram、LMKD 和后台进程调优。

退出条件：Launcher、音乐、阅读、RetroArch 和 PPSSPP 可以完成基本操作。

### A10-P4：媒体和产品化

1. 评估 CedarX/OMX 硬件视频解码；
2. 明确 Widevine L3、在线视频清晰度和 DRM 限制；
3. 建立应用兼容列表和 32/64 位策略；
4. 完成双启动、恢复镜像、升级和多机型 overlay。

## 8. 最近执行队列

1. 用户回到设备旁后完成 fix58 最后一次冷启动，仅收集证据。
2. 不再向 Android 11 增加 framework bypass。
3. 审计 H616 完整源码解包后的磁盘需求和构建依赖。
4. 构建原始 H616 Android 10 产品作为工具链基准。
5. 接入 `h700_rgsp` overlay，并生成第一版 Android 10 system/vendor。
6. 用现有安全 handoff 验证 Android 10 init。
7. 进入 H616 图形组合和 720x480 画面验证。

## 9. 验收原则

- 所有运行组件必须能追溯到 H616、RGSP 或明确的自研实现；
- H618 文件不得进入主线产物；
- 产品属性不得出现 `r36s`、`rk3326`、`rk30board`；
- 每次设备写入必须保留 CID、boot/env、e2fsck 和回读校验；
- 第一幅画面之前不扩大到摄像头、DRM、HDMI 和复杂媒体服务。
