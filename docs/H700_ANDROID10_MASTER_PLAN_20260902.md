# H700 Android 10 主线总控文档

日期：2026-09-02  
状态：生效，取代此前以 R36S Android 11 为运行基线的路线

## 2026-09-11 交接更新：方案 A 单卡原型

22:31 新只读取证已完成：实卡前 8MiB 除 GPT 外与原 TF1 捕获一致，
Boot0 存在，boot 分区完整读回亦一致。此前启动区未验证现已补证，
不能继续归因为“没有写 Boot0”。但 Brandy 源码中的启动包候选位置
LBA 24576 / 32800 均落入当前 boot 分区，实卡对应位置无 TOC1 头。
8MiB 捕获不覆盖这些位置，旧 writer/finalizer 已阻断。
尚未写修复：需要原 Linux 工作卡的完整启动包和相关分区取证；当前
COM4 打开失败、原 IP 无响应。7 项离线检查测试通过。

用户最新实测：64GB 安卓卡插入 TF1 主卡槽，按电源键仍黑屏、无可见反应。
方案 A 当前为“实机启动失败”，并非等待验收或启动通过。

纠正此前交接：现存 p1-p4 回读日志结束于 2026-09-11 10:30:47，
8MiB 启动区文件则于 14:49:31 生成；收尾脚本不写入或校验启动区。
不能据上午日志认定下午修订的完整启动方案已写入成功。目标卡历史身份为
USB `Generic MassStorageClass`、序列号 `000000001539`，容量
62239277056 字节；重新接卡时须再次识别，不能固定假设仍为 Disk 3。

先保留失败卡并只读回读启动区域和 GPT，核实实卡后再决定最小修复范围。
本轮仅检查主机文件并更新文档，未写卡、未编译、未操作设备电源或串口。
详见 `H700_ANDROID10_SINGLE_CARD_FAILURE_20260911.md`；
后续四阶段计划见 `H700_ANDROID10_RELEASE_READINESS_20260911.md`。

旧的双卡 handoff 结论继续有效，但仅适用于原 TF1/TF2 测试链。不得把
双卡暖启动通过、单卡离线写卡成功或单次单卡启动成功互相替代。

2026-09-10 17:29 新窗口已接手中断会话并恢复 Android：核实本轮新 p4
完整备份及 19 块恢复成功回执后，重新执行 Audio 受保护启动准备；
system/vendor 全哈希及三分区只读检查通过，TF1 一次性启动写入回读成功。
暖重启后 23 项 Audio 组件检查、声卡 system:audio 0660 权限、无临时覆盖、
TF1 boot/env 恢复、标记消耗、AT4K/IME 保留均通过，临时 SSH 已关闭。
低幅测试音完整播放 96000 帧；QQ 音乐实际播放时 PCM 为 RUNNING、
两次硬件指针前进且输出为 SPEAKER，媒体音量 3/15。约 20 分钟采样中
核心与音频服务 PID 不变，崩溃缓冲为空、当前 p1 FAT 无报错。
设备停留在 QQ 音乐播放，实际扬声器出声等待用户确认；不计为正式 60 分钟
监测、冷启动、纯实体键流程或全部项目验收。固件仍有 DRAM 重训练和
自行更新 boot0，TF1 前 4 MiB 确有变化，不能声称整张 TF1 不变。
本次未重复修复 data、未替换音频 vendor、未额外清理磁盘。
详见 `H700_ANDROID10_AUDIO_STARTUP_RECOVERY_20260910.md`；
新证据 `out/rgsp-audio-resume-20260910/`。

2026-09-10 12:49 用户已授权保留音频修复的前提下修复本次启动并进入
Android 测试，同时清理 D 盘冗余。三份旧 16 GiB 展开镜像经无损归档、
完整解压哈希及删除前源文件复核后已移除，48 GiB 原始数据均有归档保留；
D 盘可用空间回升至约 117 GiB，当前音频及回退镜像未删。
新 p4 备份 `out/tf2-data-backup-audio-20260910/` 已于 12:40:58 开始，
第一遍已读取 10/16 GiB，尚待第二次原机全读及主机验证，不能视为备份完成。
原机 data 保持未挂载，SSH 仅临时开启；尚未执行新 p4 写回或启动准备。
恢复工具已增加显式 Audio 配置及音频 vendor 前后保护校验，当前新数据
候选/补丁尚未产生，禁止使用旧 24 块补丁。详见
`H700_ANDROID10_AUDIO_STARTUP_RECOVERY_20260910.md`。

