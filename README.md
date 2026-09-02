# H700 Android 10 Development Kit

> **Current baseline (2026-09-02):** H616 Android 10 is the implementation
> mainline. The former R36S Android 11 work is frozen as a diagnostic archive,
> and H618 Android 12 is retained only as a selected backup reference.

这是 RGSP/H700 Android 移植的第一阶段本地工具包。它只准备和校验
Android `boot.img` 探针，不会自动写入设备内部存储。

## 当前目标

1. 保留原厂 boot image 的关键 header、加载地址和分区布局。
2. 用 H700 vendor kernel、RGSP DTB 和最小 Android ramdisk 生成测试副本。
3. 先在备用 TF 卡或可恢复介质上验证 Android logo、adb/串口和基础挂载。

当前仓库已具备 H616 Android 10 完整源码和镜像、H700 Longan 芯片级配置、RGSP
实机 kernel/DTB/日志，以及 H700 投影仪 Android 10 启动证据。主线 overlay 位于
`android/h700-android10/`，权威计划见
`docs/H700_ANDROID10_MASTER_PLAN_20260902.md`。
H616 主资料的路径、大小与实算校验值见
`docs/H616_ANDROID10_PROVENANCE_20260902.md`。

`reference/` 已准备最小外部参考集，包括 Android 10/LineageOS manifest、R36S
device tree 的关键文件、R36S Android multiboot 脚本和 Andr36oid 构建环境说明。
它们均为浅克隆或稀疏检出，不包含完整 AOSP 和可刷镜像。详情见
`reference/README.md`。

## Android 11 Archive

原 Android 11 init/ADB bring-up 包和脚本已封存：

```text
archive/android11-r36s/
android/legacy-android11/
```

它由 H700 实机 kernel/DTB、handoff ramdisk 和修改后的 LineageOS 18.1
system-as-root 镜像组成。RK3326 bootloader 和硬件 HAL 没有进入 H700 启动包。
完整限制、校验和、TF2 安装与 UART 临时启动步骤见该目录的 `README.md`。

它只用于对照，不再接受新的 framework bypass。fix58 仍需一次最终冷启动验证，但
无论结果如何都不会改变 Android 10 主线决策。

## Storage Boundary

项目的大容量资料、完整源码和构建输出只允许位于 D 盘。当前 Ubuntu WSL2 发行版
注册于 `D:/Works/H700Android/.wsl/Ubuntu/`，Linux 构建根为
`/home/lpf/h700-android10/`；`.wsl/`、镜像、压缩包和构建目录均被 Git 忽略。

`tools/prepare_h616_android10_source.ps1` 会拒绝使用不在项目 `.wsl` 目录中的
Ubuntu 发行版，也会拒绝非空目标目录，防止完整源码再次误落到 C 盘。

轻量代码、脚本和文档已纳入私人仓库：
`https://github.com/LPF970915/H700Android`。完整源码、镜像、日志、构建输出和
D 盘 WSL2 VHDX 不进入 Git 历史。

## 使用方式

```powershell
# 1. 查看原始 boot.img，不修改文件
py -3 .\tools\android_bootimg.py inspect .\input\boot.img

# 2. 解包，保留 kernel/ramdisk/second/dtb 和 header.json
py -3 .\tools\android_bootimg.py extract .\input\boot.img .\work\base

# 3. 生成探针 boot.img。kernel 必须是 RGSP/H700 兼容内核。
.\tools\make_probe.ps1 `
  -BaseBoot .\input\boot.img `
  -Kernel .\input\Image `
  -Out .\out\rgsp-android-probe.img
```

`make_probe.ps1` 默认只接受一个已经解包的 Android boot image 作为模板，
并复制其中的 second/dtb/header 字段。它不会处理 GPT、U-Boot env、boot0
或任何块设备写入。

## 真机测试前置条件

- 完整备份 GPT、`mmcblk0p1`、`mmcblk0p3`、`mmcblk0p4`、`/mnt/vendor` 和
  `/mnt/data`。
- 先证明 U-Boot 能从 TF 卡读取测试 boot 分区；不能假设现有环境变量已经
  支持 `mmc1`。
- 维护窗口内停止原厂前端，确认 `fb0/disp/ion/input/ALSA` 已释放后再测
  `SDL_VIDEODRIVER=mali` 或 Android SurfaceFlinger。
- `boot_fastboot` 字符串不是 fastboot 协议可用性的证明，必须单独验证。

详细路线见以下基线文档：

- `docs/H700_ANDROID10_MASTER_PLAN_20260902.md`
- `docs/H700_ANDROID10_BASELINE_STATUS_20260902.md`
- `docs/H700_ANDROID10_MIGRATION_CLEANUP_20260902.md`
- `docs/H700_ANDROID11_ARCHIVE_20260902.md`

- `docs/H700_ANDROID_GPU_DEVELOPMENT_HANDOFF_20260831.md`
- `docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md`
- `docs/RGSP_H700_ANDROID_BOOT_ANALYSIS_20260826.md`
- `docs/R36S_TO_H700_ANDROID_PORTING_BASELINE_20260826.md`
- `docs/H700_H616_H618_SOURCE_ANALYSIS_PLAN_20260831.md`
- `docs/H700_LOCAL_SOURCE_ANALYSIS_20260831.md`

无触摸 Android 交互方案和模板：

- `docs/RGSP_H700_NO_TOUCH_ANDROID_INTERACTION_20260827.md`
- `reference/no-touch/`
- `tools/capture_h700_input.ps1`

其中 `R36S_TO_H700_ANDROID_PORTING_BASELINE_20260826.md` 是多窗口工作的统一入口，
包含 R36S 可复用边界、推荐 Android 版本、TF1/TF2 架构、阶段计划和协作约定。

## TF2 状态

经用户授权，设备上的 `/dev/mmcblk1` 已初始化为 Android 测试卡；当前分区布局
和实际 PARTUUID 见 `docs/RGSP_ANDROID_PROBE_STATUS_20260826.md`。格式化脚本
`device/format_tf2_android.sh` 具有破坏性，只允许目标为 125 GB 级别的
`mmcblk1`，不要在其他设备上直接复用。
