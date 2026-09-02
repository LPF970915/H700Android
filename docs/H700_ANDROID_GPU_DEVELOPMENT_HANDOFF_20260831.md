# H700 Android GPU 开发交接手册

日期：2026-09-01  
适用主线：RGSP / RG34XXSP，Allwinner H700，`sun50iw9`，Linux 4.9.170  
资料根目录：`D:\Works\H700Android\H700_Android_Example`  
分析工作区：`D:\Works\H700Android\work\h700-source-analysis`

## 1. 交接结论

当前资料**足以支撑 H700 Android 移植主线，并足以制作第一版完整 GPU/图形候选包**；但还不足以在没有 RGSP 实机运行时验证和投影仪 vendor 二进制导出的情况下宣称最终量产系统一次成功。

当前主线不应改成“全程使用 H618 Android 12”。建议保持：

```text
现有 Android 11 headless framework
        +
H616 Android 10 的 Linux 4.9 图形实现、ION、Gralloc/HWC 和 Mali donor
        +
RGSP H700 已验证的 kernel/DTB、720x480 LCD、AXP2202 和 TF 分区配置
```

H618 Android 12 源码和镜像继续保留，定位为 Android 12/HAL 结构对照资料；其 Linux 5.4、DRM/dma-buf 或预编译 GPU 库不能直接放入当前 H700 Linux 4.9 环境。

## 2. 已验证的当前基线

### 2.1 H700 运行时

- SoC：H700，厂商平台标识 `sun50iw9`，部分资料使用 `allwinner,h616` compatible。
- Kernel：Linux 4.9.170，AArch64，厂商 BSP 路线。
- 图形设备：`/dev/fb0`、`/dev/disp`、`/dev/ion`、`/dev/mali0`；没有 `/dev/dri`，不能假设 DRM/KMS。
- GPU：Mali-G31，`mali_kbase`；当前 RGSP 运行记录为 `v1.r20p0-01rel0`。
- 屏幕：RG34XXSP/RGSP 基线为 720x480，约 59 Hz，实际 panel/旋转必须按机型确认。
- 内存：约 1 GiB；必须使用 Android 10/11 low-RAM、无 GMS 和受控后台策略。
- PMIC：AXP2202；不能套用开发板的 AXP806 配置。
- 当前 Android：`zygote64` 和 `system_server` 已能启动。fix43 已完成实机验证；fix46 最新记录显示 RGSP 可稳定进入 Android console 并持续约 296 秒。当前仍是 headless framework，图形栈尚未恢复；日志还显示 DRAM training、AXP2202、Wi-Fi GPIO、MMC 和 VE 等设备级问题，需要与图形问题分开处理。

### 2.2 已完成的资料处理

- H616 Android 10 `android.tar.gz`、`longan.tar.gz`：MD5 校验通过。
- H618 Android 12：18 个分卷逐个校验通过，已合并为 `h618/H618-Android12-Src.tar.gz`，大小 `34,092,137,014` 字节。
- H616/H618 镜像已解压；H616 Longan 已确认包含 H616、H700 配置、Linux 4.9、U-Boot、boot0、BL31、DTB 和打包配置。
- 原始压缩包没有删除。H616 v1.1/v1.2 镜像 MD5 不同，不能视为重复文件。

### 2.3 投影仪 H700 donor 证据

投影仪 `H21S-700-V3.0` 的冷启动日志已经确认完整 Android 运行路径：

- `init second stage started`；
- `system/vendor/product` logical partitions 创建；
- `mali_kbase` 与 Mali arch `7.0.9 r0p0`；
- `bootanim` 启动并正常退出；
- `sys.boot_completed=1`。

因此投影仪卡 Android Logo 不是“系统没有进入 Android”的证据。当前 RX 焊盘损坏只阻止
串口写入和在线导出，不阻止 RGSP 继续使用 H616/H700 源码和已有 RGSP 运行路径开发。
投影仪应作为静态 donor；只有在 H616 图形栈 ABI 验证失败，或需要其专有 vendor 库时，
才继续修复 RX、尝试 ADB 或进行外部 eMMC 读取。