2026-09-10 12:19 TF2 插回原机检查：当前为 TF1 Linux，双卡 CID、USB
供电、TF1 boot/env/恢复文件和无启动标记检查通过。p1 经正常卸载后的
只读 FAT 检查通过，原挂载参数已恢复；p2/p3 只读 ext4 五阶段检查通过。
但当前 p4 再次存在 `needs_recovery`，现有启动保护函数实机返回 1，
因此未准备 Android 启动或重启。此标志不等于已证实用户文件损坏。
data 保持未挂载，未执行任何修复；不可重放安装 APK 前的旧恢复。
下一步须重新完整备份当前 p4、在副本验证恢复方案，再单独审查写回范围。
此前 p1 授权不包含 p4 写入。音频持久镜像已在卡上，但 QQ 音乐重启后
出声仍未验收。详见 `H700_ANDROID10_AUDIO_RETURN_CHECK_20260910.md`。

2026-09-10 11:58 p1 本轮授权修复完成：音频刷写后的 p1 已重新完整备份，
仅在副本修复并核验全部文件内容；候选仅有 60 字节变化，位于 4 个
元数据扇区。实卡仅写 p1，完整回读 SHA256 为
`721ca44d984263f54f61cdf444d018ff733b4ff97ffd39ec81d791b88d13d887`；
实卡导出的回读副本经独立 `fsck.fat -n -v` 检查退出 0，原有 FAT
状态/簇链/计数诊断不再出现。GPT、完整 system、音频 vendor 写后校验一致，
未写 data/ROMS/TF1，未做全卡哈希，未请求启动或重启。
24 项写入保护与 6 项 FAT 副本检查测试通过。全部进程及磁盘句柄已关闭，
可由用户在 Windows 安全弹出 TF2，关机状态插回原机，TF1 保留。
下一步仍须检查原机当前 p4 日志/干净状态及受保护启动条件，不能重放旧恢复。
持久 QQ 音乐出声尚待下一次启动验收。证据：
`out/tf2-p1-audio-repair-20260910-114004/`，
详见 `H700_ANDROID10_P1_AUDIO_REPAIR_20260910.md`。

2026-09-10 11:32 音频持久镜像已刷入 TF2：新备份及完整 system/vendor
写前哈希通过，仅写 p3，完整回读为
`9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`。
GPT/p1/system 与本次写前备份一致，未向 data/ROMS/TF1 写入；
data/ROMS 未做完整哈希，不能称整卡逐字节验收。
回执和回退材料：`out/tf2-audio-backup-20260910-110849/`；
管理员日志：`out/tf2-audio-deploy-20260910-110849/`，所有进程已结束。
注意 p1 只读副本检查仍有 dirty bit、日志文件簇链长度及空闲簇计数问题，
未执行修复，未出现此前簇几何错误；不能直接放行 Android 启动。
最初 p1 副本与部署备份之间仅 1 字节访问日期变化，符合 Windows 读取恢复
文件后的日期更新；本次 Apply 前后 p1 完全一致，不宣称整个接卡期间不变。
TF2 暂留电脑，下一步需单独审查并授权当前 p1 的恢复范围，不可重放旧恢复。
Audio 启动/运行检查配置已加入，20 项启动保护、22 项写卡保护、
7 项音频打包及运行组件配置测试通过，未执行实机启动检查或重启。
持久启动后 QQ 音乐出声、冷启动、休眠及正式持续运行仍待验收。
详情见 `H700_ANDROID10_AUDIO_FAILURE_20260910.md`。

