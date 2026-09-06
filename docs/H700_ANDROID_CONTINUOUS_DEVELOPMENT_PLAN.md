# H700 Android 持续开发计划

> **归档提示（2026-09-02）**：本文保留此前 Android 11 headless bring-up 的阶段记录。
> 当前权威路线已经切换到 `H700_ANDROID10_MASTER_PLAN_20260902.md`，不得继续把
> R36S Android 11 framework 作为产品基线。

> **Android 10 当前进度（2026-09-06）**：Fix64 已取得 RGSP 720×480 安卓桌面截图。
> 用户已确认实体 LCD 显示一致；完整重启验证通过，长时老化和多次冷启动尚未完成。
> 当前证据与验收边界见 `H700_ANDROID10_FIX64_VISIBLE_UI_20260906.md`；
> 本文下方的 Android 11/headless 状态仍为历史记录，不作为当前状态。

**版本**：0.3
**日期**：2026-09-01
**状态**：执行基线（headless framework 已推进至 fix46；H616/H618 donor inventory 已完成初步结论）
**目标**：建立可扩展到多款 H700 掌机的 Android 平台，而不是为单一机型制作一次性镜像。

## 1. 总体结论

H700 已有量产 Android 实现，芯片级运行 Android 没有已知硬性障碍。当前 RGSP/RG34XXSP 原厂系统已经证明：

- SoC 为 Allwinner H700，厂商 BSP 使用 `sun50iw9`/H616 compatible 身份；
- 内核为 Linux 4.9.170，AArch64；
- 内核启用 Binder、Ashmem、ION 和 Android 兼容配置；
- 原厂 boot 分区是 Android legacy boot image 格式；
- 显示栈为 `/dev/fb0 + /dev/disp + /dev/ion + /dev/mali0`，没有 DRM/KMS；
- 原厂 Linux 前端可以稳定使用 LCD、输入、ALSA、AXP2202 电源/电池和厂商脚本；
- Android handoff 已通过多轮实机测试；当前已完成 Android init、system/vendor/data 挂载、Binder 权限、APEX/linkerconfig、zygote64 和 system_server bring-up。fix43 已完成实机验证，fix46 最新记录显示 RGSP 可稳定进入 Android console 并持续约 296 秒；当前仍是 headless framework，下一主线是恢复软件 framebuffer 或匹配的 H700 Gralloc/HWC/EGL。
- H616 Android 10 完整源码和镜像、H618 Android 12 完整源码和镜像，以及 H616 Longan 中的 H700 芯片级配置，已经足以支撑 H700 Android 主线开发。H618 继续作为结构对照，不作为当前 Linux 4.9 图形二进制 donor。
- 投影仪 `H21S-700-V3.0` UART 冷启动日志已确认其实际进入 Android 并达到 `sys.boot_completed=1`；其 RX 焊盘损坏只阻止在线命令和导出，不再作为 RGSP 主线前置条件。

项目采用以下总体路线：

```text
AOSP/Lineage Android 10 low-RAM、无 GMS
        +
H700 common 平台层
        +
每个机型的 kernel/DTB/panel/input/power/audio overlay
        +
先软件 framebuffer，再 GPU/HWC
        +
Linux 默认系统和可恢复 Android 双系统
```

## 2. 目标和非目标

### 2.1 目标

建立一套可扩展到以下目标机型的 H700 Android 平台：

```text
RG35XX Plus / RG35XX+
RG35XX H
RG35XX SP
RG28XX
RG40XX H
RG40XX V
RG CubeXX
RG34XX
RG34XX SP
RGSP
```

型号名称只作为目标清单，不作为硬件兼容性证据。每个型号必须建立硬件 manifest，确认 SoC、内存、屏幕、PMIC、音频、无线、振动和 U-Boot 版本。

### 2.2 非目标

第一阶段不追求：

- GMS、Play 商店和完整 Google 服务；
- Android 12/13/14；
- 动态分区、A/B OTA 和安全启动产品化；
- 一开始移植完整 Pegasus Qt/QML 主题生态；
- 直接复用 RK3326/R36S kernel、DTB、vendor、GPU 或音频二进制；
- 在没有 UART 和恢复介质的情况下持续写入真实启动分区。

