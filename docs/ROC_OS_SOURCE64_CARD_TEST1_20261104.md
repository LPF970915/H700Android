# ROC OS ARM64 Source64 Clean Test1 整卡镜像

用户已授权在第二轮源码修正和离线复审基础上完成整卡封装。本版适用 RG34XXSP / H700 / 2GB，属于新源码系统的工程测试版；整卡文件离线校验完成，上机首启尚未验收。没有操作当前设备或写卡。

## 交付

- 文件：`out/roc-os-source64-card-20261104/ROC_OS_ARM64_Source64_Clean_Test1_20261104.img.gz`
- 压缩大小：596,398,309 字节；解压大小：32,434,554,368 字节。
- gzip SHA-256：`d9e3bff75cf1fa5f9f71ffdbd14073c5cec81cb6bff6191294cf720724188a4b`
- 解压 IMG SHA-256：`e03c5d9a501185f97aeda4f76ea6498499f631a66ca8ffaf311f7e44ff4e6530`
- SHA 文件在同一目录；脱敏证明见 [镜像锁](baselines/roc-os-source64-card-test1-20261104/image-lock.json)。镜像和原始日志留在本地，不上传 Git。

这是包含硬件启动前段、boot、system、vendor、全新 userdata 及备份 GPT 的完整整卡镜像，不再是单独的 sparse 分区。先解压为 `.img`，使用至少 64GB 的 TF 卡整卡烧录。目标卡内容会被替换；原工作卡和其他回退材料继续保留。首次测试先仅将测试卡放入 TF1，TF2 留空；保持供电，扩容过程中可能自行重启，暂勿断电。TF2 随后单独验收。

## 内容与校验

保留父硬件前段中的 Boot0、内核、DTB、启动地址及其他硬件数据。boot 的 identity repack 与父文件字节一致；新 boot 只换入已审计的统一存储 init 和三份静态 ARM64 增长工具，CPIO 其他条目和元数据保持，旧 ROMS/FAT 增长工具不带入。

system/vendor 使用本轮重编并通过 118 项离线检查的源码产物。默认中文、AT4K、樱花壁纸和系统硬件/导航帮助组件保留；不含此前首批第三方应用、ROM、BIOS、账号或存档。新建的 userdata 只有文件系统初始内容，根目录 UID/GID 为 1000:1000、模式 0771，SELinux 标签为 `system_data_root_file`。主机及实际 Android ARM64 fsck 均通过。

TF1 前六个必要分区边界保持，p7 为 userdata，p8 为空。系统卡剩余空间首次启动时扩展给内部存储，TF2 独立作为可移除存储；可用容量仍需扣除文件系统开销及系统数据。增长逻辑验证新布局/UUID、拒绝错误卡和边界，先提交备份 GPT，再提交主表，必要时重启后继续文件系统增长。

整卡所有连续区间逐段回读；完整 gzip 解压后的全卡 SHA 与原 IMG 一致。另从已锁定的编译 sparse 文件独立计算展开哈希，与整卡中的 system/vendor 区间闭合比对。封装持续使用单核、CPU0–1、nice19、6GiB RAM/512MiB swap 和 idle IO，未放宽资源限制；封装耗时约七分钟，峰值内存 5GiB、swap 0。

复现入口：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700Source64Card -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700Source64CardAudit -Execute
```

已存在的交付文件不会被覆盖。源码与旧镜像、每次派生/失败证据、当前未提交的 SPACE_REVIEW 修改均保留。

## 后续验收

需要在备用卡验证启动、首次扩容实际容量、TF2、中文/默认桌面/A 解锁、Menu 下拉/亮度/鼠标、Hall、电源和重启保留。离线文件检查与 QEMU 工具执行不等于 H700 实机启动、断电恢复或深度休眠验收。

正式发布仍需完整源码清单/复现、功耗温控与长期稳定性，以及蓝牙支持范围、SELinux/ADB/root/签名和更新恢复策略。当前为 eng 测试镜像，不能称为已完成正式发布验收。
