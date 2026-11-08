# ROC OS 发行概览与候选版本

[中文首页](../README.md) · [English home](../README.en.md)

更新日期：2026-11-08。**DisplayAuto Test2 已标记 `REJECTED_PHYSICAL_DISPLAY_REGRESSION`，停止推荐，不应继续试刷此包。** 离线封装与核验通过属于历史事实，后续实机结果已否决该显示选择方案。当前没有新的显示验收通过包，不要求用户再次盲刷；原 Universal Test1 的 RG SP 通过记录、RC4 历史冻结基线及四项既有运行问题保持原范围。

## Recovery720 Test3 恢复包封装中

**Test2 保持撤回。** Recovery720 Test3 正在封装，目标仅为撤销错误的分辨率选择、消除 720 屏回归；尚未完成，本文不指定文件大小、SHA 或下载。

恢复包恢复原启动环境、内核和 DTB 原字节，保留 images21 的 Android 原生 framebuffer 尺寸、Hall 首样本修复、可选摇杆扩展和认证 ADB；不新增内存或摇杆启动门槛。独立核验还须从实际整卡比较引导区和 DTB，不能以脚本检查代替。错误 Test2 的封装输入已按交付记录快照，旧写入入口已拒绝继续打包。

用户确认 RG35XX H 的原系统卡可正常开机，原固件路径待补充。可靠多机型方案仍需对照真实可启动固件的引导、DRAM 和面板资料。**Recovery720 不是 RG35XX H 修复版，也不是全系通过结论。** 四项既有运行问题仍开放，不要求用户再次盲刷。

## 已拒绝 Test2 的身份与历史离线结果

**以下仅用于识别已拒绝的文件，不是推荐刷写包。** 此包离线完成于 2026-11-08，文件名沿用修复起始日：`ROC_OS_ARM64_H700_DisplayAuto_Test2_20261107.img.gz`，压缩 591,044,661 字节，解压 32,434,554,368 字节。没有公开镜像上传；保留大小与哈希用于追溯。

gzip SHA-256：

```text
1745a1cd87a7a2281095675abe6ae0cb08f1543d2eef9fa2531caad89cdbd135
```

raw SHA-256：

```text
9651002dbd5dd022ba4f4f8c47cbc25264cb9a47e943ceb5fe2e54639124e4cc
```

Android 显示配置设为 `OverrideFramebufferSize=0` 并移除固定宽高；已有 HWC 与导航/鼠标读取实际屏幕尺寸。启动钩子在进入内核前使用原 U-Boot 的 LCD 探测：`lcd_type=old` 只在内存中切换 11 项 640×480 数值时序；`boe`/未知保留父包 720×480。保留实际内核注册驱动名，不修改 Boot0/U-Boot 可执行代码、内核和密钥，不 saveenv、不绑卡，也不引入 RAM/摇杆启动门槛。720×720 等其他面板尚未由此实现证明支持。

Hall v2 要求先观察到 OPEN→CLOSED 边沿，避免无 Hall 机器初始低电平直接触发息屏；3613 项实际编译类检查通过。这是首样本保护，不能作为正常深睡/开盖恢复通过的证据。

本轮增量产物为 images21/prepare38。116 个实际 APK 签名、10 个配对 ELF、37 个启动根、5 项 shell/CRC/vendor-prefix/实际内核检查、完整分区范围、gzip 与 Windows SHA 均通过；整包封装 483.527 秒、独立核验 32.973 秒。中途缓存旧 APK/镜像、消费者名称、原厂空环境条目和错误驱动别名等问题被检查拦截并保留失败记录，未交付失败包。

**实机否决结果：** 用户报告 RG35XX H 按电源无明显反应，RG34XXSP 闪 Logo 后黑屏。原 RG SP 经认证 ADB 确认 boot_completed=1、user/Enforcing，实际 HWC 为 640×480/59.941Hz，而 720 实物屏花屏重影。电脑端仅重启 adb server 后恢复取证，未重启设备。这明确证明 `lcd_type=old` 被错误地当作 640×480 分辨率判据，是本轮面板选择回归。正在撤销该判据、调查可靠面板识别；没有新包或新的显示通过结论。720×720 和其他修订仍未完成，四项既有问题不因此改变。

