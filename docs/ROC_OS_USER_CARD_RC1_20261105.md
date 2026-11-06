# ROC OS ARM64 User RC1 整卡候选镜像（2026-11-05）

完整整卡已封装并独立复核，适用 RG34XXSP / H700 / 2GB。仍待新user镜像真机验收；本轮没有接触、刷写或切换当前设备安全模式。

**2026-11-06 真机状态修正：用户烧录 RC1 后未进入 Android。离线封装校验仍有效，启动验收失败，RC1 暂停作为可用版本推荐。** 用户说明用 Rufus 4.7 直接选取约586MB的 `.img.gz`，TF1单卡；此前 Source64 Clean Test1 能启动。Rufus v4.7 源码支持 gzip 磁盘镜像，不能仅因未手动解压归因于烧录方法。尚未回读本次实体卡，不能把原始文件校验当作写卡回读。

## RC1 与成功 Test1 的启动差异复审（2026-11-06）

只读检查原交付对应的 boot、system.raw、vendor.raw 和项目历史启动记录；没有修改源码、镜像、设备或安全模式，没有启动构建、重新封装或刷写。详细脱敏凭据见[启动审计](baselines/roc-os-user-rc1-boot-audit-20261106/acceptance.json)，本地原始结果在 `out/roc-os-user-rc1-firstboot-20261105/boot-delta-v1.json` 和 `vendor-boot-delta-v1.json`。

已成功链路是 BootROM → Boot0/U-Boot → p4 内核与 Linux shell ramdisk `/init` → 按 sdc0 找 TF1、增长 p7、挂载 system/vendor/data → 绑定 Linux devtmpfs/proc/sys、准备 APEX → `switch_root /android-root /init selinux_setup` → Android init 加载策略、执行 second_stage → ueventd/APEX/zygote/system_server → AT4K。它不是把编出的 Android ramdisk.img 直接放入 boot。历史[双 ABI 切根修正](RG34XXSP_DUALABI_HANDOFF_P1B_20261031.md)和[Source64 入口审计](ROC_OS_SOURCE64_AUDIT_20261103.md)是本次对照依据。

| 检查对象 | 原交付实物比较 | 含义 |
| --- | --- | --- |
| boot 分区之外的整个前段 | 逐字节相同 | 没有新换 Boot0、U-Boot、资源/env 或分区入口 |
| 内核、DTB、加载地址和页大小 | 相同 | 无新的内核/DTB差异 |
| ramdisk CPIO 集合和条目 | 集合相同，仅 `init` 改变 | 增长脚本、静态工具、BusyBox和库保持 |
| `/init` | 两版均链接 `/system/bin/init` | 根入口未断链 |
| `/system/bin/init` | 两版均普通0755 ELF、init_exec标签 | 没有重现旧版嵌套绝对链接使切根前 `-x` 失败的问题 |
| bootstrap linker64、bootstrap libc | 均存在且标签正确，init解释器路径相同 | 早期加载入口齐全；APEX linker链接保留 |
| vendor fstab | 506字节、SHA完全相同 | 挂载设备别名没有新增差异 |
| h700_stick_axes.ko | 20160字节、SHA完全相同 | 模块本体未换；加载时点由 Android su 服务移到切根前 |
| SELinux | eng/permissive → user/enforcing | 是早期行为的关键变化，不能用旧eng通过替代验收 |

ramdisk `/init` 的实际增量只有失败匿名shell改为等待、切根前设置输入DAC权限，以及固定内核/模块身份后加载摇杆模块；boot header 的 cmdline 从 `enforcing=0 androidboot.selinux=permissive` 改成 `enforcing=1 androidboot.selinux=enforcing`。U-Boot源码会将header cmdline追加到环境bootargs，但本次实际 `/proc/cmdline` 尚未读到；user init自身也强制选择enforcing。

发现两项有直接源码和实际策略支持的交接缺陷，尚不能称为本次唯一根因：

