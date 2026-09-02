# H700 本地 Android 资料实测分析

日期：2026-09-01  
资料根目录：`D:\\Works\\H700Android\\H700_Android_Example`  
分析工作区：`D:\\Works\\H700Android\\work\\h700-source-analysis`

## 已完成

- H616 Android 10 `android.tar.gz`、`longan.tar.gz` 的 MD5 校验通过。
- H618 Android 12 18 个分卷逐个校验通过，并合并为
  `work\\h700-source-analysis\\h618\\H618-Android12-Src.tar.gz`（34,092,137,014 字节）。
- H616/H618 官方镜像已解压为 `.img`，大小分别约 1.05 GiB 和 1.16 GiB。
- H616 Longan 已解压，包含 H616 和 H700 两套 `device/config/chips`、Linux 4.9、
  U-Boot、boot0、BL31、DTB/打包配置。
- H616 Android 10 已选择性解压 `device/softwinner/cupid-perf1`、`cupid-common`、
  `hardware/aw` 和 `vendor/aw` 相关目录。

## 对当前 H700 卡点最有价值的文件

### 1. 图形栈

H616 Android 10 不是只有一个 Mali 库，而是有完整的成套实现：

```text
hardware/aw/gpu/mali-bifrost/mali-g31/arm64/lib64/libGLES_mali.so
hardware/aw/gpu/mali-bifrost/gralloc/src/
hardware/aw/hwc2/
hardware/aw/display/include/hardware/sunxi_display2.h
device/softwinner/cupid-perf1/hal.mk
```

`hal.mk` 同时打包 allocator/mapper 2.0、composer 2.2、`hwcomposer.cupid`、
`gralloc.cupid` 和 `libion`。`hardware/aw/gpu/product_config.mk` 显示
`TARGET_GPU_TYPE=mali-g31` 时选择 `mali-bifrost`，并把 `libGLES_mali.so` 放入
`vendor/lib[64]/egl`。这比 Gemini 所说的“只要复制 libGLES_mali.so”更准确：
必须连同 gralloc、HWC、ION 和 `mali_kbase` ABI 一起验证。

H616 参考库 SHA-256：

```text
arm/lib/libGLES_mali.so       21F8AD390FD514DEF2F6B9C98F80FF0DF049B847D0097ECC6F8D854AD3AD18CA
arm64/lib64/libGLES_mali.so   03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8
```

这些哈希只用于建立 donor 记录，不能证明它们可直接运行在 RGSP H700 上。

进一步对照发现，H616 Longan 的 Bifrost 内核 Kbuild 使用
`MALI_RELEASE_NAME = r20p0-01rel0`，而 RGSP 运行基线记录的 H700 GPU 驱动为
`v1.r20p0-01rel0`。这不是最终运行时证明，但说明现有资料很可能包含与 RGSP
同一 DDK 代际的 `mali_kbase` 内核实现，GPU 缺失问题已经具备实际修复路径。

### 2. 内核/设备树

Longan H700 `p1` 配置确认：

```text
LICHEE_CHIP=sun50iw9p1
Linux 4.9
CONFIG_SUNXI_GPU_TYPE="mali-g31"
CONFIG_DRM=n
CONFIG_FB=y
CONFIG_ASHMEM=y
CONFIG_ION=y
CONFIG_ION_SUNXI=y
CONFIG_ION_OF=y
Binder: binder,hwbinder,vndbinder
```

这与当前 RGSP 已观测到的 `/dev/fb0`、`/dev/disp`、`/dev/ion`、`/dev/mali0`、
`mali_kbase` 路线相符，是当前最可靠的移植参考。

但 Longan 的 `h700/configs/p1/board.dts` 仍是开发板示例：compatible 写作
`allwinner,h616`，LCD 默认关闭且为 1280x800，HDMI 开启，PMIC 为 AXP806。
RGSP 是 720x480、AXP2202、掌机按键和约 1 GiB RAM，因此只能复用 SoC/内核/HAL
接口，不能直接复用整份 DTS、PMIC、LCD 或分区表。

### 3. Android 设备配置

`device/softwinner/cupid-perf1` 提供了可直接借鉴的：

- `fstab.sun50iw9p1` 的 first-stage mount、dynamic partitions、zram/f2fs 规则；
- `init.device.rc` 对 disp、CPU、zram 和模块加载的处理；
- `BoardConfig.mk`、`hal.mk`、`cupid_perf1.mk` 的 HAL/分区组合；
- `configs/go/go_base.mk`、LMKD whitelist 等低内存裁剪入口。

其中 fstab 默认面向 eMMC/dynamic-partition 电视盒子，不适合直接套到 RGSP 的 TF
启动布局；需要按当前 `/dev/mmcblk0p4`、`/dev/mmcblk1` 和实际 GPT 重写。

## H618 Android 12 的定位

H618 资料保留为结构对照和后续 API 研究。当前不建议把 Android 12 的 Linux 5.4、
DRM/dma-heap、Gralloc/HWC 或预编译 GPU 库直接移入 RGSP 的 Android 11 + Linux 4.9
环境。H618 源码总包已合并并保留，待需要比较具体接口时再按路径选择性提取。

## 投影仪 H700 donor 的运行证据（2026-09-01）

投影仪主板为 `H21S-700-V3.0`，目前只有板端 TX 和 GND 可读，RX 写入口焊盘已损坏。
尽管不能从串口输入命令，冷启动日志已经证明该板实际完成了 Android 启动：

