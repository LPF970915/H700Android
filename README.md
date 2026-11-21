# ROC OS · H700 Android 10

**为 H700 掌机适配的 Android 10，用实体按键操作没有触摸屏的安卓设备。**

[English](README.en.md) · [当前状态](docs/CURRENT_STATUS.md) · [下载与校验](docs/PUBLIC_DOWNLOADS.md) · [构建指南](docs/PUBLIC_BUILD.md)

**当前正式版 0.0.4 · 2026-11-22**。一张系统卡支持十二款 H700 掌机。首次开机默认进入 35XX H 组，音量键切换五组面板，十字键只在当前组内选机型。保存后，下次按电源直接进入 Android。

[各机型首次开机按键表](docs/H700_BOOT_GUIDE_0.0.4_zh-CN.md) · [0.0.4 发行说明](docs/ROC_OS_0.0.4_20261122.md) · [网盘与 SHA-256](docs/PUBLIC_DOWNLOADS.md)

## 当前功能

- 首次开机默认使用 35XX H 面板。五组菜单只显示本组机型，启动和保存前再次检查，避免选到其他面板的机型。
- 40XX V/H 单独一组，默认按 V 初始化。直板 34XX 和 34XX SP／RGSP 分开点屏，直板沿用实测有效的显示参数。开机 Logo 等比缩至 480×320。
- 手柄 A 键使用 Android 标准 BUTTON_A 映射，锁屏和屏幕键盘支持实体 A 确认。内置手柄增加数字 L2／R2 的 Android 扳机轴，系统附带手柄检测工具。
- 内置可用方向键操作的离线中文拼音输入法。USB0 默认以设备模式连接电脑，系统沿用 MTP 和已授权 ADB。

系统保留十字键导航、虚拟鼠标、翻盖服务、双 ABI 应用支持和默认 2 GiB TF1 交换空间。

## 源码与自行构建

仓库提供 H700 适配层、源码覆盖、构建与验证工具及公开工程记录；大型基础源码和镜像通过网盘获取。当前公共 Android 覆盖层含 **1,766 个目标、633 个仓库输入**，已包括 Navigation18 和 ViewRoot 导航保护。

真实生产构建已完成 framework、双 ABI ART 及依赖 preopt，其产物继续包含在 0.0.4。公共构建入口仍从指定 **0.0.1 提取 kernel、DTB、bootloader 和基础 ramdisk**。公共指南的 Android 用户空间重编范围与作者的增量整卡封装范围见[构建验证状态](docs/PUBLIC_BUILD_STATUS.md)；最新组件与依赖入口见[源码地图](docs/TEST10_SOURCE_MAP.md)。

- [公共构建指南](docs/PUBLIC_BUILD.md)
- [H616 基础源码来源](docs/H616_ANDROID10_PROVENANCE_20260902.md)
- [第三方来源与许可](docs/THIRD_PARTY_INPUTS.md)
- [历史版本记录](docs/HISTORY.md)与[工具分类](tools/README.md)

构建者使用自己的签名密钥；官方私钥、设备身份和原始运行日志不公开。仓库不提供游戏 ROM 或商业游戏资源，各第三方组件保留各自许可。

## 反馈

通过 [Issues](https://github.com/LPF970915/H700Android/issues) 提供机型、完整镜像文件名／哈希、触发步骤、是否刚熄屏或合盖，以及可用日志。请去除设备标识和账户、网络信息；重启后的暂时恢复不能独立证明故障已修复。
