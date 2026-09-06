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

## 9. 2026-09-06 串口恢复后的实测采集

RX 焊点修复后，`COM4` 在 1.8 V、115200 8N1 下可双向通信。投影仪无需停留在 Logo，可正常进入 Android shell；本次冷启动日志：

`out/logs/uart/projector-h21s700/rgsp_uart_20260906_173603_115200.log`

只读诊断 transcript：

`out/logs/uart/projector-h21s700/rgsp_serial_exec_20260906_174256_115200.log`

关键实测值：

- `uid=2000(shell)`，`ro.debuggable=1`、`ro.secure=0`，但 `su` 不存在；`/system/build.prop`、`/vendor/build.prop`、`/product/build.prop` 为 `0600 root:root`，串口 shell 不能直接读取。等价属性已由 `getprop` 完整记录。
- Android 10 / API 29，`ro.hardware=sun50iw9p1`，`ro.build.display.id=hercules_tv-eng 10 ... 733`，`sys.boot_completed=1`。
- `system/vendor/product` 由 `dm-0/dm-1/dm-2` 挂载；`super` 为 `mmcblk0p4`，约 2.2 GiB；整颗 eMMC 约 14.6 GiB。
- 可用工具：`/system/bin/base64`、`sha256sum`、`dd`、`gzip`；未提供 `lsblk`。
- `persist.sys.usb.config=mtp,adb`，但当前主机未检测到 `adb` 客户端，暂按 UART 只读路径处理。

## 10. 已导出的关键文件

文件均通过 UART base64 分块传输，并在设备端/主机端核对 SHA-256：

```text
out/donor/projector-h21s700/vendor/etc/fstab.sun50iw9p1
out/donor/projector-h21s700/vendor/etc/vintf/manifest.xml
out/donor/projector-h21s700/vendor/etc/vintf/compatibility_matrix.xml
out/donor/projector-h21s700/vendor/etc/init/init.display.rc
out/donor/projector-h21s700/vendor/etc/init/hwinfo.rc
out/donor/projector-h21s700/vendor/etc/init/init.pqd.rc
out/donor/projector-h21s700/vendor/etc/init/dom2reg.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.graphics.composer@2.2-service.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.camera.provider@2.4-service.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.audio@2.0-service.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.wifi@1.0-service-lazy.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.usb@1.0-service.rc
out/donor/projector-h21s700/vendor/etc/init/android.hardware.media.omx@1.0-service.rc
out/donor/projector-h21s700/vendor/etc/firmware/rtl8822bs_fw
out/donor/projector-h21s700/vendor/etc/firmware/rtl8822bs_config
out/donor/projector-h21s700/vendor/etc/firmware/bt.cfg
```

本轮已验证的 SHA-256 包括：`fstab.sun50iw9p1=d93f1eb1fcd84ebc0897242ae75bd9529278f5b0b426abb545061c4061bbdda2`、`manifest.xml=2a763431d9c3ed1ed6f20ba4c1ae13b2538b6a8e2394c9c656b50dfb659fb863`、`compatibility_matrix.xml=0d10a38352427cbbb5295b64f8c56b9be3ebcf8add73773dee2865979e9c047d`、`rtl8822bs_fw=fc2d018a00af896bc26945755990c758bde0b91b3f121de4d3136e87884def12`。

## 11. 下一步导出策略

1. 优先通过 USB ADB、网络或 U 盘寻找高速只读接收通道；115200 UART 不适合搬运约 2.2 GiB 的 `super`。
2. 若只能 UART，先导出小分区：`boot`、`recovery`、`vbmeta`、`vbmeta_system`、`vbmeta_vendor`、`env`、boot0/boot1，并记录设备端 `sha256sum`。
3. `super` 仅在确认接收端空间、传输时间和断点策略后再导出；禁止任何 `dd ... of=/dev/mmcblk0*` 写回命令。
4. `build.prop` 的 root-only 权限不影响移植分析：使用已采集的 `getprop`，并从可读的 VINTF、fstab、init rc、固件和分区镜像补齐实现细节。

## 12. 2026-09-06 HAL 与运行时接口补充

vendor 文件清单：

`out/logs/uart/projector-h21s700/rgsp_serial_exec_20260906_184651_115200.log`

