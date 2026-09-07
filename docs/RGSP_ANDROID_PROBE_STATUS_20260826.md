# RGSP Android 探针状态（历史记录与当前覆盖）

> **当前状态覆盖（2026-08-31）**：本文前半部分保留 fix1–fix21 的逐轮历史证据，
> 不再代表当前停点。当前主线已通过 fix40–fix42 进入 headless framework：
> `zygote64` 和 `system_server` 可以启动；fix42 约 183 秒后因
> `LightsService -> SurfaceControl -> SurfaceFlinger` 同步等待被 Watchdog 杀死。
> fix43 已生成跳过该调用的候选 `services.jar`，尚未完成实机验证。当前最高优先级
> 是 H700 图形 HAL/软件 framebuffer，不是重新处理 Android init/fstab。

历史记录起始日期：2026-08-26；当前覆盖日期：2026-08-31  
设备：RGSP / Allwinner H700 (`sun50iw9`)  
现场地址：`192.168.31.164`（MAC `68:8F:C9:35:EF:C5`）

## 已完成

- Windows PowerShell OpenSSH 已通过 `SSH_ASKPASS` 连接设备。
- 现场只读 inventory 已保存到 `out/rgsp-inventory-clean.txt`。
- 从设备读取 `/dev/mmcblk0p4`，保存为 `input/boot-live.img`。
- 现场与本地副本 SHA-256 一致：

```text
d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5
```

- 已确认当前 boot image：
  - Android legacy boot header，页大小 2048
  - kernel 地址 `0x40080000`
  - ramdisk 地址 `0x42000000`
  - kernel 为 ARM64 Linux Image，大小 17,686,536 bytes
  - ramdisk 为 gzip cpio，大小 2,606,312 bytes
  - DTB 为 FDT v17，实际大小 137,564 bytes
  - vendor header 的原始 `dt_size` 字段为 `2`，不能按普通 Android 镜像直接截断

## 探针产物

`out/rgsp-boot-init-probe.img` 是第一枚启动链探针：

- 使用真实 RGSP kernel、DTB 和原厂 BusyBox ramdisk。
- 只替换 ramdisk 顶层 `/init`。
- `/init` 会在串口输出 `[rgsp-probe]` 标记，挂载 proc/sys/devtmpfs，然后进入早期 shell。
- 它**不是完整 Android**，不会启动 SurfaceFlinger、zygote 或 Android framework。
- 镜像大小 64 MiB，与原始 boot 分区一致。

```text
SHA-256  6d31e561b8f4e90af72f3544b0c6761d1577ffcf1e40c7bf522a6694796ad618
文件     out/rgsp-boot-init-probe.img
```

## 现场硬件事实

- 当前启动命令为 `run setargs_nand boot_normal`。
- `boot_normal` 通过 `sunxi_flash read 45000000 boot;bootm 45000000` 启动。
- 内核启用 Binder、Ashmem、ION 和 Android 兼容配置，但 `CONFIG_DRM=n`。
- 显示节点仍是 `/dev/fb0`、`/dev/disp`、`/dev/ion`、`/dev/mali0`。
- 当前系统没有 `adbd`、`surfaceflinger`、`servicemanager` 等 Android 用户空间组件。

## 尚未执行

- 没有写入 `mmcblk0p3/p4`、GPT 或 U-Boot 环境。
- 没有验证 U-Boot 是否可以直接从 TF 卡接管 Android boot 分区。
- 没有重启到探针镜像；需要备用 TF 卡、可观察串口或明确的恢复方式。

## TF2 实测

- 卡二当前为 `/dev/mmcblk1p1`，125,068,865,504 bytes（约 125 GB），exFAT，
  卷标 `android`，挂载点 `/mnt/sdcard`。
- 当前约 37 GB 已用、约 80 GB 可用；原有 `roms/`、`ROCgalgame_refactor_backups/`
  等目录保持不变。
- 已创建 `/mnt/sdcard/ANDROID_PROBE/` 并上传探针镜像；设备端 SHA-256 校验通过：

```text
6d31e561b8f4e90af72f3544b0c6761d1577ffcf1e40c7bf522a6694796ad618
```

- exFAT 单分区适合作为 staging/共享 ROM，不应假设 U-Boot 2018.05 能直接读取
  该文件或 exFAT。是否重分区为 FAT boot + ext4 system/vendor，必须等 UART
  确认 TF2 在 U-Boot 中的编号和文件系统支持后再决定。

## TF2 格式化结果

按用户授权，已清空并重新建立 GPT；原卡二上的 ROM 和备份数据不再保留。

| 分区 | 容量 | 文件系统 | 卷标 | PARTUUID |
|---|---:|---|---|---|
| `mmcblk1p1` | 256 MiB | FAT32 | `ANBOOT` | `0720745f-bbfb-4940-bef7-8595c6f34f4b` |
| `mmcblk1p2` | 8 GiB | ext4 | `ANDROID_SYSTEM` | `096d7fa1-62e8-c242-9876-cfdd5a92b8eb` |
| `mmcblk1p3` | 2 GiB | ext4 | `ANDROID_VENDOR` | `6aa8b46e-b96f-9545-bbfb-1b7d2bdc7da8` |
| `mmcblk1p4` | 16 GiB | ext4 | `ANDROID_DATA` | `734716ed-e7d9-e74f-9b3e-4f1cb8d448ed` |
| `mmcblk1p5` | 90.2 GiB | FAT32 | `ROMS` | `324a1514-de37-6344-8d09-ed5dd8b90da2` |

当前挂载：

```text
/dev/mmcblk1p1 -> /mnt/android-boot
/dev/mmcblk1p5 -> /mnt/sdcard
```

探针已复制到 `/mnt/android-boot/rgsp-boot-init-probe.img`，设备端校验通过。

## Android 11 userspace alpha 产物

已从 Andr36oid 2025-09-02 LineageOS 18.1 R36S 镜像中提取 Android 11
system-as-root 用户空间。上游压缩包 SHA-256 已与 GitHub Release 元数据一致：

```text
d7a29edd33d5dbb1597efde1be5978d185b764ad61bdd8f324eafc9bbcb5f2aa
```

已排除上游 RK3326 loader、U-Boot、trust、kernel 和 DTB，并对 system 镜像做了
以下 RGSP alpha 修改：

- product/device 身份改为 `rgsp`；
- board platform 改为 `sun50iw9`；
- 启用 `ro.config.low_ram=true`；
- 加入 `fstab.rgsp`、`init.rgsp.rc`、`ueventd.rgsp.rc`；
- 启用无认证 bring-up ADB；
- 隔离 RK3326 graphics/audio/power/lights/Wi-Fi service；
- 暂停 SurfaceFlinger 和 boot animation，以串口/ADB bring-up 为第一目标。

产物目录：`out/rgsp-android11-alpha/`

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `rgsp-android11-handoff-boot.img` | 64 MiB | `05e6e0afde1eec134043791fd90019c3bb6accc4aac3e2eb7398cac0b3229bfc` |
| `rgsp-android11-system-alpha.img.gz` | 857.53 MiB | `20d39509492c0b602606f652584959487823354a81cb49ca1a9ea847df842c42` |
| 解压后的 system image | 2,365,268,480 bytes | `793e4384f86c6c72a15ec6b60f4ac70701dc4218e189a6f5e7b929701e823f3f` |

handoff boot 使用实机 kernel 和 RG34XXSP DTB，只替换原厂 ramdisk 顶层 `/init`。
该 `/init` 等待 `/dev/mmcblk1p2`，只读挂载 Android system image，然后通过
BusyBox `switch_root` 执行 Android `/init`。

已验证：

