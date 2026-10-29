# H700 Android 10 — 开发基线

整理基线：**v5i / native35 + USB ConfigFS 与网络检测修复，2026-10-28**。源码冻结标签为 `baseline/h700-v5i-usb-network-20261028`，空间整理检查点为 `baseline/h700-storage-trim-20261028`。其上已加入 RG34XXSP 菜单、双摇杆和锁屏增量，见 [本轮记录](docs/RG34XXSP_DEVELOPMENT_20261028.md)。原交付镜像尚未加入这些修复重新封装。

导航 v8 新增 [Menu 下拉入口与默认强制横屏](docs/RG34XXSP_MENU_LANDSCAPE_20261029.md)：短按 Menu 回桌面、单独长按约 0.7 秒展开快捷设置，十字键导航/分页、A 切换、B 收起；横屏默认开启并记住偏好，微信读书正文已验证 720×480 重排。此前的 [Select 长按鼠标呼出](docs/RG34XXSP_SELECT_HOLD_20261028.md)：Navigation v7 改用 **Select 单独按住至少 2 秒后松开**，旧肩键组合已移除，Select＋Start 不触发鼠标，开启时光标居中并提示。用户已在 2026-10-29 确认实体呼出、移动和 B 关闭；四肩键单键采样与当前 Android 映射一致。此前 [控制器鼠标、电源盘点与模拟器初测](docs/RG34XXSP_INPUT_POWER_EMULATORS_20261028.md)保留 v6 历史记录。当前开发在 `codex/rg34xxsp-at4k-input-lockscreen` 分支，`main` 仍为整理基线。

2026-10-30 用户实测确认的[首批预装软件](docs/FIRST_PREINSTALL_BATCH_20261030.md)为：**QQ 音乐 TV、Animeko TV、PPSSPP、RetroArch（RA）、NOVA、KOReader**。NOVA 必须使用**手机/平板模式**，TV 模式显示不全。该名单用于后续预装集成，尚未重新封装 IMG。此前 [720×480 小屏首轮筛选](docs/RG34XXSP_SMALL_SCREEN_APPS_20261028.md)保留当时的测试条件及版本锁；当前选择以新名单为准。

新增[微信读书墨水屏版实测](docs/RG34XXSP_WEREAD_20261029.md)：官方 2.1.2 支持 ARM32；用户扫码后已验证正文缩小、控制器 HAT 左右翻页、B 返回和进程重启续读。其后通过上述系统横屏增量验证正文重排与翻页；工具栏/目录仍需要虚拟鼠标辅助，尚未通过全程十字键验收。

本工程整合 H700 掌机上的 Android 10、无触屏按键导航和单卡存储。当前实机已由无摇杆 RGSP 切换为用户提供的 34xxsp：H700、2GB RAM、双摇杆。两台设备的产品属性都可能显示 `RGSP H700`，应按序列号区分。

2026-10-29 的 [硬件接口对照与实测](docs/RG34XXSP_HARDWARE_CHAIN_20261029.md)确认电源键熄屏/唤醒、QQ 音乐 TV 外放及音量键正常；合盖传感器有信号但未接入 Android 熄屏，亮度与蓝牙仍有集成缺口。该记录是后续硬件适配的起点。

其后单独加入 [合盖息屏、开盖唤醒](docs/RG34XXSP_LID_20261029.md)，当前已启用真实 Hall 读取，受控循环通过 Android 电源状态验证。新版本实体开合尚待确认，显示关断和内核深度待机仍有待排查；原 IMG 未更新。

先阅读：

- [当前状态与验收边界](docs/CURRENT_BASELINE_20261028.md)
- [源码恢复与构建](docs/REPRODUCE_BASELINE_20261028.md)
- [本地保留与空间清理清单](docs/STORAGE_RETENTION_20261028.md)
- [243 GiB 空间构成与第二轮精简](docs/SPACE_REVIEW_20261028.md)
- [基线凭据和哈希](docs/baselines/h700-v5i-usb-network-20261028/README.md)
- [工具分类](tools/README.md)
- [后续开发索引](docs/DEVELOPMENT_NOTES.md)
- [历史版本查询](docs/HISTORY.md)

