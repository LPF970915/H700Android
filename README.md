# ROC OS · H700 Android 10

**为 H700 掌机适配的 Android 10 系统，让没有触摸屏的设备也能用按键操作安卓。**

[English](README.en.md) · [候选版本与已知问题](docs/RELEASE_OVERVIEW.md) · [项目历程与视频讲稿](docs/PROJECT_STORY.md) · [开发源码分支](https://github.com/LPF970915/H700Android/tree/codex/rg34xxsp-at4k-input-lockscreen)

ROC OS 从 H700 上的 Android 启动与显示适配起步，逐步加入手柄导航、虚拟鼠标、小屏桌面、亮度与合盖服务、存储整合，并完成 ARM64 user 系统构建和生产签名候选镜像。当前主要开发、测试设备为 **RG34XXSP（H700、2GB RAM、双摇杆）**；早期也使用过独立机型 ANBERNIC RG SP。**项目目标是所有 H700 设备共用同一镜像；RC5 已在 RG34XXSP 2GB 实测，Universal Test1 已通过原 RG SP 1GB/无摇杆首启与基础操作；全 H700 型号矩阵尚未完成。**

**重要撤回（2026-11-08）：DisplayAuto Test2 已因实机显示回归被拒绝，停止推荐，不应继续试刷此包。** 它曾通过离线核验，但原 RG SP 的 720 屏被错误选择为 640×480，出现花屏重影；RG35XX H 与 RG34XXSP 也有失败反馈。不能把 `old`/`boe` 单独当作分辨率判据。Recovery720 Test3 已完成原 720 启动路径恢复的离线核验，原 RG SP 实物回归待验；它不是 RG35XX H 修复版或全系通过结论。当前仍没有新的显示实体验收通过包，可靠面板识别尚在调查。原 Universal Test1 的 RG SP 通过记录和 RC5 四项问题保持原状态。

## 机型兼容范围

早前 RC5/Bootfix1 专机启动路径换卡到 **ANBERNIC RG SP** 后停在厂商 Logo。此前 **Universal Test1 已直接刷入原 RG SP 并成功启动**，无需先放入 RG34XXSP 初始化或扩容。认证 ADB 读到约 1GB 内存、user/Enforcing、PID1 umask0000；专用摇杆模块未加载，Android 仍正常继续。用户确认显示系统，A 解锁、Home 下拉、Select 鼠标和十字键四项正常；Mali、Thermal 五项温度和 11 个关键文件哈希检查通过。首次 Android 画面约 122 秒出现，此次初报 Logo 随后自行进入系统，不能记为新包失败。

RG SP 是独立机型，不是 RG35XXSP 的简称；[官方规格](https://anbernic.com/products/rg-sp)为 H700、1GB RAM、无摇杆。旧包曾强制要求 RG34XXSP 摇杆模块成功加载，模块会拒绝低于 1.5GiB 的设备；新包已取消这项基础启动硬依赖，保留模块保护。内部 `ro.product.device=rgsp` 是历史代号，不是自动识别型号的功能。**Universal Test1 的 RG34XXSP 摇杆复验、其他 H700 机型及四项既有运行问题仍待验证。**

只读审计未发现按设备序列号或卡 CID 绑卡；首启扩容处理 GPT/userdata、文件系统检查和扩容。后续适配将全局 profile 固定为 `rg34xxsp`，并把原来按机型可选的摇杆模块变成 Android 启动前的强制依赖，收窄了实现的兼容范围。按此源码条件，即使新卡第一次就在 1GB RG SP 启动也会被阻断，并非先在 RG34XXSP 扩容后才绑定。新的 **H700 Universal Test1 已完成离线核验**：独立 boot 层已将摇杆模块改为可选扩展；无摇杆、1GB、模块拒绝/缺失、哈希不符或 ABI 不符时，跳过扩展、保留原控制器并继续 Android。模块 GPIO/ADC 与内存护栏保留；不再让扩展加载失败成为系统启动门槛。旧 1GiB 必停负例与新 10 组 shell 路径检查已通过，实际包内 init/helper、37 个启动根、10 个配对 ELF、116 个 APK 签名与完整范围/gzip 核验已通过；原 RG SP 首启已通过，其余机型和同包摇杆复验仍待完成。它沿用 RC5 images18 的 system/vendor、已有 kernel/DTB 和 umask000 修正，不全量重编 Android。

**显示兼容限制：Universal Test1 在 RG35XX H 640×480 上黑屏；后续 DisplayAuto Test2 已因回归被拒绝。** 用户报告 Test2 在 RG35XX H 按电源无明显反应、RG34XXSP 闪 Logo 后黑屏。原 RG SP 实测 boot_completed=1、user/Enforcing，但 HWC 为 640×480/59.941Hz，720 实物屏花屏重影，证明 `lcd_type=old` 并不代表 640 面板。这是本轮面板选择逻辑引入的回归；尚未形成新显示修复包，不安排再次盲刷。离线检查通过不能代替显示运行验收，Hall 首样本保护也不能关闭深睡问题。详见[撤回状态与兼容矩阵](docs/RELEASE_OVERVIEW.md)。

## 已实现的功能

| 方向 | 内容与适用范围 |
| --- | --- |
| 无触屏操作 | 十字键、确认/返回、Home 下拉快捷设置、Select 长按鼠标；RC5 干净首启已确认三项基础导航正常，恢复后的偶发焦点异常见下文 |
| 小屏界面 | 默认中文、AT4K 桌面、横屏与系统界面适配；第三方应用仍可能需要虚拟鼠标 |
| ARM64 | 完整 ARM64 user 构建，保留 ARM32 应用运行路径；已验证真实 64 位运行与 Mali-G31 GLES，兼容性取决于具体应用 |
| 存储 | 已实现 TF1 统一内部存储、TF2 外置存储；Source64 工程阶段已有扩容、文件保留与 TF2 测试，最终 user 候选仍有范围复验待补 |
| 硬件 | 亮度、Hall 合盖服务、音频和 Thermal HAL；五项温度有效，扬声器/耳机切换已实测。正常深睡、开盖恢复和完整电源保护尚未闭环 |
| 发行工程 | user、SELinux Enforcing、专用生产签名、认证 USB ADB，以及分区、依赖、签名与整卡 SHA-256 核验 |

当前桌面保留 **AT4K、图库、文件、设置、日历、时钟、音乐** 七项入口。隐藏多余入口时保留 WebView 引擎、内容提供器等系统依赖。早期试用过的模拟器、阅读器、影音应用不等于当前纯净候选的预装清单；其他应用另行确认。

## 当前版本与已知问题

| 版本 | 定位 |
| --- | --- |
| RC4 | 已冻结的受控内测基线，保留用于比较和回退；不等同于正式稳定版 |
| RC5 | RG34XXSP 上的较早真机测试版本；干净首启、七项入口、基础导航、五项温度及固定 bringup 唤醒锁释放已通过各自检查 |
| RC5 Bootfix1 | 已完成离线核验的启动候选，修正 umask；沿用 RC5 system/vendor，尚未取得真机结论 |
| H700 Universal Test1 | 较早通用启动候选，将摇杆扩展改为可选；整卡与独立核验通过，原 RG SP 1GB/无摇杆首启及基础操作通过，其他机型待验 |
| H700 DisplayAuto Test2 | **已拒绝 / 停止推荐**：曾通过离线检查，实机误选面板导致显示回归，无新的显示验收通过包 |

RC5 已确认、后续候选尚未关闭的四项问题：

- **Wi-Fi 配置保存异常**：干净首启保存失败，用户重启后仍需重新输入密码。根因已定位，Bootfix1 已作针对性修正，实机效果待验证。
- **开盖唤醒异常**：息屏、合盖后再开盖可能仍黑屏，本次测试需短按电源唤醒。
- **USB 恢复异常**：息屏/合盖恢复后电脑可能无法枚举设备，重新插拔无效；普通菜单重启在本次测试中可临时恢复。
- **设置页焦点回跳**：向下操作时焦点可能跳回右上角；重启后暂时消失，尚未定位，不能视为修复。

正式元数据、面向他人的默认调试配置、组件再分发许可、实卡恢复/升级、最终同镜像验收及构建复现比对仍有待收尾。当前诊断配置保留工作站公钥预授权；认证已启用，root 被拒绝、网络 ADB 关闭。116 个 APK 已核验为项目生产签名角色，`dev-keys` 元数据不等于使用公开测试私钥。

完整状态和候选镜像哈希见[发行概览](docs/RELEASE_OVERVIEW.md)。

## 镜像与安装

本仓库保存适配代码、配置、构建与核验工具、公开技术记录。**此页尚未指定公开下载镜像。** 后续发布以 [Releases](https://github.com/LPF970915/H700Android/releases) 中明确的版本说明、支持机型、文件名和 SHA-256 为准；源码提交或文档更新不代表镜像已上传。

测试镜像曾使用 Rufus 4.7 写入至少 64GB 的专用 TF1 卡。整卡烧录会覆盖目标卡数据，应先备份并核对目标磁盘；其他 H700 设备不要直接套用。首启、TF2 与升级方式应遵循对应镜像说明。

## 源码与项目范围

- 本仓库是基于 AOSP / Allwinner 厂商基础的 **H700 适配层与工程记录**。完整 AOSP/Longan、大型厂商输入、部分图形预编译组件不在仓库中，克隆仓库不等于具备完整重建输入。
- 内核、DTB 和部分厂商组件沿用已验证输入；不宣称所有组件均由本项目从零编写或开源重编。
- 当前默认 `main` 的代码仍是较早冻结层。较新的适配源码与 RC4 记录见[开发分支](https://github.com/LPF970915/H700Android/tree/codex/rg34xxsp-at4k-input-lockscreen)及 [RC4 标签](https://github.com/LPF970915/H700Android/tree/baseline/roc-os-user-rc4-pilot-20261107)。RC5/Bootfix1 的本地进展不代表对应源码已全部推送。
- 镜像、签名私钥、设备身份、原始设备日志和 Wi-Fi/账户数据不随文档发布。仓库不提供游戏 ROM 或商业游戏资源。
- 各组件遵循各自的许可与通知；仓库未为全部第三方内容授予统一许可。见[第三方来源](docs/THIRD_PARTY_INPUTS.md)。

## 文档与反馈

- [发行概览与已知问题（中英双语）](docs/RELEASE_OVERVIEW.md)
- [项目历程、视频分镜与口播草稿](docs/PROJECT_STORY.md)
- [历史版本查询](docs/HISTORY.md)
- [早期 v5i 源码恢复与构建说明](docs/REPRODUCE_BASELINE_20261028.md)（历史基线，不是 RC5 一键构建教程）
- [工具分类](tools/README.md)

欢迎通过 [Issues](https://github.com/LPF970915/H700Android/issues) 反馈：请提供机型、镜像版本/哈希、操作步骤、是否经历息屏或合盖、重启后是否仍存在。公开日志请去除设备标识、网络名称、IP 和账户信息。