- 压缩 system image 解码后的字节数和 SHA-256 与原始 ext4 镜像完全一致；
- handoff boot 解包后的 kernel、DTB 与实机备份完全一致；
- handoff ramdisk `/init` 与项目源文件完全一致；
- 修改后的 ext4 image 通过 `e2fsck -fn`；
- boot image 工具单元测试通过；
- 安装和准备 shell 脚本通过 `sh -n`。

该 alpha 是 Android init/ADB 启动验证镜像，不是可日用图形 Android。使用说明见
`out/rgsp-android11-alpha/README.md`。

## 下一步

1. 通过 UART 验证 U-Boot 中 TF2 的实际 MMC 编号和 FAT32 读取能力。
2. 将 system alpha 写入 TF2 `mmcblk1p2`，不要修改任何 `mmcblk0` 分区。
3. 临时 `fatload` handoff boot，观察 `[rgsp-android]` 和 Android init 日志。
4. Android init/ADB 成功后再引入 H700 Android Gralloc/HWC 和其他 HAL。

## 2026-08-26 后续安装状态

- 因当前只有普通 USB 数据线，Windows 未枚举 USB-UART，跳过 U-Boot 串口读取验证；没有修改 U-Boot 环境。
- 已通过 SSH 将 `rgsp-android11-system-alpha.img.gz` 写入 TF2 `/dev/mmcblk1p2`。
- 写入脚本确认 TF2 容量、boot/system PARTUUID，并明确拒绝写入 `/dev/mmcblk0`；写入后 `e2fsck` 和 `resize2fs` 均通过。
- 已将 `rgsp-android11-handoff-boot.img` 复制到 `/mnt/android-boot/`，SHA-256：
  `05e6e0afde1eec134043791fd90019c3bb6accc4aac3e2eb7398cac0b3229bfc`。
- Android system 分区标签为 `RGSP_ANDROID_ALP`，其 `build.prop` 标识 Android 11、设备 `rgsp`、模型 `RGSP H700 Android Alpha`。
- 当前仍未执行 `bootm`；实际启动需要后续确认 U-Boot 能读取 TF2，或建立不依赖 TF2 U-Boot 读取的安全启动路径。
- 已通过 SSH 发起一次卡二启动测试并完成重启。重启后 `192.168.31.164` 仍由设备 MAC `68:8F:C9:35:EF:C5` 响应 ICMP（TTL=64），但 SSH/ADB 端口未恢复，无法仅凭网络确认是否已进入 Android 用户空间；未再次写入任何分区。
- 随后 SSH 恢复并完成启动源确认：设备实际从 TF1 原厂 Linux 启动，根分区为 `/dev/mmcblk0p5`，内核命令行包含 `root=/dev/mmcblk0p5`；Android alpha 用户空间未启动。简单重启不会让当前 U-Boot 自动选择 TF2。
- 已备份并修改 U-Boot env（仅 `/dev/mmcblk0p3` 前 128 KiB），将 `bootcmd` 改为 `run rgsp_tf2_boot`；该脚本按 U-Boot `mmc 0`、`mmc 1` 顺序查找 TF2 handoff 文件，找不到时回退原厂 `run setargs_nand boot_normal`。
- 修改 env 后再次重启，设备在 180 秒内无 ICMP、SSH 或 USB ADB 枚举，暂无法判断停在 `fatload`、`bootm`、handoff init 还是 Android init；需用卡一恢复 Linux 后离线检查卡二记录。
- 已继续监测 300 秒，设备仍未恢复网络；无法通过 SSH 远程拔出 TF2。下一步必须断电取出 TF2、保留 TF1 后开机，利用 `rgsp_tf2_boot` 的回退分支恢复原厂 Linux，再进行离线分析。

## 2026-08-27 新卡一恢复后的分析

- 重新制作的卡一可正常启动原厂 Linux，当前根分区仍为 `/dev/mmcblk0p5`；设备硬件和原厂 boot 镜像没有损坏。
- 新卡一 env 前 128 KiB SHA-256 为 `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`，与修改前备份完全一致。
- 旧测试脚本在尝试 `mmc dev 1` 后直接执行原厂 `sunxi_flash` 回退，没有先恢复 `mmc dev 0`。这很可能导致原厂 boot 从错误的 MMC 上下文读取，是旧卡一无法启动 Linux 的主要原因；由于没有 UART，此项为有现场证据支持的推断。
- 卡二 `ANBOOT` 可正常读取；handoff boot SHA-256 仍为 `05e6e0afde1eec134043791fd90019c3bb6accc4aac3e2eb7398cac0b3229bfc`。
- 卡二 Android system/data ext4 只读检查通过。FAT32 仅有未正常卸载的 dirty bit，不是本次无网络的主要原因。
- `ANDROID_DATA` 只有 `lost+found`，最后挂载时间早于 U-Boot 测试，说明失败启动没有到达 Android `post-fs-data`。
- 已发现 Android alpha 的确定性配置错误：handoff 已把 `mmcblk1p2` 作为 system-as-root 执行 `switch_root`，但 `fstab.rgsp` 又要求把同一设备挂载到 `/system`。该重复挂载会破坏 `/system/bin` 路径，是 Android early-init 停止的首要软件原因。
- 下次测试前必须：回退前执行 `mmc dev 0`、删除 fstab 的 `/system` 重复挂载项，并让 handoff init 把阶段标记持久写入 TF2。

## 2026-08-27 旧卡一恢复

