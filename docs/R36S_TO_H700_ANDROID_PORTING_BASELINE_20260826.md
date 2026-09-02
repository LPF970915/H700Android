# R36S 到 RG34XXSP/H700 Android 移植参考基线

> **定位更新（2026-09-02）**：R36S 现在仅是启动、分区和诊断方法参考，Android 11
> system/vendor 已封存。产品实现基线为 H616 Android 10，见
> `H700_ANDROID10_MASTER_PLAN_20260902.md`。

日期：2026-08-26  
目标设备：ANBERNIC RG34XXSP-class，Allwinner H700 / `sun50iw9`  
用途：供多个开发窗口共享上下文、拆分任务和避免重复或危险操作

## 1. 结论

R36S 的 Andr36oid 和 R36S-Multiboot 可以作为 H700 Android 移植的重要
架构参考，但不能作为二进制来源直接刷写。

应当复用的内容：

- LineageOS/AOSP 设备树的组织方式；
- Android 系统镜像的生成流程；
- 每个系统拥有独立 boot/root/data 分区的思路；
- U-Boot 上电按键选择系统的实现方式；
- 根据实际分区号改写 boot 参数和 Android `fstab` 的方法；
- 多面板分别维护 DTB 的方法；
- 低内存设备使用 zram 和 low-RAM 配置的经验。

严禁直接复用的内容：

- RK3326 kernel、DTB、内核配置；
- Rockchip `idbloader.img`、`trust.img`、U-Boot；
- R36S 的 GPT 扇区偏移和分区编号；
- `rk30board` HAL、Gralloc、HWC、GPU 和音频库；
- R36S LCD、按键、电源和无线硬件参数；
- 完整 Andr36oid 或 R36S-Multiboot 镜像。

CPU 性能强弱不是移植难度的主要决定因素。Android 能否较快落地，主要取决于
厂商 BSP、内核 Android 功能、显示/GPU HAL、设备树和可用闭源库是否成套。

## 2. 当前实机已验证事实

以下内容来自本项目的 RG34XXSP 实机只读探测，不是由 R36S 推断：

| 项目 | 当前事实 |
|---|---|
| SoC 身份 | H700，厂商 BSP 沿用 `sun50iw9` / H616 compatible |
| CPU / RAM | 4 x Cortex-A53，约 973 MiB 可用内存 |
| 原厂内核 | Linux 4.9.170，AArch64 |
| Android 内核能力 | Binder、Ashmem、ION 已启用 |
| GPU | Mali-G31，厂商 `mali_kbase` + `libmali` |
| 显示 | 无 DRM；`fb0 + disp + ion + mali0` |
| 内屏 | 720 x 480，约 59 Hz，32 bpp |
| boot 分区 | `/dev/mmcblk0p4`，legacy Android boot image 格式 |
| boot image | H700 kernel + Linux BusyBox ramdisk，不是 Android 用户空间 |
| U-Boot | 存在 `boot_normal`、`boot_recovery`、`boot_fastboot` 字符串 |
| 默认 Linux rootfs | `/dev/mmcblk0p5` |
| TF2 | Linux 下表现为 `/dev/mmcblk1p1`，当前用作外置 ROM 卡 |
| fastboot | 尚未证明 USB fastboot 协议真实可用 |
| TF2 启动 | 尚未证明 U-Boot 能在启动阶段读取 TF2 |

详细证据见：

- `docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md`
- `docs/RGSP_H700_ANDROID_BOOT_ANALYSIS_20260826.md`

## 3. R36S 路线的实际结构

截至 2026-08-26，公开参考实现包括：

- Andr36oid R36S LineageOS 18.1 device tree：
  `https://github.com/andr36oid/android_device_gameconsole_r36s`
- Andr36oid 发布仓库：
  `https://github.com/andr36oid/releases`
- Andr36oid Docker 构建环境：
  `https://github.com/andr36oid/docker_build`
- R36S-Multiboot：
  `https://github.com/EatPrilosec/R36S-Multiboot`

R36S device tree 的公开分支为 `lineage-18.1`。其中可观察到：

