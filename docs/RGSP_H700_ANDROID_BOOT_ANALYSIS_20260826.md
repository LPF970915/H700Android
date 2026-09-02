# RGSP / H700 Android 启动能力实测报告

日期：2026-08-26  
设备：RGSP  
SSH：`root@192.168.31.164`  
板卡标识：`/mnt/vendor/oem/board.ini = RGSP`

## 1. 结论摘要

这台 RGSP 不是纯 Linux-only 启动设计。它的 Allwinner 启动链已经保留了 Android 兼容结构：

- 内部 `boot` 分区（`/dev/mmcblk0p4`）是标准 Android boot image 格式。
- U-Boot 环境中存在 `boot_normal`、`boot_recovery`、`boot_fastboot`。
- boot image 名称为 `sun50i_arm64`，加载地址为 `0x40080000` / `0x42000000`。
- 当前内核启用了 `CONFIG_ANDROID`、`CONFIG_ANDROID_BINDER_IPC`、`CONFIG_ASHMEM`、`CONFIG_ION`。
- 设备存在 `/dev/binder` 和 `/dev/ashmem`。

但当前系统并不是 Android：

- `boot` 中的 kernel 是厂商 Linux 4.9.170。
- ramdisk 是 BusyBox/Linux init，包含 `etc/init.d/rcS`，没有 Android `init`、`system`、`vendor` 用户空间。
- 当前 rootfs 为 Ubuntu 22.04 用户态，根分区是 `/dev/mmcblk0p5`。

因此最准确的判断是：**RGSP 已经具备 Android boot.img 级别的启动基础，移植 Android 的难点集中在 Android 用户空间、HAL、LCD/GPU/音频/电源适配，而不是重新发明启动格式。**

## 2. 设备基线

| 项目 | 实测值 |
|---|---|
| SoC/平台 | Allwinner `sun50iw9` / H700 系列 |
| CPU | AArch64，4 核 Cortex-A53 |
| 内核 | Linux 4.9.170，2026-06-24 构建 |
| 用户态 | Ubuntu 22.04 LTS 定制系统 |
| 内存 | 996,480 kB，约 1 GB，无 swap |
| 板卡 | RGSP |
| 当前根分区 | `/dev/mmcblk0p5`，ext4，label `linuxrootfs` |
| 应用分区 | `/dev/mmcblk0p6`，ext4，label `appfs` |
| 数据分区 | `/dev/mmcblk0p7`，ext4，PARTLABEL `UDISK` |
| 内置 ROM 分区 | `/dev/mmcblk0p8`，FAT，PARTLABEL `primary` |
| 外置卡 | `/dev/mmcblk1p1`，FAT，label `ROMS` |

## 3. 内部 GPT 分区

```text
mmcblk0p1  64 MiB   special
mmcblk0p2  32 MiB   boot-resource
mmcblk0p3  16 MiB   env
mmcblk0p4  64 MiB   boot
mmcblk0p5   7 GiB   rootfs
mmcblk0p6   4 GiB   appfs
mmcblk0p7  1.3 GiB  UDISK / data
mmcblk0p8  1.9 GiB  primary / ROMS
mmcblk1p1  外置卡   ROMS
```

当前 GPT 不是 R36S/RK3326 常见的整张 SD 卡 Linux 布局，而是 Allwinner 厂商固件使用的多分区结构。Android 双系统方案必须围绕这套 GPT 和 U-Boot 环境设计，不能直接套 R36S 镜像。

## 4. boot 分区实测

`file -s /dev/mmcblk0p4` 结果：

```text
Android bootimg
kernel (0x40080000)
ramdisk (0x42000000)
page size: 2048
```

Android boot header 解析：

```text
magic         ANDROID!
name          sun50i_arm64
kernel_size   17,686,536 bytes
ramdisk_size   2,606,312 bytes
kernel_addr   0x40080000
ramdisk_addr  0x42000000
page_size     2048
ramdisk       gzip 压缩 cpio newc
```

boot 分区 SHA-256：

```text
d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5  /dev/mmcblk0p4
```

ramdisk 中可见：

```text
etc/init.d/rcS
etc/fstab
etc/inittab
usr/bin/* BusyBox 工具
```

`rcS` 主要执行 devtmpfs、devpts、sysfs 挂载，并挂载 `/dev/nanda` 到 `/boot`，属于 Linux initramfs，不是 Android ramdisk。

## 5. U-Boot 环境证据

从 `env` 分区字符串中读到：

```text
nand_root=/dev/nand0p4
mmc_root=/dev/mmcblk0p5
init=/init

setargs_nand=setenv bootargs ... root=${nand_root} ...
setargs_mmc=setenv bootargs ... root=${mmc_root} rootwait ...

boot_normal=sunxi_flash read 45000000 boot;bootm 45000000
boot_recovery=sunxi_flash read 45000000 recovery;bootm 45000000
boot_fastboot=fastboot

recovery_key_value_min=0x10
recovery_key_value_max=0x13
fastboot_key_value_min=0x2
fastboot_key_value_max=0x8
bootdelay=0
```

这说明：

1. U-Boot 能从名为 `boot` 的分区读取 Android boot image。
2. U-Boot 预留了 recovery 镜像启动入口。
3. U-Boot 预留了 fastboot 命令入口。
4. 启动选择很可能由电源键/组合键数值触发，而不是标准交互式 U-Boot 菜单。
5. 当前 boot image 虽然使用 Android 格式，但 rootfs 参数仍指向 Linux `mmcblk0p5`。

## 6. Android 内核兼容能力

当前 `/proc/config.gz` 中确认：