- 使用新制作的系统卡从 TF1 启动 Linux，并将旧系统卡插入 TF2 槽进行离线恢复。
- 当前运行卡为 `/dev/mmcblk0`，CID `1d41445553440000200000b3f801a22d`；旧卡为 `/dev/mmcblk1`，CID `1d414455534400002000009f9401a1e7`。
- 写入前确认旧卡 `/dev/mmcblk1p3` 前 128 KiB SHA-256 为修改后值 `5e6968322f63aa4d815d9c68109756231aaf10577329f45cefc35017e8f8b56d`，并包含 `bootcmd=run rgsp_tf2_boot`。
- 已仅将原始 env 的前 128 KiB 写回旧卡 `/dev/mmcblk1p3`；写入过程通过根分区、CID、源哈希和目标哈希四重保护。
- 恢复后 env 前 128 KiB SHA-256 为 `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`，`bootcmd` 已恢复为 `run setargs_nand boot_normal`。
- 旧卡完整 env 分区 SHA-256 为 `8dd964ef0d525071626040d7cdce6c16925aaa6108d35558a0a5f032592b78a2`，与修改前完整备份一致。
- 旧卡 boot 分区 SHA-256 为原厂值 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`。
- 旧卡 rootfs 通过 `e2fsck -fn`，Ubuntu 22.04 根文件系统可正常只读挂载。旧卡已具备恢复原厂 Linux 启动的条件。

## 2026-08-27 Android fix2

- 旧卡一恢复后已实机从 `/dev/mmcblk0p5` 启动；其 CID 为 `1d414455534400002000009f9401a1e7`。Android 卡二 CID 为 `fe3432534400000020000005bc01896b`。
- 内核日志显示硬件控制器对应关系为 `sdc0=TF1`、`sdc1=RTL8821CS SDIO`、`sdc2=TF2`。上次 U-Boot 脚本尝试 `mmc 1`，很可能访问的是 Wi-Fi SDIO 而非 TF2；fix2 改为 `mmc dev 2` 和 `fatload mmc 2:1`。
- U-Boot 回退路径现在始终先执行 `mmc dev 0`，再运行原厂 `setargs_nand` 和 `boot_normal`。
- 新增一次性标记 `RGSP_ANDROID_TRY.ONCE`。handoff init 启动后立即删除标记；后续重启若标记不存在，U-Boot 自动回退 TF1 Linux。
- 已删除 `fstab.rgsp` 中把 system-as-root 再次挂载到 `/system` 的错误项；data 改为 `/dev/mmcblk1p4`，zram 改为 `/dev/zram0`。
- handoff init 现在把阶段标记和 Android init stdout/stderr 写入卡二 ANBOOT 的 `RGSP_ANDROID_BOOT_LAST.log`，早期失败会在记录后强制重启。
- fix2 boot 镜像：`out/rgsp-android11-handoff-boot-fix2.img`，SHA-256 `e7cbfbefa4dc23d14ea32864bcaadb2794ba9be62be876b8705325c11c6c91e8`。
- fix2 env 完整镜像：`out/rgsp-env-tf2-boot-fix2-20260827.bin`；写入的 128 KiB env SHA-256 为 `addbc6717746bd940b420ae5ccb120731aec500534dc0fae2ff219dab87e8536`。
- 原始 16 MiB env 已额外保存到旧卡一 `/mnt/mmc/RGSP_RECOVERY/env-original-pre-fix2.bin`，SHA-256 `8dd964ef0d525071626040d7cdce6c16925aaa6108d35558a0a5f032592b78a2`。
- 卡二 FAT dirty bit 已修复，system ext4 再次通过 `e2fsck -fn`；最终预检通过，等待 fix2 重启测试。

## 2026-08-27 fix2 结果与 fix3 方案

- fix2 重启后设备无网络；强制重启时旧卡一仍不能进入 Linux。把旧卡移到 TF2 槽后确认其 env 仍为 fix2，而 boot 分区仍是原厂哈希。
- 这证明 `mmc dev 2` 在该厂商 U-Boot 中也不能作为可靠的可返回探测命令；启动流程在到达显式 `mmc dev 0` 回退前已经停止。因此后续禁止通过持久 env 探测 TF2。
- 已再次从旧卡自身 `/RGSP_RECOVERY/env-original-pre-fix2.bin` 恢复 `/dev/mmcblk1p3` 前 128 KiB。
- 恢复后旧卡完整 env SHA-256 为 `8dd964ef0d525071626040d7cdce6c16925aaa6108d35558a0a5f032592b78a2`，boot SHA-256 为 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`，`bootcmd=run setargs_nand boot_normal`。
- fix3 不再修改 U-Boot env，也不让 U-Boot 访问 TF2。测试前临时把 handoff boot 写入 TF1 boot 分区；handoff init 从 TF2 ANBOOT 校验原厂 boot 备份后，第一时间把原厂镜像恢复到 TF1 `/dev/mmcblk0p4`，再进入 Android。
- fix3 若缺少恢复镜像或哈希不符，会拒绝自动重启，避免循环；原厂 boot 成功恢复后，任何 Android 失败或人工重启都会回到 TF1 Linux。
- fix3 预检发现原厂 ramdisk 没有独立的 `sha256sum`、`awk`、`reboot`、`switch_root` 链接；已改为显式调用 `/bin/busybox`。实机运行 ramdisk 内 BusyBox v1.22.1，确认所需 applet 全部存在。
- 最终 fix3 boot：`out/rgsp-android11-handoff-boot-fix3.img`，SHA-256 `819753cad091ac920f2317480e067a1e0aaee815c0bdb3c3860b539e23ceafe9`。
- fix3 已通过 `sh -n`、boot image 单元测试、kernel/DTB 哈希、打包后 `/init` 字节一致性和实机 BusyBox applet 校验。
- 原厂 TF1 boot 已同时备份到 Android 卡 `rgsp-linux-boot-original.img` 和旧卡一 `RGSP_RECOVERY/boot-original-pre-fix3.img`，两者 SHA-256 均为 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`。
- 最终写入前 CID、原厂 env、原厂 boot、双份恢复镜像、一次性标记和修正后 fstab 全部通过防护检查。fix3 已临时写入 TF1 `/dev/mmcblk0p4`，读回 SHA-256 正确；env 未改变。

## 2026-08-27 fix3 结果与 fix4

- fix3 的 handoff init、TF2 分区识别、原厂 TF1 boot 自动恢复、一次性标记消费和 Android system 只读挂载均成功。
- fix3 的确定性失败点为 `mount --move`；原厂 ramdisk 的 BusyBox 1.22.1 不接受该长选项，持久日志记录为 `ERROR: failed to preserve boot-log mount`。
- fix4 改为尝试在 Android 新根下二次挂载 TF2 ANBOOT，而不是移动原挂载点。镜像为 `out/rgsp-android11-handoff-boot-fix4.img`，SHA-256 `4a4acb38d8028548eaea438aad13dbfe451d2ed38dbab10e2b59d64a0d240117`。
- fix4 启动前全部保护条件通过；启动后再次成功恢复并校验原厂 TF1 boot，消费一次性标记，并挂载 Android system。
- fix4 的持久日志确定失败于 `ERROR: failed to remount boot-log partition under Android root`，随后自动回退原厂 Linux。回退后 TF1 boot 和 env 哈希均保持原厂值。
- 实机离线检查确认 Android system 是只读挂载，且其 `/mnt/rgsp-boot` 目录不存在；未检查 `mkdir` 返回值导致后续挂载目标不存在。这是 fix4 失败的直接原因。
- fix4 日志已归档为 `out/RGSP_ANDROID_BOOT_fix4_20260827.log`，TF2 上另存为 `RGSP_ANDROID_BOOT_fix4_20260827_033058.log`。

## 2026-08-27 fix5

- 从 fix4 ramdisk 取出原厂 BusyBox 1.22.1 后实机验证：`mount -o bind` 可用；`mount --move` 不支持，`mount -o move` 虽能解析但在当前环境返回 `EINVAL`。
- fix5 不修改 Android system 分区。handoff init 先把 `/dev`、`/proc`、`/sys` bind 到 Android 新根，再把已挂载的 TF2 ANBOOT bind 到新根可写 devtmpfs 下的 `/dev/rgsp-boot`。
- 上述完整 bind 拓扑已在设备当前 Linux 环境和只读 Android system 上实测成功。
- 新增 `tools/extract_ramdisk.py`，用于在没有外部 `cpio` 命令时安全解包 gzip `newc` ramdisk。
- fix5 镜像为 `out/rgsp-android11-handoff-boot-fix5.img`，SHA-256 `cebe8b0b2f0353549c9e3991fe08f67dba9be4f025918c6244ab0c33eadfb467`。
- fix5 已通过 shell 语法检查、boot image 工具测试、打包后 `/init` 字节一致性检查；kernel 和 DTB 哈希与 fix4 完全一致。
- 写入 fix5 前后 env 前 128 KiB 均为原厂哈希；`/dev/mmcblk0p4` 写后读回为 fix5 哈希，一次性标记存在。
- fix5 启动后超过五分钟无 ICMP、SSH 或 TCP ADB，说明已越过 fix4 的快速失败点，但未能自动回退。等待物理电源复位后读取 TF2 持久日志；handoff 设计上在进入 Android 前已恢复原厂 TF1 boot，仍需回到 Linux 后进行最终哈希确认。

## 2026-08-27 fix5 最终结果与 fix6

- 设备耗尽电量前显示的绿色仰躺机器人，与 TF1 `boot-resource/fastbootlogo.bmp` 逐像素资源一致，因此该界面是厂商 Fastboot，而不是 Recovery 或常规充电动画。
- fix5 持久日志最终停在 `executing Android init; subsequent stdout/stderr follows`，证明 handoff 已成功执行 `switch_root` 并启动 Android `/init`；没有新增 Android stdout/stderr、data 文件或 pstore 记录。
- 充电并重启 Linux 后再次确认：TF1 boot 为原厂 SHA-256 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`，env 前 128 KiB 为原厂 SHA-256 `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`。
- fix6 为 TF2 Android system 增加与内核参数 `androidboot.hardware=sun50iw9p1` 匹配的 `fstab.sun50iw9p1`、`init.sun50iw9p1.rc` 和 `ueventd.sun50iw9p1.rc`，并加入五分钟阶段监视脚本。
- fix6 修改前后 `mmcblk1p2` 均通过 `e2fsck -fn`；四个新文件的 SHA-256 已记录在 `out/RGSP_ANDROID_FIX6_PREP.log`。
- fix6 使用与 fix5 相同、已验证的 handoff boot，SHA-256 `cebe8b0b2f0353549c9e3991fe08f67dba9be4f025918c6244ab0c33eadfb467`。写入前后 env 未改变，handoff 再次自动恢复原厂 TF1 boot 并消费一次性标记。
- fix6 的新 boot 日志仍停在 `executing Android init`；`RGSP_ANDROID_STAGE_LAST.log`、`RGSP_ANDROID_WATCH_LAST.log` 和 `RGSP_ANDROID_POWERCTL_LAST.log` 均未生成，五分钟 watchdog 未运行。
- AOSP first-stage init 会重新建立 `/dev` tmpfs。fix6 把 TF2 日志 bind 到 `/dev/rgsp-boot`，该挂载会被 Android first-stage init 遮蔽，导致 stage 写入失败、watcher 无法打开日志后退出。因此“无监视日志”本身不能证明 `init.sun50iw9p1.rc` 未被解析。
- TF2 data 仍只有 `lost+found`，没有 `/data/rgsp-alpha`、`/data/adb` 或 `/data/misc/adb`；ext4 超级块最后挂载时间仍为 `2026-08-27 00:34:18 +08:00`。这证明 fix6 没有完成设备 rc 中的 data 挂载和 `post-fs-data`。
- fix6 日志已归档为 `out/RGSP_ANDROID_BOOT_fix6_20260827.log`，SHA-256 `564f32c57bad9242fe4e4cde0c8a46208a3aaa16fe0c01d555d686846012ccc7`。
- 下一轮必须把持久日志挂载点移出 `/dev`，使用 Android root 中预创建且不会被 first-stage init 覆盖的专用目录；在得到 first-stage/second-stage 明确阶段记录前，不再扩大到图形或 HAL。