2026-09-10 10:32 音频持久候选已构建并离线验收：解决声卡节点权限恢复、
RGSP 实际 mixer 路由和产品继承重复来源。以已部署 codec vendor 为基底，
仅合入三个文件，完整内容/权限/标签对比与严格只读 fsck 通过。
候选 `out/rgsp-audio-candidate-20260910/vendor.raw.img`，2 GiB，
SHA256 `9d0c8d4a95b69131a70db6aebdfa1d9b3967afa9dc7dc8e95932872ecb372cc2`。
7 项打包测试、18 项写入保护测试和 Audio 写卡入口 Plan 通过。
尚未刷卡：电脑仅检测到内部硬盘，等待正常关机后将 TF2 接入读卡器，
再新备份、仅写 p3、完整回读；持久启动和 QQ 音乐播放仍待验收。
旧构建产物不能刷写，详见 `H700_ANDROID10_AUDIO_FAILURE_20260910.md`。

2026-09-10 08:58 声音阻塞：用户在 QQ 音乐尝试播放但无声。只读采样确认
媒体音量 11/15、未静音、输出为 speaker；底层音频 HAL 在打开 mixer 失败后，
于 audio_route_update_mixer 空指针崩溃并反复重启。/dev/snd 节点实际为
root:root 0600，与 ueventd 要求的 system:audio 0660 不符，阻止非 root
音频服务访问。尚未修改权限或 mixer，需先暂停并降低音量后进行可回退验证；
donor mixer 与 RGSP 控件匹配也仍待检查。声音验收未通过，详见
`H700_ANDROID10_AUDIO_FAILURE_20260910.md`。

2026-09-10 09:22 音频临时修复成功：将媒体音量降至 3/15，临时修正 card 0
声卡节点权限并绑定仅内存扬声器路由；真实 mixer 控件为 9 项，随后低幅
440 Hz 测试音 PCM 播放头完整跑到 96000 帧，用户确认听到声音。临时绑定、
开关状态已成功回退，未写 vendor；更正：两个 card 0 节点权限仍为临时
system:audio 0660，未执行权限回退。已在 RGSP 源码准备持久候选
ueventd 声卡权限与真实 mixer XML，尚未构建、刷卡或重启验收。

2026-09-10 08:45 应用测试更新：用户已手动安装 QQ 音乐 TV 9.0.0.39
和 X-plore 4.46.00，串口包管理查询确认两者已安装，QQ 音乐当前在前台。
用户实测 Files 中 A 不能确认、Y 可以；另有 Recent 焦点陷阱及文件名裁切。
不能将本轮安装计为完整纯十字键验收：中途使用过 Downloads intent 引导，
且安装由用户手动完成。X-plore 先作为普通应用验证，未内置或授予 root，
未改全局键位；下一步分别验收文件管理器与 QQ 音乐的实体键流程。
详见 `H700_ANDROID10_TV_APK_INPUT_20260910.md`。四阶段计划尚未全部完成。

2026-09-10 07:53 当前交接点：按授权完成 codec 受保护启动准备及一次暖重启，
恢复后的 p1/data 已通过本轮 Android 挂载与核心回归；20 项固定组件哈希通过，
持久化 codec 无临时覆盖，百度 HTTPS 实际页面已截图核验，Wi-Fi 自动重连、
两次百度 ping 3/3、Settings 打开及返回 AT4K 通过。HOME/IME 选择保留，
TF1 boot 自动恢复且 env 原值、一次性标记已消耗，核心 PID 在本轮采样中未变，
最终开机约 8.2 分钟，崩溃缓冲为空、p1 当前内核日志无 FAT 报错。
注意原固件本次又自行更新 boot0，TF1 前 4 MiB 哈希确有变化，不能宣称整卡未变。
当前设备停在 Android AT4K 桌面；本轮未做第二次重启或关机。
阶段 1 的 p1/data 与持久 codec 关键阻塞已解除，但不等于全项目验收完成：
TF2 单卡启动、断电冷启动、正式 60 分钟监测、设置保存重启、声音/休眠、
实体按键与 APK 流程仍待验收。详细证据见
`H700_ANDROID10_FIX72_POST_RECOVERY_BOOT_20260910.md`。

