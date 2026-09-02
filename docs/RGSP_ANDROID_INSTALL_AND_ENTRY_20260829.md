# RGSP H700 Android 安装与进入路径

日期：2026-08-29  
设备：RG SP V2.0 / Allwinner H700 / Linux 4.9.170

## 当前可用结构

按实施计划的 TF1/TF2 架构，当前卡二已经具备 Android 测试分区：

```text
TF1 / mmcblk0
  p3  原厂 U-Boot env（保持原厂）
  p4  原厂 Linux/Android handoff boot（测试时临时写入，失败会恢复）
  p5  原厂 Linux rootfs

TF2 / mmcblk1（Linux 编号）
  p1  ANBOOT FAT32，保存 handoff boot 和持久日志
  p2  ANDROID_SYSTEM ext4
  p3  ANDROID_VENDOR ext4
  p4  ANDROID_DATA ext4
  p5  ROMS FAT32
```

已验证的 Android 进入方式是：TF1 的 H700 kernel/DTB + handoff ramdisk，挂载
TF2 p2/p3/p4 后执行 Android `/init`。fix32 及后续 fix40–fix42 已实机证明该路径
可以进入 Android 串口 shell、启动 zygote64 和 system_server，并在失败时自动恢复
TF1 Linux。

## 推荐的安装/进入顺序

### 1. 安装 Android 分区

在原厂 Linux 下只写 TF2：

```sh
e2fsck -fn /dev/mmcblk1p2
e2fsck -fn /dev/mmcblk1p3
e2fsck -fn /dev/mmcblk1p4
```

将 Android system image 写入 TF2 p2，vendor/data 保持对应镜像和标签；不要写
`/dev/mmcblk0`，不要修改 boot0、GPT、U-Boot 或 env。现有安装脚本和分区校验见：

```text
device/install_rgsp_android11_alpha_tf2.sh
docs/RGSP_ANDROID_PROBE_STATUS_20260826.md
```

### 2. 不保存 env 的临时进入（首选）

先打开 `COM4`，再让设备冷启动并在 U-Boot 的 `Hit any key to stop autoboot:`
处按键。确认 TF2 的 U-Boot 编号后，按以下模板执行：

```text
mmc list
mmc dev <TF2>
mmc info
fatls mmc <TF2>:1
fatload mmc <TF2>:1 0x45000000 rgsp-android11-handoff-boot.img
run setargs_nand
setenv bootargs "${bootargs} androidboot.hardware=rgsp androidboot.console=ttyS0 androidboot.selinux=permissive"
bootm 0x45000000
```

`<TF2>` 必须由 UART 实测确定。Linux 的 `mmcblk1` 不能直接当作 U-Boot 编号；
内核目前显示 TF2 对应 `sdc2`，但 U-Boot 是否暴露为 `mmc 2` 仍待 P1 实测。

成功标志：

```text
[rgsp-android] handoff init reached
[rgsp-android] Android root mounted; preparing switch_root
console:/ #
```

退出或失败时，不执行 `saveenv`；复位后 U-Boot 回到原厂 Linux。

### 3. 当前 fix42/fix43 handoff 方式

在 U-Boot 直接读取 TF2 尚未实测前，当前 fix42/fix43 仍通过 TF1 `/dev/mmcblk0p4` 临时承载
boot image。prepare 脚本写入前执行完整保护检查，Android handoff 启动后会：

1. 校验并恢复 TF1 原厂 boot；
2. 挂载 TF2 system/vendor/data；
3. 执行 Android `/init`；
4. 记录串口和持久日志；
5. 失败或 watchdog 后回到原厂 Linux。

fix42 实测已到达 Android `console:/ #`，zygote64 和 system_server 均可运行；约
183 秒后 system_server 因 headless 模式下 LightsService 等待不存在的 SurfaceFlinger
被 Watchdog 杀死。fix43 只跳过该 LightsService 启动调用，候选包尚未完成实机验证。

### fix32–fix43 后续诊断（截至 2026-08-31）

TF2 data 的 tombstone 已取得 zygote32/zygote64 的完整 backtrace；两者都在
`libnativeloader.so (OpenNativeLibrary)` 处报告：
`Error finding namespace of apex: no namespace called com_android_art`。
同一系统在 Linux chroot 复现时，`linkerconfig` 的确定性首错为：
`Check failed: !"undefined var" VENDOR_VNDK_VERSION is not defined`。
它在 abort 前会写出包含 `namespace.com_android_art` 的部分配置，说明 ART
目录规范化已经生效，当前缺口是 Android 属性 `ro.vndk.version` 没有进入
linkerconfig 的属性空间。镜像中该值只存在于未加载的
`/system/vendor/default.prop`，而实际加载的 `prop.default` 不含它。

fix33–fix42 已陆续解决 VNDK/APEX namespace、Binder 节点权限、图形服务隔离和
Watchdog/HIDL 诊断问题；这些都是 P3 bring-up 补丁，不是最终 H700 产品方案。
fix43 仍沿用一次性 marker、写后回读和失败自动恢复，未修改 U-Boot env、GPT、
boot0 或原厂恢复路径。

## 下一项现场任务（P1，非当前 framework 阻塞）

使用 `tools/probe_rgsp_uboot_mmc.ps1` 完成只读 U-Boot 探针：

1. 冷启动时拦截 autoboot；
2. 执行 `mmc list`、`mmc dev 0/1/2`、`mmc info`；
3. 对候选控制器执行 `fatls mmc N:1` 和 `ext4ls mmc N:2 /`；
4. 保存 UART 转录并执行 `reset`；
5. 不执行 `saveenv`，不改 GPT/bootloader/env。

P1 完成后才能决定是否把 Android boot 也迁移到 TF2，实现真正的“TF2 独立安装、
TF1 默认 Linux、按键临时进入 Android”。P1 尚未完成不会阻塞当前 headless framework
和图形 HAL 分析；投影仪主板暂时无法焊接 UART，也不影响 RGSP 主线。

## 当前结论

- Android system/vendor/data 已安装在 TF2，安装本身不是当前阻塞。
- 已有可靠的临时 handoff 进入 Android 串口 shell 的路径。
- 真正独立的 TF2 启动入口取决于 U-Boot 对 TF2 的 MMC 编号和 FAT/ext4 读取能力。
- 在 P1 未完成前，不修改持久 U-Boot env；framework namespace 主线已基本越过，
  当前应转入 H700 图形 HAL/软件 framebuffer，但仍禁止无 ABI 证据复制 R36S/RK3326 GPU 库。