## 2026-08-27 fix7 结果与 fix8 方案

- fix7 在 Android system 根目录预创建 `/rgsp-persist`，handoff 将 TF2 ANBOOT bind 到该目录，避免 Android first-stage init 重建 `/dev` 时遮蔽日志挂载。
- 核心 `system/etc/init/hw/init.rc` 已显式导入 `/init.sun50iw9p1.rc`；system 修改前后均通过 `e2fsck -fn`。
- fix7 boot SHA-256 为 `d888f8f342c411213e03aa70c72ce46b870dfe3a07ad6b97c2e2d82f5834dec2`。启动仍进入厂商 Fastboot 图标；`RGSP_ANDROID_STAGE_LAST.log`、watcher、logcat 和 powerctl 日志均未生成。
- `/proc/cmdline` 明确包含 `selinux=0`，运行时不存在 `/sys/fs/selinux`，而内核配置启用了 `CONFIG_SECURITY_SELINUX=y` 和 `CONFIG_SECURITY_SELINUX_BOOTPARAM=y`。Android 11 first-stage init 强制挂载 selinuxfs，失败后触发 fatal；这是 fix7 停在 second-stage rc action 之前的确定性原因。
- fix8 改由 handoff 预先挂载并 bind `/dev`、`/proc`、`/sys`，准备 `/mnt`、`/debug_ramdisk` 和 `/rgsp-persist`，随后执行 `switch_root /android-root /init second_stage`，绕过与 `selinux=0` 不兼容的 Android first-stage。
- fix8 boot SHA-256 为 `5b8fb9c158c27252b6a850739130efd830b7d7a90bffe15474786e7209a5a171`；ramdisk SHA-256 为 `4785cc02bd2984d79c81f84df255e6d0a657e2471d81a3f42244362ec8e07bda`。
- fix8 已通过 handoff shell 语法、boot image 单元测试、打包后 `/init` 字节一致性与 `0755` 权限检查；kernel 和 DTB 哈希与 fix7 完全一致，镜像大小仍为 64 MiB。

## 2026-08-27 fix8 启动测试（待回读日志）

- 写入前确认 TF1/TF2 CID、原厂 env、原厂 TF1 boot、TF2 恢复镜像、Android system `e2fsck -fn`、核心 init import 和电量状态全部正常；未修改 env、GPT、boot0 或 U-Boot 本体。
- fix8 仅写入 `/dev/mmcblk0p4`，写后读回 SHA-256 与本地产物一致；一次性标记在写入校验成功后创建。
- 重启后 8 分钟内 SSH 端口没有恢复，ADB、Fastboot 和常用 TCP 调试端口均未开放；但设备仍以 MAC `68:8F:C9:35:EF:C5` 响应 `192.168.31.164` 的 ICMP，TTL 为 64。
- 当前不能仅凭网络判断 Android second-stage 到达了哪个 action。需手动长按电源复位回到 TF1 Linux，然后读取 TF2 上的 `RGSP_ANDROID_BOOT_LAST.log`、stage、watcher、logcat 和 powerctl 日志；handoff 在进入 Android 前应已恢复原厂 TF1 boot。

## 2026-08-27 fix8 与 fix9 回读结果

- fix8 回读日志停在 `executing Android init`，没有 stage、watcher、logcat 或 powerctl 文件；证明显式传入 `second_stage` 仍未到达 rc 的 `early-init` action。
- fix8 后 TF1 boot 和 env 再次核验为原厂 SHA-256，一次性标记已消费。
- fix9 尝试将 `/dev/kmsg` bind 到 TF2 持久文件，以捕获 Android init 在 rc 解析前的 fatal；boot SHA-256 为 `6c5fd026c88d07ccf6f0acc89413ea99ca27adae9c2d5fa42ce92109d7236064`。
- fix9 handoff 完成原厂 boot 恢复、标记消费、Android root 挂载、kmsg bind 和 `switch_root` 调用，但 `RGSP_ANDROID_KMSG_LAST.log` 为 0 字节，其他 second-stage 日志仍未生成。
- 实机 chroot 诊断显示：未绑定 `/proc` 时 Android `bootstrap/linker64 --list /system/bin/init` 会退出 139；补齐 `/proc`、`/dev`、`/sys` 后可正常解析 init 的全部动态依赖，因此 CPU、ELF 解释器和 init 依赖链本身兼容。
- 对独立 devtmpfs 的测试确认普通文件可直接 bind 到 kmsg 节点并写入；但替换 kmsg 不能覆盖动态 loader 在 init logger 建立前的全部故障路径，因此不再沿用该捕获方式。

## 2026-08-27 fix10 启动测试（待回读日志）

