# ROC OS · H700 Android 10

面向 H700 掌机的 Android 10 适配项目，重点完善无触屏设备的手柄操作与小屏使用体验。

[English](README.en.md) · [当前基线与发行状态](docs/RELEASE_OVERVIEW.md) · [开发源码分支](https://github.com/LPF970915/H700Android/tree/codex/rg34xxsp-at4k-input-lockscreen)

## 当前基线：ver0.0.1

最新离线核验镜像：`ROC_OS_ARM64_ver0.0.1.img.gz`。文件大小 591,043,813 字节，SHA-256：

```text
e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346
```

该版本从 Recovery720 Test3 派生，只把 USB 启动默认配置设为 `mtp,adb`，保留认证 ADB；没有完整重编 Android。离线封装、独立核验和 Windows 哈希通过。干净 userdata 首启、实际 MTP 文件复制读回及所有 H700 机型兼容仍未验收，因此它是当前测试基线，不等于全系正式发布版。核验范围见[验收记录](docs/baselines/roc-os-usb-mtp-default-20261108/acceptance.json)。

## 项目状态

项目经历了完整 ARM64 user 源码构建、生产签名检查和多轮启动/整卡核验。当前基线为 0.0.1；较早 RC5、Universal Test1、显示恢复和 USB 诊断的技术结论/验收摘要仅作历史参考，不是更新基线；冗余整卡镜像和大型 raw 副本已清理。DisplayAuto Test2 因实机显示回归已撤回，不应继续使用。

已实现并在限定设备/阶段检查的内容包括 AT4K 桌面、图库/文件/设置/日历/时钟/音乐入口、手柄导航、Select 虚拟鼠标、亮度与合盖服务、音频、Thermal HAL、TF1 内部存储与 TF2 外置存储路径。不同设备、恢复状态和干净首启的验收范围不相同；不以局部通过推断所有机型或全部功能通过。

仍需关注：干净 userdata 首启和 MTP 实际双向复制；息屏/合盖后的唤醒与 USB 恢复；恢复后设置页焦点回跳；Wi-Fi 首次保存和重启自动连接；面板/启动兼容范围；发行元数据、第三方许可及实卡恢复流程。详情见[发行概览与已知问题](docs/RELEASE_OVERVIEW.md)。

## 源码与重建

仓库包含 H700 适配代码、构建/核验工具和项目记录，不包含完整 AOSP/Longan 上游输入、全部厂商文件或签名私钥。完整干净 user 构建已完成；后续以现有 WSL 源码树及增量构建输出继续开发，不计划重复完整重编。仅克隆 Git 仓库不足以重建镜像。

镜像、签名私钥、设备身份、原始设备日志和账户/网络资料不作为公开仓库内容。第三方组件保留各自许可和来源，见 [THIRD_PARTY_INPUTS.md](docs/THIRD_PARTY_INPUTS.md)。源码或文档提交不代表镜像已上传。请以每个版本明确列出的适用设备、验收状态和 SHA-256 为准；刷写整卡会覆盖目标卡数据。

## 反馈

请通过 [GitHub Issues](https://github.com/LPF970915/H700Android/issues) 提供机型、镜像版本/SHA、操作步骤和可公开的错误记录。发布日志前请移除设备标识、网络名称、IP 和账户信息。