## 3. 当前已验证基线

证据来源：

- `docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md`
- `docs/RGSP_H700_ANDROID_BOOT_ANALYSIS_20260826.md`
- `docs/RGSP_ANDROID_PROBE_STATUS_20260826.md`
- `docs/R36S_TO_H700_ANDROID_PORTING_BASELINE_20260826.md`

### 3.1 硬件和内核

| 项目 | 当前事实 | 影响 |
|---|---|---|
| SoC | H700，厂商标识 `sun50iw9`/`allwinner,h616` | 以 H700/sun50iw9 作为平台名，同时保留 compatible 兼容 |
| CPU/RAM | 4 x Cortex-A53，约 1 GiB RAM | 必须 low-RAM、禁用 GMS、控制后台和图片缓存 |
| Kernel | Linux 4.9.170，AArch64，厂商 out-of-tree BSP | 优先复用当前 kernel，不从新内核开始 |
| Android kernel config | Binder、Ashmem、ION 已启用 | Android init/framework 具备基础条件 |
| GPU | Mali-G31，`mali_kbase` + 厂商 `libmali` | GPU 版本必须和 kernel ABI 匹配 |
| Display | `fb0 + disp + ion + mali0`，无 `/dev/dri` | 先实现 framebuffer/software 合成，不能依赖 DRM/KMS |
| LCD | RG34XXSP 为 720x480，约 59 Hz | 需要设备级 panel/旋转/density 配置 |
| Audio | ALSA card 0 内置 codec，card 2 HDMI | 需要 tinyalsa/Audio HAL 适配 |
| Power | AXP2202 sysfs、厂商挂起脚本、Hall、PWM | 需要 Android health/power/lights/vibrator 适配 |
| Wireless | RTL8821CS SDIO，蓝牙经 UART | 需要按机型确认固件和 UART 端口 |

### 3.2 启动和存储

- U-Boot 为 2018.05，存在 `boot_normal`、`boot_recovery`、`boot_fastboot` 入口字符串。
- 原厂 `/dev/mmcblk0p4` 是 64 MiB Android legacy boot image；kernel、DTB 和 ramdisk 已完成读取、重打包和哈希校验。
- 原厂 ramdisk 是 BusyBox/Linux init，不是 Android ramdisk。
- 当前安全测试采用 TF1 保留原厂 Linux，TF2 承载 Android system/vendor/data。
- Android 11 alpha system 镜像由 R36S LineageOS 18.1 用户空间修改得到，仅作为 bring-up 材料，不是 H700 vendor，也不应作为最终发行版。
- 当前最高风险已从 Android init 转移到图形栈：SurfaceFlinger 被隔离，尚无确认匹配 H700 4.9.170/mali_kbase 的 Android Gralloc/HWC/EGL；因此当前仍是 headless framework，不是可见桌面。

### 3.3 当前调试条件与瓶颈

- 2026-08-29，Windows 已识别 CH343 USB-TTL 为 `COM4`，回环测试通过；RG SP V2.0 实测 UART 为 3.3 V、`ttyS0,115200 8N1`。
- 已保存从 BOOT0、BL31、U-Boot、Linux kernel、`/init` 到 `ANBERNIC login:` 的完整原厂 Linux 冷启动日志：`out/logs/uart/rgsp/rgsp_uart_20260829_190418_115200.log`，SHA-256 `5FC2A3CA3846CB3CB8689FEF00A8A39766D6A9BFD3A3FE7F769DBA4AFC643BEC`。
- 设备端 UDC 为 `not attached`，普通 USB-C 线不能代替 U-Boot UART。
- Android 早期启动失败时使用已验证的 3.3 V TTL UART，保持只读连接 `GND + 板 TX -> USB-TTL RX`，不要连接 VCC。
- 零基础测量、GND/UART 定位和接线安全流程见 `docs/H700_BEGINNER_MULTIMETER_UART_GUIDE.md`；任何 UART 连接必须先实测板端逻辑电平。

