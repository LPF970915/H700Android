# H700 Android 10 近期开发执行计划

日期：2026-09-02  
运行基线：提交 `94ca82e` / Fix67，H616 Android 10 主线，RGSP H700 硬件事实

## 1. 当前起点

2026-09-07 Fix72 更新：AT4K 已是实机默认 HOME；Fix70 开关/扫描和 Fix71
输入法注入测试已有证据。Fix72 已低压增量构建并合包，尚未部署。
当前优先实体密码输入和完整联网，其次 APK 操作闭环、首启与独立 TF2。
构建入口统一为 `tools/build_h700_low_pressure.ps1 -Execute`：
最多两个逻辑核、总配额一核、`-j1`、内存 6 GiB、swap 512 MiB。
不因构建失败提高限额。详见 `H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`。

2026-09-06 23:22 更新：Fix67 自动进入 Launcher，基本短按映射已完成，A 为临时
ENTER 解锁/确认。五个核心 PID 与本次启动基线一致，uptime 为 1242.20 秒。
B4 首图已实现但正式老化与冷启动验收未完成，B5 当前优先 TV 前端和网络。
本节及第 9 节是当前执行顺序；B1/B2 中的首次编译、离线组装描述是历史步骤。

同日已恢复 H21S-700-V3.0 投影仪主板 RX，并通过 UART 双向实测完整进入其
Android 10 Launcher。投影仪现在可以作为服务契约和 H700 runtime donor；其
`rtl8822bs`、投影显示链、电源和产品专有服务仍不得直接移植到 RGSP。

近期工作不再从首轮编译开始。需保留的验收欠项包括：60 分钟老化、连续冷启动、
ADB 单独验证、将所有现场修复纳入干净构建。显示证据见
`H700_ANDROID10_FIX67_STABLE_DESKTOP_20260906.md`；输入结果见
`RGSP_INPUT_CALIBRATION_20260906.md`；前端和网络计划见
`H700_ANDROID10_TV_NETWORK_PLAN_20260906.md`。

## 2. 固定边界

- H616 Android 10 是唯一主线 Android BSP；
- RGSP 原厂 H700 kernel、DTB、分区和外设事实高于 donor board 默认值；
- H618 Android 12 默认禁止进入产品。只有 H616 缺失实现、接口和 ABI 完全一致且
  有逐文件来源记录时，才允许提出例外；
- R36S Android 11 只提供诊断方法、日志工具和已验证硬件事实，不移植其 framework、
  Rockchip HAL 或产品属性；
- 首图前不做 GMS、DRM、摄像头、HDMI、复杂媒体服务和双 ABI；
- 不使用 H616/Orange Pi 的整包 `pack` 结果写入 RGSP，只复用 Android 用户空间；
- 所有源码、编译缓存、日志和镜像必须位于 D 盘项目内的 WSL2，不在 C 盘生成大型
  临时文件。

## 3. 阶段 A10-B1：首轮真实编译

目标：得到第一套可审计的 Android 10 用户空间镜像。

执行顺序：

1. 记录 JDK、Python、Git、内核、内存、swap、磁盘和源码提交/校验信息；
2. 确认 D 盘可用空间不少于 180 GiB，再开始首轮完整编译；
3. 在 `/home/lpf/h700-android10/android` 选择 `h700_rgsp-eng`；
4. 通过低压入口以 `-j1` 构建 `systemimage vendorimage ramdisk`，完整日志写入 D 盘；
5. 保存第一个真实错误，不并行堆叠补丁；
6. 如果错误位于公共 H616 工具链或源码，再用 `cupid_perf1-eng` 复现以区分 donor
   问题和 H700 overlay 问题；
7. 每次只修 device/product、VINTF、SELinux、资源或明确 HAL 依赖，不修改 framework
   以绕过启动服务；
8. 编译成功后记录产物大小、SHA-256、ELF ABI 和动态依赖闭包，再做一次增量复编。

预期产物：

```text
out/target/product/rgsp/system.img
out/target/product/rgsp/vendor.img
out/target/product/rgsp/ramdisk.img
构建环境清单、完整日志、产物 SHA-256 清单
```

退出条件：上述三个产物生成，增量复编通过，不包含 H618、R36S 或 Rockchip 身份。

空间保护：D 盘可用空间低于 120 GiB 时停止新增构建；低于 80 GiB 时不再执行编译，
先清理可重建的 `out/` 中间产物。不得用 C 盘作为 `OUT_DIR`、临时解压目录或 WSL
发行版位置。