- fix10 保留真实 `/dev/kmsg`，在 handoff 中启动独立 BusyBox reader，持续把内核 ring buffer 复制到 TF2 `RGSP_ANDROID_KMSG_LAST.log`。
- 当前 Linux 实机已验证 reader 能从 `/dev/kmsg` 捕获主动写入的唯一标记；生成文件约 32 KiB，证明读取链可用。
- fix10 boot SHA-256 为 `a7fc11f6aa6eeace018095a534d8417e0079b2a1c50772c27a15698d5879af51`；ramdisk SHA-256 为 `fcb4fb34474b870fcee6fa7e276ff31aa2e02224ee813662c29816d8cc910579`。
- fix10 已通过 shell 语法、boot image 单元测试、打包后 `/init` 一致性和权限检查；kernel/DTB 与 fix9 完全一致。
- 写入前全部保护条件和 Android system `e2fsck -fn` 通过；仅写 `/dev/mmcblk0p4` 后读回 fix10 哈希一致，再创建一次性标记并重启。
- 启动约 50 秒后设备以原 MAC/IP 恢复 ICMP，但 3 分钟内 SSH 未恢复。需手动复位回 Linux 后读取 fix10 kmsg，确定 rc 前的实际失败点。

## 2026-08-28 fix10 回读结果

- 手动复位后设备从 TF1 `/dev/mmcblk0p5` 正常进入 Linux，SSH 恢复；TF1 boot SHA-256 为原厂值 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`，env 前 128 KiB 为原厂值 `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`，一次性标记已消费。
- fix10 `RGSP_ANDROID_BOOT_LAST.log` 记录完整 handoff：恢复 TF1 boot、挂载 Android root、启动 kernel-log reader，并执行 `switch_root /android-root /init second_stage`。
- `RGSP_ANDROID_KMSG_LAST.log` 大小 34,123 bytes，包含：`init second stage started!`、属性覆盖/加载、`SELinux: Loaded file_contexts`；之后没有 `Running restorecon...`、epoll、rc import 或 `early-init` 记录。
- 因此故障已确定收敛在 Android second-stage 的 SELinux label 初始化/restorecon 之前后，排除 first-stage selinuxfs、动态 linker、property service、APEX/linkerconfig 挂载和 handoff 拓扑问题。
- 现场确认 `/sys/fs/selinux` 不存在（内核命令行含 `selinux=0`），而 system `libselinux.so` 仍执行 file-context handle 初始化。下一步应制作 system-only 的最小兼容补丁，在 SELinux disabled 场景跳过该初始化/restorecon，再进行一次性可回退测试；不得修改 U-Boot、kernel、GPT 或 boot0。
- 本轮日志已下载到 `out/RGSP_ANDROID_BOOT_fix10_20260827_181414.log` 与 `out/RGSP_ANDROID_KMSG_fix10_20260827_181414.log`，SHA-256 分别为 `13655d2972e10ee5f691b3ce9f98cda2c941224b05fdf076f561618212c2ec2b` 和 `a912a306d3383f4f4e7319bb5c156e59109d0f4d24310bb067eca7e384aaab1e`。

## 2026-08-28 当前推进判断与 fix11 离线准备

- 这是 Android 11 探针时期的状态记录。Android 10 主线的当前计划和完成情况见
  `docs/H700_ANDROID10_MASTER_PLAN_20260902.md` 与
  `docs/H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`。
- 当前实机停点仍是 Android second-stage 在 `SELinux: Loaded file_contexts` 之后、`early-init` 之前；TF1 Linux 回退、原厂 boot/env 哈希保护和 TF2 持久日志均正常。
- 已完成 fix11 的 **本地 system-only 兼容补丁**，未写入真实设备：复制 `rgsp-android11-system-alpha.img`，对 `system/lib64/libselinux.so` 的三个入口做 AArch64 最小返回补丁，绕过 `selinux=0` 时不可用的 file-context handle、restorecon 和 sethandle 路径。
- fix11 产物：`out/rgsp-android11-system-alpha-fix11.img`，最终可重复生成 SHA-256 `e6ffc8563aa6e29e6b47cf3582b5bce7ab6dcf9fe6268a5cd886a1d5232fc04c`；补丁后 ELF SHA-256 `fac1800b68852e92c90e05a03ae27987c6d926ed3b1f1a96d4497d81e76f3e46`。
- 离线验证：三个补丁入口读回反汇编分别为 `mov x0,#0; ret`、`mov w0,#0; ret` 和 `ret`；system 镜像 `e2fsck -fn` 通过。尚未刷写 TF2，也未修改 TF1、U-Boot、GPT、boot0 或持久 env。
- 下一步：完成 fix11 产物清单后，在确认电量和回退条件的前提下进行一次性实机测试；目标日志为 `early-init`、`post-fs-data`、`adbd`，失败后回到 TF1 Linux 读取完整日志。

## 2026-08-28 fix11 实机测试（等待回读）

- fix11 system 已仅写入 TF2 `/dev/mmcblk1p2`；写入后扩容为 8 GiB，设备侧 `e2fsck -fn` 通过，`system/lib64/libselinux.so` 读回 SHA-256 为 `fac1800b68852e92c90e05a03ae27987c6d926ed3b1f1a96d4497d81e76f3e46`。
- fix11 handoff boot SHA-256 为 `edb33568397e1a5a9883071dbf31692e7704e30efbf8bfff7a00da7df1e470e3`；写入 TF1 `/dev/mmcblk0p4` 后读回一致。写入前原厂 boot、env 前 128 KiB、TF2 恢复 boot 和双卡 CID 均匹配保护值。
- handoff 增加了五分钟后台 reboot watchdog；设计意图是在 Android 不可用时自动回到已经恢复的 TF1 Linux。
- 2026-08-28 13:39:35 CST 通过 SSH 重启开始测试。设备先离线，约两分钟后恢复 ICMP；SSH 22 和 ADB TCP 5555 均未开放。
- 五分钟后 watchdog 未使设备回到 Linux，说明该后台进程未跨 `switch_root` 正常执行重启；此自动回退实现不可继续沿用。
- TF1 原厂 boot 在 Android handoff 前已恢复，但当前需要一次物理长按电源复位，随后读取 TF2 `RGSP_ANDROID_BOOT_LAST.log`、`RGSP_ANDROID_KMSG_LAST.log` 和阶段日志，确认 SELinux 补丁后的新停点。

## 2026-08-28 fix11 至 fix14 收敛结果

- fix11 首次从干净 system 镜像重建时遗漏了 fix6/fix7 的设备文件，handoff 因 `/rgsp-persist` 缺失自动回退；随后已重新合入 `fstab.sun50iw9p1`、设备 rc、watcher 和核心 init 显式 import。
- fix12 证明 `libselinux.so` 的 file-context 补丁生效：日志从 `SELinux: Loaded file_contexts` 推进到 `init: Running restorecon...`，但仍未进入 `early-init`。
- fix13 对 Android `/system/bin/init` 的 `SelinuxRestoreContext()` 入口做最小返回补丁；init SHA-256 为 `a5c26547268af6a0a6890fd305a8059fa222604e6e7b39ce9348e9ea97124289`。实机推进到属性服务 socket 创建。
- fix14 跳过当前 H700 Linux 4.9 环境不兼容的 `SetupMountNamespaces()`；init SHA-256 为 `036017d5e42d4243e3f18bc014adfa71da224b5444cb0ee92cf578f4d36be5cd`。普通 kmsg reader 仍无法显示属性服务之后的真实停点，因此继续增加 init 自身持久日志。
- 上述补丁均只用于 P3 bring-up。取得原厂 H700 Android 固件后必须用匹配的 kernel、init、SELinux 和 vendor 实现替换，不作为最终平台方案。

## 2026-08-28 fix15 回读结果