1. `BOOT/boot.ini` 使用 U-Boot 加载 AArch64 `Image` 和指定面板 DTB。
2. `mkimg.sh` 创建 GPT、FAT boot 分区和 ext4 system 分区。
3. bootloader、kernel、DTB 和 Android system image 被写入同一整卡镜像。
4. 每种 LCD panel 使用独立 DTB。
5. R36S-Multiboot 为每个系统建立独立 boot/root 分区。
6. 安装脚本把实际分区号写入 `boot.<os>.ini` 和 `fstab.rk30board`。
7. 上电时通过按键选择 ArkOS、Android 或其他 Linux 系统。
8. Android `fstab` 使用 zram，公开配置为 1 GiB。

需要注意：R36S-Multiboot 中的 SD2 支持主要面向共享 ROM 存储。它不能证明
RG34XXSP 的 Boot ROM 或 U-Boot 能直接从 TF2 冷启动 Android。

## 4. H700 推荐系统版本

第一阶段推荐：**AOSP Android 10，64 位，low-RAM/Go 风格配置，不集成 GMS。**

原因：

- Android 10 对约 1 GiB RAM 比完整 Android 11/12 更容易控制；
- H700 当前 vendor kernel 4.9 与 Android 10 时期 BSP 更接近；
- H616 平台存在 Android 10 BSP/板级实现，可用于研究 Allwinner HAL 结构；
- 先匹配 Allwinner 图形和多媒体栈，比先追求 LineageOS UI 更重要；
- 无 GMS 构建可以降低常驻内存、存储和后台服务压力。

第二阶段可以尝试：**LineageOS 18.1 / Android 11 极简构建。**

Android Go 不是一个可以下载后直接刷入 H700 的通用镜像。本项目实际需要的是
AOSP low-RAM 产品配置、精简软件包以及设备专用 kernel/vendor/HAL。官方 Google
Go 应用和 GMS 也不能视作 AOSP 的一部分随意打包。

## 5. 建议的 TF1 / TF2 架构

在 TF2 启动能力得到串口实测前，采用保守结构：

```text
TF1 / mmcblk0
  原厂 Boot ROM 所识别的启动介质
  SPL + U-Boot + env
  原厂 Linux boot/rootfs
  Android boot.img 或 Android kernel/ramdisk/DTB 启动入口
  Linux/Android 启动选择逻辑

TF2 / Linux 下暂记为 mmcblk1
  android_system   ext4
  android_vendor   ext4
  android_userdata ext4
  可选 shared_roms exFAT
```

第一版的目标是从 TF1 加载 Android kernel、ramdisk 和 RG34XXSP DTB，再由
Android first-stage init 挂载 TF2 上的 system/vendor/userdata。只有在 U-Boot
实测能稳定初始化并读取第二个 MMC 控制器后，才考虑把 Android boot 组件也迁移
到 TF2。

这里的 `/dev/mmcblk0`、`/dev/mmcblk1` 是当前 Linux 运行时编号。U-Boot 中的
`mmc 0`、`mmc 1` 不保证与 Linux 编号相同，必须通过串口逐个验证。

## 6. R36S 到 H700 的对应替换

| R36S 实现 | H700 对应实现 |
|---|---|
| RK3326 U-Boot 按键 multiboot | 保留 H700 vendor U-Boot，增加可恢复启动选择 |
| `Image` + R36S DTB | H700 4.9 Android kernel + RG34XXSP DTB |
| `androidboot.hardware=rk30board` | 新建 H700 hardware/device 名称，不沿用 `rk30board` |
| `fstab.rk30board` | H700 first-stage `fstab`，按实测 MMC/by-name 路径生成 |
| Rockchip Gralloc/HWC | Allwinner H616/H700 匹配的 Gralloc/HWC/EGL/libmali |
| R36S panel0..panel6 | RG34XXSP 专用 panel、分辨率和旋转配置 |
| RK817/板级电源实现 | AXP2202 电池、亮度、休眠、LED 和 Hall 适配 |
| R36S 输入设备 | RG34XXSP evdev/GPIO/ADC 按键映射 |
| R36S Wi-Fi/BT | RTL8821CS SDIO + Realtek UART 蓝牙适配 |
| SD 卡 system/root/data | TF2 system/vendor/userdata，TF1 保留启动控制 |