2026-09-10 02:37 当前交接点：已按单独授权完成 TF2 p4 的 24 块差异恢复。
写前完整 16 GiB 哈希与原始备份一致；写后完整回读与离线候选
`b52bb83ef4c42a7cf6705526bd0f923a921f938e7a579621d9b23381832345a9`
一致。原机 e2fsck 1.46.5 的只读五阶段检查无诊断问题，needs_recovery
已清除，空闲块/节点计数正确。原始备份、两份副本和回退字节保留，
56 项恢复/启动保护测试及 7 项回执检查测试通过，实机与主机日志哈希一致。
本轮仅向 p4 写入恢复数据；原机仍为 TF1 Linux，data 未挂载，SSH 关闭，
TF1 boot/env 原值、无启动标记，未准备启动或重启。p1 当前内核日志无 FAT 报错。
数据分区阻塞已解除，但 Fix72 实机运行回归仍未完成。下一步先执行最新
codec 启动预检；准备 TF1 一次性启动及重启须另行授权，不可使用旧助手绕过门槛。
证据：`out/tf2-data-backup-20260909-2359/deployment-20260910-0211/`，
详见 `H700_ANDROID10_DATA_COPY_RECOVERY_20260910.md`。

2026-09-10 01:31 当前交接点：已完整备份当前 16 GiB data，设备两次读取与
主机解压哈希一致。仅回放日志的副本仍有两个空闲计数错误；第二副本只修正
这两个计数后，通过无诊断问题的只读全检与文件清单核验。相对原始备份共
24 个 4 KiB 块变化；候选尚未写回实卡。40 项测试通过，启动助手增加
“退出码为 0 仍拒绝计数错误/修复提示”的门槛。原机保持 Linux，data 未挂载，
SSH 已恢复关闭，TF1 boot/env 原值且无启动标记，p1 当前日志未见 FAT 错误。
下一步须单独确认实卡 p4 恢复范围；不能据副本结果宣称 Fix72 实机回归通过。
证据及候选哈希见 `H700_ANDROID10_DATA_COPY_RECOVERY_20260910.md`。

2026-09-09 23:28 当前交接点：TF2 已插回原机并进入 TF1 Linux。
p1 正常卸载后的只读 FAT 检查通过，原挂载参数已恢复；但 data 存在
needs_recovery，旧启动预检虽返回 0，其日志仍报告跳过恢复及计数差异。
新版启动助手已增加显式恢复标志检查，实机正确拒绝继续；未准备启动、重启、
挂载或修复 data。先备份当前 data 并在副本验证方案，不能绕过门槛。
详见 `H700_ANDROID10_P1_RETURN_CHECK_20260909.md`。阶段 1 尚未验收完成。

2026-09-08 13:53 当前物理交接点：仅写 vendor 的专用备份/部署/回退工具已准备，
启动助手增加显式 codec 固定哈希配置，默认仍严格匹配原版；运行检查增加三个 XML。
64 项 Python 与 18 项 PowerShell 主机测试、只读 Plan 镜像哈希校验通过。
串口复核 TF1 Linux boot/env/恢复文件及无待执行启动标记通过，尚未写卡或重启。
现需用户正常关机后将原机 TF2 插入电脑，先新备份并核验，再单独执行 p3 写入。
TF1 不换卡，另一台原装机器的独立启动测试仍未进入。
详见 `H700_ANDROID10_FIX72_CODEC_DEPLOYMENT_20260908.md`。

2026-09-08 23:20 当前进度：管理员 PowerShell 已完成 TF2 vendor-only Apply，
第 3 分区回读哈希通过，GPT/ANBOOT/system 保护范围未变，data/ROMS/TF1 未写入，
未请求重启。现在需要安全弹出 TF2 并插回原机，随后执行 codec 启动校验与
WebView/百度 HTTPS 回归；冷启动、独立启动、声音/电源和按键流程仍待后续。

