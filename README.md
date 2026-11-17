# ROC OS · H700 Android 10

**为 H700 掌机适配的 Android 10，用实体按键操作没有触摸屏的安卓设备。**

[English](README.en.md) · [当前状态](docs/CURRENT_STATUS.md) · [下载与校验](docs/PUBLIC_DOWNLOADS.md) · [构建指南](docs/PUBLIC_BUILD.md)

更新日期：**2026-11-17**。当前最新本地测试镜像是 **0.0.2 Test10**，一份整卡通过菜单选择十二种 H700 机型。整卡封装、完整独立验证及 Windows SHA256 核对均通过；新包的摇杆恢复与全机型实体覆盖仍待确认。网盘公开下载仍为 **0.0.1**，Test10 尚未上传。

## 当前功能

ROC OS 提供十字键导航、虚拟鼠标、小屏桌面、亮度与翻盖服务、TF1 内部存储和 TF2 外置存储。系统为 ARM64 Android 10 user 构建，保留 ARM32 应用运行路径、SELinux Enforcing、生产签名和认证 USB ADB。

Test10 已合入：

- 十二机型启动选择，显示对应分辨率，可保存默认并重新选择；不按运存或摇杆数量阻止 Android 启动。
- 三档面板试屏和确认后的“加载中，请稍后”提示。
- Navigation18 及框架导航保护，覆盖熄屏恢复、松开／回中、长按连发及持续时间上限。
- 公共摇杆恢复候选，分开处理 ADC 与 L3／R3，保留校准中心及唤醒后回中保护。
- 默认 2GiB TF1 交换空间、Lid4 翻盖服务和时间默认源。

已有修复进入镜像不等于全部实机通过。第三方应用仍可能需要虚拟鼠标，交换空间也不能保证解决所有应用闪退。

## 机型选择

| 分辨率 | 机型 |
| --- | --- |
| 720×480 | 34XX、34XXSP、RGSP |
| 720×720 | CubeXX |
| 640×480 | 35XX Plus、35XX+／35XX 2025、28XX、35XX H、40XX H、40XX V、35XXSP、35XX Pro |

34XXSP、RGSP、35XXSP 启用翻盖处理；各型号使用自己的摇杆数量与面板配置。28XX 按竖屏横用处理。菜单全部开放，十二机型的实物验证尚未完成。

首次只按电源进入菜单，默认使用 35XX H 的 640×480 试屏配置。若画面不可读，完整按下并松开音量减，在 **35XX H 640×480 → 34XXSP 720×480 → CubeXX 720×720** 间切换并重启返回菜单；音量加反向切换。看到菜单后选择实际机型。保存默认后下次直接启动，电源＋音量减可重新选择。

## 镜像与验证

| 项目 | 当前状态 |
| --- | --- |
| 最新本地测试包 | `ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test10_StickRecovery_20261117.img.gz` |
| 压缩大小 | 591,771,367 字节，约 592MB |
| gzip SHA256 | `ad6cec97dafc641cc4729273f3aea40dc4a4047cef32080bbbfbb88b056f8535` |
| 整卡验证 | 完整解压 32,434,554,368 字节并逐字比较，GPT、启动组件、分区和文件元数据核对通过 |
| 实体状态 | Test10 摇杆、恢复后导航、交换空间和完整机型覆盖待确认 |
| 公开下载 | 仍为 0.0.1；[下载、文件身份与适用范围](docs/PUBLIC_DOWNLOADS.md) |

使用至少 64GB 测试 TF1，TF2 留空，并核对目标卡。首次准备数据区及创建 2GiB 交换文件需要等待；后续启动复用。测试步骤和精确 raw 哈希见 [Test10 工程说明](docs/ROC_OS_H700_STICK_RECOVERY_TEST10_20261117.md)。

当前重点是复测 34XXSP／35XX H 摇杆、熄屏解锁后的导航，以及同包显示和交换空间。Wi-Fi、翻盖／休眠、USB 恢复、自动校时／RTC 保时和低概率频闪按新包分别确认。早期测试系统的问题保留在历史记录中，不直接作为 Test10 的现存故障清单。详见[当前状态](docs/CURRENT_STATUS.md)和[发行概览](docs/RELEASE_OVERVIEW.md)。

## 源码与自行构建

仓库提供 H700 适配层、源码覆盖、构建与验证工具，以及公开工程记录；大型基础源码和镜像通过网盘获取。当前公共 Android 覆盖层含 **1,759 个目标、626 个仓库输入**，已包括 Navigation18 和 ViewRoot 导航保护。

真实生产构建已完成 framework、双 ABI ART 及依赖 preopt，并进入 Test10。公共构建入口仍从指定 **0.0.1 提取 kernel、DTB、bootloader 和基础 ramdisk**；按公共指南重编 Android 用户空间，不等于从干净克隆一键重现作者的 Test10 增量启动与封装链。最新启动器、型号表、摇杆、交换空间和封装源码位置见 [Test10 源码地图](docs/TEST10_SOURCE_MAP.md)。

- [公共构建指南](docs/PUBLIC_BUILD.md)与[验证范围](docs/PUBLIC_BUILD_STATUS.md)
- [H616 基础源码来源](docs/H616_ANDROID10_PROVENANCE_20260902.md)
- [第三方来源与许可](docs/THIRD_PARTY_INPUTS.md)
- [历史版本记录](docs/HISTORY.md)与[工具分类](tools/README.md)

构建者使用自己的签名密钥；官方私钥、设备身份和原始运行日志不公开。仓库不提供游戏 ROM 或商业游戏资源，各第三方组件保留各自许可。

## 反馈

通过 [Issues](https://github.com/LPF970915/H700Android/issues) 提供机型、完整镜像文件名／哈希、触发步骤、是否刚熄屏或合盖，以及可用日志。请去除设备标识和账户、网络信息；“重启后暂时正常”不作为故障关闭依据。