## 当前状态

- v5i 软件按键可达性验收、完整 IMG 封装及独立 SHA-256 校验已完成。
- 新机 USB ADB、受来源限制的 Wi-Fi ADB、互联网检测通过一次完整内核重启验证。
- 原 v5i 的 42 项组件哈希全部一致；新增 USB/网络配置后，system/vendor 保持只读。
- 已接入 RG34XXSP 四轴和 L3/R3，重启后 Android 在原控制器上识别四轴；用户已确认实体双摇杆、十字键及虚拟鼠标正常。量化端点和 L3/R3 按压仍未单独验收。AT4K 菜单和同图锁屏的增量验收见本轮记录。
- 冷断电、所有硬件、完整 MTP 传输并未在本轮全部验收。
- 硬件 VSYNC、通用硬件视频解码、FTRACE 等限制见当前状态文档。

## Git 与本地输入

Git 保存产品配置、补丁工具、测试、技术记录，以及 **364 个文件、约 2.89MB 的实测源码覆盖快照**。它包含 native35、本轮 USB/网络修复和额外的 vold、StorageManagerService、healthd、完整固定版 LeanbackIME 输入。

Git 不包含完整 IMG、完整 AOSP/Longan、WSL VHDX、签名私钥、原始设备日志和私有会话配置。上传成功不代表这些文件可以删除，详见保留清单。既有小型 APK、Wi-Fi 驱动和工具保留原有来源，本仓库不是完整 AOSP 发行版。

## 不访问设备的核验

Python 3.11+：

```powershell
py -X utf8 tools/restore_h700_baseline.py
py -X utf8 -m unittest discover -s tools -p test_h700_baseline_restore.py -v
```

上述命令核验源码快照并在临时目录测试恢复，不启动构建、不连接设备、不写卡。

## 版本关系

| 阶段 | 状态 |
| --- | --- |
| `baseline/h700-v5f-roms` 及更早标签 | 历史参考 |
| v5i/native35，2026-10-27 | 原始已交付镜像及软件验收 |
| `baseline/h700-v5i-usb-network-20261028` | 当前源码及实机修复冻结点；未重封装 IMG |
| `baseline/h700-clean-20261028` | 保留同一源码快照，移除失效版本/文档/工具/测试及旧大产物后的工作树 |
| `baseline/h700-storage-trim-20261028` | 同一源码，清理 WSL 编译输出与停用源码副本，记录镜像无损压缩和实际空间 |
| `baseline/rg34xxsp-at4k-input-lockscreen-20261028` | AT4K 菜单与同图锁屏、原控制器双摇杆增量；实机重启通过，未重封装 IMG |
| `baseline/rg34xxsp-controller-mouse-20261028` | 释放 Select，三键鼠标组合与拖动/滑动、RetroArch 配置和小更新回退；物理电源/音频仍待验收 |
| `baseline/rg34xxsp-small-screen-apps-20261028` | 9 个应用初测、APK/夹具锁、KOReader 用户补丁；未构建系统或更新 IMG，实体使用和完整设置仍待验收 |
| `baseline/rg34xxsp-select-hold-20261028` | Navigation v7：Select 单独长按 2 秒后松开开关鼠标、排除组合键、光标居中与提示；未更新原 IMG |
| `baseline/rg34xxsp-hardware-audit-20261029` | 合盖改动前的硬件链路盘点；QQ 音乐 TV 外放与实体音量键通过，记录亮度/蓝牙/待机缺口 |
| `baseline/rg34xxsp-lid-20261029` | 独立 H700Lid 服务接入电源键睡眠/唤醒流程，受控验证通过；实体开合、背光关断和深度挂起待测，未更新原 IMG |

旧烧录/清理脚本、Android 11/R36S 实验、旧文档及一次性回归已移出当前分支，通过 [历史标签](docs/HISTORY.md) 追溯。本次清理结果见 [清理记录](docs/CLEANUP_20261028.md)。当前是 eng/root 开发系统。第三方来源见 [THIRD_PARTY_INPUTS](docs/THIRD_PARTY_INPUTS.md)。
