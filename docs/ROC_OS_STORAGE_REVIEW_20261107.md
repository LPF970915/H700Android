# ROC OS 本地空间整理（2026-11-07）

最新状态（2026-11-08 23:50）：第二阶段批准的 38 个 Windows 文件与 41 个 WSL 目录均已删除，宿主空间已实际回收并完成保留材料核验。D 盘当前可用 **397.14 GiB**。下文 11 月 7 日的保留清单与早先压缩受阻记录是历史快照，以文末第二阶段完成记录为准。

用户授权先盘点、保留必要材料，再清理冗余。本轮不改变 RC4 镜像、编译源码、安全配置或设备。此前“全部产物均保留”的历史约束在本次明确授权范围内调整为保留必要基线和证据、删除指定可再生产物。

## 已保留

- 最新 RC4 整卡 gzip、SHA、源码标签和公开/私有验收记录；RC4 的 Linux 封装工作目录也完整保留。
- v5i、Source64、RC1/Bootfix/BootDiag/RC2/RC3 等现存完整压缩镜像及清单，用于回退或故障对照。没有把失败版本重新标为可用版本。
- 完整 Native Android 源码、工具链/prebuilts、原始上游压缩包、输入文件、Source64 私有派生产品和当前 user 候选。
- 当前 `/home/lpf/roc-os-user-20261104/out` 增量构建目录，继续修改 user 候选不因本轮清理而主动丢弃缓存。
- 旧 eng 三镜像、round1 保全、最新 eng 审计 v13、关键 boot 前缀/工具、RC3 负对照 policy、当前封装工具依赖。
- 全部现存外部构建/运行/失败日志、JSON 清单、原有源码备份；旧缓存中的 468 份 log/txt/json 另先归档并逐项校验。
- 外置私有签名密钥目录及现存备份、Native-only 签名目录链接、Git 历史、`LOCAL_PRESERVE_H700_BASELINE_20261028`；没有读取或上传私钥正文。
- 用户的 `docs/SPACE_REVIEW_20261028.md` 修改，哈希保持不变；ROCreader 另一项目及其他非目标目录不动。

## 已清理

| 类别 | 目标数 | 删除前文件分配量（GiB） |
| --- | ---: | ---: |
| 旧 Source64 eng / 双 ABI 原型 Soong `.intermediates` | 2 | 50.38 |
| 已被替代的 RC 封装 system/vendor/userdata raw 工作副本 | 32 | 16.18 |
| 已保留压缩版本的旧整卡 raw 副本 | 3 | 4.40 |
| 历史 Source64 审计 v1–v12 的分区 raw 展开副本 | 24 | 13.58 |
| 旧 readiness stage-v1–v4 的分区 raw 副本，保留 v5 | 8 | 17.50 |
| Windows 中断 gzip 残件，完整 v6b gzip 和清单保留 | 1 | 约 1.33 |

WSL 共 69 个目标、278,075 个文件清单项；删除前分配量 109,573,152,768 字节。逻辑文件大小 558,759,930,969 字节含大量稀疏空白，不能当作实际回收量。Windows 另移除 1,426,608,063 字节中断残件。

这些目录中的命令日志、展开对象、policy、JSON 等未随 raw 副本一并删除。旧 eng/原型以后若重编被删除的模块，需要重新生成中间文件。历史审计/封装重放若需要已删除的工作副本，须从保留压缩镜像展开或按相应源码版本重建；不能假定所有旧临时路径仍存在。当前 RC4/user 主线工作目录和直接依赖保留。

## 校验与本地凭据

清理前确认没有活动 builder，并持有全局构建 flock；删除目标逐项检查解析后的绝对路径、用途、文件大小/时间/inode，拒绝越出指定目录和跟随目标符号链接。删除后 1,690 项受保护文件 SHA 一致，包含锁定源码、三镜像、现存 RC 压缩镜像及关键依赖；缓存日志压缩包逐项解包内容校验通过。未连接或操作掌机/卡。

本地详细材料在 `out/storage-review-20261107/`：

- `windows-inventory-before.json`、`linux-selected-du-before.txt`：盘点。
- `cleanup-plan.json`、`removal-file-inventory.json.gz`：逐项目标及文件清单。
- `obsolete-cache-logs.tar.gz`：缓存内日志/文本保全档案，已校验。
- `guard-plan.json`、`guard-execute.json`、`cleanup-result.json`：保护输入及执行结果。
- `windows-cleanup-item.json`：中断文件身份及完整 gzip 核验。
- `linux-df-*.txt`、`host-space-*.json`、`wsl-compact-*`：空间实测和虚拟盘压缩结果。

这些本地清单/日志可能含机器路径、构建环境等信息，不自动上传。当前镜像入口另写入 `out/ROC_OS_CURRENT_BASELINE.txt`，保留原路径以免破坏历史证据引用。

正式版剩余工作见 [发行缺口清单](ROC_OS_RELEASE_GAPS_20261107.md)。本轮空间整理不增加任何正式发行验收通过项。

## 实际回收量

WSL 原生压缩正常退出 0，重新启动后保护输入和关键工具复核通过。

| 宿主机实测 | 清理前 | 清理并压缩、重启后 |
| --- | ---: | ---: |
| D 盘可用空间 | 143.02 GiB | 241.73 GiB |
| Ubuntu VHDX 文件大小 | 383.75 GiB | 286.35 GiB |

D 盘净增加 **98.71 GiB** 可用空间；VHDX 文件缩小 97.4 GiB。它与删除前分配量不同，原因包括稀疏文件、文件系统/虚拟盘元数据和本轮新保全记录；不把 TRIM 报告的空闲范围计为本轮回收量。数据为 2026-11-07T04:24:40.8649737+08:00 的快照。