- fix15 将 Android init 的 `/dev/kmsg` 输出重定向到 TF2 持久文件，首次取得完整 second-stage 日志。
- Android init 已完成 rc 文件扫描、cgroup 初始化并进入 `early-init`；这确认 fix12 至 fix14 已越过此前的 second-stage 初始化阻塞。
- 当前确定性失败链为：内核命令行使用 `selinux=0`，`getpeercon()` 返回 `Protocol not available`，`setexeccon()` 返回 `Invalid argument`，导致 vendor subcontext、`linkerconfig`、`ueventd` 和 `apexd-bootstrap` 无法获得安全上下文。
- `exec_start apexd-bootstrap` 失败后，init 触发 `reboot,bootloader,bootstrap-apexd-failed`。未发现 `/misc` 分区，因此 bootloader message 写入也失败。
- 回到 Linux 后确认 TF1 boot SHA-256 为原厂值 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`，env 前 128 KiB 为 `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`，一次性标记已消费。
- 本轮日志已归档：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `out/RGSP_ANDROID_BOOT_fix15_20260828.log` | 1,532 | `caaec85075b9d005430f320f515a6227657efdf6feaad1d10f7a008a02a62e04` |
| `out/RGSP_ANDROID_INIT_fix15_20260828.log` | 11,550 | `e41d6bbe7faa8506a8bc35f9062adfe1b40a0dab0bdb3b8fc1c31c2aaf3242b3` |
| `out/RGSP_ANDROID_KMSG_fix15_20260828.log` | 33,318 | `26b3a8509e7890d585944b9c3088f023b77dc4869a6ba4c96696bb3312603642` |

## 2026-08-28 fix16 已启动，等待回读

- fix16 在保留 fix11 三处补丁的基础上，为 SELinux disabled bring-up 增加最小上下文兼容：`getcon/getpidcon/getpeercon/getfilecon/security_compute_create` 返回可释放的临时字符串，`setcon/setexeccon/setfscreatecon/setsockcreatecon/setfilecon` 和 `selinux_check_access` 临时返回成功。
- 所有补丁入口均完成 AArch64 反汇编核验；初次链接发现绝对地址解析错误后已废弃该产物，修正链接方式并重新生成，错误版本从未上传或写入设备。
- fix16 `libselinux.so` SHA-256 为 `b80d7e10192a923126b5e9f82278b3a7603231722a1c546134fe6c13bbca7f61`；写入 TF2 前已备份原库，写入后 system 通过 `e2fsck -fn`。
- fix16 handoff ramdisk SHA-256 为 `d723d4d84b54495d0fede774f6b10ae1805a03287d16121721e7ced5a7d6d565`；boot SHA-256 为 `81308ff676b27164ba9a699e27babefd4191b56b10a067466e48d27a5f9c3907`。
- 测试前 CID、原厂 boot、env、恢复镜像、system init、新 libselinux 和一次性标记全部通过校验；boot 写入 `/dev/mmcblk0p4` 后读回哈希一致。
- 2026-08-28 22:52 CST 通过 SSH 重启。约 45 秒后设备恢复 ICMP，但四分钟内 SSH 22、ADB TCP 5555 均未开放，也未自动回到 Linux。
- fix16 没有在 fix15 的 `apexd-bootstrap` 快速重启路径上立即失败，可能已进入新的用户空间停点；需物理复位回 TF1 Linux后读取 `RGSP_ANDROID_INIT_LAST.log`、stage、watcher、logcat、powerctl 和 kmsg，才能确认实际推进位置。

## 2026-08-28 fix16 最终结果

- fix16 的 SELinux-disabled 上下文兼容补丁生效：vendor subcontext 不再退出，`linkerconfig` 返回 0，`ueventd` 完成 coldboot，`apexd-bootstrap` 返回 0。
- Android init 随后执行 32 位 `boringssl_self_test32`，但 `execv('/system/bin/boringssl_self_test32')` 返回 `ENOENT`。该服务带 `reboot_on_failure`，因此触发 `reboot,boringssl-self-check-failed`。
- system 中 32/64 位 BoringSSL 文件实际存在，内核也启用了 `CONFIG_COMPAT=y` 和 `CONFIG_COMPAT_BINFMT_ELF=y`；真正缺失的是运行时 `/apex` 视图。
- `/system/bin/linker` 和 `linker64` 分别链接到 `/apex/com.android.runtime/bin/linker` 与 `linker64`，而 fix16 的 `/apex` 为空目录。由于此前为兼容内核临时跳过 `SetupMountNamespaces()`，flattened APEX 没有被暴露到该路径。
- 只读 chroot 验证中，将 `/system/apex` bind 到 `/apex` 后，32/64 位 linker 均返回 0，32/64 位 BoringSSL self-test 也均返回 0；因此不需要删除安全自检或伪造单 ABI 属性。
- 回到 Linux 后确认 TF1 boot 和 env 仍为原厂保护哈希，一次性标记已消费；TF2 init 和 libselinux 仍分别为 fix14、fix16 预期哈希。
- fix16 日志归档如下：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `out/RGSP_ANDROID_BOOT_fix16_20260828.log` | 1,532 | `5d815370305264a37d3b714d20ad59ffbcc05104e6d41f44cd6664b8f3346062` |
| `out/RGSP_ANDROID_INIT_fix16_20260828.log` | 10,708 | `b2a62187daf98d416b611fdf158984811c2cef32a18b252cd5b825a1d406bd35` |
| `out/RGSP_ANDROID_KMSG_fix16_20260828.log` | 33,314 | `cada8ee56693d0b6be4096348989be48f4df796ae8fa664b8ec0ee93a3331813` |

## 2026-08-28 fix17 已启动，等待回读

- fix17 只修改 handoff ramdisk：在执行 Android second-stage 前 bind `/android-root/system/apex` 到 `/android-root/apex`，补齐 flattened APEX 视图；未修改 TF2 system、vendor、data、U-Boot、GPT、boot0 或持久 env。
- fix17 handoff ramdisk SHA-256 为 `052734449a7f61d6cdedc742331a59f04825310c957541449225c195bbf49231`；boot SHA-256 为 `67276ead9dfee3581d1c2a752320d5499eda5e36ed6f5118cb7795cce244c19b`。
- 测试前原厂 boot、env、恢复镜像、双卡 CID、system init、fix16 libselinux、APEX 目录与一次性标记均通过保护检查；boot 写入后读回哈希一致。
- 2026-08-28 23:11 CST 通过 SSH 重启。设备很快恢复 ICMP，但四分钟内 SSH 22 与 ADB TCP 5555 均未开放，也未自动回到 Linux。
- fix17 需要物理复位后读取 init/stage/watcher/logcat/powerctl/kmsg；重点确认 32/64 位 BoringSSL 是否通过、`/init.sun50iw9p1.rc` 是否开始执行，以及是否进入 `init`、`fs` 或 `late-fs`。

## 2026-08-28 fix17 最终结果

- handoff 日志确认 `/system/apex` 到 `/apex` 的 bind 在进入 Android init 前成功，但 32 位 BoringSSL 仍以 `ENOENT` 失败，停点与 fix16 相同。
- 主 `init.rc` 顺序显示：handoff bind 后，Android early-init 先运行 `apexd-bootstrap`，随后执行 `update_linker_config`，最后才启动 BoringSSL。`update_linker_config` 会重建 APEX/linker 视图，因此覆盖了 handoff 阶段建立的 bind。
- 该结论解释了只读 chroot 测试成功而完整启动失败的差异：chroot 没有执行 Android 的 `update_linker_config` 内建动作。
- 回到 Linux 后确认 TF1 boot 和 env 为原厂保护哈希，一次性标记已消费；没有 stage、watcher、logcat 或 powerctl 文件，因为主 init.rc 的 BoringSSL action 仍排在导入的 RGSP early-init action之前。
- fix17 日志归档如下：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `out/RGSP_ANDROID_BOOT_fix17_20260828.log` | 1,588 | `1c4f0b89ff8118a609527b328cfa04849b1032097145c981137bb7c041ffd2ed` |
| `out/RGSP_ANDROID_INIT_fix17_20260828.log` | 10,708 | `e9004955548a8c91c72eaf3c2fa1539adc4a9ff03ba75c6b8c41918f192862bc` |
| `out/RGSP_ANDROID_KMSG_fix17_20260828.log` | 33,374 | `fe63a702739a0556b87371a81cbb2ea63f28bf70959f1b29fed6e53220383b9e` |

## 2026-08-28 fix18 已启动，等待回读

- fix18 在核心 `/system/etc/init/hw/init.rc` 的 `update_linker_config` 之后插入 init 内建命令 `mount none /system/apex /apex bind rec`，保证重建 linker 配置后再次暴露 flattened APEX。
- 修改前 init.rc SHA-256 为 `e75e168a438eb86a0086969e8ba901d6739bd786c7a54756d9268c021d17f697`；修改后为 `f2038ef115b7d01e5bf5e2f9dc7a080eb6b4a272ded72e33847dc506d7defad9`。原文件已备份到 TF2 ANBOOT。
- system 写入前后均通过 `e2fsck -fn`；init binary 与 fix16 libselinux 未改变。
- fix18 ramdisk SHA-256 为 `1164f2f3516b2b1f5b7d37983a0c0ccda552a00bb178f732515789e0f286d3e6`；boot SHA-256 为 `0febad562486ea5d16955b11ecd62e16ddd7af34bd7e0915ede2f99b96bedfaa`。
- 测试前后双卡 CID、原厂 boot、env、恢复镜像、system init/init.rc/libselinux 和一次性标记均通过保护检查。
- 2026-08-28 23:53 CST 通过 SSH 重启。与 fix16/fix17 不同，四分钟内设备没有恢复 ICMP、SSH 或 ADB；说明启动行为发生变化，但当前无法判断是越过自检后网络被重配，还是新 mount 动作阻塞。
- 需要物理复位回 TF1 Linux 后读取 fix18 init/stage/watcher/logcat/powerctl/kmsg，并再次核验 TF1 boot/env。若 BoringSSL 已通过，应优先处理首次出现的 RGSP stage 或 `init/fs` 错误。

## 2026-08-28 fix18 最终结果

- fix18 的二次 APEX bind 生效，32/64 位 BoringSSL 自检全部通过；RGSP watcher 首次启动，Android init 推进到 `late-fs`，并实际执行了 `post-fs-data` action。
- `/dev/mmcblk1p4` 已作为 ext4 以读写方式挂载到 `/data`，Android 首次创建了完整 data 目录结构；`vold` 保持运行，大量 native service、HAL、zygote、logd 和 netd 已开始启动。
- `servicemanager`、`hwservicemanager` 和 `vndservicemanager` 均反复收到 `SIGABRT`。静态 Binder 探针确认驱动 protocol 8、`BINDER_SET_MAX_THREADS` 和 `BINDER_SET_CONTEXT_MGR_EXT` 在 binder/hwbinder/vndbinder 三套设备上全部可用，排除内核 Binder ABI 阻塞。
- 临时接管 `/dev/socket/logdw` 后捕获精确 abort：`Check failed: selinux_status_open(true ) >= 0`，调用位置为 `android::Access::Access()`；因此失败属于 SELinux-disabled 用户空间兼容，而非 context-manager ioctl。
- fix18 日志已归档为 `out/RGSP_ANDROID_{INIT,BOOT,KMSG,STAGE,WATCH,LOGCAT}_fix18_20260829.log`。stage 内容为 `late-fs`，logcat 文件为空；TF1 原厂 boot、env 与一次性标记状态均通过回退核验。

## 2026-08-28 fix19 已启动，等待回读

- fix19 以 fix16 版 64 位 `libselinux.so` 为基线，仅将 `selinux_status_updated()` 和 `selinux_status_open()` 两个入口改为返回 0。候选库 SHA-256 为 `bf45a5ae0bd61cd9ce43640ceaca5eca3bd83030c152da737ac42e594fa3f984`。
- 补丁器强制校验输入 SHA-256、两个入口的原始 8 字节机器码和输出反汇编；两个入口均确认是 AArch64 `mov w0,#0; ret`，其余文件内容不变。
- 写入前先以只读 system 和 bind 覆盖进行 chroot 验证：`servicemanager` 持续运行 5 秒至测试超时，`hwservicemanager` 与 `vndservicemanager` 均持续运行 3 秒后由脚本主动终止，三者均未再出现 abort。
- fix19 库已备份 fix16 原文件后写入 TF2 `/dev/mmcblk1p2`；写前写后 `e2fsck -fn` 均通过，读回 SHA-256 与候选库一致。TF1 原厂 boot 与 env 仍为保护哈希。
- fix19 ramdisk SHA-256 为 `f267cc6527ee66b989e75379ec3d054f54b8cacc78f943dd62e1ad012671ae40`；boot SHA-256 为 `24d19ab2ce874c4150e84751f9fbec16cee74c6aa41e9906120f512341f547c6`。写入 TF1 `/dev/mmcblk0p4` 后完整读回一致，并建立一次性 marker。
- 已通过 SSH 发起测试重启。约三分钟内原地址 `192.168.31.164` 未恢复 ICMP、SSH 或 ADB TCP 5555；MAC `68:8F:C9:35:EF:C5` 也未在 ARP 表中映射到新地址。
- 当前设备保留在 fix19 Android 现场。下一步需物理复位回 TF1 Linux，读取 init/stage/watcher/logcat/powerctl/kmsg，重点确认三套 manager 是否持续运行、Binder context manager 是否注册、是否推进至 boot/zygote 或出现新的首个确定性失败。