## 4. 平台架构决策

### 4.1 公共层和设备层

```text
Android Common
  H700 kernel contract
  common init/sepolicy/property
  low-RAM product configuration
  common input/audio/power interfaces
  common launcher and storage contracts

Device Overlay
  kernel/DTB
  LCD panel/timing/rotation
  keylayout/keymap
  PMIC/audio profile
  Wi-Fi/BT/rumble/Hall capabilities
  partition/bootargs
```

建议目录结构：

```text
device/roc/h700-common/
device/roc/<model>/
vendor/roc/h700-common/
vendor/roc/<model>/
kernel/allwinner/h700/       # 如后续获得/整理内核源码
hardware/roc/h700/           # 自研 HAL、daemon、诊断工具
packages/apps/RocLauncher/
```

### 4.2 设备 manifest

每个目标型号必须有一份 manifest，例如：

```json
{
  "model": "rg34xxsp",
  "soc": "h700",
  "platform": "sun50iw9",
  "ram_mb": 1024,
  "screen": {"width": 720, "height": 480, "rotation": 0},
  "input_profile": "rg34xxsp",
  "audio_profile": "axp2202-codec0",
  "brightness_backend": "sunxi-disp",
  "has_lid": true,
  "has_hdmi": true,
  "has_rumble": true,
  "has_wifi": true,
  "has_bluetooth": true
}
```

应用和平台服务只消费能力，不在业务代码中散落型号判断。

### 4.3 显示路线

按以下顺序实施：

1. Android init/ADB，无图形；
2. 软件 framebuffer 合成，优先支持 720x480；
3. Android 应用层 EGL/GLES 验证；
4. 尝试复用 Linux `libmali` 的行为和扩展；
5. 实现或移植 H700 匹配的 Gralloc/HWC/EGL；
6. 再考虑视频解码和 HDMI。

没有匹配 Android 版 Mali/HWC 时，软件渲染仍是可接受的 bring-up 和低内存产品路径。

## 5. 现有项目可复用资产

### 5.1 PegasusG by ROC

项目路径：`D:/Works/PegasusG by ROC`

关键资产：

- `src/h700_services.cpp`：AXP2202、电池、亮度、音量、Hall、挂起和厂商脚本调用；
- `H700/`：H700 打包、启动器、输入映射和应用布局；
- `H700/build_app.sh`：AArch64 交叉编译、设备 sysroot、SDL2/ALSA 链接；
- H700 720x480 UI 和游戏前端行为。

迁移方式：将 `H700Services` 提取为平台接口，保留 Linux backend，再增加 Android system service/vendor daemon backend。不要把 shell 命令原样搬进 Android 应用。

### 5.2 ROCreader

项目路径：`D:/Works/ROCreader`

关键资产：

- `H700/sysroot_device/`：设备 Linux sysroot；
- `sync_device_sysroot.sh`：从设备同步库、头文件和 pkg-config；
- H700 显示、EGL、输入、电源和双屏探针；
- 低 glibc 交叉编译和部署流程。

注意：sysroot 中的 `libmali.so`、`libEGL.so`、`libGLESv2.so` 是 Linux/glibc AArch64 库，不能直接放进 Android vendor。它们适合做 ABI、扩展和硬件行为参考。

### 5.3 ROCgalgame

项目路径：`D:/Works/ROCgalgame`

关键资产：

- H700 720x480 profile 和按键映射；
- 游戏进程启动/退出生命周期；
- 音频、存档、ROM 扫描和状态恢复；
- H700 打包和部署脚本。

注意：当前 H700 README 默认 KMSDRM，而 RGSP 没有 DRM/KMS。Android/LINUX 目标必须改为实际可用的 framebuffer/mali/Android Surface 后端。

### 5.4 ROCwallpaper

项目路径：`D:/Works/ROCwallpaper`

关键资产：

- Android Gradle/Kotlin 工程；
- Activity、WallpaperService、Surface 生命周期；
- `EGL14`、OpenGL ES 2.0 context、window surface 和 swap buffers；
- 纹理缓存和低内存渲染经验。

