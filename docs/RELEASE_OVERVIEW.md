# ROC OS 基线与发行状态

更新日期：2026-11-08。当前指定基线为 **ROC OS ARM64 ver0.0.1**，文件 `out/roc-os-h700-usb-mtp-default-verified-20261108/ROC_OS_ARM64_ver0.0.1.img.gz`，591,043,813 字节，SHA-256 `e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346`。解压后为 32,434,554,368 字节，SHA-256 `09935c4935ca579d6956388b2a3af509b4d6c4763e36a047091373a4218208e3`。

0.0.1 从 Recovery720 Test3 派生，只替换 system 中的 `h700-usb-configfs.rc`，让 USB 默认 functions 为 `mtp,adb`，保留认证 ADB 和 USB 选择入口。它**不是完整重编镜像**：沿用既有 Android system 的其余文件、bootloader/environment、kernel、DTB、vendor、userdata 和 GPT。整卡封装、独立核验、gzip/分区检查及 Windows SHA 已通过。验收收据：[acceptance.json](baselines/roc-os-usb-mtp-default-20261108/acceptance.json)。

**当前状态：本地离线核验通过，实机验收仍待完成。** 干净 userdata 冷启动、实际 MTP 文件复制并读回哈希尚未通过记录；不能把桌面识别或 USB 设备枚举当作文件传输验收。全 H700 型号/面板兼容、正式发行和第三方再分发许可也未完成。本仓库没有指定公开下载或声称正式稳定发行。

## 已知问题与边界

- USB 诊断中，鼠标选择 MTP 后电脑曾枚举 `WPD / ROC OS`，但尚未完成真实复制读回；手柄确认 MTP 单选项也存在问题。当前诊断卡含临时配置，**不是** 0.0.1 镜像。
- Wi-Fi 首次配置保存/重启自动连接、息屏/合盖后的开盖唤醒、恢复后 USB 枚举、恢复后 Settings 焦点回跳仍有开放记录。普通重启暂时恢复不等于根因修复。
- H700 显示适配仍开放。DisplayAuto Test2 因实机显示回归已拒绝；Recovery720 Test3 是旧 720 启动路径恢复的离线包，不是 RG35XX H 修复版或全系支持结论。
- Universal Test1 曾在原 RG SP 1GB/无摇杆设备启动通过；该记录不证明 0.0.1、其他 H700 型号、全部面板或外围功能已经实测通过。
- 源码项目已完成干净完整 user 构建。后续开发应在本地保留的同一份 WSL Android/Longan 源码树与 user 增量输出上续编，不计划再次做完整重编。

## 本地文件与版本规则

当前镜像索引：[ROC_OS_CURRENT_BASELINE.txt](../out/ROC_OS_CURRENT_BASELINE.txt)。公开仓库不包含镜像、完整 AOSP/Longan 厂商输入、签名私钥或原始设备隐私日志。后续镜像采用 `ROC_OS_ARM64_ver主.次.修订.img.gz` 命名；每次更新需同时记录文件大小、gzip/raw SHA-256、基础镜像、改动范围和验收边界。文档或源码推送不代表镜像已发布。

刷写为整卡操作，会覆盖目标卡数据。按具体镜像的说明核实型号、卡槽、TF1 容量和数据备份。