## 2026-08-28 fix19 最终结果

- 设备持续停留在 Android 启动图标，未自动进入桌面；物理复位后正常返回 TF1 Linux。原厂 boot SHA-256、env 前 128 KiB、双卡 CID 均匹配保护值，一次性 marker 已消费。
- fix19 日志仍推进到 `late-fs` 并实际执行 `post-fs-data`，`/data` 读写挂载正常；zygote、surfaceflinger 和大量 native/HAL 服务均被启动，但随后进入反复退出和重启。
- 完整启动中的 `servicemanager`、`hwservicemanager`、`vndservicemanager` 仍反复收到 `SIGABRT`。这与只读 chroot 中三者使用 fix19 库可持续运行的结果不同，因此不能继续假定仍是 `selinux_status_open()` 同一条检查。
- 卡二仅存在 `/system/lib/libselinux.so` 与 `/system/lib64/libselinux.so` 两份库；三套 manager 为 64 位且 64 位库读回确认为 fix19 哈希。`/data/tombstones`、dropbox、anr 和 logd 持久目录均无崩溃文件，普通 logcat 仍为 0 字节。
- 本轮日志已归档为 `out/RGSP_ANDROID_{INIT,BOOT,KMSG,STAGE,WATCH,LOGCAT}_fix19_20260828.log`。需在正式 init 环境中直接截获 logdw 数据，确认越过 fix19 后的下一条精确 abort。

## 2026-08-28 fix20 已启动，等待回读