迁移方式：先将其改造成 H700 Android EGL/GLES 诊断 APK。目标 Android 10 时需要检查并将 `minSdk` 从当前 API 31 调整到 API 29，逐项核对 API 使用。

## 6. 持续开发阶段

每个阶段都必须有可验证的退出条件。没有达到退出条件，不进入下一阶段。

### P0：工程治理、恢复和观测

**目标**：建立不会刷死设备的开发环境。

- [x] 接入 3.3 V TTL UART，确认 BOOT0、U-Boot、kernel、Linux console，并采集 Android fix40–fix42 日志；
- 保留两张 TF1：一张原厂恢复卡，一张测试卡；
- 备份 GPT、env、boot、rootfs、vendor、data、DTB 和内核配置；
- 统一 SHA-256 命名和 `input/`、`work/`、`out/` 目录；
- 每次真实设备写入都记录目标设备、分区、源哈希、读回哈希和回退步骤。

**退出条件**：任何 Android 测试失败后，能够在 5 分钟内回到原厂 Linux，并能保存完整 UART 日志。

### P1：硬件 manifest 和 Linux oracle

**目标**：把 RGSP 的 Linux 行为固化成可重复测试。

- 收集 model、compatible、panel、分辨率、旋转、PMIC、Codec、Wi-Fi/BT、Hall、PWM；
- 为 `fb0/disp/ion/mali0` 编写最小测试工具；
- 记录亮度 ioctl、ION buffer、EGL 初始化和 ALSA mixer 行为；
- 对原厂前端进行 `strace`/FD/maps 观察；
- 建立第一份 `rg34xxsp` manifest，并预留其他型号字段。

**退出条件**：在 Linux 下可独立运行显示、输入、音频、电源和亮度回归测试。

### P2：Android 10 构建基线

**目标**：在主机完成可重复的 Android 10 构建环境。

- 使用 AOSP/Lineage Android 10，64 位、low-RAM、无 GMS；
- 建立 `h700-common` product/device 配置；
- 先使用 permissive SELinux 做 bring-up；
- 移除 RK3326 loader、kernel、DTB、graphics/audio/power vendor；
- 生成最小 system/vendor/data 镜像和构建 manifest；
- 固定工具链、源码 revision 和第三方许可证。

**退出条件**：主机可以从干净环境重建相同 SHA-256 的最小镜像。

### P3：Android init、ADB 和挂载

**当前状态：bring-up 基本达成（fix46）；产品化退出条件尚未满足，headless framework 和图形栈仍在验证。**

**目标**：先证明 Android 用户空间能运行，不碰图形。

- 以原厂 boot header、H700 kernel 和 RGSP DTB 为基础；
- 构建 Android ramdisk、first-stage init、ueventd 和 fstab；
- 从 TF2 挂载 system/vendor/data；
- 处理 system-as-root，不重复挂载 `/system`；
- 启动 `servicemanager`、property service 和 `adbd`；
- 所有阶段标记写入 TF2 持久日志。

**退出条件**：UART 能看到 Android init，ADB shell 可用，`post-fs-data` 完成，连续重启 10 次成功。

### P4：软件显示和输入

**当前状态：已具备 donor 和候选实现，仍是最高优先级验证项。** SurfaceFlinger 目前被隔离，
需要先验证软件 framebuffer，再接入 H616/H700 匹配的 Gralloc/HWC/EGL 成套实现。

**目标**：优先取得第一幅 Android 画面，再验证硬件加速路径。

- 实现最小 framebuffer HWC 或 software composer；
- 对接 `/dev/fb0` 和必要的 `/dev/disp`；
- 固定 32 bpp、720x480、旋转和 vsync 行为；
- 以 `ROCwallpaper` 为 EGL/GLES 应用层验证器；
- 生成 Android `.kl/.kcm`，按设备名匹配输入；
- 完成基础 Launcher 和焦点导航。

**退出条件**：SurfaceFlinger 或等效显示路径能稳定显示测试画面，按键可操作，连续运行 60 分钟不黑屏。

### P5：H700 平台服务和 HAL