## 3. GPU 资料和版本匹配

H616 Android 10 中发现的是一套成组图形实现，而不是单独一个 `libGLES_mali.so`：

```text
hardware/aw/gpu/mali-bifrost/mali-g31/
hardware/aw/gpu/mali-bifrost/gralloc/src/
hardware/aw/hwc2/
hardware/aw/display/include/hardware/sunxi_display2.h
device/softwinner/cupid-perf1/hal.mk
```

这套资料包含：

- ARM32/ARM64 `libGLES_mali.so`；
- ION allocator/mapper 源码；
- 基于 `/dev/disp` 的 Allwinner HWC2；
- fbdev 支持、Composer 2.2、allocator/mapper 2.0、`libion`；
- Mali-Bifrost 内核源码和 Sunxi 平台集成。

参考库哈希，仅用于 donor 记录，不代表可直接运行：

```text
ARM32  21F8AD390FD514DEF2F6B9C98F80FF0DF049B847D0097ECC6F8D854AD3AD18CA
ARM64  03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8
```

重要匹配线索：

```text
H616 Longan mali_kbase：r20p0-01rel0
RGSP H700 GPU 运行记录：v1.r20p0-01rel0
```

这说明 H616 donor 与 RGSP 处于同一 DDK 代际，GPU 缺失问题已有现实的修复路径；仍必须完成 ioctl、EGL、ION 和 HWC 运行时验证。

## 4. 推荐集成顺序

不要先替换整个系统，也不要先恢复完整 SurfaceFlinger。按以下阶梯逐项验证：

1. **库依赖检查**：确认 `libGLES_mali.so`、`libEGL.so`、`libGLESv2.so` 的架构、SONAME、NEEDED 和 Android linker 命名空间。
2. **Mali 设备检查**：在 RGSP 上确认 `/dev/mali0` 存在，读取 `mali_kbase` 版本，执行最小 ioctl/API 探针。
3. **EGL 初始化**：用最小 ARM64 测试程序或将 `ROCwallpaper` 改成诊断 APK，测试 `eglGetDisplay`、`eglInitialize`、GLES context 和 `eglSwapBuffers`。
4. **ION 分配/导入**：验证 H616 Gralloc 使用的 ION heap、fd 生命周期、cache 同步和 RGSP kernel 行为。
5. **fbdev 输出**：先写入 `/dev/fb0` 测试图，固定 720x480、32 bpp、stride 和旋转。
6. **`/dev/disp` HWC 提交**：再验证 buffer import、layer 合成、vsync 和 page flip。
7. **最小 SurfaceFlinger**：只有前述步骤通过后，恢复 SurfaceFlinger，逐步接入 Gralloc/HWC/EGL。
8. **framework/Launcher**：最后恢复 Lights、输入焦点、Launcher 和应用生命周期。

任何一步失败都要记录：命令、退出码、`logcat`、`dmesg`、库哈希、设备节点、内核模块版本和回退动作。

## 5. 当前不要做的事

- 不把 H618 Android 12 的 Mali、Gralloc、HWC、DRM 或 dma-heap 二进制直接复制到 H700 4.9。
- 不把 H616 的 `libGLES_mali.so` 单独塞进 vendor；必须连同匹配的 Gralloc/HWC/ION 和 kernel ABI 一起验证。
- 不直接复制 H616/H618 开发板整份 DTS、fstab 或分区表。开发板示例通常是 HDMI、不同 LCD、不同 PMIC 和不同内存布局。
- 不把 Linux/glibc sysroot 中的 `libmali.so`、`libEGL.so`、`libGLESv2.so` 直接作为 Android vendor 库。
- 不为了验证 GPU 立即改写内部 eMMC、U-Boot 环境或唯一恢复卡。
- 没有软件 framebuffer 画面前，不把“GPU 库已找到”写成“SurfaceFlinger 已解决”。

