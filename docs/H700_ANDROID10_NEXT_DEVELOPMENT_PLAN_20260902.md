# H700 Android 10 近期开发执行计划

日期：2026-09-02  
基线：提交 `fb451d6`，H616 Android 10 主线，RGSP H700 硬件事实

## 1. 当前起点

2026-09-06 更新：已有实机运行的 Android 10 镜像，Fix64 已实现原生框架、
Launcher、应用列表和真实 LCD 输出，用户已确认实体画面。当前是 B4 首图已实现、
稳定性验收未完成，开始并行推进 B5.1 输入接入。

近期工作不再从首轮编译开始。需保留的验收欠项包括：60 分钟老化、连续冷启动、
ADB 单独验证、将所有现场修复纳入干净构建。显示证据见
`H700_ANDROID10_FIX64_VISIBLE_UI_20260906.md`；输入准备见
`H700_ANDROID10_INPUT_PRECALIBRATION_20260906.md`。

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
4. 先以 `-j4` 构建 `systemimage vendorimage ramdisk`，完整日志写入 D 盘；
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

目标：在不写设备的情况下准备完整、可回退的 Android 10 测试包。

1. 从 RGSP 已验证启动链取 kernel、DTB、boot header 和 cmdline；
2. 将 Android 10 ramdisk 与 RGSP kernel/DTB 组合，不引入 H616 bootloader、DTS 或
   分区表；
3. 静态检查 boot header、加载地址、页大小、ramdisk 内容、fstab、PARTUUID、init
   import、ueventd 权限和 SELinux 文件；
4. 检查 system/vendor 的 VINTF、32 位 ELF 闭包、Binder 配置和 flattened APEX；
5. 生成仅面向 TF2 的部署目录、SHA-256 清单和回退说明；
6. 在用户不在设备旁时只准备文件，不执行写卡、U-Boot env 修改或重启。

退出条件：部署包可重复生成，所有输入都有来源和哈希，写入动作仍为显式人工步骤。

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

2026-09-06 更新：Fix64 已取得真实 720×480 锁屏、桌面和应用列表截图，
修复 GPU/ION 应用访问权限及 Homlet 编译路径，并加入本机专用的软件 VSYNC
兼容选项。完整证据和剩余问题见 `H700_ANDROID10_FIX64_VISIBLE_UI_20260906.md`。
用户已确认实体 LCD 与桌面截图一致，Fix64 完整重启和看门狗自动退出验证通过。
这不代表下述 60 分钟和 10 次冷启动退出条件已经满足。

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

1. 物理按键、休眠键、Hall 和无触摸导航；
2. H616 Audio HAL 5.0 对接 H700 `audiocodec` card 0/device 0，并以 H700 投影仪
   Android 10 日志校验服务顺序和 mixer 路由；
3. AXP2202 电量、充电、关机、背光和亮度；
4. 振动、RTL8821CS Wi-Fi 和蓝牙；
5. zram、LMKD、dexpreopt 和后台限制的 1 GiB 内存调优；
6. Launcher、文件管理、音乐/视频、阅读、RetroArch 和 PPSSPP 应用验收。

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

## 9. 近期十项执行队列（2026-09-06 调整）

1. 保留 Fix64 制品、GPU/显示证据、恢复哈希和运行期日志上限；
2. 修复 `/dev/input/event*` 权限和标签，确认三个本机输入设备进入 EventHub；
3. 已完成 RGSP 短按逐键记录并安装临时基础 keylayout；长按、重复、斜向和组合键
   延后到映射工具阶段，其他 H700 机型必须独立校准；
4. 验证桌面 DPAD+A/B 导航，并保留游戏中的标准 BUTTON/HAT 语义；
5. 评测 ARM32/API29、无 GMS、720x480、低内存的轻量 TV 式桌面和屏幕键盘；
6. 实现虚拟鼠标模式、滚动/拖动与紧急退出，避免重复输入及抢占游戏 Select；
7. 修复设置服务依赖（当前首要是 wifi 未发布），完成设置、文件管理、PPSSPP 的
   无触摸操作闭环；
8. 交叉执行 60 分钟老化、多次冷启动、GPU 帧时间与内存检查，不降低 B3/B4 门槛；
9. 继续音频、电池/亮度、电源、无线和内存调优；
10. 完整回收现场补丁，验证干净构建、部署与恢复的可重复性。

## 10. 工作量判断

按当前资料完整度，首图不是从零开始，但也不是一次编译即可完成：

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
