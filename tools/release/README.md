# Source64 发行准备与离线恢复

这些工具不访问 ADB，不打开或写入物理磁盘，不修改当前设备的调试、安全、分区或挂载状态。现有 `roc_os_source64-eng` 和已冻结镜像保持。正式发行仍需通过门禁，不能把属性覆盖文件当成 enforcing、正式签名或可恢复升级已经完成。

## 低负载入口

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700ReleasePrep -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700SourceInventory -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700BuildManifest -Execute
```

这些目标均使用全局构建锁，单核、CPU0–1、nice19、RAM6GiB、swap512MiB、idle IO，3小时上限。不会与原构建并行。原始报告、测试失败和清单放在忽略的 `out/source64-release-prep-20261104/run-v*/`，不覆盖旧运行。

测试用的普通文件/稀疏GPT和ext4镜像保留在 WSL `/home/lpf/roc-release-prep-20261104/run-v*/`。稀疏GPT文件的逻辑长度约32GB，实际仅少量块，不在NTFS上创建完整大镜像。日志和路径索引留在out目录。

## 发行配置

`android/h700-android10/device/roc/roc_os_release_candidate/` 仅注册 `roc_os_release_candidate-user`。它要求外部 `ROC_RELEASE_KEYS_DIR` 包含releasekey/platform/shared/media/networkstack的pk8和x509；缺少密钥或选择eng时拒绝解析。早期准备阶段仅在仓库定义；后续已在 Native 独立目录准备并生成构建图，完整user分区仍未编出。见[隔离候选进度](../../docs/ROC_OS_USER_CANDIDATE_20261104.md)。

`H700UserPrepare` 核对最新工程构建/审计和原输入，创建受守卫的Native候选目录；只在本地复制已审计AT4K并创建指向私有密钥目录的符号链接，不复制私钥实体。`H700UserGraph` 在独立输出执行 `m -j1 nothing` 并保存成功或失败结果。`H700UserSigningProbe` 核对Ninja签名计划并离线验证专用平台密钥签署APK，**不安装、不编全系统、不制作镜像**。三者都经过低负载入口，不得与其他构建并发；实际源码增量、链接目标、密钥公开摘要和原工程三镜像另有守卫。

`H700UserBuild` 在同一隔离user输出执行 systemimage/vendorimage/ramdisk完整编译，使用相同资源上限；记录实际退出码、源保持、三分区SHA及六个真实ARM64/ARM32 ELF。当前首次运行是仍有功能/安全遗留项的中间构建，不能据编译成功直接封装、刷卡或发布。活动批次中不得改其Native输入、候选源或构建脚本；3小时超时续编还须核对动态输入锁和失败类型。

`roc_release_properties.mk` 应用在独立 **user 候选**继承 Source64 产品之后，清理属性变量中的旧安全值，设置认证 ADB、非 debuggable、默认 USB 无功能、禁用 TCP ADB，并排除 su/Superuser 包。它目前是隔离的配置输入，未部署到原产品、未编出或验证 user 系统。继承延迟展开、复制来的属性文件和启动脚本仍需以实际产物复审，不能只看 Make 变量。

`release-policy.json` 与 `audit_release.py` 检查实际已审计分区的属性加载顺序、init 控制台/su 域、boot permissive 参数、签名和验收证据。当前工程镜像应被拒绝，这个拒绝是门禁正常工作，不是工具执行失败。

检查未来候选时，将已审计目录、真实 boot cmdline、公开证书注册表和绑定同一分区哈希的验收记录传入：

```sh
python3 tools/release/audit_release.py --snapshot /path/to/audit-work \
  --cmdline-file /path/to/actual-boot-cmdline.txt \
  --signing-registry /private/path/public-signers.json \
  --evidence /private/path/acceptance-evidence.json