**目标**：把已有 Linux 硬件经验包装成 Android 系统接口。

- `healthd/health HAL`：AXP2202 电池、充电、温度；
- `lights/brightness`：厂商亮度 sysfs/ioctl；
- `power`：suspend、reboot、poweroff、Hall 自动休眠；
- `vibrator`：PWM channel 2，限时和串行访问；
- `audio.primary`：tinyalsa、speaker/headphone/HDMI；
- Wi-Fi/蓝牙：复用固件和 Realtek 初始化流程；
- 统一 root 权限边界，应用不直接拥有 disp/ion/PWM 写权限。

**退出条件**：按键、音频、亮度、电池、关机和基本休眠可用；所有 HAL 失败都有日志和安全回退。

### P6：GPU、媒体和 HDMI

**目标**：在软件显示基础上逐项增加硬件能力。

- 对比 Linux `libmali` 与 Android 所需 ABI；
- 搜索并验证 Android 版 `libmali/gralloc/hwcomposer/EGL`；
- 先测试 EGL/GLES，再测试 HWC buffer import；
- 评估 H700 VE/视频解码库；
- 实现 HDMI 输出切换、音频路由和恢复；
- 如果 GPU/HWC 无法复现，保持软件渲染产品分支，不阻塞主线。

**退出条件**：GPU 加速路径可重复启停，或明确记录为可选能力；软件渲染路径继续通过回归。

### P7：前端、模拟器和存储

**目标**：形成掌机可用体验。

- 先移植 Android Launcher/RetroArch，不先移植完整 Pegasus Qt/QML；
- 复用 ROCgalgame 的游戏生命周期和输入协议；
- ROM 使用公共扫描服务，配置和存档写入 Android data；
- 支持 FAT32/exFAT 共享 ROM、热拔出、磁盘满和损坏文件；
- 将 PegasusG 的元数据、主题和启动协议抽取为可选模块；
- 处理应用切换时显示、音频和输入资源释放。

**退出条件**：至少 20 次游戏启动/退出循环无资源泄漏，5,000 个 ROM 扫描不触发 OOM。

### P8：多机型扩展和发布

**目标**：从 RGSP 单机扩展为 H700 平台。

- 选择一台不同屏幕比例的第二机型验证 overlay；
- 每个型号建立独立 DTB、panel、keylayout、audio/power profile；
- system/common 尽量保持相同，boot/vendor 按机型生成；
- 建立构建矩阵和每型号硬件回归；
- 输出恢复镜像、升级说明、哈希清单和已知限制；
- 默认 Linux，Android 通过一次性按键/启动项进入，失败自动回退。

**退出条件**：至少两种不同屏幕比例机型使用同一 common system 成功启动并完成基本功能。

## 7. 验收标准

### 7.1 启动级

- U-Boot、kernel、handoff、Android init 日志完整；
- Android system/vendor/data 挂载正确；
- ADB 可用；
- 连续启动/回退 20 次；
- 原厂 Linux boot/env 哈希保持不变，除非有明确批准。

### 7.2 图形级

- LCD 正确分辨率、方向和刷新率；
- 软件渲染或 GPU 渲染可明确识别；
- Surface 创建、销毁和重建无黑屏；
- 60 分钟稳定运行；
- 原厂前端与 Android 之间不存在 fb0/disp/ion 资源争用。

### 7.3 平台级

- 所有实体按键和音量键正确映射；
- speaker/headphone/HDMI 音频路由正确；
- 电池、充电、亮度、Hall、振动可用；
- 关机、重启、休眠、唤醒可恢复；
- Wi-Fi/蓝牙可连接，时间异常不阻塞主界面。

### 7.4 产品级

- 20 次游戏启动/退出循环；
- 5,000～10,000 ROM 扫描；
- SD 热拔出、磁盘满、损坏图片和超长文件名；
- 无网、错误 RTC、DNS/TLS 失败；
- Android 崩溃后回到 Linux；
- 不集成 GMS 时内存峰值和后台进程受控。

## 8. 风险与停止条件

