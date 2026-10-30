# 本地保留与清理后的边界

2026-10-28 已按用户指令清理旧版本与冗余产物。首轮具体删除范围、空间变化、检查结果和未执行项见 [清理记录](CLEANUP_20261028.md)，其标签为 `baseline/h700-clean-20261028`。第二轮 WSL 空间整理后的检查点为 `baseline/h700-storage-trim-20261028`；Git 源码冻结标签不变。

## 继续保护的内容

| 路径 | 保留原因 |
| --- | --- |
| `LOCAL_PRESERVE_H700_BASELINE_20261028/` | 签名、关键小型二进制、原始凭据、整理前 Git bundle 和未提交文件；本次增加旧阶段小型证明与清理记录，含私钥，不能公开 |
| `out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx.img` | 唯一保留的当前完整 IMG，32,434,554,368 字节，未上传 GitHub，也未加入 USB/网络修复重新封装 |
| `out/h700-v5i-dpad-20261027-native35-notouch-stage/` | 最终 system/vendor raw/sparse 及组件/源码锁；其他 14 轮旧阶段已删除 |
| `.wsl/Ubuntu/ext4.vhdx` | 当前完整 AOSP、工具链与 ROCreader；第二轮按用户选择清理 Android 编译输出和停用源码副本，见下文 |
| `H700_Android_Example/`、`input/` | 原始上游源码、BSP、供体和硬件输入；Git 不包含这些原包 |
| `out/settings-deep-audit-20261023/` | 原始软件验收/失败/恢复证据，Git 只含摘要与索引 |
| `out/h700-34xxsp-usb-network-20261028/` | 当前新机 USB、网络和重启验证的原始记录 |
| `out/tv-apps-20261028/` | 小屏应用初测的 9 个 APK（合计约 260 MiB）、自制夹具和原始截图/记录；Git 仅保存版本/哈希/结果。没有另复制一套 APK |
| `out/qqmusic-tv-20261029/` | 官方 QQ 音乐 TV ARM32 APK、静态签名/兼容校验与安装凭据；Git 只保存锁和听音结果 |
| `out/video-gapps-20261029/`、`LOCAL_PRESERVE_H700_BASELINE_20261028/video-gapps-20261029/` | 首批预装选定的 Animeko TV APK、视频应用筛选及谷歌组件离线准备材料、失败实验和回退证据；含私有会话数据，不上传、不作为普通缓存清理。选定名单见 `FIRST_PREINSTALL_BATCH_20261030.md` |
| `out/mt-manager-20261030/`、`LOCAL_PRESERVE_H700_BASELINE_20261028/mt-cleanup-20261030/`、`.tmp/mtw30/` | MT 官方 APK 与按键测试、11 款试验/采样 App 的卸载前数据及恢复索引；微信读书归档和短路径暂存含账号/阅读数据，禁止上传，不能当作普通临时缓存删除。设备应用卸载不代表本地资料已授权清理 |
| `out/weread-eink-20261029/` | 官方微信读书墨水屏版 APK、来源/签名/ABI 校验及初测记录；二维码和后续账号画面只留本地，Git 仅保留脱敏结论 |
| `out/rg34xxsp-lid-20261029/`、`LOCAL_PRESERVE_H700_BASELINE_20261028/lid-20261029/` | 合盖独立 APK、首次原型与受控回归、原始状态、AOSP 写入前备份；不是整卡或内核深度挂起通过证明 |
| `LOCAL_PRESERVE_H700_BASELINE_20261028/app-selection-20261028/` | 本轮私有操作记录、生成脚本、失败/最终补丁、安装前及最终设置证明的新增保全；以该子目录清单为准，未复制全部 APK/媒体/画面，也未完成外部备份 |
| 其他 `out/native-*`、`out/flicker-*` 证据目录 | 组件恢复及未解决显示问题的原始证据；未按缓存一概删除 |
| `out/video-analysis-tools/` | 保留的视频分析工具仍实际引用的依赖 |
| `out/rgsp-v5c-fat-dirty-20260913/`、`out/rgsp-v5d-reboot-failure-20260913/` 的小型捕获 | 当前脏 FAT 回归使用的真实失败夹具，不是重复完整镜像 |

保全目录的 `PRIVATE_MANIFEST.json` 锁定已保存文件。大镜像、完整源码、WSL 和大部分原始证据并未全复制进这个小型目录，也没有完成外部存储备份。

## 已删除和仍能恢复的区别