## 已完成的工作

完整 ARM64 user 构建、专用生产密钥及备份、116 个实际 APK 的生产签名角色核验、user/Enforcing 实机启动和认证 USB ADB 已完成。RC5 已核对新启动身份及 11 个可读关键文件与交付分区的哈希；干净首启七入口、Home 下拉、Select 鼠标和十字键由用户确认正常，Thermal HAL Ready 且五项温度有效。固定 bringup 唤醒锁已实际释放。扬声器/耳机切换另有前序实测记录。

上述结论各有范围：温度能读不代表完整热保护通过，唤醒锁释放不代表正常深睡通过，初始导航正常也不代表恢复后的焦点异常已解决。

## H700 Universal Test1 离线完成

较早候选：`ROC_OS_ARM64_H700_Universal_Test1_20261107.img.gz`。压缩包 **591,046,971 字节**；解压 **32,434,554,368 字节**；至少 64GB TF1。整卡封装、独立核验及 Windows SHA 通过，原 RG SP 首启已通过。以下为身份核对信息，不是公开下载地址。

gzip SHA-256：

```text
98d1848f188b1368a1041347fb940b239c64ddf60a5d693ac335987765b401ae
```

解压后 raw SHA-256：

```text
e1952c3b630be32b4dd706fadc09d98f203e74c87f555ec94562b278b4dbeea3
```

独立 boot 层把强制摇杆模块改为可选扩展：无摇杆、1GB、模块拒绝/缺失、哈希或 ABI 不符时，跳过扩展、保留原控制器并继续 Android。模块内存/GPIO/ADC 护栏保留。旧 1GiB 必停负例与新 10 组 shell 退出路径检查通过；实际包内 init/helper、共用 kernel/DTB/命令行、37 个启动根、10 个实际 ARM64/ARM32 配对 ELF、116 个 APK 签名、完整范围及 gzip 核验均已通过；这些结果不代替全 H700 实机验证。

新包沿用 RC5 images18 system/vendor、已有 H700 kernel/DTB 和 Wi-Fi umask000 修正，不全量重编 Android。该改动移除本轮引入的专机启动硬依赖，不能据此宣布所有板型及相关服务已经验收，也不关闭原有四项使用问题。

## Universal Test1 原 RG SP 首启结果

用户直接刷入上述同一 SHA 的镜像。认证 ADB 确认 boot_completed=1、MemTotal 996480 KiB、user/Enforcing、PID1 umask0000；专用摇杆模块未加载，Android 正常继续。首次 Android 画面约 122 秒出现，Mali 和 Thermal HAL Ready/五项有效温度通过，11 个可读关键文件与交付分区 SHA 一致。用户亲自确认显示系统、A 解锁、Home 下拉、Select 鼠标和十字键正常。最初反馈 Logo 后系统自行完成首启，诊断未通过重启、重刷、现场补丁或安全降级促成通过。

这是原 RG SP 1GB/无摇杆的首启与基础操作通过；Universal Test1 的 RG34XXSP 摇杆复验、其他型号、长期使用及四项原有故障仍单列待验。

## 较早候选镜像身份

以下为本地候选身份，供核对版本使用，不是公开下载链接。

| 项目 | RC5 真机测试版 | RC5 Bootfix1 离线候选 |
| --- | --- | --- |
| 文件名 | `ROC_OS_ARM64_User_RC5_20261107.img.gz` | `ROC_OS_ARM64_User_RC5_Bootfix1_20261107.img.gz` |
| gzip 大小 | 591,044,264 字节 | 591,042,742 字节 |
| 解压后大小 | 32,434,554,368 字节 | 32,434,554,368 字节 |
| 离线封装与独立核验 | 通过 | 通过 |
| 实机范围 | 已刷入并完成部分验收，有四项开放故障 | 尚未刷入，无整包实机结论 |

RC5 gzip SHA-256：

```text
9469ec7c8b7dcb25b973b16463a4a68172705b7aade05a6dd77b341f15ebca73
```

Bootfix1 gzip SHA-256：

```text
7322cd89acef33c41cb7a285f917375fcdda88f204d3e76125f8d616d8450d9d
```