2026-09-08 13:16 当前检查点：Fix72 已完成暖启动及 17 项核心组件回归，
但应用测试发现 WebView 缺少媒体配置导致崩溃。临时内存修复已显示百度 HTTPS，
随后撤销覆盖；低压 vendor 构建通过，已从原 Fix72 制作仅新增三个 XML 的
独立候选 `out/rgsp-fix72-codec-candidate-20260908/`，保留全部原有文件、
权限与扩展属性，通过只读 fsck、独立差异核验和 62 项主机测试，尚未刷入设备。
原镜像与回退材料保留，旧启动/部署工具的哈希保护未放宽。
13:15 只读采样时本次开机约 63 分钟，核心 PID 不变、AT4K 前台、百度 ping 3/3；
这不是正式连续监测通过。用户不在机器旁，本轮未重启、休眠或改写卡上系统。
Y 解锁已有映射与框架代码依据，尚未补做 Fix72 实体按键验收。
独立启动、冷启动、声音/电源和纯按键应用流程仍未完成，AT4K 布局研发继续暂停。
详见 `H700_ANDROID10_FIX72_HARDWARE_REGRESSION_20260908.md`。

2026-09-07 23:33 优先级更新：用户确认先固定可回退候选并上机回归，
再推进独立启动、冷启动/持续运行、硬件与应用流程，最后精修 AT4K。
本轮 Fix72 全部产物大小/哈希复核、两份镜像只读 fsck 和 21 项离线测试通过。
COM4 实机开机时长约 12 小时，TF1 boot/env 恢复哈希一致，但不计为正式老化通过。
电脑未接入 TF2 读卡器，未刷写或重启；当前运行版本仍不是完整 Fix72。
需新备份当前系统及 data，并将旧引导准备脚本的重复分区修复与启动选择分开审查。
详见 `H700_ANDROID10_FIX72_DEPLOYMENT_GATE_20260907.md`。

2026-09-07 16:40 离线进展：Fix72 已完成低压增量构建与新候选合包，
包含 Fix71 紧凑 LeanbackIME、显式选择的 RGSP 首启助手、DocumentsUI、
PackageInstaller，以及固定哈希的 Fix67 图形/Fix70 Wi-Fi 修复。
候选目录为 `out/rgsp-fix72-wifi-profile/`，未部署、未修改设备。
构建仅允许 CPU 0-1、总配额一核、`-j1`、6 GiB 内存和 512 MiB swap。
本次并非两次干净重建，也未完成 TF2 独立冷启动或联网验收。详情见
`H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`。

补充：2026-09-07 20:11 已在实机连接 `Xiaomi_0421` 并通过串口访问
`www.baidu.com`；DNS、ICMP 和 HTTP `200 OK` 均通过。Android 的
`PARTIAL_CONNECTIVITY` 仅反映 Google `generate_204` HTTPS 探测受当前
网络重置/超时，实际外网访问已成立。

以下按时间倒序保留实机和历史状态。

2026-09-07 12:33 最新交互进展：Fix71 已编译并试装 AOSP TV 输入法，
RGSP 专用 A 键适配和紧凑尺寸已加入源码；注入按键完成选字、B 收起、
A 重开及 X 删空测试，等待物理键复核。AT4K 通过自身“隐藏桌面卡片”
选项移除大块空白，应用与 Settings 图标已完整显示；未修改 720x480/213dpi。
仍未提交网络密码，联网验收未完成。Fix70 已推送为 `f7445b8`，
其离线镜像不包含这次数据分区侧的键盘试装。详见
`H700_ANDROID10_FIX71_INPUT_DISPLAY_20260907.md`。

2026-09-07 20:11 网络实测更新：用户已输入密码并连接 `Xiaomi_0421`。
设备 `wlan0` 获取 `192.168.31.164/24`，网关和 DNS 均为 `192.168.31.1`；
通过串口访问 `www.baidu.com` 成功，DNS 解析、3 次 ICMP、HTTP `200 OK`
均通过。Android 状态仍为 `PARTIAL_CONNECTIVITY`，仅因为当前网络对
Google `generate_204` HTTPS 探测重置、Google 备用探测超时；实际外网
访问已成立，不能把该标记解释为 Wi-Fi 或 DHCP 失败。

