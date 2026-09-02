# H21S-700-V3.0 H700 Android donor extraction

日期：2026-09-01  
目标：从投影仪量产 Android 系统中提取可用于 RGSP 等 H700 Linux 掌机开发的实现材料。本文只规划只读导出，不执行刷写。

## 1. 已确认的 donor 基线

- 主板：`H21S-700-V3.0`
- SoC：Allwinner `sun50iw9` / `sun50iw9p1`（H700）
- 内存：2 GiB，LPDDR3
- eMCP/eMMC：`R821MB`，约 14.6 GiB；存在 boot0、boot1、RPMB
- U-Boot：2018.05，`jenkins-h700_v12-733`，2022-12-20 构建
- Linux：4.9.170，AArch64，GCC 5.3.1
- Android：legacy boot + Android first/second stage init；`system`、`vendor`、`product` 为 `super` 中的 logical partitions
- 串口：`115200 8N1`，TX 输出稳定可读；USB-TTL 使用 1.8 V 档

## 2. eMMC 分区映射

内核命令行给出的分区名：

```text
mmcblk0p1  bootloader
mmcblk0p2  env
mmcblk0p3  boot
mmcblk0p4  super
mmcblk0p5  misc
mmcblk0p6  recovery
mmcblk0p7  cache
mmcblk0p8  vbmeta
mmcblk0p9  vbmeta_system
mmcblk0p10 vbmeta_vendor
mmcblk0p11 metadata
mmcblk0p12 private
mmcblk0p13 frp
mmcblk0p14 empty
mmcblk0p15 media_data
mmcblk0p16 Reserve0
mmcblk0p17 UDISK
```

## 3. 已观测到的 Android/H700 实现

- `init` 成功建立 `system`、`vendor`、`product` logical partitions（`dm-0`、`dm-1`、`dm-2`）。
- 出现 `console:/ $`，并处理到 `sys.boot_completed=1`；说明 Android framework 已经运行，不是只停在 bootloader。
- Mali：`GPU identified as 0x3 arch 7.0.9 r0p0`，内核模块名为 `mali_kbase`。
- 显示：全志 `disp`、LCD/DSI 时钟配置，投影仪使用 `MS7200` 视频/HDMI 相关芯片。
- 音频：内置 codec、HDMI、DAudio；外部 `AC107` codec 配置存在但注册失败。
- 无线：Realtek Bluetooth USB 驱动；`vendor.wifi_hal_legacy` 服务。
- 外设：sunxi IR、sunxi keyboard/GPADC、UVC video、投影马达控制服务。
- 启动参数：`androidboot.hardware=sun50iw9p1`、`buildvariant=eng`、`selinux=permissive`、`firmware_class.path=/vendor/etc/firmware`。

## 4. 不应直接移植的内容

- 投影仪专用 LCD/DSI 参数、MS7200/HDMI/CEC、马达 GPIO、灯控和传感器设备树节点。
- 投影仪专用音频 codec、AC107、GPIO/regulator 配置。
- 投影仪专用 `bootloader`、BL31、U-Boot、GPT 和 eMMC 环境；RGSP 必须保留自己的启动链。
- 整个 `super` 镜像直接刷入 RGSP；应提取文件、接口、属性和 HAL，按 RGSP 分区/设备树重建。
- `selinux=permissive`、`buildvariant=eng` 等调试配置不能作为最终产品配置。

## 5. 当前提取阻塞点

当前只连接了：

```text
投影仪 TX -> USB-TTL RX
投影仪 GND -> USB-TTL GND
```

这能读取日志，但不能向 `console:/ $` 发送命令。主板 RX 焊盘曾被拔掉，因此需要以下任一通道：

1. 沿 RX 走线找到同一网络的过孔/串联电阻，补一根细飞线；
2. 用投影仪 USB OTG/数据口连接电脑，检查是否枚举 ADB；
3. 使用外部 eMMC/ISP 读取器做离线只读镜像（风险和工作量更高）。

## 6. 恢复 RX 后的第一批只读命令

```sh
getprop > /sdcard/h21s700-getprop.txt
cat /proc/cmdline > /sdcard/h21s700-cmdline.txt
cat /proc/partitions > /sdcard/h21s700-partitions.txt
cat /proc/version > /sdcard/h21s700-version.txt
cat /sys/block/mmcblk0/device/cid > /sdcard/h21s700-cid.txt
ls -l /dev/block/by-name > /sdcard/h21s700-by-name.txt
mount > /sdcard/h21s700-mount.txt
find /vendor/etc/init /vendor/etc/vintf /vendor/lib /vendor/lib64 /vendor/bin /vendor/bin/hw /vendor/etc/firmware -type f -o -type l | sort > /sdcard/h21s700-vendor-file-list.txt
```

然后只读导出分区（目标存储应为外接 U 盘/网络/ADB，不要写回 eMMC）：

```sh
sha256sum /dev/block/by-name/boot /dev/block/by-name/recovery /dev/block/by-name/super \
  /dev/block/by-name/vbmeta /dev/block/by-name/vbmeta_system /dev/block/by-name/vbmeta_vendor
```

完整 `super`、boot0/boot1、GPT、vendor 文件树和 DTB 导出前，先确认接收端空间与传输方式；禁止使用 `dd ... of=/dev/mmcblk0*`。

## 7. 面向 RGSP 的提取优先级

1. `boot` 中的 kernel、DTB/DTBO、模块和 cmdline 证据。
2. `super` 中的 `/vendor`：HIDL HAL、init rc、VINTF、sepolicy、固件、Mali/显示/音频/无线库。
3. `/system` 中与 Android 版本、APEX、framework 配置相关的差异。
4. U-Boot/boot0/GPT 仅用于理解 H700 启动链，不直接复制到 RGSP。
5. 按 RGSP 自己的 LCD、按键、音频、电源和存储布局重建 device/vendor 配置。

## 8. 证据日志

完整冷启动原始日志：

`out/logs/uart/projector-h21s700/h21s700_coldboot_20260901_105638_115200.log`

该日志已确认 Android framework、logical partitions、Mali、显示、无线和 `sys.boot_completed=1`。