Bootfix1 解压后 raw SHA-256：

```text
46e928c87a8db56ac8e61098001e581d55936223c3eb095249332eaebae18bdd
```

Bootfix1 恢复自定义启动交接前的标准 `umask 000`。RC5 跳过 Android 第一阶段初始化的清零步骤，PID1 继承 `0022`，使首次创建的 Wi-Fi 目录从要求的 `0770` 变成 `0750`，系统服务缺少组写权限。已有目录在后续启动才被 chmod，造成首次失败与后来行为不同。修正版沿用 RC5 system/vendor，不重编 Android 主体；内核、DTB、命令行及除 init 内容外的全部 ramdisk 项保持一致。该修正针对 Wi-Fi 首次写入根因，不能宣称另外三项故障随之解决。

## 跨机型兼容范围

**项目目标是所有 H700 设备使用同一镜像，完整型号覆盖尚未完成。** RC5 已在 RG34XXSP 2GB 完成部分验收；Universal Test1 已在原 RG SP 1GB/无摇杆直接首启并通过基础操作。较早专机路径换卡到 RG SP 的 Logo 失败作为历史回归保留，不计作新包再次失败。RG SP 并非 RG35XXSP 简称，[官方规格](https://anbernic.com/products/rg-sp)为 H700、1GB RAM、无摇杆。

较早 RC5/Bootfix1 启动源码强制加载 `h700_stick_axes.ko profile=rg34xxsp`，失败即停止进入 Android；模块明确拒绝低于 1.5GiB 内存的设备。这是与本次现象相符的源码阻断条件；没有取得该卡启动日志，实际停止点和唯一根因尚未实证，仍可能存在更早的内存或设备树适配差异。内部 `ro.product.device=rgsp` 只是历史代号，不代表按机型自动识别或适配。此项单列为兼容失败，不合并进 RG34XXSP 的四项使用故障，也不据此移除模块内存/GPIO 保护。

只读审计未发现按 CPU/设备序列号或卡 CID 绑定；实际扩容脚本仅处理 GPT/userdata、fsck 与 resize，布局使用整包固定 UUID。后续迁移写死全局 `rg34xxsp` profile，并将原先可选的摇杆模块改成启动前强制依赖，是实现兼容范围收窄的回归。按此条件，新卡首次在 1GB RG SP 启动也会被阻断，不依赖此前是否在 RG34XXSP 扩容。上述为 RC5/Bootfix1 的兼容回归；新的 Universal Test1 已将模块改为可选并完成离线核验。原 RG SP 首启已实测通过，其他板型能力及相关服务的实测仍待完成，不能以删除模块保护替代适配。

| 机型/配置 | 当前候选实测状态 |
| --- | --- |
| RG34XXSP 2GB | RC5 完成部分验收；Universal Test1 同包摇杆复验待补；四项问题仍开放 |
| 独立机型 RG SP 1GB | Universal Test1 直接刷入，1GB/无摇杆首启及 A/Home/Select/十字键通过；旧包 Logo 失败保留为历史 |
| RG35XX H 640×480 | Universal Test1 黑屏；Test2 用户报告按电源无明显反应，Test2 已拒绝 |
| 720×480 RG SP/RG34XXSP | Test2：RG SP 实际误选 640、花屏重影；RG34XXSP 闪 Logo 后黑屏。Test2 已拒绝，旧版通过记录仍保留 |
| 720×720 及其他面板修订 | 未由当前两条分支证明支持，待适配/实测 |
| 其他 H700 板型/内存配置 | 尚无当前候选的兼容结论，仍属于全 H700 目标的待适配/验证范围 |

## RG35XX H 显示兼容阻断

用户将同一 Universal Test1 卡移到 640×480 RG35XX H，反馈黑屏、插 USB 有系统音；电脑没有匹配的 PnP/ADB。声音不能证明 Android 已完成启动，目前没有真机日志确定黑屏发生阶段。

对实际打包 boot 的 DTB 审计确认：`lcd_driver_name=rg34xxsp_v1`、`lcd_x=720`、`lcd_y=480`、时钟 26MHz、HT820/VT536。实际 vendor 显示配置仍为 `OverrideFramebufferSize=1`、720×480。上一轮仅移除了摇杆/RAM 的启动硬依赖，没有完成跨面板选择或显示配置适配，不能声称已支持全 H700 显示。

此项作为独立兼容阻断保留；后续 DisplayAuto Test2 的离线显示/Hall 改动曾通过检查，但实机显示回归已否决该包，不再推荐。不能用单改 `wm size` 或盲改 DTB 宽度代替面板/时序适配。RG SP 1GB 首启与基础按键通过仍成立，四项原有运行问题也不改变状态。

## 当前四项已知故障

| 问题 | 实际影响与当前结论 |
| --- | --- |
| Wi-Fi 首次保存/重启自动连接失败 | 用户明确确认重启后仍需手动输入密码。重连后有写入成功日志，但没有再重启复验。Bootfix1 已修已定位根因，实机效果待验 |
| 息屏/合盖后开盖不自动亮屏 | 本次需要短按电源唤醒。正常深睡及 Hall 唤醒仍未通过 |
| 恢复后 USB 不枚举 | 同线同口重新插拔仍无效；普通菜单重启本次可临时恢复。切换 USB 调试因按键异常无法完成，不是已验证办法 |
| 设置/开发者选项焦点回跳 | 按下却回到右上角；重启暂时抑制症状，根因未知。故障发生时未抓到原始输入现场，不能用重启后的记录代替 |

后三项出现在恢复相关操作后，目前不能确定共同根因。普通重启只算临时恢复，不算修复。

## 发行配置与支持范围

- 当前版本适合按**公测预览候选**说明状态，不宣称正式稳定版。本文没有指定公开镜像下载。
- 当前保留诊断 USB 和工作站公钥预授权；认证启用、root 拒绝、网络 ADB 关闭。面向他人的默认策略仍需确定。
- 源码构建的 `dev-keys` 元数据尚待收口；实际 APK 的生产签名已核验，两者应分别说明。
- 最终同包的长期待机、充电/低电/高温保护、当前 user 存储与外设范围、实卡恢复升级仍有未验收项；缺少验收不等于这些功能已被证明损坏。
- 第三方应用与厂商组件的再分发许可、构建复现比对尚未闭环。公开仓库不包含全部重建输入。
- 镜像烧录会覆盖目标卡。测试使用至少 64GB 专用 TF1；升级是否保留数据应以具体发布说明为准。

RC4 冻结源码为 [`780df2bb`](https://github.com/LPF970915/H700Android/commit/780df2bbd30eb99c7a34acb47636c3c383947e2e)，标签为 [`baseline/roc-os-user-rc4-pilot-20261107`](https://github.com/LPF970915/H700Android/tree/baseline/roc-os-user-rc4-pilot-20261107)。此提交不包含尚未提交的 RC5/Bootfix1 增量。本次更新介绍文档，不改变镜像或验收基线。

## English release overview

As of November 8, 2026, **DisplayAuto Test2 is rejected (`REJECTED_PHYSICAL_DISPLAY_REGRESSION`), no longer recommended and should not be flashed for further trials**; earlier **Universal Test1** results are retained, **RC5 Bootfix1 is retained as an earlier candidate**, **RC5 has RG34XXSP hardware results and Universal Test1 has original RG SP fresh-boot results**, and **RC4 remains the frozen internal-test baseline**. These are separate validation scopes. No public image download is designated here.

**Recovery720 Test3 is being packaged:** it only reverts the incorrect display selection and restores the original boot environment, kernel and DTB while retaining images21 native framebuffer sizing, the initial Hall-sample correction, optional sticks and authenticated ADB. Final image identity and whole-card verification are pending. Test2 remains withdrawn; this recovery is not an RG35XX H fix or all-H700 acceptance. The user confirmed the RG35XX H stock card boots normally; its firmware path is awaited for comparison of actual boot, DRAM and panel configuration. No further blind flash is requested, and the four runtime issues remain open.

**Rejected Test2 identity:** `ROC_OS_ARM64_H700_DisplayAuto_Test2_20261107.img.gz` completed offline checks on November 8: 591,044,661 bytes compressed, 32,434,554,368 bytes raw. The hashes above identify this rejected file for traceability, not a recommended image or public download.

The new Android display configuration sets `OverrideFramebufferSize=0` and removes fixed dimensions. Existing HWC/navigation/mouse code reads actual dimensions. Before kernel entry, a hook uses the original U-Boot LCD probe: `old` selects eleven numeric 640×480 timing properties in RAM; `boe`/unknown keeps the parent 720×480 settings. The actual registered driver name, Boot0/U-Boot code, kernel and keys are retained. No saveenv, card binding or RAM/stick startup gate is added. Hall v2 requires an observed OPEN→CLOSED edge; 3,613 checks against the compiled class passed. This guards the initial low sample and does not establish normal suspend/resume.

Incremental images21/prepare38, 116 APK signatures, ten paired ELFs, 37 startup roots, five shell/CRC/vendor-prefix/actual-kernel tests, full image ranges, gzip and Windows SHA passed historical offline checks. Physical results subsequently rejected the selection logic: RG35XX H had no obvious power-on response and RG34XXSP flashed a logo then went black, as reported by the user. On the original RG SP, authenticated ADB confirmed boot_completed=1 and user/Enforcing, but HWC output was 640×480/59.941Hz with corruption/ghosting on its physical 720 panel. Only the host adb server was restarted for access, not the device. This proves `old` alone is an invalid resolution discriminator. No replacement display package has passed; the criterion is being reverted and reliable identification investigated, without requesting another blind flash. Earlier model results, the RC4 baseline and four runtime issues retain their scope.

The complete ARM64 user build, dedicated production keys and backup, production signing-role checks for 116 APKs, hardware boot with SELinux Enforcing and authenticated USB ADB are complete. On RC5, 11 readable critical files matched the delivered partitions; fresh provisioning, seven desktop entries and basic Home/Select/D-pad operation passed. Thermal HAL was ready with five finite temperature readings, and the fixed bring-up wake lock was actually released. Speaker/headphone switching was checked in an earlier stage. These results do not establish normal deep sleep, full thermal protection or freedom from intermittent recovery failures.

The completed Universal Test1 file is `ROC_OS_ARM64_H700_Universal_Test1_20261107.img.gz`: **591,046,971 bytes** compressed, **32,434,554,368 bytes** raw, requiring a TF1 card of at least 64GB. The gzip/raw SHA-256 values above identify it; no public download is designated here. Its separate boot layer makes the stick module optional: refusal/absence, hash or ABI mismatch, no sticks or 1GB memory skips the extension, preserves the original controller and continues Android. Module memory/GPIO/ADC guards remain intact. The old mandatory-stop negative case and ten new shell exit-path checks passed; actual packaged init/helper, preserved kernel/DTB/command line, 37 startup roots, ten paired ELFs, 116 APK signatures, complete ranges, gzip and Windows SHA verification also passed. Hardware-family-wide validation remains pending. It reuses RC5 images18 system/vendor, the existing kernel/DTB and the umask000 fix without a full Android rebuild. This removes the introduced model-specific startup dependency; it does not establish every board/service as working or close the four existing issues. The user directly flashed Universal Test1 to the original RG SP, without first initializing it on an RG34XXSP. Authenticated ADB confirmed boot_completed=1, MemTotal 996480 KiB, user/Enforcing, PID1 umask0000 and the specialized stick module unloaded. Android appeared after about 122 seconds. Mali, Thermal HAL readiness/five finite readings and 11 critical-file hashes passed. The user confirmed the system display, A unlock, Home quick settings, Select mouse and D-pad operation. This boot completed without diagnostic reboot/reflash, runtime patches or reduced security. The initial logo report for Universal Test1 was followed by successful startup; it is not another boot failure. Same-image RG34XXSP stick revalidation, other models and the four existing issues remain open.

The table and hashes above identify the exact completed local RC5 and Bootfix1 images. Both passed offline packaging and independent verification; **Bootfix1 has not been flashed or hardware-accepted**. It restores `umask 000` before the custom init handoff. RC5 had inherited `0022`, turning first-created Wi-Fi directories from requested mode `0770` into `0750` and denying group writes. Existing directories were chmodded on a later boot, explaining the different first/subsequent-boot behavior. Bootfix1 keeps RC5 system/vendor without rebuilding Android; kernel, DTB, command line and all other ramdisk entries remain unchanged.

**Goal and current coverage:** one image for all H700 devices remains the goal. RC5 has RG34XXSP 2GB results; Universal Test1 has passed original 1GB stickless RG SP fresh boot and basic controls. The full model matrix remains incomplete. The following logo failure and blocking source condition concern the older RC5/Bootfix1 path, not the new successful Universal Test1 boot. Moving the card to the separate ANBERNIC RG SP left it at the manufacturer logo with no Android USB/ADB enumeration. RG SP is not shorthand for RG35XXSP; its [official specifications](https://anbernic.com/products/rg-sp) list H700, 1GB RAM and a stickless design. Startup requires the RG34XXSP stick module, which rejects devices below 1.5GiB RAM. This source-level blocker is consistent with the early stop, but no boot log was obtained: the actual stopping point and sole cause are unproven, and earlier memory/device-tree differences may also exist. The internal `ro.product.device=rgsp` is a historical identifier, not hardware autodetection or support. Earlier RG SP builds do not establish current-image compatibility. This failure is separate from the four RG34XXSP usage issues and does not justify removing module memory/GPIO guards.

The read-only audit found no CPU/device-serial or card-CID binding in the inspected packaged growth script and layout. Growth handles GPT/userdata, filesystem checks and resizing; UUIDs are fixed per package rather than per device. Later migration hard-coded the global `rg34xxsp` profile and turned a previously optional stick module into a mandatory pre-Android dependency, narrowing compatibility. The same source condition would block a fresh card first booted on a 1GB RG SP; prior expansion on an RG34XXSP is not required. Universal Test1 has made the module optional and completed offline verification; hardware startup, board capabilities and service behavior still need validation while retaining hardware safety guards. Other H700 boards and memory configurations remain unverified.

**RG35XX H display blocker:** moving the same Universal Test1 card to the 640×480 RG35XX H produced a black screen. The user heard a system sound on USB connection, but no matching computer PnP/ADB interface was detected. The Android boot stage remains unknown. The actual packaged DTB still specifies `lcd_driver_name=rg34xxsp_v1`, 720×480, a 26MHz clock and HT820/VT536; the vendor display configuration still forces a 720×480 framebuffer with `OverrideFramebufferSize=1`. Removing the stick/RAM dependency did not implement panel selection or display adaptation. This is an open display compatibility blocker, separate from the four runtime issues. The subsequent DisplayAuto Test2 passed historical offline checks but has now been rejected for a physical display regression; it is no longer recommended. Changing only `wm size` or DTB width would not establish a valid fix. The successful original RG SP boot remains valid; full H700 support is incomplete.

Four RC5 issues remain open:

1. Wi-Fi configuration was not retained; the user re-entered the password after reboot. Later writes succeeded after reconnecting, but no further reboot validation followed. Bootfix1 targets the identified cause; its hardware effect remains unverified.
2. Opening the lid after screen-off/lid recovery did not light the screen; a short power press was needed.
3. USB stopped enumerating after recovery, including after cable reconnection. A normal menu reboot temporarily restored it. Toggling USB debugging could not be completed and is not a proven workaround.
4. Down navigation in Settings/Developer Options jumped to the upper-right corner. Reboot temporarily suppressed it; the cause is unknown and failure-time raw input was not captured.

The last three issues may be related, but no common cause has been established. Reboot recovery is not a fix.

Release metadata, public ADB defaults and the preauthorized workstation public key policy, redistribution permissions, real-card recovery/upgrade, final same-image power/storage/peripheral checks and source rebuild comparison remain open. Actual APK production signatures must not be confused with the remaining `dev-keys` metadata. Authentication is enabled, root is refused and network ADB is disabled. The scope should be described as a **public-preview candidate**, without claiming a completed stable release. Coverage now includes RC5 on RG34XXSP and Universal Test1 fresh boot/basic controls on the original RG SP; it does not establish all H700 models or same-image RG34XXSP stick behavior.

The RC4 commit and tag linked above do not contain the uncommitted RC5/Bootfix1 work. Updating these documents does not change the image or accepted baseline.