2026-09-07 11:54 最新实机进展：Fix69 已通过受保护 Fix67 handoff 进入
Android，AT4K 已实际设为默认 HOME，Launcher3 保留恢复。Fix70 修复
Wi-Fi 驱动状态属性缺失和重载接口名不匹配；已安装重新编译的 HAL 与 init，
连续两轮开关通过，Settings 显示真实扫描结果。尚未输入网络凭据，
认证、DHCP、DNS、HTTPS 和重连未验收。SurfaceFlinger 仍为 Mali-G31/r20p0，
核心 PID 未变，检查时 crash buffer 为空；这不是完整稳定性验收。
TF1 原 boot/env 哈希已在 Android 内复核恢复，TF2 独立冷启动仍未完成。
详见 `H700_ANDROID10_FIX70_WIFI_HOME_20260907.md`。

以下 10:55 记录为写卡阶段历史状态，不代表当前仍在等待插卡。

2026-09-07 10:55 当前部署进展：Fix69 已将 RGSP Wi-Fi 模块、固件和 HAL
加载路径与 Fix67 启动修复离线合包，并写入 TF2 p2/p3；全量回读哈希通过。
旧 system/vendor、ANBOOT、GPT 已备份，TF1 和 TF2 data/ROM 分区未写入。
下一步是插回 RGSP，通过 COM4 验证受保护启动、`wlan0`、扫描及联网；
不能据此认定已联网或已具备脱离 TF1 的 TF2 独立冷启动能力。详见
`H700_ANDROID10_FIX69_WIFI_DEPLOYMENT_20260907.md`。

用户随后明确调整优先级：Launcher3 的触摸手势入口不适合当前无触摸掌机，
因此优先切换 AT4K 为默认 HOME，并保留 Launcher3 恢复入口；不再以联网
或全部焦点问题解决作为切换前提。Wi-Fi、Settings、返回和输入法继续独立验收。

2026-09-06 23:22 当前进展：Fix67 在构建镜像加部署修复后自动进入 Launcher，
Mali-G31/r20p0 硬件渲染已验证，基础按键已完成，不再从逐键采集开始。
`wifi`、`wifiscanner`、`connectivity`、`netd` 已在实机发布；目前未见
`8821cs` 模块和 `wlan0`，网络瓶颈已移至驱动及其加载链。
当前 P2/B4 首图已完成，稳定性验收尚未结束；P3/B5 改为优先 TV 前端与网络。
60 分钟老化、10 次冷启动以及干净重建可复现性仍未完成。

2026-09-02 历史基线进展：完整 H616 Android+Longan 源码已在 D 盘 WSL2 落盘；原厂
`cupid_perf1-eng` 和新 `h700_rgsp-eng` 均已通过 `lunch` 与 `m nothing`。当前进入
首轮实际镜像编译阶段，详见 `docs/H700_ANDROID10_BASELINE_STATUS_20260902.md`。

## 1. 固化决策

项目正式切换为以下层级：

```text
主线实现：H616 Android 10 完整源码和官方镜像
硬件事实：RGSP 原厂 H700 kernel/DTB/Linux 行为和实机日志
运行佐证：H21S-700-V3.0 H700 Android 10 冷启动日志
诊断档案：R36S LineageOS 18.1 / Android 11 fix1-fix58
备份对照：H618 Android 12 精选源码和 vendor 参考集
```

H618 不进入主线。它面向 Android 12、较新的 HAL/内存/图形体系和更高内存设备，
只能用于接口演进、服务命名和实现差异对照。

## 2. Android 10 产品定义

- Android 10 / API 29；
- H616 `sun50iw9p1` / `cupid` HAL 代际；
- RGSP 自有 H700 Linux 4.9.170 kernel 和 DTB；
- 初期 ARM32 用户空间、64 位 Binder、flattened APEX；
- `ro.config.low_ram=true`、Go 风格裁剪、无 GMS；
- TF1 保留 Linux 和恢复能力，TF2 承载 system/vendor/data；
- 第一目标为稳定 Launcher、按键和 PPSSPP，不先追求 DRM 高清或完整电视功能。

后续可评估双 ABI 产品，但只能在 32 位主线稳定后进行，不能让 64 位应用兼容性再次
破坏 1 GiB 内存基线。

## 3. 可以继承的 Android 11 成果

