# H700 Android 10 主线总控文档

日期：2026-09-02  
状态：生效，取代此前以 R36S Android 11 为运行基线的路线

2026-09-07 12:33 最新交互进展：Fix71 已编译并试装 AOSP TV 输入法，
RGSP 专用 A 键适配和紧凑尺寸已加入源码；注入按键完成选字、B 收起、
A 重开及 X 删空测试，等待物理键复核。AT4K 通过自身“隐藏桌面卡片”
选项移除大块空白，应用与 Settings 图标已完整显示；未修改 720x480/213dpi。
仍未提交网络密码，联网验收未完成。Fix70 已推送为 `f7445b8`，
其离线镜像不包含这次数据分区侧的键盘试装。详见
`H700_ANDROID10_FIX71_INPUT_DISPLAY_20260907.md`。

2026-09-07 11:54 最新实机进展：Fix69 已通过受保护 Fix67 handoff 进入
Android，AT4K 已实际设为默认 HOME，Launcher3 保留恢复。Fix70 修复
Wi-Fi 驱动状态属性缺失和重载接口名不匹配；已安装重新编译的 HAL 与 init，
连续两轮开关通过，Settings 显示真实扫描结果。尚未输入网络凭据，
认证、DHCP、DNS、HTTPS 和重连未验收。SurfaceFlinger 仍为 Mali-G31/r20p0，
核心 PID 未变，检查时 crash buffer 为空；这不是完整稳定性验收。
TF1 原 boot/env 哈希已在 Android 内复核恢复，TF2 独立冷启动仍未完成。
详见 `H700_ANDROID10_FIX70_WIFI_HOME_20260907.md`。

以下 10:55 记录为写卡阶段历史状态，不代表当前仍在等待插卡。

2026-09-07 10:55 当前部署进展：Fix69 已将 RGSP Wi-Fi 模块、固件和 HAL
加载路径与 Fix67 启动修复离线合包，并写入 TF2 p2/p3；全量回读哈希通过。
旧 system/vendor、ANBOOT、GPT 已备份，TF1 和 TF2 data/ROM 分区未写入。
下一步是插回 RGSP，通过 COM4 验证受保护启动、`wlan0`、扫描及联网；
不能据此认定已联网或已具备脱离 TF1 的 TF2 独立冷启动能力。详见
`H700_ANDROID10_FIX69_WIFI_DEPLOYMENT_20260907.md`。

用户随后明确调整优先级：Launcher3 的触摸手势入口不适合当前无触摸掌机，
因此优先切换 AT4K 为默认 HOME，并保留 Launcher3 恢复入口；不再以联网
或全部焦点问题解决作为切换前提。Wi-Fi、Settings、返回和输入法继续独立验收。

2026-09-06 23:22 当前进展：Fix67 在构建镜像加部署修复后自动进入 Launcher，
Mali-G31/r20p0 硬件渲染已验证，基础按键已完成，不再从逐键采集开始。
`wifi`、`wifiscanner`、`connectivity`、`netd` 已在实机发布；目前未见
`8821cs` 模块和 `wlan0`，网络瓶颈已移至驱动及其加载链。
当前 P2/B4 首图已完成，稳定性验收尚未结束；P3/B5 改为优先 TV 前端与网络。
60 分钟老化、10 次冷启动以及干净重建可复现性仍未完成。

2026-09-02 历史基线进展：完整 H616 Android+Longan 源码已在 D 盘 WSL2 落盘；原厂
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

当前完成度：已有实际 Android 10 镜像并在设备运行；HWC 等组件增量构建已经
实测。现场累积修复仍需完整回收进构建输入，两次干净构建的退出条件尚未满足。

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

1. 使用现有 RGSP 映射，试装 TV Launcher 和可用的无触摸屏幕键盘；
2. 优先补齐 Settings 网络操作、RTL8821CS 驱动、扫描、认证与联网；
3. 保留 Launcher3 回退后确定默认 HOME，逐项补齐 Settings 真实后端；
4. 按需实现 Select 虚拟鼠标兜底及多机型校准，不抢占游戏手柄语义；
5. H616 Audio HAL 5.0 对接 `audiocodec` card 0/device 0；
6. AXP2202 电量、充电、亮度、关机、Hall、振动和蓝牙；
7. low-RAM、zram、LMKD 和后台进程调优。

退出条件：Launcher、音乐、阅读、RetroArch 和 PPSSPP 可以完成基本操作。

### A10-P4：媒体和产品化

1. 评估 CedarX/OMX 硬件视频解码；
2. 明确 Widevine L3、在线视频清晰度和 DRM 限制；
3. 建立应用兼容列表和 32/64 位策略；
4. 完成双启动、恢复镜像、升级和多机型 overlay。

## 8. 最近执行队列

近期工作已经从迁移整理切换到实际 bring-up。详细命令顺序、空间保护、验收门槛、
实体机依赖和工作量判断统一见：

`docs/H700_ANDROID10_NEXT_DEVELOPMENT_PLAN_20260902.md`

当前关键路径：

1. 固定 Fix67、当前 RGSP keylayout、payload 哈希和回退证据；
2. 审核用户提供的 AT4K APK，以普通应用试装验证；暂不设默认、不授予特权；
3. 用现有按键验证 TV 焦点、确认/返回、弹窗退出和无触摸屏幕键盘；
4. 补齐 RTL8821CS 模块与加载路径，再通过 Settings 完成扫描和联网；
5. 验收通过才切换默认 HOME，Launcher3 与串口恢复保持可用；
6. 逐页补齐 Settings，随后推进音频、电源、虚拟鼠标、多机型校准和游戏闭环；
7. 交叉完成老化、冷启动、低内存和干净构建复现。

TV 前端是用户操作入口，不替代 Settings、SystemUI、framework、HAL 和驱动；
不继承 Homlet/投影仪整机配置，也不把完整电视产品依赖引入掌机。
APK 检查与网络分层门槛见 `H700_ANDROID10_TV_NETWORK_PLAN_20260906.md`。

Android 11 fix58 的最后一次冷启动只做历史取证，不阻塞上述 Android 10 离线开发。

## 9. 验收原则

- 所有运行组件必须能追溯到 H616、RGSP 或明确的自研实现；
- H618 文件不得进入主线产物；
- 产品属性不得出现 `r36s`、`rk3326`、`rk30board`；
- 每次设备写入必须保留 CID、boot/env、e2fsck 和回读校验；
- 第一幅画面之前不扩大到摄像头、DRM、HDMI 和复杂媒体服务。