## 6. 软件 framebuffer 兜底

如果 H616 Android 图形成套实现最终无法通过 ABI 或运行时验证，主线仍可先走软件 framebuffer/最小 composer：

- 目标是先得到稳定的 Android 画面和按键焦点导航；
- GPU、视频解码和 HDMI 作为可选能力，不阻塞 Android 基础产品路径；
- 这条路径也能继续验证输入、音频、电源、Launcher 和模拟器集成。

## 7. 投影仪主板 UART 决策

**结论：投影仪主板 UART 目前为 P3/可选项，不应阻塞 RGSP Android/GPU 主线。**

原因：

- RGSP 已经有可用的 3.3 V TTL UART、完整冷启动日志和 `logcat`/`dmesg` 观测路径；
- GPU 兼容性关键是 H700 4.9.170 的 `mali_kbase`、ION、`/dev/disp` 和 Android 用户态 ABI，投影仪 UART 本身不能证明 RGSP ABI 兼容；
- 投影仪当前更适合作为静态 donor：提取 boot、DTB、vendor、system、GPU 库和属性，做版本/SONAME/符号对比即可。

只有在以下情况之一成立时，才值得继续攻关投影仪 UART：

- 需要把投影仪固件作为更接近 H700 的运行时 donor；
- 其 eMMC 内容无法离线读取，必须靠启动日志确认 kernel/DTB/Android 版本；
- H616 donor 经过明确 ABI 比对仍失败，而投影仪镜像可能含有独特的 H700 Android 图形库或配置；
- 需要确认 boot0/U-Boot 的启动参数、显示初始化或电源时序。

若以后尝试，优先采用万用表/示波器/逻辑分析仪做非破坏性识别，使用临时探针或 pogo pin；连接 3.3 V USB-TTL 时先接 GND 和板端 TX 到适配器 RX，禁止连接 VCC，先确认逻辑电平再监听。

## 8. 下一窗口直接执行清单

- [x] 实机验证 fix43；确定 headless 停点为 `DisplayManagerService` 同步查询 SurfaceFlinger。
- [x] fix46 实机记录：RGSP 可进入 Android console 并持续约 296 秒，仍无图形桌面。
- [ ] 从 H616 donor 建立 `libGLES_mali + Gralloc + HWC + libion` 文件清单和依赖报告。
- [ ] 对 RGSP 的 `/dev/mali0`、`/dev/ion`、`/dev/disp`、`/dev/fb0` 做只读/最小写入探针。
- [ ] 先生成软件 framebuffer 测试图，再接入 HWC。
- [ ] 将 `ROCwallpaper` 改为最小 EGL/GLES 诊断 APK，确认 Android linker 和 EGL 初始化行为。
- [ ] 按 RGSP 1 GiB、AXP2202、720x480 和自有 TF 分区重建 device overlay；不复制开发板 DTS/fstab。
- [ ] 所有真实设备写入继续使用 TF2、一次性标记、读回校验和自动回退；投影仪 UART 不作为前置条件。

## 9. 相关文档

- `docs/H700_LOCAL_SOURCE_ANALYSIS_20260831.md`
- `docs/H700_H616_H618_SOURCE_ANALYSIS_PLAN_20260831.md`
- `docs/H700_ANDROID_CONTINUOUS_DEVELOPMENT_PLAN.md`
- `docs/RGSP_H700_GPU_SOFTWARE_STATUS_20260830.md`
- `docs/RGSP_ANDROID_FIX43_LIGHTS_HEADLESS.md`
- `docs/RGSP_ANDROID_PROBE_STATUS_20260826.md`
- `docs/H700_PROJECTOR_X10_FIRST_INFO_CAPTURE_20260831.md`
