# 本地保留与清理后的边界

2026-10-28 已按用户指令清理旧版本与冗余产物。具体删除范围、空间变化、检查结果和未执行项见 [清理记录](CLEANUP_20261028.md)。Git 源码冻结标签不变；当前精简工作树另有 `baseline/h700-clean-20261028` 标签。

## 继续保护的内容

| 路径 | 保留原因 |
| --- | --- |
| `LOCAL_PRESERVE_H700_BASELINE_20261028/` | 签名、关键小型二进制、原始凭据、整理前 Git bundle 和未提交文件；本次增加旧阶段小型证明与清理记录，含私钥，不能公开 |
| `out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx.img` | 唯一保留的当前完整 IMG，32,434,554,368 字节，未上传 GitHub，也未加入 USB/网络修复重新封装 |
| `out/h700-v5i-dpad-20261027-native35-notouch-stage/` | 最终 system/vendor raw/sparse 及组件/源码锁；其他 14 轮旧阶段已删除 |
| `.wsl/Ubuntu/ext4.vhdx` | 完整 AOSP、构建环境与产物，本轮未删 WSL 或进行缩容 |
| `H700_Android_Example/`、`input/` | 原始上游源码、BSP、供体和硬件输入；Git 不包含这些原包 |
| `out/settings-deep-audit-20261023/` | 原始软件验收/失败/恢复证据，Git 只含摘要与索引 |
| `out/h700-34xxsp-usb-network-20261028/` | 当前新机 USB、网络和重启验证的原始记录 |
| 其他 `out/native-*`、`out/flicker-*` 证据目录 | 组件恢复及未解决显示问题的原始证据；未按缓存一概删除 |
| `out/video-analysis-tools/` | 保留的视频分析工具仍实际引用的依赖 |
| `out/rgsp-v5c-fat-dirty-20260913/`、`out/rgsp-v5d-reboot-failure-20260913/` 的小型捕获 | 当前脏 FAT 回归使用的真实失败夹具，不是重复完整镜像 |

保全目录的 `PRIVATE_MANIFEST.json` 锁定已保存文件。大镜像、完整源码、WSL 和大部分原始证据并未全复制进这个小型目录，也没有完成外部存储备份。

## 已删除和仍能恢复的区别

旧阶段的分区镜像和临时目录已物理删除；其小型组件/源码/fsck 证明保存在私有目录 `cleanup-20261028/retired-stage-receipts/`。它们只能说明当时产物身份，不能恢复被删除的大镜像。

从当前分支删除的旧文档、脚本、重复源码和测试仍能从公开冻结标签取回，见 [历史查询](HISTORY.md)。没有保留另一整套重复源码目录。

原 v5i 的 222,298,112 字节硬件前缀、Mali/GLES、平台签名和 grow runtime 已私下保存；前缀不是可刷镜像，不能作为删除唯一完整 IMG 的依据。历史封装器的 v5f seed 仍未找到，当前保留策略不因此放宽。

## 后续清理

本轮没有留下通用自动删除入口。进一步处理 WSL、原始输入、当前镜像或原始证据，先明确具体范围、可恢复来源并完成必要的外部私有备份。不要按日期、名称或“Git 已上传”推断它们可删。

补充的旧截图、Python 缓存和空目录批量清理被自动审批拒绝（`blocked by policy`，未给出具体原因），没有执行；这些小型忽略内容可能仍留在本地，不进入 Git。