| 风险 | 等级 | 触发条件 | 处理 |
|---|---|---|---|
| UART 临时铜线接触不稳 | P0（已缓解，RGSP） | 日志中断或乱码 | RGSP 已有稳定只读线路；投影仪主板目前无法焊接，暂不作为主线依赖 |
| MMC/U-Boot 编号不稳定 | 高 | `mmc dev` 探测会停机或误回退 | 采用 TF1 handoff，避免持久探测 TF2 |
| Android init/fstab 不匹配 | 高 | system-as-root 重复挂载、post-fs-data 失败 | 只保留一种挂载拓扑，持久记录阶段 |
| 无 Android HWC/Gralloc | 高 | SurfaceFlinger 无法创建 buffer | 先走软件 framebuffer；GPU 作为可选分支 |
| Linux `libmali` 不能用于 Android | 高 | 依赖 glibc 或 ABI 不符 | 寻找 Android 版或实现软件渲染 |
| 1 GiB RAM | 中高 | zygote/system_server/模拟器 OOM | Android 10 low-RAM、无 GMS、限制缓存 |
| 机型硬件差异 | 中高 | 同型号不同 panel/PMIC/存储 | manifest + overlay，禁止按型号猜测 |
| 闭源媒体栈 | 中高 | 视频解码、HDMI 或 HWC 崩溃 | 先禁用硬解，记录为可选能力 |
| Root 权限过大 | 中 | 应用可直接写 disp/ion/PWM | 平台 daemon + 最小权限 |

### 明确停止条件

满足任一条件时，停止扩大范围，先重新评估：

- 已有 UART 仍无法在 2 周内确定 Android 停点；
- Android init/ADB 已稳定，但 4～6 周无法得到最小软件 framebuffer 画面；
- GPU/HWC 经过明确 ABI 比对仍无可用实现；此时保留软件渲染产品分支；
- 第二机型 overlay 需要修改大量 common 代码，说明架构边界错误；
- 任何测试会破坏唯一原厂恢复路径。

## 9. 多窗口协作规则

### 9.1 工作域所有权

| 工作域 | 负责内容 | 可修改目录 |
|---|---|---|
| Boot | U-Boot、boot image、MMC、回退 | `ramdisk/`、`tools/`、`out/` |
| Kernel/DTB | kernel config、DTB、panel、驱动 | `kernel/`、`device/roc/*` |
| Android Build | AOSP product、init、fstab、sepolicy | `android/`、`device/`、`vendor/` |
| Graphics/HAL | framebuffer、EGL、Gralloc、HWC、Audio/Power HAL | `hardware/roc/` |
| Platform | H700 服务、输入、电源、存储协议 | `platform/`、抽取后的库 |
| Frontend | Launcher、RetroArch、Pegasus、ROCgalgame | 各应用仓库 |
| Device Test | UART、ADB、启动日志、回归 | `research/`、`out/logs/` |
| Docs | 基线、决策、验收和变更记录 | `docs/` |

### 9.2 并发和写入规则

- 共享工作区中，不允许两个窗口同时修改同一个 boot image、GPT 镜像、env 或设备分区。
- 大型镜像和闭源 vendor 放入 `input/` 或 `work/`，不提交到源码仓库。
- `out/` 只放可重复生成或明确标注哈希的产物。
- 真实设备写入必须由 Device Test 窗口执行，其他窗口只生成普通文件。
- 任何修改都必须说明是否写入真实块设备。
- 不得回滚其他窗口未创建的用户改动；发现冲突时在文档或消息中记录，不直接覆盖。

### 9.3 产物命名

```text
<platform>-<device>-<component>-<version>-<date>.<ext>

例：
rgsp-h700-handoff-boot-p0-20260827.img
rg34xxsp-android10-system-p3-20260827.img
rgsp-uart-boot-20260827.log
```

每个产物必须同时提供：

```text
SHA256SUMS.txt
输入文件列表
构建命令
工具版本
验证结果
已知限制
```

### 9.4 窗口交接模板

```text
任务：
工作域：
输入文件及 SHA-256：
修改文件：
已验证事实：
仍是假设：
是否写入真实设备：是/否
关键命令和结果：
产物及 SHA-256：
失败和回退方式：
下一窗口必须知道：
```