1. 继续继承 Linux devtmpfs，并预建 `/dev/.coldboot_done` 跳过 Android coldboot。Android `SecondStageMain` 在任何RC执行前调用 `SetStdioToDevNull` 打开 `/dev/null`，此后才执行内置 `SelinuxRestoreContext`，再加载并执行 `early-init`。因此新增 `restorecon_recursive /dev` 无法修复首次打开 `/dev/null` 之前的问题。继承节点的本次实际标签仍需日志确认；历史成功eng日志确有 Binder 节点通用 `device` 标签、访问被拒但由permissive放行的证据。
2. 新动作安装在 `/vendor/etc/init/roc-user-input.rc`，其restorecon内建命令受vendor subcontext调度。直接从RC1 vendor.raw提取的策略与编译策略SHA一致；查询没有找到 `vendor_init device:chr_file relabelfrom` 和 `vendor_init binder_device:chr_file relabelto` 的allow，init域对应权限同样未找到。仅把动作提前到early-init，或只移到system RC，均不足以证明能修正这些继承字符节点。应修正handoff的节点创建/标签时序，不能靠扩大任意设备访问或关闭enforcing掩盖。

策略探针用实际 `ueventd binder_device:chr_file create` allow作为正对照、应用加载策略为负对照；保留较早将init/setenforce误命名为positive_control的原始记录，本次凭据明确纠正，未将该零返回当正对照。

最初USB `1f3a:1010`、USB Developer、FF/42/03与项目Allwinner U-Boot fastboot定义一致；不能仅凭躺倒绿色机器人判定Android Recovery。后续按键/长按开机后出现的 `1f3a:efe8` 是另一时点的FEL状态，不能拼接成原始故障发生顺序。原先按Recovery解释屏幕并给出组合键的判断不成立。实际user init默认 `REBOOT_BOOTLOADER_ON_PANIC=0`，故也不能仅凭fastboot现象认定init fatal自动转入bootloader。

下一步需要只读取本次卡的 `/data/rgsp-persist/RGSP_SINGLE_CARD_BOOT.log`、可用的pstore/串口记录，确认是否已到 `Android root ready; switching root`，以及首个内核/SELinux错误；再做候选目录内的针对性修复和新版本验证。联网、壁纸、桌面换签等在更晚阶段，现有证据优先指向更早的交接适配。RC1原件、旧Test1、所有失败记录与SPACE_REVIEW继续保留，未以退回permissive生成替代镜像。

## 失败卡只读取证与 Bootfix1（2026-11-06）

用户将本次卡接读卡器后，通过容量、USB身份、GPT磁盘GUID、七分区起点与p7 GUID守卫匹配唯一非系统卡。只以Windows `FileAccess.Read`打开底层盘，未卸载/格式化/修复/刷写卡。读取前段、userdata前512MiB，再按真实ext4 inode/extent追加三段64KiB；没有journal回放。最初常规debugfs因采样未包含全部bitmap拒绝打开，保留失败；只读 `-c` 跳过bitmap读取后发现日志目录inode在后段，补齐真实数据后才提取文件，没有把未采到的块当成空目录。

实际卡完整64MiB boot与RC1逐字节相同；完整8GiB system和2GiB vendor流式SHA与交付的展开分区SHA全部一致。因此没有证据支持压缩格式不兼容、这三个分区写错或截断。初次哈希脚本遇到PowerShell Math.Min的Int32重载错误，未开始分区哈希即停止；v4显式Int64修正后全量读取通过，旧脚本及失败结果保留。

p7分区已扩为52,904,851,968字节，ext4文件系统为52,904,849,408字节，根目录读取到lost+found及rgsp-persist。日志文件220字节，两次均记录：

```text
[rgsp-single-card] TF1 internal userdata; TF2 removable
[rgsp-single-card] Android root ready; switching root
```

