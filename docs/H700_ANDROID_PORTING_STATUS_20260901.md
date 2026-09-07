# H700 Android 移植当前状态与窗口交接

> **已被取代（2026-09-02）**：当前主线为 H616 Android 10。本文的 Android 11
> 状态只用于历史对照，最新状态见 `H700_ANDROID10_MASTER_PLAN_20260902.md`。

日期：2026-09-01  
状态：RGSP headless Android 已推进至 fix46；H616/H618 donor 资料完成第一轮综合评估。

## 1. 一句话结论

现有 H616/H618 完整源码和镜像、H700 Longan 芯片级配置、RGSP 实机日志，以及投影仪
H700 冷启动日志，**足以支撑 H700 Android 移植主线开发，并足以制作第一版图形候选包**。
它们还不能保证最终量产系统一次成功，因为 RGSP 的 LCD/PMIC/内存/分区/输入适配和
图形 ABI 仍需实机验证，投影仪专有 `vendor/super/boot` 尚未导出。

## 2. 资料角色分工

| 资料 | 当前定位 | 可以做什么 | 不应做什么 |
|---|---|---|---|
| H616 Android 10 源码/镜像 | 主 donor | Android 10、Linux 4.9、H700 配置、Mali/ION/Gralloc/HWC、init/HAL 研究 | 不直接复制开发板 DTS/fstab 或整套镜像 |
| H618 Android 12 源码/镜像 | API/架构对照 | Android 12 framework、VNDK、HAL 结构比较 | 不把 Linux 5.4、DRM/dma-heap、GPU 二进制混入 H700 4.9 |
| RGSP 原厂 Linux/Android 日志 | 目标硬件事实 | 720x480、AXP2202、1 GiB、设备节点、启动/回退行为验证 | 不把 R36S/RK3326 组件当作 H700 vendor |
| H21S-700 投影仪日志 | 静态 H700 运行 donor | `sun50iw9p1`、4.9.170、Mali arch 7.0.9、super logical partitions、服务启动证据 | 不直接刷投影仪 bootloader/GPT/DTB/super |

## 3. 已确认事实

### 3.1 投影仪已进入 Android

日志：

`out/logs/uart/projector-h21s700/h21s700_coldboot_20260901_105638_115200.log`

已看到：

- `init second stage started`；
- `system/vendor/product` logical partitions 创建；
- `mali_kbase`，GPU `arch 7.0.9 r0p0`；
- `bootanim` 启动并退出；
- `sys.boot_completed=1`。

投影仪画面卡在 Android Logo 不能证明 Android 未启动，更可能是显示前端、MS7200、
LCD/DSI 或厂商界面问题。RX 焊盘损坏只影响串口输入和在线导出，不阻塞 RGSP 主线。

### 3.2 RGSP 当前状态

- `zygote64`、`system_server` 已能启动；
- fix43 已实机验证；
- fix46 最新记录可进入 `console:/ #`，约 296 秒内未立即回退；
- 当前仍是 headless framework，无可见 Android 桌面；
- 设备日志中的 DRAM training、AXP2202、Wi-Fi GPIO、MMC、VE 报错要与图形问题分开处理；
- SSH/ADB 网络通道不应作为唯一观测手段，优先使用 UART 和持久日志。

## 4. 当前主线技术决策

```text
现有 Android 11 headless framework
        +
H616 Android 10/H700 Linux 4.9 图形 donor
        +
RGSP 自有 kernel/DTB、720x480 LCD、AXP2202、1 GiB 和 TF 分区
        +
先软件 framebuffer，再 EGL/GLES，再 Gralloc/HWC，最后恢复完整 SurfaceFlinger
```

H616 Mali-Bifrost 的 `mali_kbase` release 为 `r20p0-01rel0`，与 RGSP 记录的
`v1.r20p0-01rel0` 处于同一 DDK 代际，这是强匹配线索，不是运行时兼容证明。必须把
`libGLES_mali`、Gralloc、HWC、ION、EGL 和内核 ABI 作为一套验证。

## 5. 下一窗口直接执行

1. 生成 H616 图形栈文件、依赖、SONAME、NEEDED 和 SHA-256 清单。
2. 对比 H616 `mali_kbase` 与 RGSP 当前模块的 release、ioctl、设备节点和内核配置。
3. 在 RGSP 上探测 `/dev/mali0`、`/dev/ion`、`/dev/disp`、`/dev/fb0`。
4. 先输出 720x480 软件 framebuffer 测试图。
5. 用最小程序或 `ROCwallpaper` 验证 `eglGetDisplay`、`eglInitialize`、GLES context、`eglSwapBuffers`。
6. 验证 ION buffer 分配/导入、`/dev/disp` layer/vsync/page-flip，再恢复 SurfaceFlinger。
7. 同步建立 RGSP device overlay：LCD、旋转、AXP2202、按键、音频、Wi-Fi/BT、TF 分区和 fstab。
8. 真实设备写入继续使用 TF2、一次性标记、读回校验和自动回退。

## 6. 投影仪 donor 后续触发条件

只有在以下情况发生时，才把 RX 修复、ADB 或外部 eMMC 读取提升为高优先级：

- H616 图形栈经过明确 ABI 比对仍无法初始化；
- 需要投影仪独有的 Mali/Gralloc/HWC/firmware/vendor 服务；
- 需要对比投影仪 `boot`、DTB、`super` 或 VINTF 的具体二进制差异。

恢复 RX 后先做只读采集，不执行任何写入 eMMC 的命令。USB-TTL 继续使用 1.8 V，VCC
悬空；不要在通电状态焊接。

## 7. 相关文档

- `docs/H700_LOCAL_SOURCE_ANALYSIS_20260831.md`
- `docs/H700_ANDROID_GPU_DEVELOPMENT_HANDOFF_20260831.md`
- `docs/H21S700_ANDROID_DONOR_EXTRACTION_20260901.md`
- `docs/H700_ANDROID10_MASTER_PLAN_20260902.md`
- `docs/H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`