该清单确认投影仪实际存在并使用以下 H616/Cupid 代际组件：

- `hwcomposer.cupid.so`、`gralloc.cupid.so`、`libdisplayconfig.so`、`libhwc_config.so`；
- `android.hardware.graphics.allocator@2.0`、`mapper@2.1`；
- `android.hardware.audio@5.0`、`audio.primary.cupid.so`；
- `libvdecoder.so`、`libvencoder.so` 以及完整 `media_codecs*.xml`；
- HIDL 服务二进制：audio、bluetooth、camera、configstore、DRM、gatekeeper、graphics、health、keymaster、light、media.omx、memtrack、power、sensors、USB、Wi-Fi。

运行时 HIDL/服务/ALSA 快照：

`out/logs/uart/projector-h21s700/rgsp_serial_exec_20260906_185325_115200.log`

重要证据：

- `lshal` 显示 `audio@5.0`、`graphics composer@2.2`、`allocator@2.0`、`mapper@2.1`、`health@2.0`、`power@1.0`、`wifi@1.3`、`bluetooth@1.0` 均已真实注册并有服务 PID；
- `service list` 中存在 `wifi`、`wifip2p`、`audio`、`media.audio_flinger`、`SurfaceFlinger`、`display_output` 等 framework 服务；
- ALSA card 0 为 `audiocodec`，另有 `sndspdif`、`sndahub`、`sndhdmi`、`snddaudio0`；这可用于 RGSP Audio HAL 的 card/device 路由对照；
- 投影仪 shell 读取 `/dev/input/event*` 被权限拒绝，不能据此推断没有输入设备；
- 投影仪没有 `/sys/class/power_supply` 电池节点，不能作为 RGSP AXP2202 health/power donor。

## 13. UART 导出的终点与剩余价值

通过 115200 UART 已取得的高价值内容包括：Android 完整启动日志、getprop、分区映射、挂载、VINTF、fstab、init rc、图形/音频/媒体配置、HWC/Gralloc/Audio/解码库、Realtek 8822BS 固件、HIDL 注册表和 ALSA 拓扑。

以下内容仍有研究价值，但不适合继续用当前 UART 方式搬运：

1. root-only 的三个 `build.prop`（可由 getprop 等价覆盖）；
2. `boot`、`recovery`、`vbmeta*`、boot0/boot1 和 `super` 原始镜像；
3. 完整 `/proc/device-tree` 二进制树；当前尝试因 UART 中混入 audit 日志而未纳入有效产物；
4. 更大的 vendor/system ELF 库和投影仪专用应用数据。

若没有 ADB、网络、U 盘或 eMMC 只读读取器，继续采集上述项目的收益低于风险和传输时间。投影仪可以在此处断开，切换到 RGSP 主板继续开发；已导出的 donor 文件和日志足以支撑当前 Android 10 的音频、无线服务、HIDL/VINTF、媒体和启动链对照工作。

## 12. 2026-09-06 RX 修复后的完整实测结论

RX 修复后已通过 UART 双向通信确认投影仪完整运行 Android 10，而不是停留在
Android Logo 或只进入 shell：`sys.boot_completed=1`、`dev.bootcomplete=1`、
`bootanim=stopped`、`surfaceflinger=running`，前台 Activity 为
`com.mylove.ailaunch/.activity.MainActivity2`。

本轮证据：

```text
out/logs/uart/projector-h21s700/rgsp_uart_20260906_173603_115200.log
out/logs/uart/projector-h21s700/rgsp_serial_exec_20260906_181103_115200.log
```

该结果确认投影仪 donor 最有价值的用途是对照 Android 服务启动顺序、VINTF、
init rc、GPU/HWC、音频和无线契约。投影仪无线芯片为 `rtl8822bs`，RGSP 为
`rtl8821cs`，不能直接复用其驱动或固件；投影仪也没有电池，因此 health/power
实现不能替代 RGSP 的 AXP2202 适配。

投影仪专有的 MS7200、LCD/HDMI/CEC、pqd、灯控、马达、AC107 和 Pixel/hercules_tv
产品身份均禁止进入 RGSP。其 `androidboot.selinux=permissive` 和 `buildvariant=eng`
只用于诊断取证，不能作为 RGSP 最终产品配置。
