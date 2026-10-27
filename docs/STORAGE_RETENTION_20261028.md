# 本地保留与空间清理边界

日期：2026-10-28。**本轮未删除大文件。Git 上传成功不代表本地独有输入可以删除。**

## 当前必须保留

| 路径 | 作用 | Git 能否替代 |
| --- | --- | --- |
| `LOCAL_PRESERVE_H700_BASELINE_20261028/` | 约 345.5MB：旧 Git bundle、未提交文件、私有会话、原始交付/验收、签名、Mali/GLES、ARM runtime、硬件前缀 | 不能；被忽略，需私下复制到其他存储 |
| `out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx.img` | 盘点发现的唯一当前完整 IMG，32,434,554,368 字节 | 不能；未上传，不能因推送成功删除 |
| `out/h700-v5i-dpad-20261027-native35-notouch-stage/` | 最终 system/vendor sparse/raw 和封装锁，逻辑约 11.58GB | Git 只有锁与源码，不含镜像 |
| `.wsl/Ubuntu/ext4.vhdx` | 完整 AOSP、环境与产物，逻辑文件约 187.44GB | 不能整体替代，快照只是修改层 |
| `H700_Android_Example/.../H616_Android_Source_Code/android.tar.gz` | 约 22.27GB 基础源码 | Git 不含完整源码 |
| 同目录 `longan.tar.gz` | 约 1.41GB BSP | 不能 |
| `input/boot.img`、`input/boot-live.img` 及既有恢复输入 | 启动/硬件对照，需核对归属 | 不能 |
| `out/settings-deep-audit-20261023/` 等原始证据 | 原失败、恢复、软件验收与运行证据 | Git 只有摘要/索引；未全量异地备份 |

保全目录位于 `out/` 外，避免普通输出清理误删。`PRIVATE_MANIFEST.json` 记录每个备份文件的 SHA。目录含私钥，不可公开。所有大文件和原始证据并未全装进这个小型保全目录。

## 已保存的应急输入

已保存实际使用的 Mali 模块/GLES、adbd/vold、平台签名材料、保留 POSIX 模式的 grow runtime、原始报告及整理前 Git 历史/未提交文件。

另保存 v5i 的前 222,298,112 字节，SHA 与原封装前缀一致，含 GPT/boot0/boot-resource/env/boot。**该前缀不是可刷镜像，也不含完整 system/vendor/空数据/ROMS，不能据此删除唯一完整 IMG。**

原 36KiB 调试补丁也不是当前卡的通用回滚镜像：后续文件增加后必须拒绝旧整分区块回退。

## 后续可评估空间

`out/` 逻辑文件合计约 218.01GB，大量来自约 11.58GB 一份的旧 stage；`work/` 约 10.47GB，上游输入约 25.21GB。文件长度相加与稀疏文件实际磁盘占用可能不同。

旧 `h700-v5g*`、`h700-v5h*`、10 月 25/26 日 native30/33/34 阶段是优先评估候选，**不是本轮删除授权清单**。部分失败与回滚记录仍依赖它们，先保留小型证明并确认替代输入。

## 真正清理时

1. 从公开标签重新 clone，运行快照验证和恢复测试。
2. 私下把保全目录、唯一 IMG、源码包和必要证据复制到其他存储，核对哈希。
3. 制定具体绝对路径、体积、用途及替代来源清单，不能仅按文件日期或名称推断可删。
4. 按明确范围处理旧 stage、临时副本和可重建产物。WSL 内部删除、VHDX 压缩、删除发行版本身是不同操作。

根目录 `cleanup_*.ps1` 和旧烧录脚本未针对当前基线重新验证，不能直接当清理方案。当前历史封装器所需 v5f seed 已未找到，更应先保住唯一 v5i 完整镜像。