## 10. 当前执行队列

按优先级执行，不并行进行高风险刷写：

1. [已完成 2026-08-29] 接入并验证 RGSP 3.3 V UART，保存完整 U-Boot/Kernel/Linux 登录日志；
2. [已完成 2026-08-31] 通过持久 logdw/UART 证明 zygote64 和 system_server 可启动，定位 fix42 的 LightsService/SurfaceFlinger Watchdog 停点；
3. [已完成 2026-09-01] fix46 实机验证：RGSP 可进入 Android console 并持续约 296 秒，仍无图形桌面；
4. [下一步] 完成 RGSP 硬件 manifest 和 Linux oracle 测试；
5. [已完成 2026-09-01] 对 H616/H618 源码和镜像完成第一轮 inventory、版本/ABI/图形栈结论；
6. [下一步] 对 `ROCreader/H700/sysroot_device` 做 Android/Linux 库分类和 ABI 报告；
7. [下一步] 建立 Android 10 low-RAM host build；
8. [下一步] 从 H616 donor 生成 Mali/Gralloc/HWC/ION/EGL 依赖清单并构建第一版候选包；
9. [下一步] 实现最小软件 framebuffer 显示；
10. 抽取 PegasusG 的 H700Services 为平台接口；
11. 接入输入、Audio HAL、Power/Health/Lights/Vibrator；
12. 评估 H700 Android `libmali`/Gralloc/HWC 与当前 kernel 的可复用程度；
13. 选择第二款不同屏幕比例 H700 机型验证 common/overlay 架构。

## 11. 相关文档和项目

- [RG34XXSP H700 硬件基线](/D:/Works/H700Android/docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md)
- [RGSP Android 启动分析](/D:/Works/H700Android/docs/RGSP_H700_ANDROID_BOOT_ANALYSIS_20260826.md)
- [RGSP Android 探针状态](/D:/Works/H700Android/docs/RGSP_ANDROID_PROBE_STATUS_20260826.md)
- [R36S 到 H700 Android 参考基线](/D:/Works/H700Android/docs/R36S_TO_H700_ANDROID_PORTING_BASELINE_20260826.md)
- [PegasusG by ROC](/D:/Works/PegasusG%20by%20ROC/README.md)
- [ROCreader H700 构建说明](/D:/Works/ROCreader/H700/README.md)
- [ROCgalgame H700 说明](/D:/Works/ROCgalgame/H700/README.md)
- [ROCwallpaper Android 工程](/D:/Works/ROCwallpaper/README.md)

## 12. 版本记录

### 0.2 — 2026-08-31

- 将当前状态更新为 fix42 已验证 system_server、fix43 候选待测；
- 明确图形 HAL/SurfaceFlinger 是当前最高优先级阻塞；
- 纳入 H616/H618 完整源码和镜像的选择性分析任务；
- 记录投影仪 UART 暂不可用不阻塞 RGSP 主线。

### 0.3 — 2026-09-01

- 纳入 H616/H618 完整源码和镜像与 H700 Longan 配置的综合能力评估；
- 明确 H616 Android 10 为当前主 donor，H618 Android 12 仅作结构/API 对照；
- 纳入投影仪 H21S-700 冷启动日志，确认其已进入 Android 并达到 `sys.boot_completed=1`；
- 将 RGSP 最新状态更新为 fix46：可进入 Android console，但图形栈仍未恢复；
- 将投影仪 RX 修复降级为可选 donor 提取任务，不再作为 RGSP 图形主线前置条件。

### 0.1 — 2026-08-27

- 初始建立 H700 多机型 Android 平台计划；
- 纳入 RGSP/RG34XXSP 当前启动探针和 fix5 状态；（历史版本，当前状态见 0.2）
- 固化 Android 10 low-RAM、无 GMS、软件 framebuffer 优先策略；
- 固化 common/overlay 架构和多窗口所有权规则；
- 纳入 PegasusG、ROCreader、ROCgalgame、ROCwallpaper 的可复用资产。