## 7. 分阶段实施路线

### P0：备份和恢复能力

- 备份 GPT、`mmcblk0p1`、`p2`、`p3`、`p4`。
- 保存 `/mnt/vendor`、`/mnt/data`、完整设备树和 `/proc/config.gz`。
- 计算 SHA-256，并至少验证一次备份可读。
- 准备备用 TF1，不在唯一原厂卡上测试。
- 接通并记录 UART 串口日志。

完成条件：能恢复原厂启动，且任何 Android 探针失败后不会失去 Linux 环境。

### P1：证明 TF2 的 U-Boot 可见性

- 在 TF2 FAT 分区放置唯一命名的小型测试文件。
- 串口中执行 MMC 枚举、选择和 FAT/ext4 读取测试。
- 记录 U-Boot MMC 编号、控制器地址和可读文件系统。
- 不修改 env，不写 bootloader，不改 GPT。

完成条件：明确 U-Boot 是否能读取 TF2，以及对应的设备和分区语法。

### P2：最小 Android boot 探针

- 以原厂 legacy `boot.img` header 为模板。
- 使用 H700 vendor kernel 和 RG34XXSP DTB。
- 构建只包含 Android init、ueventd 和 ADB 所需文件的 ramdisk。
- 首次探针保持 SELinux permissive，仅用于 bring-up。
- 通过串口、USB gadget 或屏幕日志确认 `/init` 已执行。

完成条件：进入 Android init/ADB shell，不要求 SurfaceFlinger 和完整 system。

### P3：挂载 TF2 Android 分区

- 为 TF2 建立测试用 system/vendor/userdata 分区。
- 优先使用稳定的 PARTUUID 或 by-name 路径，避免硬编码 Linux 枚举顺序。
- 在 first-stage init 中挂载 system/vendor。
- 启用 userdata 格式化、扩容和错误恢复流程。
- 加入 512-1024 MiB zram，按实测内存压力调整。

完成条件：Android framework 能启动，ADB 中可见 system/vendor/data。

### P4：显示和输入

- 先验证 framebuffer/软件合成路径。
- 再匹配 `mali_kbase`、`libmali`、EGL、Gralloc 和 HWC 版本。
- 适配 720x480、方向、density、vsync 和背光。
- 完成全部实体按键、音量键、电源键和 Hall 输入映射。

完成条件：SurfaceFlinger 稳定显示，Launcher 可操作，连续启动不黑屏。

### P5：外围设备和低内存优化

- ALSA Audio HAL、耳机检测和扬声器路由。
- RTL8821CS Wi-Fi、蓝牙、USB gadget/host。
- AXP2202 电量、充电、温度、亮度和关机。
- suspend/resume、翻盖休眠、唤醒源。
- low-RAM、LMKD、zram、后台进程和动画裁剪。

完成条件：达到日常可用的掌机系统基线。

### P6：双启动产品化

- 在不破坏原厂恢复路径的前提下实现启动选择。
- 默认 Linux，按键临时进入 Android。
- 持久默认项必须有超时和自动回退。
- Android 更新只写 Android 分区，不能覆盖 SPL/U-Boot/env。

完成条件：Linux 和 Android 均可独立升级和恢复，连续切换测试通过。

## 8. 多窗口协作约定

所有新窗口开始工作前，按顺序阅读：

1. 本文档；
2. `docs/RGSP_H700_ANDROID_BOOT_ANALYSIS_20260826.md`；
3. 与任务相关时再读完整硬件基线。

任务拆分建议：

| 工作窗口 | 所有权范围 | 禁止越界 |
|---|---|---|
| Boot | SPL/U-Boot/env、MMC 枚举、启动选择 | 不写真实介质，除非已有备份和明确批准 |
| Kernel/DTB | kernel config、panel、input、power、Wi-Fi | 不引入 RK3326 二进制或 DTS |
| Android Build | AOSP/Lineage product、ramdisk、fstab、SELinux | 不猜测分区号或硬件属性 |
| Graphics/HAL | EGL、Gralloc、HWC、SurfaceFlinger | 不混用不同版本 libmali/mali_kbase |
| Image/Tools | GPT 镜像生成、校验、刷写说明 | 默认只生成普通文件，不直接写块设备 |
| Device Test | UART、ADB、启动日志、回归表 | 测试结果必须注明固件哈希和日期 |