旧阶段的分区镜像和临时目录已物理删除；其小型组件/源码/fsck 证明保存在私有目录 `cleanup-20261028/retired-stage-receipts/`。它们只能说明当时产物身份，不能恢复被删除的大镜像。

从当前分支删除的旧文档、脚本、重复源码和测试仍能从公开冻结标签取回，见 [历史查询](HISTORY.md)。没有保留另一整套重复源码目录。

原 v5i 的 222,298,112 字节硬件前缀、Mali/GLES、平台签名和 grow runtime 已私下保存；前缀不是可刷镜像，不能作为删除唯一完整 IMG 的依据。历史封装器的 v5f seed 仍未找到，当前保留策略不因此放宽。

## 后续清理

用户随后要求进一步压缩 243 GiB 工作区，选择“保留完整源码，清理编译产物并压缩镜像”，并明确保留 ROCreader、清理不用的 H616 源码。第二轮范围、无损压缩校验、原文件删除被拒绝的状态、WSL 回收量与后续编译影响见 [空间复核](SPACE_REVIEW_20261028.md)。当前 H700 开发源码本身基于 H616，继续保留；清理的是另一个停用副本，不是删除全部 H616 来源。

整 IMG 及最终 system/vendor raw 已分别生成经过完整解压和原 SHA 校验的 `.gz`。自动审批拒绝删除三个原文件，目前原文件与压缩包同时保留；若用户手动删除原文件，必须保留对应 `.gz`，需要 raw 输入时再解压。最终 sparse、组件/源码锁仍保留。

本轮没有留下通用自动删除入口。进一步处理 WSL、原始输入、当前镜像或原始证据，先明确具体范围、可恢复来源并完成必要的外部私有备份。不要按日期、名称或“Git 已上传”推断它们可删。

补充的旧截图、Python 缓存和空目录批量清理被自动审批拒绝（`blocked by policy`，未给出具体原因），没有执行；这些小型忽略内容可能仍留在本地，不进入 Git。

2026-10-29 Menu/横屏增量另保留 `LOCAL_PRESERVE_H700_BASELINE_20261028/force-landscape-20261029/` 的旧系统 JAR、Navigation v7、显示策略、源码和私有回退脚本，以及 `out/force-landscape-20261029/` 的新 APK/JAR/验收证据。Git 只收脱敏锁和源码；这些文件不是本轮可清缓存。见 [增量记录](RG34XXSP_MENU_LANDSCAPE_20261029.md)。

2026-10-30 增补 [天马 G / GBA 实测与预装](RG34XXSP_PEGASUS_GBA_20261030.md)。官方 ARM32 前端、主题/元数据适配、独立 LCD3x 配置及 NuPlayer 预览修复已在现机验证；新镜像封装另计。`out/pegasus-gba-20261030/` 与本地保全同名子目录保存 APK、原始材料、测试/回退输入，不能按缓存删除；ROM 不上传 Git、不加入新镜像。

## 2026-10-30 新镜像与实际保留状态

三个旧 raw（v5i 整 IMG、native35 system/vendor raw）目前已不在原路径，其经过校验的 `.gz` 均仍在；此前“原文件与 gzip 并存”仅描述 10-28 自动清理未执行时的状态。

`out/h700-v6a-preinstall-20261030/` 的新无 ROM 镜像 gzip、整镜像/分区/资源锁、首次启动平台测试与构建日志，以及 WSL `/home/lpf/h700-release-v6a-20261030/` 的新候选分区、payload、保留的中断材料和回读证明，均需保护，不能因代码已推 Git 而视为缓存。新 raw 在 gzip 完整解压 SHA 和再次 gzip 哈希确认后移除，保留可无损恢复的压缩包，释放约 30.2GiB；未删除旧压缩基底、源码、ROCreader 或原始材料。镜像未上传 Git。

2026-10-30 v6b：保护 `out/h700-v6b-preinstall-20261030/` 成品 gzip、锁/日志/设备临时夹具记录及重命名保留的中断压缩输出，WSL `/home/lpf/h700-release-v6b-20261030/` 与 `...-fd8-prototype/`，以及保全目录 `v6b-20261030/` 的原生输入写前备份。直接分区流压缩，没有生成新的 32GB raw；旧 v6a 与 v5i gzip 均保留。Git 仅收配置、工具与脱敏报告，不含镜像/APK/私有记录。

ARM64 可行性验证的 `out/arm64-feasibility-20261030/` 与对应低负载构建日志保留探针、失败/成功取证及原始设备证明，包含私有设备身份，仅脱敏结果与自有源码入 Git；没有复制或替换设备系统/厂商库，未生成新镜像。