这将实际故障范围缩小到shell切根前标记之后；此前新加的模块哈希/ABI检查和insmod、system/vendor/data挂载均已越过。它不包含Android init的首个错误，不能单凭这一行证明exec或SELinux加载已经完成。文件系统带needs_recovery标记，未在证据卡上执行修复。

前段差异仅在主GPT及两份Boot0的参数/校验和区域，两份Boot0副本一致且完整加法校验通过；其余前段块与原镜像一致。DRAM参数变动不自动判成损坏，也未写回原值。脱敏记录见[实体卡回读](baselines/roc-os-user-rc1-boot-audit-20261106/card-readback.json)。

Bootfix1采用保留BSP自身 `system/core/init/first_stage_init.cpp` 的设备准备语义：Android根挂独立tmpfs `/dev`，仅预建kmsg/random/urandom/ptmx/null及三处实际MMC块别名；保留旧Linux侧devtmpfs供切根前模块/扩容使用。移除伪造 `.coldboot_done`，Binder/input/display等由真实ueventd coldboot按保留的vendor规则及file_contexts创建。user/enforcing、内核、DTB、模块、增长逻辑、正式签名system/vendor和干净userdata均沿用RC1，不新增任意设备访问allow，也不改旧BSP。

隔离挂载命名空间已验证五组行为（正确节点与别名、拒绝已有挂载、拒绝两类错误设备ID、真实ARM64 BusyBox mknod）及十一项实际策略访问/重标记查询；正对照为ueventd创建Binder，旧通用device访问为负对照。此预检不等于H700真机enforcing启动通过。独立Bootfix1封装作业使用原资源限额和全局锁，进行完整gzip重建及解压后除boot外所有字节相等的独立比较；不重启已完成的user编译，也不写读卡器中的卡。

Bootfix1封装与全量比较已经完成：`roc-user-bootfix1-20261106-010931` 退出0，耗时8分04.389秒、CPU7分39.481秒，峰值511.2MiB、swap0。没有重新编译system/vendor，它们与userdata及其余引导前段的每个字节均沿用原RC1。boot仅更新shell init并增加设备准备脚本，内核、DTB、地址、enforcing cmdline和其余CPIO保持。Windows再次独立计算gzip SHA一致。

- 本地新文件：`out/roc-os-user-card-bootfix1-20261106/ROC_OS_ARM64_User_RC1_Bootfix1_20261106.img.gz`，585,708,720字节。
- gzip SHA256：`3f697d7d93357156585564c03053bfaa5f1e2c5d1f9690f8104576d882abbb23`。
- raw：32,434,554,368字节，SHA256 `f335a2db7c12d8e8cd3438b554c5ec1c3c3ff393bfcf023a1e7f6e1ed15c6f61`。
- 新boot SHA256：`b52268737297007e6142d4ee92856511d23b3ff039366cc3af38e90f84c5740f`。
- 输入、隔离预检、资源及完整比较凭据：[Bootfix1镜像锁](baselines/roc-os-user-rc1-bootfix1-20261106/image-lock.json)。

读卡采集进程及封装进程均已结束，没有活动builder，原heartbeat仍暂停。用户已收到用Rufus4.7烧录这个新文件、仅TF1正常冷启动并回复画面结果的请求；新boot真机启动/enforcing仍待验收。未自动写卡、切换安全模式、上传镜像或提前替换已验收Git基线。源码、全部旧镜像、失败采样及用户SPACE_REVIEW修改保留。

## Bootfix1 真机未进入界面及诊断准备（2026-11-06）

用户反馈Bootfix1仍停厂商Logo，本次没有躺倒机器人。按用户配合再次只读采样同一张卡，实际boot与Bootfix1原件完全一致（SHA b5226873…）。日志包含新标记 `fresh tmpfs dev prepared` 并到达切根前标记；userdata已经出现Android创建的app、system、system_de、dalvik-cache、tombstones、vendor、apex等目录，明显越过原RC1仅lost+found/rgsp-persist的阶段。因此handoff修正有实际阶段进展，但界面启动仍失败，不能把它标为修复完成。