每个窗口交付内容必须包含：

- 修改或新增的文件；
- 使用的输入文件及 SHA-256；
- 已验证事实和仍为假设的内容；
- 执行过的命令及关键结果；
- 是否涉及真实设备写入；
- 下一窗口开始前必须知道的风险。

多个窗口不得同时修改同一个 boot image、GPT 镜像或设备分区。中间产物统一放入
`work/`，最终可测试产物放入 `out/`，外部原始输入放入 `input/`。大型镜像、备份
和闭源 vendor 文件不应提交到源码仓库。

## 9. 安全边界

以下操作默认禁止，必须在完整备份、串口恢复和明确人工确认后才允许：

- 向真实 `/dev/mmcblk*` 执行 `dd`；
- 覆盖 SPL、boot0、U-Boot、trust、env 或 GPT；
- 修改当前唯一原厂 TF1；
- 把 R36S/RK3326 镜像写入 H700；
- 在未验证目标路径时自动格式化或扩展分区；
- 把发现 `boot_fastboot` 字符串当成 fastboot 已可用；
- 把 Linux 下的 MMC 编号直接套用到 U-Boot 或 Android `fstab`。

本项目工具默认只能读取、解包和生成普通镜像文件，不能自动写入块设备。

## 10. 当前决策与待验证问题

已确定：

- 采用 R36S 的架构经验，不采用其二进制。
- 第一目标为 Android 10 low-RAM、无 GMS。
- 原厂 Linux 必须保留为默认和恢复系统。
- TF2 优先承载 Android system/vendor/userdata。
- Android boot 探针先于完整图形系统。

待验证：

- U-Boot 是否能初始化并读取 TF2；
- U-Boot 中两个 MMC 控制器的编号；
- boot image 内 DTB 的真实来源和装载方式；
- H700/H616 Android BSP 中可用 HAL 与当前 4.9.170 kernel 的版本匹配度；
- SurfaceFlinger 能否通过现有 fbdev/disp/ION 栈启动；
- 原厂 `libmali` 是否包含 Android Gralloc/HWC 所需接口；
- Android suspend/resume 是否能复用当前 AXP2202 和 Hall 驱动；
- fastboot USB gadget 是否真实工作。

## 11. 下一项统一任务

当前不再以“开始下载完整 AOSP”作为前置条件：项目已进入 headless framework bring-up，
且用户已经拥有 H616/H618 的完整 Android 源码和镜像。下一项统一任务改为：

**对 H616/H618 资料做选择性 inventory 和 ABI/图形栈对照，优先寻找与 H700
4.9.170、sun50iw9、fbdev/disp/ION、mali_kbase 匹配的成套 HAL。**

UART 只读验证 U-Boot 的 MMC 枚举和 TF2 文件读取仍然重要，但属于启动产品化 P1，
不是当前 Android framework 或图形 HAL 分析的硬性前置条件。

当前窗口已将安装与进入流程整理到 `docs/RGSP_ANDROID_INSTALL_AND_ENTRY_20260829.md`，
并新增 `tools/probe_rgsp_uboot_mmc.ps1` 作为不保存 env 的只读 U-Boot 探针。

这个结果决定后续启动产品化选择：

- TF1 启动 Android、TF2 放 system/vendor/data；或
- Android boot 和用户空间全部位于 TF2；或
- 先使用 recovery/测试分区启动 Android 探针。

H616/H618 源码和镜像的使用边界：

- 两套资料都值得保留，但不需要先完整编译两套；优先解包镜像、建立文件/版本清单，
  再对源码做定向搜索和单模块分析。
- H616 Android 10 通常更接近当前 H700 Linux 4.9/Android 10 目标；H618 Android 12
  主要用于比较较新的 HWC/Gralloc、init、Audio/Power HAL 实现，不能直接与当前内核
  或 GPU 二进制混用。
- 最有价值的交付物是“成套匹配矩阵”，不是某个单独 `libGLES_mali.so` 的复制。