- fix20 是纯诊断轮次：新增静态 AArch64 `rgsp-logdw-capture`，通过 init 为 `logd` 创建的 `ANDROID_SOCKET_logdw` 接收正式启动日志，将二进制包转换为可搜索文本并逐包 `fsync` 到 TF2 `RGSP_ANDROID_LOGDW_LAST.log`。
- 捕获器已在 Linux 实机以 Unix datagram socket 模拟测试，包含 NUL 与二进制头的 `Abort message` 可完整持久化。捕获器 SHA-256 为 `6a31e4b79f1303261608eed23bb2258e6446dca4ab85fbf00c14416acc35472c`。
- 诊断版 `logd.rc` 仅将主 `logd` service 临时指向捕获器并以 root 运行，保留 init 创建的三个日志 socket；原始 `logd.rc` 已备份到 ANBOOT。修改前 SHA-256 为 `ff0c7f55bbc6fec6cc8da29257c23cb2a4ba65b53cd6203628b2242d1fabdfd7`，修改后为 `2ea41acef64581cc67634afddd844c712e9745d8e664b258ce15d249cf66275d`。
- system 写前写后 `e2fsck -fn` 均通过，fix19 `libselinux` 保持不变。fix20 ramdisk SHA-256 为 `89976422c28bcf84324679670841c500e08b98478d5432ea3cb5dcb81c14d276`，boot SHA-256 为 `09107fb22043ba228cc462fd0bc5cab43fc106dbcd5faf65d3454ae5667fa9aa`。
- fix20 boot 写入 TF1 `/dev/mmcblk0p4` 后读回一致，env 未变化，marker 已建立并通过 SSH 重启。Android 已运行超过 40 秒，现等待物理复位回 TF1 Linux后读取 `RGSP_ANDROID_LOGDW_LAST.log`。

## 2026-08-29 fix20 最终结果

- `RGSP_ANDROID_LOGDW_LAST.log` 捕获到正式启动环境中的确定性根因：H700 内核不支持 binderfs，init 的 `mount binder binder /dev/binderfs` 失败；随后保留的预创建 `/dev/binder`、`/dev/hwbinder`、`/dev/vndbinder` 节点均为 `0600 root:root`。
- Android manager 以 uid 1000 启动，因节点权限得到 `Opening '/dev/binder' failed: Permission denied`、`Opening '/dev/hwbinder' failed: Permission denied`，继而 `Binder driver ... could not be opened. Terminating.` 并触发 SIGABRT。此前 chroot 验证以 root 运行，因此没有暴露该问题。
- 同一捕获日志还显示若干后续缺库（如 `libstatssocket.so`、`libnetd_resolv.so`），但它们是在 Binder 权限阻塞之后出现；本轮先处理决定性 Binder 节点权限。
- fix20 诊断日志已保存到 `out/RGSP_ANDROID_LOGDW_fix20_20260828.log`，并确认 TF1 原厂 boot/env、双卡 CID 和一次性 marker 均正常。

## 2026-08-29 fix21 已启动，等待回读

- fix21 仅修改实际执行的 `/init.sun50iw9p1.rc`，在 `early-init` 与 `init` 阶段显式执行 `chmod 0666 /dev/binder`、`/dev/hwbinder`、`/dev/vndbinder`，覆盖 binderfs 不可用时的预创建节点权限问题；fix19 `libselinux` 与 fix20 logdw 捕获保持不变。
- 修改前 `init.sun50iw9p1.rc` SHA-256 为 `865207bf328a6aac80c19ff9f1e62d597c2670df66da2c5933d5c13dc6ba50c9`，修改后为 `a26a584812227c1978b0c4caa8c20973bdd1d40dc5709c059a2864aef9d80577`。
- system 写前写后 `e2fsck -fn` 均通过，TF1 原厂 boot/env 未改变；fix21 boot SHA-256 为 `328434afe5000884a89e085475f9d576a39406717b323b06282cd164ec3930d6`，写入后读回一致。
- 已通过 SSH 发起 fix21 测试，设备运行 60 秒未恢复网络，当前等待物理复位回 TF1 Linux 后读取日志，重点确认 Binder manager 是否不再出现 `Permission denied`。

## 2026-08-29 fix21 最终结果

- fix21 回读确认显式 `chmod 0666` 生效：`servicemanager` 状态为 `running`，`hwservicemanager` 输出 `hwservicemanager is ready now`，本轮 `RGSP_ANDROID_LOGDW_LAST.log` 已不再出现 Binder `Permission denied` 或 manager 的 Binder abort。
- Android init 已推进到 `fs`，但尚未进入 `late-fs`；watcher 最后阶段为 `fs`，`vold` 持续 `restarting`。
- 当前新的首个确定性错误为 `/system/bin/lmkd` 缺少 `libstatssocket.so`；同时 `vold` 对多个 loop 设备报告 `LOOP_GET_STATUS64 ... No such device or address`，随后 `Unable to start VoldNativeService`。
- fix21 证明当前主线已从 Binder 权限阻塞转移到 Android 用户空间库/存储拓扑兼容问题。设备端 `ttyS0` 仍是 `115200` 内核 console，后续建议先用 UART 做一次从 U-Boot 到 Android 的完整冷启动采集，再处理缺库和 vold/loop 配置。

## 2026-08-29 fix21 日志回读补充

- fix21 持久日志已回收并保存为：
  - `out/RGSP_ANDROID_INIT_fix21_20260829.log`（19,731 bytes，SHA-256 `40e023b4e5116d4b6ab248183659962ddeb8797ed1537fd99950618839519794`）
  - `out/RGSP_ANDROID_BOOT_fix21_20260829.log`（1,588 bytes，SHA-256 `86d99fae6cbe7985886080cd57997474f6e5921ac95c56999fba4eb8c3e6f5dc`）
  - `out/RGSP_ANDROID_KMSG_fix21_20260829.log`（157,910 bytes，SHA-256 `a60236eb1b8da9cb66682500b2f93ce00bc3f2e7fe336cb9b478a08140000a3d`）
  - `out/RGSP_ANDROID_STAGE_fix21_20260829.log`（内容 `fs`）
  - `out/RGSP_ANDROID_WATCH_fix21_20260829.log`（16,384 bytes，SHA-256 `07df9d810b1dbd96921fda44c7213b4de215a9c23c3006d75913776bce48b5c6`）
  - `out/RGSP_ANDROID_LOGDW_fix21_20260829.log`（5,990 bytes，SHA-256 `5f58fc1e9d9aeabd1d1adc4fb3bf25e4bbc66722dc340b7370d0ee53feaddb6f`）
- `servicemanager` 状态已为 `running`，`hwservicemanager` 输出 `hwservicemanager is ready now`；本轮没有 Binder `Permission denied`、`Binder driver could not be opened` 或 manager SIGABRT。
- 首个 linker 错误为 `/system/bin/lmkd` 找不到 `libstatssocket.so`。文件实际存在于 `/system/apex/com.android.os.statsd/lib64/libstatssocket.so`；`libnetd_resolv.so` 也存在于 `/system/apex/com.android.resolv/lib64/libnetd_resolv.so`。因此下一步应修正 APEX/linker namespace 暴露或提供兼容的 system-side 链接路径，而不是盲目删除库依赖。
- `vold` 能启动并识别文件系统，但对 loop0～loop7 反复报告 `LOOP_GET_STATUS64 ... No such device or address`，随后 `Unable to start VoldNativeService`；需要结合 H700 4.9 内核的 loop 配置和当前 `/fstab.rgsp`，确认是否应禁用 loop/snapshot 路径或补充所需 ioctl 能力。
- 当前设备已回到 TF1 Linux，`/dev/mmcblk0p4` 原厂 boot SHA-256 为 `d42252f30730d35ca7759a651da7260ba482144130e58f05f23ea5e33270a6f5`，env 前 128 KiB 为 `d1a0856a8fb4c6f3b785943929a59206424a189f92efcbea48c26b31f472a396`，一次性 marker 已消费。UART 线材到达前，可继续通过持久 logdw/init 日志推进，不必停工等待串口。