已采到的tombstones、anr、dropbox及cache/recovery目录中没有可用错误文件；misc的部分inode未能从未回放journal的局部采样中解析，不能据此断言没有崩溃或文件系统损坏。没有在卡上回放journal、运行fsck修复或修改分区。具体Android阻塞点仍待实时日志。脱敏凭据：[Bootfix1真机失败取证](baselines/roc-os-user-rc1-bootfix1-20261106/runtime-failure-readback.json)。

为避免继续猜测性试刷，BootDiag1诊断变体仅增加一个system侧init RC，把已有H700 ConfigFS初始化提前到post-fs-data，在zygote-start或后续界面等待之前开放经过认证的USB ADB；新干净userdata只预置本机既有ADB公钥，不含私钥，去掉公钥注释。保持原user adbd（ALLOW_ADBD_ROOT=0）、ro.secure=1、ro.adb.secure=1、ro.debuggable=0、enforcing及网络ADB关闭。诊断变体不作为发行候选，也不提升Git验收基线；定位后应撤去临时USB默认开启。

本BSP实际将sys.usb.config映射为system_radio_prop，不能凭其他Android版本的usb_prop名称推断权限。初次诊断封装020212因错误类型名的权限预检返回0主动失败，发生在私有分区复制/修改之前，日志和结果保留；路径预检另发现默认属性文件实际为/default.prop而非/prop.default，已纠正。没有放宽策略来绕过预检。修正版单独通过真实init解析器和五项实际策略查询后，启动独立020457封装作业，输出v2，与失败尝试隔离；不重复启动任何完成的user编译。所有资源上限与全局锁保持，实体卡仍只读。

用户补充Bootfix1在Logo等待超过10分钟，按启动阻塞继续取证，不以短暂首启等待解释。BootDiag1的020457作业已退出0：10分12.288秒、CPU9分19.325秒、峰值5,370,806,272字节（包含文件缓存）、swap0。完整解压并逐块对照原Bootfix1及两份私有替换分区通过；boot、vendor及其他整卡范围保持Bootfix1，system只增加诊断RC，userdata仅预置公钥目录/文件。主机与实际ARM64 fsck均通过，公钥文件1000:2000、0640、adb_keys_file标签回读通过。原init/adbd/bootstrap linker、build.prop、default.prop、plat CIL与原USB RC共七文件SHA前后相同；ro.secure=1、ro.adb.secure=1、ro.debuggable=0及user属性复核通过。未开启网络ADB或改写现机安全。

本地文件：`out/roc-os-user-bootdiag1-20261106-v2/ROC_OS_ARM64_User_BootDiag1_20261106.img.gz`，585,710,201字节；gzip SHA256 `0e2ee363759b220b41961f4caab5e0bfeef7461bb6a8e3a15764ada2055f8f86`，raw32,434,554,368字节/SHA256 `cfd33927ef5b631f659e64a4381a5e880534262329334d1d7feeeeb8fafafbd9`，Windows再次计算gzip SHA一致。脱敏凭据：[BootDiag1镜像锁](baselines/roc-os-user-bootdiag1-20261106/image-lock.json)。这是取得实时日志的私有诊断镜像，不是新发行验收通过。

用户已收到烧录该新文件、仅TF1、开机时立即接电脑USB并保持连接（即使停Logo）的请求，待回复“已开机并接USB”后检查认证ADB与实时错误。所有读卡进程和封装作业结束，没有活动builder；旧heartbeat仍暂停。未自动写卡或上传镜像，未将诊断默认USB和公钥预置并入正式产品/已验收Git基线。

## 文件与烧录

