# H700 Android 10 — 开发基线

当前整理基线：**v5i / native35 + USB ConfigFS 与网络检测修复，2026-10-28**。源码冻结标签为 `baseline/h700-v5i-usb-network-20261028`，当前空间整理检查点为 `baseline/h700-storage-trim-20261028`。原交付镜像尚未加入本轮修复重新封装。

本工程整合 H700 掌机上的 Android 10、无触屏按键导航和单卡存储。当前实机已由无摇杆 RGSP 切换为用户提供的 34xxsp：H700、2GB RAM、双摇杆。两台设备的产品属性都可能显示 `RGSP H700`，应按序列号区分。

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
- 双摇杆实体采样和适配尚未进行。冷断电、所有硬件、完整 MTP 传输并未在本轮全部验收。
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

旧烧录/清理脚本、Android 11/R36S 实验、旧文档及一次性回归已移出当前分支，通过 [历史标签](docs/HISTORY.md) 追溯。本次清理结果见 [清理记录](docs/CLEANUP_20261028.md)。当前是 eng/root 开发系统。第三方来源见 [THIRD_PARTY_INPUTS](docs/THIRD_PARTY_INPUTS.md)。
