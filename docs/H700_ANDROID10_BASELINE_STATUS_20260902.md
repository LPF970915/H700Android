# H700 Android 10 基线状态

日期：2026-09-02  
状态：干净开发基线已建立，尚未生成可刷镜像

## 已完成

- 主线固定为 H616 Android 10 / API 29，RGSP H700 kernel、DTB 和板级 overlay；
- R36S Android 11 fix6-fix58 脚本、ramdisk 和产品文件已集中封存；
- H618 Android 12 只保留约 133 MiB 精选对照资料，不进入产品目录；
- 清理 98 个重复文件或目录，回收 82.71 GiB；
- H616 `android.tar.gz` 和 `longan.tar.gz` 已完成 MD5 回读验证；
- 完整 Android+Longan 源码已解到 D 盘项目内的 Ubuntu WSL2 VHDX；
- 原厂 `cupid_perf1-eng` 与新 `h700_rgsp-eng` 均通过 `lunch`；
- 两个产品均通过 `m nothing` 全量 Soong/Make 构建图解析；
- 安卓 10 产品目录未发现 `r36s`、`rk3326`、`rk30board` 或 H618 引用。

## 本地位置

- Windows 项目：`D:/Works/H700Android/`；
- Ubuntu VHDX：`D:/Works/H700Android/.wsl/Ubuntu/ext4.vhdx`；
- Linux 构建根：`/home/lpf/h700-android10/`；
- Android 源码：`/home/lpf/h700-android10/android/`；
- Longan BSP：`/home/lpf/h700-android10/longan/`；
- 主线 overlay：`android/h700-android10/device/roc/`。

完整源码和未来构建输出不得迁回 C 盘。准备脚本会验证 Ubuntu 发行版必须位于本项目
`.wsl` 目录，并同时检查宿主 D 盘与 Linux 文件系统余量。

2026-09-02 最终复核：Ubuntu 注册 `BasePath` 为
`D:/Works/H700Android/.wsl/Ubuntu`，D 盘 `ext4.vhdx` 约 119.81 GiB；Linux 内
`/home/lpf/h700-android10` 约 52 GiB。C 盘未发现本项目的源码压缩包、失败解压目录
或旧 Ubuntu VHDX，可用空间约 117.86 GiB；D 盘可用空间约 230.53 GiB。

## 主线已切断的依赖

新产品不继承 `device/softwinner/cupid-common/cupid-common.mk`，因此不会自动带入：

- HDMI-CEC、电视启动动画和 4K 显示默认值；
- AC100/AC107、HDMI/SPDIF 作为默认音频端点；
- PPPoE、电视 Launcher、PlayReady/Widevine 产品包；
- 投影仪服务、Orange Pi 分区表、DTS、PMIC 或启动链。

`cupid` 和 H616 board selector 只用于选择 Android 10 HAL 代际。Widevine L3 变量仅
作为全志全局 Makefile 的源码目录解析守卫，产品没有请求 DRM 包。

## 尚未完成

1. 构建第一版 `h700_rgsp` system/vendor 镜像；
2. 将 RGSP 已验证 kernel、DTB 和 Android 10 ramdisk 组合成测试 boot；
3. 验证 TF2 system/vendor/data 挂载并到达 ADB、zygote、原生 system_server；
4. 对接 H616 Mali-G31、Gralloc、HWC2、ION 与 RGSP 720x480 面板；
5. 得到第一幅稳定画面后再启用输入、音频、电池、亮度、无线和产品化功能。

从当前状态到第一幅安卓画面还剩三个主要门槛：完整镜像构建、Android 10 init/存储
启动、H616 图形栈与 RGSP 面板对接。当前已经越过“资料不明、源码未落盘、产品无法
解析”的准备阶段，但尚不能承诺一次构建即可出画面。

## 下一执行队列

详细计划已更新为 `docs/H700_ANDROID10_NEXT_DEVELOPMENT_PLAN_20260902.md`。

1. 在 D 盘空间保护下编译 `h700_rgsp-eng` 的 system/vendor/ramdisk；
2. 完成产物哈希、32 位 ELF 依赖、VINTF、SELinux 和来源检查；
3. 使用 RGSP kernel/DTB 组装测试 boot 和 TF2 部署包；
4. 用户在场后完成 Android 10 init/存储/ADB 冷启动验证；
5. 稳定原生 `system_server` 后接入 H616 图形栈并验证 720x480 首图；
6. 首图之后再开发输入、音频、电源、无线和低内存优化。

当前可在没有实体机的情况下连续推进步骤 1-3。Android 11 fix58 取证不阻塞主线。