```

退出0表示提供的证据满足检查；退出2表示仍有阻断项。证据必须包含 `images`（与审计 `result.json` 完全相同）和 `checks`。这些记录需要来自实际测试，工具不替代设备验收或签名授权。完整 APK 签名覆盖、最终镜像 boot/ramdisk 以及 late factory 属性导入也必须纳入最终验收；基础快照未覆盖的项不能仅凭属性检查判为通过。

`signing-policy.template.json` 只存证书 SHA-256，绝不存私钥。平台共享 UID 相关应用须使用同一正式平台证书；保留原签名的 APK 逐项列入允许表。保留 BSP 的6张公开测试证书不得用于正式平台身份。历史发行准备阶段尚无正式密钥；2026-11-04 用户另行授权创建的身份与备份进度见 [本轮记录](../../docs/ROC_OS_RELEASE_RUN_20261104.md)，不代表已有正式签名镜像。

## 签名密钥一次性创建

`H700ReleaseKeys` 通过同一限额入口执行 `create_keys.py`，仅供明确授权后的首次创建，不能当作每次构建的前置步骤。它在仓库外私有目录生成五组 RSA4096 PKCS8/X509 密钥，拒绝覆盖已有身份；私钥不会写入日志或 Git。证书有效期为生成日起 10950 天。

工具将标准 OpenPGP AES256 加密备份与随机恢复口令分开保存，验证解密回读并拒绝独立篡改样本；不会上传它们。复制备份到另一介质后还须保存恢复口令，并验证可恢复，不能仅有本机副本。`keys.public.json` 只含公开证书/公钥摘要和验证状态。已有目录但缺完成记录时必须先检查中断位置，禁止删除重建或静默轮换签名身份。长期维护须另行管理证书到期及密钥继承策略。

历史工程基线有 `su` 域工厂/品牌服务、root 控制台、permissive boot 等遗留项。2026-11-04 的 Source64 新分区已以独立 UID 的 ROCProvisioning 应用替换前两组服务，并补了工程卡上的 API 路径验证；干净首启、最终正式签名与其余安全项仍待验证，不能将该增量直接视为 user/enforcing 系统。见[本轮记录](../../docs/ROC_OS_RELEASE_RUN_20261104.md)。

## 离线 userdata 备份与恢复

仅处理已关机取得、未挂载使用的 **完整 raw 镜像普通文件**。gzip 必须先独立解压并核对镜像 SHA。拒绝设备文件、符号链接、硬链接，以及不匹配的 compact GPT、系统分区范围、userdata UUID。原卡读取/刷写仍在回来后的实体验收中执行。

```powershell
# 只读检查；下列路径是需要替换的示例。
.\tools\release\recover.ps1 -Action inspect -Image D:\Backups\ROC-card.img
# 新建私有备份目录，只备份userdata；不包含完整引导/系统镜像。
.\tools\release\recover.ps1 -Action backup -Image D:\Backups\ROC-card.img -Bundle D:\Backups\ROC-data
# 默认只计划，不写入目标镜像。
.\tools\release\recover.ps1 -Action restore -Image D:\Backups\ROC-card-copy.img -Bundle D:\Backups\ROC-data
# 写入的是普通文件副本中的userdata范围，随后完整回读并检查保护范围。
.\tools\release\recover.ps1 -Action restore -Image D:\Backups\ROC-card-copy.img -Bundle D:\Backups\ROC-data -Execute
```

PowerShell 入口施加同样的资源限制和全局互斥锁。恢复前必须完整匹配备份数据哈希、GPT几何及引导/system/vendor保护区哈希；范围或系统版本不符即拒绝。它用于同一布局、同一系统的恢复，不是跨容量或跨版本迁移工具。目标userdata超级块已损坏时可以从完整备份恢复，GPT和保护区仍必须正确。

备份包含私人数据，请使用本地私有目录和可靠的访问权限保存；工具在支持POSIX权限的文件系统请求0700/0600，NTFS权限仍取决于父目录ACL。备份不能代替完整、已校验的整卡救援镜像。超级块/UUID检查不等于fsck，实际文件系统健康还需离线 `e2fsck -n`；工作卡不得执行故意断电或损坏测试。

## 源码与外部输入清单

`H700SourceInventory` 流式记录保留 Android BSP 树中每个普通文件的相对路径、长度、模式和 SHA-256，以及符号链接目标。跳过各级 `.git/.repo/__pycache__` 和根 `out`，不跟随符号链接、不把树外内容伪装为已锁定输入。生成后可用 `inventory.py --verify` 检查修改、新增和缺失；验证也应置于相同资源限额内执行。

这是**当前保留树的内容快照**，不是丢失的上游 repo manifest，也不是第二次干净构建的证明。当前源码树快照不能反推历史每个文件的编译时状态。原371项输入与两项ABI5库另行对照已冻结锁；引导前缀、保留内核/DTB、APK和厂商库继续列为外部来源/许可待核项。

清单不是备份，也不授权删除源码、Longan参考内核树、外部输入、旧镜像或失败产物。完整 JSONL 留本地，Git 只保存工具、脱敏摘要和清单本身的 SHA。仅克隆公开 Git 仍不能重建整个 BSP。

`H700BuildManifest` 使用只读 `ninja -t commands` 保存当前三个分区目标的重建命令计划和Ninja图文件SHA，不执行其中任何命令。原始计划可能含本地路径，只留忽略的out；它不是历史编译执行日志，也不能替代编译器发现的全部依赖或上游提交清单。树外两项链接单独记录存在性、字面命令引用和可用文件哈希，不静默跟随任意外部目录。
