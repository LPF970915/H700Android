# ROC OS 发行概览与候选版本

[中文首页](../README.md) · [English home](../README.en.md)

更新日期：2026-11-07。最新本地候选为 **RC5 Bootfix1**；当前真机运行 **RC5**；保留的已冻结内测基线为 **RC4**。三者分别记录，不能合并为一次最终验收。

## 已完成的工作

完整 ARM64 user 构建、专用生产密钥及备份、116 个实际 APK 的生产签名角色核验、user/Enforcing 实机启动和认证 USB ADB 已完成。RC5 已核对新启动身份及 11 个可读关键文件与交付分区的哈希；干净首启七入口、Home 下拉、Select 鼠标和十字键由用户确认正常，Thermal HAL Ready 且五项温度有效。固定 bringup 唤醒锁已实际释放。扬声器/耳机切换另有前序实测记录。

上述结论各有范围：温度能读不代表完整热保护通过，唤醒锁释放不代表正常深睡通过，初始导航正常也不代表恢复后的焦点异常已解决。

## 候选镜像身份

以下为本地候选身份，供核对版本使用，不是公开下载链接。

| 项目 | RC5 真机测试版 | RC5 Bootfix1 离线候选 |
| --- | --- | --- |
| 文件名 | `ROC_OS_ARM64_User_RC5_20261107.img.gz` | `ROC_OS_ARM64_User_RC5_Bootfix1_20261107.img.gz` |
| gzip 大小 | 591,044,264 字节 | 591,042,742 字节 |
| 解压后大小 | 32,434,554,368 字节 | 32,434,554,368 字节 |
| 离线封装与独立核验 | 通过 | 通过 |
| 实机范围 | 已刷入并完成部分验收，有四项开放故障 | 尚未刷入，无整包实机结论 |

RC5 gzip SHA-256：

```text
9469ec7c8b7dcb25b973b16463a4a68172705b7aade05a6dd77b341f15ebca73
```

Bootfix1 gzip SHA-256：

```text
7322cd89acef33c41cb7a285f917375fcdda88f204d3e76125f8d616d8450d9d
```

Bootfix1 解压后 raw SHA-256：

```text
46e928c87a8db56ac8e61098001e581d55936223c3eb095249332eaebae18bdd
```

Bootfix1 恢复自定义启动交接前的标准 `umask 000`。RC5 跳过 Android 第一阶段初始化的清零步骤，PID1 继承 `0022`，使首次创建的 Wi-Fi 目录从要求的 `0770` 变成 `0750`，系统服务缺少组写权限。已有目录在后续启动才被 chmod，造成首次失败与后来行为不同。修正版沿用 RC5 system/vendor，不重编 Android 主体；内核、DTB、命令行及除 init 内容外的全部 ramdisk 项保持一致。该修正针对 Wi-Fi 首次写入根因，不能宣称另外三项故障随之解决。

## 当前四项已知故障

| 问题 | 实际影响与当前结论 |
| --- | --- |
| Wi-Fi 首次保存/重启自动连接失败 | 用户明确确认重启后仍需手动输入密码。重连后有写入成功日志，但没有再重启复验。Bootfix1 已修已定位根因，实机效果待验 |
| 息屏/合盖后开盖不自动亮屏 | 本次需要短按电源唤醒。正常深睡及 Hall 唤醒仍未通过 |
| 恢复后 USB 不枚举 | 同线同口重新插拔仍无效；普通菜单重启本次可临时恢复。切换 USB 调试因按键异常无法完成，不是已验证办法 |
| 设置/开发者选项焦点回跳 | 按下却回到右上角；重启暂时抑制症状，根因未知。故障发生时未抓到原始输入现场，不能用重启后的记录代替 |

后三项出现在恢复相关操作后，目前不能确定共同根因。普通重启只算临时恢复，不算修复。

## 发行配置与支持范围