- `init second stage started`；
- `system`、`vendor`、`product` logical partitions 创建成功；
- `mali_kbase` 加载，GPU 报告 `arch 7.0.9 r0p0`；
- SurfaceFlinger 启动 `bootanim`；
- `bootanim` 正常退出；
- 处理到 `sys.boot_completed=1`。

因此，投影仪的“Android Logo”现象不能作为 Android 未启动的证据，更可能是投影显示链、
MS7200、LCD/DSI 或厂商前端问题。该板目前应视为**静态 H700 运行 donor**，不应阻塞 RGSP
主线。完整日志见：

`out/logs/uart/projector-h21s700/h21s700_coldboot_20260901_105638_115200.log`

RX 修复、ADB 或外部 eMMC 读取仍有价值，因为它们可以补齐 `boot/super/vendor/DTB` 等
二进制材料；但在这些通道可用前，不能从投影仪执行只读导出命令。

## 压缩包处理结论

本轮没有删除任何原始包：

- H616 v1.1 backup 与 v1.2 的 MD5 不同（分别为
  `6B2850C46D6FE6C7093E6173C014C4F5`、`C3DD3E76A8B8B745655BC44BDE9702B0`），
  不能当作重复文件删除；
- H616 Android/Longan 源码包仍是可重复提取的原始来源；
- H618 分卷虽已合并，但在完成目标目录提取和总包校验前继续保留。

可在下一轮完成 H618 目标目录提取、镜像二次提取并生成清单后，再删除确认冗余的
分卷或镜像压缩包。

## 9. 综合资料能力评估（2026-09-01）

结合 H616/H618 完整源码和镜像、RGSP 实机日志，以及投影仪 H700 冷启动日志，当前资料
已经足以支撑 H700 Android 移植的主线开发：

| 能力范围 | 结论 | 说明 |
|---|---|---|
| Android 10 构建、init、ADB、挂载 | 足够 | H616 Android 10 源码、镜像和 H700 Longan 配置完整 |
| H700 Linux 4.9、boot 链、DTB 研究 | 足够 | Longan 含 H700 kernel/U-Boot/boot0/BL31/DTB/打包配置 |
| Mali/Gralloc/HWC 第一版候选 | 足够开始 | H616 提供成套 Bifrost、ION、Gralloc/HWC；仍需 RGSP ABI 验证 |
| H618 Android 12 API/架构对照 | 足够 | 适合结构研究，不适合直接混入当前 4.9 图形栈 |
| RGSP 最终硬件适配 | 不足 | 仍需 RGSP 自己的 LCD、PMIC、内存、按键、音频、分区和 DTB |
| 完整量产 donor 二进制复刻 | 不足 | 投影仪 `vendor/super/boot` 尚未导出，闭源库仍需版本比对 |

这意味着当前项目已从“寻找资料”进入“组装并验证候选实现”阶段。资料足够制作第一版
可启动、可调试、可恢复图形候选包，但不能在没有 RGSP 实机验证的情况下承诺一次成功。

## 10. 是否足以支撑开发

结论：**足以支撑 H700 Android 移植主线，并足以针对当前 GPU/SurfaceFlinger 卡点制作
第一版完整图形候选包；不足以在没有 RGSP 实机验证和投影仪 vendor 二进制导出的情况下
保证最终量产系统一次成功。**

现有资料已经覆盖：

1. H700/H616 的 Linux 4.9 Mali-Bifrost/mali_kbase 内核源码；
2. AArch64/ARM32 `libGLES_mali.so` 闭源用户库；
3. ION 版 Gralloc allocator/mapper 源码；
4. 基于 `/dev/fb0`、`/dev/disp` 的 Allwinner HWC2 源码；
5. Android 10 设备、init、ueventd、SELinux、HAL 和打包规则。

剩余工作不是继续泛化地“寻找 GPU 库”，而是把已有 donor 按 RGSP 实际 ABI 重新组装并验证：

- 对比 RGSP `mali_kbase` 与 `r20p0-01rel0` 的 ioctl/API 版本；
- 用 RGSP 的 `sunxi_display2.h`、ION header 和 `/dev/disp` 行为检查 HWC/Gralloc；
- 将 `cupid` 平台名、720x480 LCD、AXP2202 和当前 TF 分区替换进设备配置；
- 先构建最小 `libGLES_mali + gralloc + hwcomposer` 测试包，再恢复 SurfaceFlinger；
- 通过 ADB、屏幕输出或日后 UART 观察 EGL 初始化、buffer 分配和 HWC 提交结果。

最现实的路线是先保留现有 Android 11 framework，移植 H616 的 Android 10 图形
实现和库；不要为了 GPU 卡点整体切换到 H618 Android 12。

## 11. 下一窗口直接执行清单

1. 从 H616 donor 生成 `libGLES_mali`、Gralloc、HWC、ION、EGL 的完整文件/依赖/哈希清单。
2. 将 H616 `mali_kbase` 配置与 RGSP 当前内核模块逐项比对，重点检查 release、ioctl 和设备节点。
3. 在 RGSP 上完成 `/dev/mali0`、`/dev/ion`、`/dev/disp`、`/dev/fb0` 的只读或最小写入探针。
4. 先输出 720x480 软件 framebuffer 测试图，再验证 EGL/GLES，最后恢复 SurfaceFlinger。
5. 保持 H616 Android 10 为主 donor，H618 Android 12 只做 API/架构对照。
6. 投影仪 RX/ADB/eMMC 读取仅作为补充 donor 任务；不得把它设为 RGSP 图形主线前置条件。
