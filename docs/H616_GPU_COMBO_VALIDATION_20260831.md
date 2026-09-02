# H616 Android 10 图形组合验证记录

日期：2026-08-31  
目标：为 RGSP/H700 Linux 4.9.170 评估 H616 Android 10 的成套 `Mali-G31 + Gralloc + HWC2 + ION` donor。

## 当前结论

- H616 donor 的 Mali 内核用户态代际与 RGSP 一致：两侧均为 `mali_kbase r20p0-01rel0`。
- H616 有真实的 Mali-Bifrost gralloc 源码和 Allwinner `/dev/disp` HWC2 源码；当前资料中没有对应的 HWC2 预编译 `.so`。
- `libGLES_mali.so` 只能作为 donor 记录，不能单独复制到 H700。必须先通过 EGL、ION、fbdev 和 `/dev/disp` ioctl 阶梯验证。
- H700 运行时节点：`/dev/mali0`、`/dev/ion`、`/dev/disp`、`/dev/fb0` 均存在；未发现 `/dev/dri`，因此不能套用 DRM/KMS 路线。

## Mali donor 文件

| ABI | 文件 | 大小 | SHA-256 |
|---|---|---:|---|
| ARM32 | `work/h700-source-analysis/h616/android/hardware/aw/gpu/mali-bifrost/mali-g31/arm/lib/libGLES_mali.so` | 13,279,144 | `05DC81F866B7AB947D20F283F25DCD96CA2F56FFD48E637B68778C1A994A6925` |
| ARM32（arm64/lib 路径下的 32 位副本） | `.../mali-g31/arm64/lib/libGLES_mali.so` | 13,259,996 | `21F8AD390FD514DEF2F6B9C98F80FF0DF049B847D0097ECC6F8D854AD3AD18CA` |
| ARM64 | `.../mali-g31/arm64/lib64/libGLES_mali.so` | 18,145,112 | `03333D495E3566C7D85CA2E000DA569A16CE8F022EA25C0EA61950C891D5C7F8` |

ELF 检查结果：三者 SONAME 均为 `libGLES_mali.so`；ARM32 两个文件均为 ELF32，`lib64` 文件为 ELF64。共同的 NEEDED 为：
`libcutils.so`、`android.hardware.graphics.common@1.0.so`、`libnativewindow.so`、`liblog.so`、`libm.so`、`libc.so`、`libdl.so`、`libz.so`、`libc++.so`。

## Gralloc 组合

源码根目录：

`work/h700-source-analysis/h616/android/hardware/aw/gpu/mali-bifrost/gralloc/src`

`Android.mk` 显示：

- Android P 以前使用 legacy ION API，Android P 及以后使用 `libion` 新 API；当前 H700 Android 11 需要确认实际 `libion` ABI。
- 模块安装到 `vendor/lib/hw` 和 `vendor/lib64/hw`，模块名随 gralloc 版本可能是 `gralloc.<platform>.so` 或 allocator/mapper HIDL 实现。
- 依赖 `libhardware`、`liblog`、`libcutils`、`libion`、`libsync`，新平台还依赖 `libnativewindow`、HIDL allocator/mapper 和 `android.hardware.graphics.common@1.x`。
- 默认 `GRALLOC_DISABLE_FRAMEBUFFER_HAL=1`，但源码仍包含 fbdev 路径；若 HWC2 未接通，软件 framebuffer 兜底需单独启用并固定 720x480/32bpp/stride。
- `ion/ion_4.12.h` 使用 `/dev/ion`、`ION_IOC_NEW_ALLOC`、`ION_IOC_HEAP_QUERY` 等 Linux 4.12 风格接口，必须和 H700 4.9 的实际 ioctl 编号及 heap 名称核对，不能只按头文件编译通过判断兼容。

## HWC2 组合

源码根目录：`work/h700-source-analysis/h616/android/hardware/aw/hwc2`

`Android.mk` 目标模块为 `hwcomposer.$(TARGET_BOARD_PLATFORM)`，核心依赖包括 `libEGL`、`libGLESv1_CM`、`libion`、`libsync_aw`、`libdisplayconfig` 和 HIDL display-config 服务。`de2family/DisplayOpr.cpp` 明确：

- 打开 `/dev/disp` 并调用 `DISP_GET_OUTPUT`、`DISP_DEVICE_GET_CONFIG`、`DISP_DEVICE_SWITCH`、`DISP_HWC_COMMIT`、`DISP_LAYER_SET_CONFIG2`、`DISP_VSYNC_EVENT_EN` 等 ioctl；
- 备用 fbdev 路径打开 `/dev/graphics/fb0`；
- 图层 buffer 通过 ION metadata/fd 传递，要求 Gralloc 私有 handle 与 HWC 结构布局一致。

因此 HWC2 能否运行的关键不是 Java framework，而是 H700 `/dev/disp` ioctl ABI、ION fd/metadata 布局、720x480 panel 参数以及 `libsync_aw`/`libdisplayconfig` 配套库。

## H700 实机只读探针（2026-08-31）

- Kernel：Linux 4.9.170，AArch64。
- `/proc/modules`：`mali_kbase 512000`，版本 `r20p0-01rel0 (UK version 11.17)`；另有 `8821cs`、`rtl_btlpm`。
- 设备节点：`/dev/mali0`（0666）、`/dev/ion`（0600 root）、`/dev/disp`（0600 root）、`/dev/fb0`（0660 root:video）。
- 未发现 `/dev/dri`；当前不能使用 H618 Android 12 的 DRM/dma-buf 二进制路线。
- fbdev 只读参数：模式 `U:720x480p-59`，virtual size `720x960`，32 bpp，stride 2880 bytes；这表明当前 Linux 使用双页高度的 720x480 线性 framebuffer。
- ION debugfs heap：`cma`、`secure`、`sys_user`、`sys_user_shrink`。CMA 区间为 `0x77c00000-0x7bc00000`，总计 64 MiB；`sys_user` 中可见 `ion_disp2` 的 7,372,800-byte 分配。
- `/proc/iomem` 中 GPU MMIO 为 `0x01800000-0x0180ffff`。

H616 Android userspace `sunxi_display2.h` 与同套 Linux 4.9 kernel header 并非逐字相同，SHA-256 分别为 `FEA8F32F5E5CA479B8EFCF4DAC813728D2C7B56D044B86660B7E531E0F1E9766` 和 `7D125520F813389EBE69E6018F94B786A404AE288BC419E6CAA980C55F96733D`。核心 ioctl 编号在 kernel header 中包括 `DISP_HWC_COMMIT=0x0e`、`DISP_GET_OUTPUT=0x10`、`DISP_DEVICE_GET_CONFIG=0x15`、`DISP_LAYER_SET_CONFIG2=0x49`；后续必须继续做结构大小和字段偏移检查，不能只比较 ioctl 编号。

## 下一步阶梯

1. 在 H700 Linux 上编译/运行最小 ARM64 Mali ioctl 探针，仅执行 open 和无副作用 capability query。
2. 做 `libGLES_mali.so` 的 linker namespace/NEEDED 闭包检查，不写入系统分区。
3. 编译 H616 Gralloc 的最小 allocator/mapper，先针对 `/dev/ion` heap query 和 fd 生命周期做单元验证。
4. 以固定 720x480、32bpp 做 fbdev 只读参数读取；写测试图前需单独确认可逆性并记录回退。
5. 再编译 HWC2，先执行 `/dev/disp` 输出枚举和模式查询，最后才恢复 SurfaceFlinger。