- TF1 handoff、一次性启动标记和自动 Linux 回退；
- TF2 分区、PARTUUID 和 system/vendor/data 挂载事实；
- boot/env/CID 哈希校验与写后只读复核；
- UART、logdw、logcat、kmsg、tombstone 和 DropBox 采集；
- Binder 节点、ION、Mali、disp、fb0 和 ALSA 设备事实；
- H616 图形 fix51-fix56 和音频 fix58 的 ABI/运行证据；
- RGSP 720x480、AXP2202、按键、Hall、RTL8821CS 等硬件资料。

## 4. 禁止继承的 Android 11 内容

- `r36s`、`rk3326`、`rk30board` 产品和硬件身份；
- Rockchip Gralloc、HWC、GPU、Vulkan、音频和媒体二进制；
- Android 11 `framework.jar`、`services.jar` 的 headless/bypass 修改；
- 为混合 APEX、linkerconfig、VNDK 或 HAL 代际而建立的永久产品补丁；
- 把 diagnostic fix 编号继续当作 Android 10 产品版本。

Android 10 必须从未修改的 framework 启动。出现 framework 崩溃时先修正 device、HAL、
VINTF、权限和资源配置，不能先删除 SystemServer 服务。

## 5. H616 使用边界

直接复用或编译：

- Android 10 framework/build system；
- Mali-G31 r20p0 用户态、Gralloc、HWC2、ION；
- Audio HAL 5.0、audio policy、tinyalsa；
- Allwinner init、ueventd、VINTF、power/health/lights 实现框架；
- low-RAM、Go、flattened APEX 和 dexpreopt 配置。

必须替换：

- Orange Pi bootloader、GPT、DTS、HDMI/TV 产品层；
- AXP806 等开发板 PMIC 配置；
- AC107、摄像头、CEC、DRM 和不属于掌机的服务；
- eMMC/dynamic-partition fstab；
- 板级 LCD、GPIO、无线、电池、音频路由和输入映射。

## 6. 当前文件入口

- 主线 overlay：`android/h700-android10/`
- Android 11 档案：`android/legacy-android11/`
- H616 源码分析：`work/h700-source-analysis/h616/`
- H616 来源与校验：`docs/H616_ANDROID10_PROVENANCE_20260902.md`
- H618 精选集：`work/h700-source-analysis/h618/selected/`
- H700 投影仪日志：`out/logs/uart/projector-h21s700/`
- fix58 音频结论：`docs/fix58-h616-audio-analysis-20260902.md`

## 7. 后续开发阶段

### A10-P0：可重复构建

1. 完整解出 H616 `android.tar.gz` 和 `longan.tar.gz` 到同一个独立构建目录。
2. 固定 Ubuntu/WSL、JDK、Python、repo/build 工具版本。
3. 将 `android/h700-android10/device/roc` 接入源码树。
4. 先构建原始 `cupid_perf1`，确认 H616 源码本身可重现。
5. 再构建 `h700_rgsp-eng`。

当前完成度：已有实际 Android 10 镜像并在设备运行；Fix72 已将键盘、显示配置、
Mali 模块和首启助手回收进构建输入，再用固定哈希部署修复合包。
仍非原始构建产物直接复现全部运行状态，两次干净构建的退出条件尚未满足。

源码准备使用 `tools/prepare_h616_android10_source.ps1`。目标必须位于 WSL2
Linux 文件系统，避免在 NTFS 上构建 AOSP 时丢失大小写、权限或符号链接语义。
本项目的 Ubuntu VHDX 固定在 `D:/Works/H700Android/.wsl/Ubuntu/`，不得把完整
源码或构建输出放回 C 盘默认 WSL 目录。

退出条件：两次干净构建生成一致的关键文件清单，失败与环境问题均记录。

### A10-P1：init 和存储

1. 复用 RGSP kernel、DTB 和已验证 handoff boot header。
2. 使用 Android 10 原生 init、flattened APEX 和 linker 配置。
3. 按真实 PARTUUID 挂载 TF2 system/vendor/data。
4. 保留 Binder 权限和持久日志能力，但不移植 Android 11 framework patch。

退出条件：连续 10 次到达 ADB、zygote、未修改的 system_server。

### A10-P2：第一幅画面