## 4. 阶段 A10-B2：测试 boot 与 TF2 部署包

2026-09-06 更新：B2 离线预检已完成。当前包位于
`out/h700-android10-preflight/`，包含当前 Android 10 `system.img`、
`vendor.img`、固定 8 GiB/2 GiB raw 镜像、64 MiB 测试 boot、完整 SHA-256
清单和确认保护的 TF2 写入脚本。两个 raw 镜像均通过 `e2fsck -fn`，本阶段
没有写入设备。详细记录见 `docs/H700_ANDROID10_PREFLIGHT_20260906.md`。

目标：在不写设备的情况下准备完整、可回退的 Android 10 测试包。

1. 从 RGSP 已验证启动链取 kernel、DTB、boot header 和 cmdline；
2. 将 Android 10 ramdisk 与 RGSP kernel/DTB 组合，不引入 H616 bootloader、DTS 或
   分区表；
3. 静态检查 boot header、加载地址、页大小、ramdisk 内容、fstab、PARTUUID、init
   import、ueventd 权限和 SELinux 文件；
4. 检查 system/vendor 的 VINTF、32 位 ELF 闭包、Binder 配置和 flattened APEX；
5. 生成仅面向 TF2 的部署目录、SHA-256 清单和回退说明；
6. 在用户不在设备旁时只准备文件，不执行写卡、U-Boot env 修改或重启。

历史 B2 离线产物检查已通过，随后已进入 B3/Fix67 实机阶段。
原 B2 boot 不等同于 Fix67 已验证入口，不能跳过后续部署修复。

## 5. 阶段 A10-B3：init、存储和无画面启动

目标：证明 Android 10 自身可以在 RGSP kernel 上稳定运行，再处理显示。

需要实体机、UART 和用户在场：

1. 回读 TF1/TF2 CID、boot/env 和关键分区哈希；
2. 写入 TF2 system/vendor/data 和一次性 handoff 测试入口；
3. 冷启动并同时采集 UART、kernel、init、logcat、tombstone 和 DropBox；
4. 依次解决分区挂载、dm/文件系统、SELinux、VINTF、Binder、APEX、zygote 和
   `system_server` 问题；
5. 保持 Linux 自动回退，任何失败不得形成不可恢复的默认启动路径。

阶段门槛：

- B3.1：首次到达 ADB shell；
- B3.2：zygote 启动且不循环崩溃；
- B3.3：未修改的 `system_server` 连续运行 10 分钟；
- B3.4：连续 3 次冷启动到达相同状态；
- B3.5：首图完成后再扩展为连续 10 次启动验收。

## 6. 阶段 A10-B4：H616 图形栈与第一幅画面

2026-09-06 历史更新：Fix64 已取得真实 720×480 锁屏、桌面和应用列表截图，
修复 GPU/ION 应用访问权限及 Homlet 编译路径，并加入本机专用的软件 VSYNC
兼容选项。完整证据和剩余问题见 `H700_ANDROID10_FIX64_VISIBLE_UI_20260906.md`。
用户已确认实体 LCD 与桌面截图一致，Fix64 完整重启和看门狗自动退出验证通过。
这不代表下述 60 分钟和 10 次冷启动退出条件已经满足。

同日后续 Fix67 已修复干净镜像缺 EGL、缺 Mali 模块、未挂 data 和 framework
未触发的问题，自动到达桌面；保持下面的稳定性门槛不变。

目标：得到稳定的 RGSP 720x480 Android 画面。

执行顺序：

1. 核对 RGSP kernel 暴露的 `/dev/mali0`、`/dev/ion`、`/dev/disp`、`fb0` 与 H616
   Android 10 HAL 的 ioctl/ABI；
2. 初始产品只启用 32 位用户空间图形组件。除非某个必需服务被实证为仅有 64 位
   实现，否则不引入双 ABI；
3. 闭合 Mali-G31 r20p0、allocator/mapper、Gralloc、HWC2、ION heap 与
   SurfaceFlinger 依赖；
4. 固定 720x480、像素格式、stride、缓冲数、旋转、刷新率和 vsync；
5. 依次验证纯色 buffer、SurfaceFlinger、bootanimation 和最小 Launcher；
6. 每轮保存 `dumpsys SurfaceFlinger`、`dmesg`、logcat、tombstone 和截图/录像证据。