重启后重新校验 1,690 项保护 SHA、候选签名目录链接、6 个构建凭据列出的直接 staging ELF 及 9 个关键宿主工具的存在/共享库解析。当前 user 缓存仍在。此项没有重新编译，也不是新一轮完整固件功能验收。详细结果见本地 post-compact-verification.json。

## 2026-11-08 第二阶段清理

用户另行批准本地精确清单 `out/storage-review-20261108/wsl-delete-plan.json` 中的 41 个 WSL 历史构建/测试/封装目录。逐项删除复核通过，41/41 不再存在，WSL 报告回收分配空间 194,134,732,800 字节；WSL 内可用空间从 657,981,333,504 增至 852,116,082,688 字节。执行收据为 `out/storage-review-20261108/wsl-delete-execution.json`。

删除计划保留 `/home/lpf/h700-android10` 唯一完整源码树、`/home/lpf/roc-os-user-20261104` 当前 user 增量输出、当前 USB/MTP 诊断 v2、项目仓库、签名密钥目录和 Native-only 签名链接、构建工具及 ROCreader。清理后收据确认源码和输出仍在，签名链接仍指向 `/home/lpf/.roc-os/keys/production-v1`。ver0.0.1 镜像与其 Recovery720 Test3 父镜像 SHA-256 复核未变。

本阶段记录的是 WSL 文件系统内的可用空间增量，不等同于 Windows D 盘已增加同等容量。后续压缩尝试中，`wsl --manage Ubuntu --compact` 因 `ERROR_SHARING_VIOLATION` 失败；VHDX 大小仍为 355,219,800,064 字节，D 盘可用空间实测为 244,408,049,664 字节，尚未拿到这批 WSL 删除所释放的宿主机空间。压缩仍待解决 VHDX 占用句柄后完成。完整删除清单和收据留在本地 `out/storage-review-20261108/`，不上传机器路径清单。

### 2026-11-08 压缩续查

用户批准结束先前阻塞任务并压缩后，重新确认 Ubuntu 与 Docker WSL 发行版均为 `Stopped`，`Get-DiskImage` 显示 Ubuntu VHDX `Attached=False`。提权执行 `wsl --shutdown` 成功，但随后一次 `wsl --manage Ubuntu --compact` 仍以 `HCS/ERROR_SHARING_VIOLATION` 退出；VHDX 仍为 355,219,800,064 字节，D 盘可用空间为 244,408,029,184 字节，未观察到宿主空间回收。Restart Manager 未能提供可靠的持有者列表。

用户随后明确批准重启 `WslService` 与 `vmcompute`。当前执行身份查询到两项服务仍在运行，但停止 `WslService` 被 Windows 拒绝（`OpenService FAILED 5 / Access is denied`），未有服务被停止，发行版仍保持停止。不得把此状态写成已完成压缩；需在具备 Windows 管理员服务控制权限的上下文中重启这两项服务，再执行一次官方 WSL 压缩并核对 VHDX 与 D 盘实测。此期间未运行编译、卡片/设备操作、格式化或额外清理；未触及四个已提交本地提交之外的源码变更。

### 2026-11-08 23:50 宿主空间回收与保留校验完成

等待管理员启动请求返回期间，实测 VHDX 已缩小，D 盘可用空间同步增加。随后启动的管理员脚本因 Windows PowerShell 5 不支持其 `ProcessStartInfo.ArgumentList` 用法，在预检查阶段失败，未执行服务重启或压缩；此前官方压缩尝试也未记录成功退出。因此仅确认已观察到的空间回收结果，不把成功归因于该脚本，也未再重复压缩。

| 实测项目 | 本轮压缩续查前 | 核验并正常关闭 WSL 后 |
| --- | ---: | ---: |
| Ubuntu VHDX 文件大小 | 355,219,800,064 字节（330.82 GiB） | 173,199,589,376 字节（161.30 GiB） |
| D 盘可用空间 | 244,408,029,184 字节（227.62 GiB） | 426,428,207,104 字节（397.14 GiB） |

本轮宿主可用空间净增 **182,020,177,920 字节（169.52 GiB）**，VHDX 缩小 182,020,210,688 字节；这是第二阶段 WSL 清理后的宿主实测，不与此前 Windows 清理或 11 月 7 日回收量重复相加。

Ubuntu 正常启动，保留目录全部存在。按 prepare-v38 / images-result-v21 及其原始输入凭据只读复核：371 项受保护原始输入、1,237 项 Source64 产品文件、42 项 Native 候选文件、当前 user 三镜像、6 个实际 ELF、8 项运行文件，以及 ver0.0.1 与 Recovery720 Test3 两份整卡 gzip 的 SHA 全部匹配；四个当前 user 宿主工具存在且没有缺失共享库。Native-only 签名链接目标正确，当前 MTP v2、源码、增量输出和 ROCreader 均保留，41 个批准删除目录未重新出现。未读取私钥内容，未重新编译或操作设备/卡片；核验结束后 `wsl --shutdown` 返回 0。

凭据为本地 `out/storage-review-20261108/post-compact-verification.json`、`host-space-final.json`；管理员脚本的失败收据另保留，不作为成功证明。本项验证保留输入和现存产物完整，不宣称执行过新的编译或发行验收。后续仍使用完整源码 `/home/lpf/h700-android10` 和 user 增量输出 `/home/lpf/roc-os-user-20261104/out` 开发，不启动完整重编。