1. 编译 H616 arm32/arm64 Mali-G31 库和 Gralloc/HWC2 组合。
2. 核对 `/dev/ion` heap、private handle、`/dev/disp` ioctl 结构。
3. 固定 RGSP 720x480、32 bpp、stride、旋转和 vsync。
4. 启动 SurfaceFlinger、bootanimation 和最小 Launcher。

退出条件：稳定显示 60 分钟，连续重启无黑屏。

### A10-P3：掌机基本功能

1. 使用现有 RGSP 映射，试装 TV Launcher 和可用的无触摸屏幕键盘；
2. 优先补齐 Settings 网络操作、RTL8821CS 驱动、扫描、认证与联网；
3. 保留 Launcher3 回退后确定默认 HOME，逐项补齐 Settings 真实后端；
4. 按需实现 Select 虚拟鼠标兜底及多机型校准，不抢占游戏手柄语义；
5. H616 Audio HAL 5.0 对接 `audiocodec` card 0/device 0；
6. AXP2202 电量、充电、亮度、关机、Hall、振动和蓝牙；
7. low-RAM、zram、LMKD 和后台进程调优。

退出条件：Launcher、音乐、阅读、RetroArch 和 PPSSPP 可以完成基本操作。

### A10-P4：媒体和产品化

1. 评估 CedarX/OMX 硬件视频解码；
2. 明确 Widevine L3、在线视频清晰度和 DRM 限制；
3. 建立应用兼容列表和 32/64 位策略；
4. 完成双启动、恢复镜像、升级和多机型 overlay。

## 8. 最近执行队列

近期工作已经从迁移整理切换到实际 bring-up。详细命令顺序、空间保护、验收门槛、
实体机依赖和工作量判断统一见：

`docs/H700_ANDROID10_NEXT_DEVELOPMENT_PLAN_20260902.md`

当前关键路径：

1. Fix72 已完成备份、p2/p3 写入及回读；data 回放超出授权的异常记录与原始备份保留、回放入口禁用。重新授权后，暖重启、17/17 组件、AT4K/输入法、TF1 boot/env 回退及百度 HTTP 通过；后续发现 WebView 因媒体配置缺失崩溃，临时内存覆盖后百度 HTTPS 已显示，覆盖已撤销。2026-09-10 持久 codec/audio 方案完成暖启动回归，声音链路已有用户确认；实体按键、冷启动、休眠和整体验收仍开放。详见 `H700_ANDROID10_FIX72_POST_RECOVERY_BOOT_20260910.md`；
2. 固定构建与部署修复输入，补齐干净构建复现；编译只走低压入口；
3. 上机验证方案 A 单卡启动、重启、断电冷启动和第二 TF 槽扩展卡；
4. 完成老化、10 次冷启动、低内存、设置保存与 Wi-Fi 重连/重启持久性；
5. 按实际 RGSP 后端完成音频、电量/充电、亮度、电源/休眠唤醒及蓝牙；
6. 验收实体 A/DPAD/B/X、A 解锁、符号输入及文件浏览、安装、授权、应用和 HOME 流程；
7. 固化镜像布局、写卡/校验/回退工具、SHA256 清单和用户说明；
8. 最后精修 AT4K 小屏布局；此前仅处理阻碍验收的界面问题，替代桌面开发暂停。

TV 前端是用户操作入口，不替代 Settings、SystemUI、framework、HAL 和驱动；
不继承 Homlet/投影仪整机配置，也不把完整电视产品依赖引入掌机。
APK 检查与网络分层门槛见 `H700_ANDROID10_TV_NETWORK_PLAN_20260906.md`。

Android 11 fix58 的最后一次冷启动只做历史取证，不阻塞上述 Android 10 离线开发。

## 9. 验收原则

- 所有运行组件必须能追溯到 H616、RGSP 或明确的自研实现；
- H618 文件不得进入主线产物；
- 产品属性不得出现 `r36s`、`rk3326`、`rk30board`；
- 每次设备写入必须保留 CID、boot/env、e2fsck 和回读校验；
- 第一幅画面之前不扩大到摄像头、DRM、HDMI 和复杂媒体服务。