```text
CONFIG_ANDROID=y
CONFIG_ANDROID_BINDER_IPC=y
CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"
CONFIG_ASHMEM=y
CONFIG_ION=y
CONFIG_ION_SUNXI=y
CONFIG_ION_OF=y
CONFIG_SUNXI_GPU_TYPE="mali-g31"
CONFIG_SUNXI_IOMMU=y
CONFIG_FB=y
```

设备节点：

```text
/dev/binder
/dev/ashmem
/dev/ion
/dev/mali0
/dev/fb0
/dev/disp
```

这对 Android 移植非常有利，因为 Binder、Ashmem、ION 和 Mali 内核支持已经存在。仍然需要 Android 用户空间正确配置 Binder 服务、Gralloc/HWC、EGL/GLES 和 SurfaceFlinger。

## 7. 对 dArkOS 路线的对应关系

R36S 的 dArkOS 路线可以借鉴“启动选择和独立系统镜像”的思想，但实现对象不同：

```text
R36S:
  RK3326 U-Boot
  dArkOS Linux
  LineageOS Android

RGSP:
  sun50iw9/H700 U-Boot
  原厂 Linux + Pegasus
  H700 Android kernel + Android system/vendor
```

不能直接复制：

- RK3326 kernel
- RK3326 DTB
- R36S LCD 参数
- R36S boot.ini
- R36S 分区表
- R36S GPU/音频/电源 HAL

可以复用的架构思想：

- 保留原厂 Linux 作为默认系统。
- Android 放在备用 TF 卡或独立测试分区。
- 使用 U-Boot 的 boot/recovery/fastboot 能力。
- 通过启动键或启动配置选择系统。
- 两个系统共享 ROM 卡，但各自使用独立的系统和数据分区。

## 8. 推荐的 H700 Android 实施路线

### 阶段 A：只读备份

必须先备份：

```text
/dev/mmcblk0p1  special
/dev/mmcblk0p2  boot-resource
/dev/mmcblk0p3  env
/dev/mmcblk0p4  boot
GPT 分区表
/mnt/vendor
/mnt/data
```

尤其不能直接覆盖 `mmcblk0p1`、`mmcblk0p3`、`mmcblk0p4`。

### 阶段 B：Android boot 探针

先制作新的 Android boot image，但只替换 kernel/ramdisk 的测试副本：

1. 使用 H700 vendor kernel 或兼容 Android kernel。
2. 使用 RGSP 专用 DTB。
3. 保留 `0x40080000` 和 `0x42000000` 加载地址。
4. 将 Android ramdisk 先做成最小 init。
5. 只在备用 TF 卡或可恢复 boot 分区上测试。
6. 目标是先显示 Android Logo，再进入 adb/串口 shell。

### 阶段 C：硬件 HAL

按以下顺序适配：

1. LCD 和背光
2. SurfaceFlinger + Gralloc/HWC
3. 物理按键和音量键
4. ALSA Audio HAL
5. AXP2202 电池和充电
6. Power/Hall 合盖唤醒
7. 双 TF 卡
8. Wi-Fi、蓝牙、USB、HDMI
9. GPU 视频解码

### 阶段 D：Android Pegasus

系统稳定后再安装 Android Pegasus 或自定义前端。当前 Linux Pegasus 的状态、RA 启动脚本和 SDL 生命周期不能直接复制到 Android，需要改为 Android Activity、Intent、Storage Access 和 Android RetroArch 调用链。

## 9. 主要风险

| 风险 | 说明 |
|---|---|
| boot image 误判 | 当前 boot.img 是 Linux kernel + Linux ramdisk，不是 Android 系统 |
| 分区覆盖 | 写错 `env`/`boot`/GPT 可能导致无法启动 |
| LCD 不匹配 | Android SurfaceFlinger 需要 RGSP 专用 panel 参数 |
| GPU 闭源库 | `libmali`、Gralloc、EGL、HWC 必须版本匹配 |
| 内存 | 约 1 GB RAM，不适合完整 GMS Android |
| 合盖唤醒 | Linux 已有厂商电源链，Android 需要重新实现 |
| fastboot | U-Boot 有 `fastboot` 字符串，但当前系统没有用户态 fastboot 工具，实际 USB 协议仍需验证 |
| 启动按键 | recovery/fastboot 的键值范围已知，具体物理按键映射仍需实测 |

## 10. 当前阶段判断

| 项目 | 状态 |
|---|---|
| H700 CPU 运行 Android | 硬件可行 |
| Android boot image 格式 | 已实测存在 |
| U-Boot normal/recovery/fastboot | 已发现字符串证据 |
| Android Binder/Ashmem/ION | 当前内核已启用 |
| 完整 Android 用户空间 | 当前不存在 |
| RGSP 专用 Android 镜像 | 尚未找到 |
| 直接刷 R36S Android | 不可行 |
| 备用 TF 卡 Android 探针 | 可立即规划 |
| 覆盖内部系统 | 高风险，暂不建议 |

最终结论：**RGSP 的 Android 路线是“基于现有 Allwinner Android boot 框架补齐 Android 用户空间和 HAL”，不是从零修改 U-Boot，也不是把 R36S 镜像直接刷入。最安全且最接近 dArkOS 的实现是：原厂 Linux + Pegasus 保留为默认系统，Android 使用备用 TF 卡或独立启动项进行验证。**

## 11. 原始证据与本地副本

- 设备硬件基线：`docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md`
- Pegasus 交接基线：`docs/PEGASUS_GBA_H700_TRANSFER_BASELINE.md`
- 本次 boot 分区压缩副本：`.tmp/rgsp-p4-20260826.img.gz`
- 本次 ramdisk 副本：`.tmp/rgsp-ramdisk.gz`
- 设备连接：`root@192.168.31.164`