退出条件：Launcher 稳定显示 60 分钟，连续 10 次冷启动无黑屏、花屏、重启或持续
buffer 泄漏。

这是首图前不确定性最高的阶段。若 H616 用户态与 RGSP kernel 的 private handle、ION
或 disp ABI 不一致，优先适配 H616 Android 10 HAL 源码，不回退到 H618 Android 12
二进制，也不通过 framework headless 补丁绕开显示服务。

## 7. 阶段 A10-B5：掌机基本功能

首图稳定后按以下顺序展开：

1. 基于已有短按映射，优先 TV 桌面、无触摸屏幕键盘、Settings 和 Wi-Fi 联网；
2. 后续完善虚拟鼠标、多机型校准、休眠键及 Hall；
3. H616 Audio HAL 5.0 对接 H700 `audiocodec` card 0/device 0，并以 H700 投影仪
   Android 10 日志校验服务顺序和 mixer 路由；
4. AXP2202 电量、充电、关机、背光和亮度；
5. 振动和蓝牙；
6. zram、LMKD、dexpreopt 和后台限制的 1 GiB 内存调优；
7. Launcher、文件管理、音乐/视频、阅读、RetroArch 和 PPSSPP 应用验收。

音频不再沿用 Android 11 fix58 的二进制拼装方式；fix58 只作为 H616 HAL 与 H700
ALSA 设备已经具备可行性的证据。

## 8. 可立即执行与等待项

不需要实体机即可继续：

- A10-B1 全部编译和错误修复；
- A10-B2 boot/镜像组装、静态检查和部署包准备；
- 图形/音频 ELF、VINTF、SELinux 与源码差异的离线审计。

必须等待用户和设备在场：

- TF2 写入、U-Boot env 修改、冷启动和回退验证；
- UART/ADB 实机日志采集；
- 屏幕、按键、音频、电池、无线和休眠的功能验收；
- Android 11 fix58 最后一次冷启动取证。该取证不阻塞 Android 10 离线开发。

## 9. 近期十项执行队列（2026-09-07 调整）

1. 同步 Fix67 与本机 A→ENTER keylayout 的产品配置和证据；输入基础已完成；
2. 保持已设好的 AT4K 默认 HOME，保留 Launcher3；不授予额外特权；
3. 复核 720x480 布局、DPAD+A/B、弹窗退出与内存，不重做逐键长按校准；
4. Fix72 候选先离线验收，再由用户在场安排保留 data 的部署回归；
5. 保留本机 `8821cs.ko`、固件和 Fix70 两个固定哈希文件，补验重启恢复；
6. 用 DPAD 屏幕键盘实际输入密码，完成认证、DHCP、DNS、HTTPS 和重连；
7. 验证 DocumentsUI、安装器、授权、应用启动与 AT4K 返回，补验 HOME/IME 持久性；
8. 单独验证空白 data 首启和 TF2 独立冷启动，随后按需实现 Select 虚拟鼠标；
9. 音频、电量、亮度、Hall、蓝牙及低内存调优按独立后端推进；
10. 交叉执行 60 分钟老化、10 次冷启动与完整构建/空白 data 复现，不降低门槛。

AT4K 不是 framework 或网络服务的替代品。试装失败不切换整个产品为 Homlet，
也不启用全部电视 feature 来规避依赖。

## 10. 工作量判断

以下是 2026-09-02 的首图前历史估计，已被 Fix67 实机结果超越，不再作为剩余工期：

- 首轮镜像编译与产品依赖收敛：预计 1-3 个主要修复回合；
- init/存储/SELinux/VINTF：预计 2-6 次实体冷启动回合；
- 图形 ABI、HWC2 和面板：预计 3-10 个实现与实机验证回合，风险最高。

乐观情况下约 3-5 个有效开发日可以进入第一幅画面；常规预期为 1-2 周的离线编译
和实体机迭代。若确认 H616 图形用户态与 RGSP kernel 存在实质 ABI 差异，周期可能继续
增加。这里的时间不含长时间编译等待和用户不在设备旁造成的测试间隔。

## 11. 第一幅画面之后才决定的事项

- 是否从纯 32 位转为双 ABI；
- 是否引入 CedarX/OMX 硬件视频解码；
- Widevine L3 和在线视频清晰度策略；
- userdebug/user 发布版本、OTA、恢复镜像和多机型 overlay；
- 私人仓库的 CI、release 和大文件制品存储方式。