- 文件：`out/roc-os-user-card-20261105/ROC_OS_ARM64_User_RC1_20261105.img.gz`，585,700,498字节。
- gzip SHA-256：`c549d011a1a332e92a1b317601f6128e2b849813ec40bdac988eaa05913e4ee5`。
- 解压IMG：32,434,554,368字节，SHA-256：`44dfc8e35744f92260c64005e2fc4ca0410c6205bcbd8d92f62bea13fc99c8ed`。
- 使用至少64GB备用卡。先解压为`.img`再整卡烧录，目标卡内容会替换；保留当前工作卡。首次仅放TF1，TF2留空，保持供电等待扩容及可能的自动重启。

包括硬件引导前段、boot、system、vendor、全新userdata和主备GPT。Boot0、内核、DTB、启动地址保持；新boot沿用统一存储增长逻辑，准备精确身份匹配的摇杆，移除失败匿名shell并请求SELinux enforcing。TF1余量首启扩展给内部存储，TF2独立作为外置卡。不含旧账号、网络密码、存档、ROM或旧userdata。本版换用ROC签名身份，应按完整镜像干净首启，不把旧eng userdata混入新系统。

## 修复与验证

四组su启动功能在候选中实现迁移：摇杆/节点权限在硬件启动阶段准备，Android早期恢复设备标签；网络默认值和壁纸原图由独立UID的平台签名应用处理。壁纸使用MediaStore待提交记录及SHA回读，不替换已有文件；壁纸失败不触发下次开机重置系统默认配置。键盘校验绑定实际换签APK。Hall仅对历史AVC中的单一节点增加只读标签规则，没有扩大为任意sysfs访问。

11项发行工具回归通过。实际镜像116个APK全部通过Android10签名校验，证书均来自固定ROC production-v1五组身份；桌面、导航、SystemUI、设置、Hall、旋转和初始化应用采用ROC平台身份。签名不完整的CTS测试占位包及其配对模块仅从候选排除，原件与中间镜像、所有失败记录均归档保留。

36个启动根、548个ELF、631个命名空间状态、41个早期对象无依赖缺项；10个实际ARM64/ARM32 ELF核对通过。实际user属性secure=1、adb.secure=1、debuggable=0、USB默认none、TCP ADB关闭，编译策略无permissive域。旧产品MAC文件不在镜像中；合法空产品策略摘要与vendor配对一致，不含人工空CIL/映射。

主机和Android ARM64 fsck通过，userdata根1000:1000、0771、system_data_root_file标签正确。整卡连续区段回读、完整gzip解压SHA，以及独立解析编译sparse得到的system/vendor展开SHA均一致。原ramdisk的BusyBox及自带库完成QEMU预执行和哈希工具验证。所有重任务保持单核、CPU0–1、nice19、RAM6GiB、swap512MiB、idle IO、单次3小时上限。

## 验收边界

这是完整可刷的**测试候选版**，并非正式发行验收通过。新user镜像尚未真机启动；历史eng通过不能替代本镜像的首启、扩容、导航/Hall/亮度/Wi-Fi/TF2、充电/温控/深睡、认证ADB和恢复验收。保持bringup电源策略，不宣称续航/深睡通过。

源码直接构建的标签仍是`dev-keys`；这并非使用公开AOSP测试私钥，116个APK实际证书已核对ROC专用身份。正式signed-target-files元数据、运行时安全、双构建对照、许可和同镜像最终验收仍开放。私钥及口令没有写入源码、Git或镜像，镜像不上传Git。

详细输入、分区和整卡SHA见[镜像锁](baselines/roc-os-user-card-rc1-20261105/image-lock.json)。原始审计、失败目录与SPACE_REVIEW用户修改保留。

## 工具

编译使用`tools/build_h700_low_pressure.ps1 -Targets H700UserBuild -Execute`；封装为`tools/release/package_candidate.ps1 -Execute`，独立复查为`tools/release/package_candidate.ps1 -VerifyOnly -Execute`。工具只操作固定普通文件并持有全局锁，已有交付不会覆盖。不要自动重启已完成作业；新版本需先审查输入与版本名。