- 当前版本适合按**公测预览候选**说明状态，不宣称正式稳定版。本文没有指定公开镜像下载。
- 当前保留诊断 USB 和工作站公钥预授权；认证启用、root 拒绝、网络 ADB 关闭。面向他人的默认策略仍需确定。
- 源码构建的 `dev-keys` 元数据尚待收口；实际 APK 的生产签名已核验，两者应分别说明。
- 最终同包的长期待机、充电/低电/高温保护、当前 user 存储与外设范围、实卡恢复升级仍有未验收项；缺少验收不等于这些功能已被证明损坏。
- 第三方应用与厂商组件的再分发许可、构建复现比对尚未闭环。公开仓库不包含全部重建输入。
- 镜像烧录会覆盖目标卡。测试使用至少 64GB 专用 TF1；升级是否保留数据应以具体发布说明为准。

RC4 冻结源码为 [`780df2bb`](https://github.com/LPF970915/H700Android/commit/780df2bbd30eb99c7a34acb47636c3c383947e2e)，标签为 [`baseline/roc-os-user-rc4-pilot-20261107`](https://github.com/LPF970915/H700Android/tree/baseline/roc-os-user-rc4-pilot-20261107)。此提交不包含尚未提交的 RC5/Bootfix1 增量。本次更新介绍文档，不改变镜像或验收基线。

## English release overview

As of November 7, 2026, **RC5 Bootfix1 is the latest local candidate**, **RC5 is the version actually running on hardware**, and **RC4 remains the frozen internal-test baseline**. These are separate validation scopes. No public image download is designated here.

The complete ARM64 user build, dedicated production keys and backup, production signing-role checks for 116 APKs, hardware boot with SELinux Enforcing and authenticated USB ADB are complete. On RC5, 11 readable critical files matched the delivered partitions; fresh provisioning, seven desktop entries and basic Home/Select/D-pad operation passed. Thermal HAL was ready with five finite temperature readings, and the fixed bring-up wake lock was actually released. Speaker/headphone switching was checked in an earlier stage. These results do not establish normal deep sleep, full thermal protection or freedom from intermittent recovery failures.

The table and hashes above identify the exact local RC5 and Bootfix1 images. Both passed offline packaging and independent verification; **Bootfix1 has not been flashed or hardware-accepted**. It restores `umask 000` before the custom init handoff. RC5 had inherited `0022`, turning first-created Wi-Fi directories from requested mode `0770` into `0750` and denying group writes. Existing directories were chmodded on a later boot, explaining the different first/subsequent-boot behavior. Bootfix1 keeps RC5 system/vendor without rebuilding Android; kernel, DTB, command line and all other ramdisk entries remain unchanged.

Four RC5 issues remain open:

1. Wi-Fi configuration was not retained; the user re-entered the password after reboot. Later writes succeeded after reconnecting, but no further reboot validation followed. Bootfix1 targets the identified cause; its hardware effect remains unverified.
2. Opening the lid after screen-off/lid recovery did not light the screen; a short power press was needed.
3. USB stopped enumerating after recovery, including after cable reconnection. A normal menu reboot temporarily restored it. Toggling USB debugging could not be completed and is not a proven workaround.
4. Down navigation in Settings/Developer Options jumped to the upper-right corner. Reboot temporarily suppressed it; the cause is unknown and failure-time raw input was not captured.

The last three issues may be related, but no common cause has been established. Reboot recovery is not a fix.

Release metadata, public ADB defaults and the preauthorized workstation public key policy, redistribution permissions, real-card recovery/upgrade, final same-image power/storage/peripheral checks and source rebuild comparison remain open. Actual APK production signatures must not be confused with the remaining `dev-keys` metadata. Authentication is enabled, root is refused and network ADB is disabled. The scope should be described as a **public-preview candidate**, without claiming a completed stable release. Compatibility beyond the tested RG34XXSP is not established.

The RC4 commit and tag linked above do not contain the uncommitted RC5/Bootfix1 work. Updating these documents does not change the image or accepted baseline.
