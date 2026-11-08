# ROC OS 项目历程与视频讲解稿

这段开发经历的主线，是让 H700 掌机上的 Android 从能显示桌面，逐步变成可以用实体按键操作、可以构建和核对版本的系统。到了发布准备阶段，成果已经相当具体，恢复链路和少数偶发问题也仍然存在。

本文依据项目提交、阶段记录，并抽样回顾项目聊天「施工13」「施工14」整理；未逐条通读全部历史聊天。时间线是事实整理；后面的第一人称口播是供作者改写的草稿，不代替作者对个人感受的表述。

## 时间线

| 阶段 | 关键进展 | 视频中值得解释的变化 |
| --- | --- | --- |
| 2026 年 9 月上旬：启动与桌面 | 9 月 2 日建立 Android 10 基线；随后完成图形与按键映射、桌面启动、AT4K 和 Wi-Fi 调整 | 首先解决系统能否启动、能否看见界面、能否联网 |
| 9 月中旬至 v5i：可交付工程镜像 | 单卡整镜像、焦点导航、桌面默认值与存储逐步固化；10 月 27 日 v5i 完成软件范围验收和整卡核验 | 从临时调通转向可以保存、刷写、比较的版本 |
| 10 月 28—30 日：换机与无触屏体验 | 转到 H700/2GB/双摇杆 RG34XXSP；适配原控制器四轴、AT4K 菜单、Select 鼠标、下拉栏、横屏与 Hall；试用阅读、影音及模拟器应用 | Android 的界面出现了，并不代表十字键能到达所有按钮；应用选择也必须考虑小屏与按键 |
| 10 月 30 日—11 月 2 日：ARM64 原型 | 先验证 64 位执行及 Mali EGL，再到双 ABI 原型、Test1/Test2/Test2a 与实际卡启动 | 芯片支持 64 位，只是起点；运行时、驱动、应用和系统服务还要一起工作 |
| 11 月 3—4 日：源码构建与存储整合 | Source64 完整分区构建、差异审计、首启修正、TF1 统一 userdata 与 TF2 外置存储、Light/Thermal 接入 | 从已有系统的补丁适配，走向独立产品源码构建；编译成功后仍需迁入和复验真实功能 |
| 11 月 4—7 日：user 与 RC 迭代 | 将 eng/root 启动功能迁往 user 路径，建立生产签名、Enforcing 和认证 ADB；RC2 修启动环境，RC3 暴露 HAL 属性权限回归，RC4 修正并冻结内测基线 | 发行配置改变权限环境，工程镜像能运行的逻辑需要重新检查 |
| 11 月 7 日晚：RC5 与发布取舍 | 七入口、自动初始化、有限 Wi-Fi 写入重试、限定唤醒锁释放；实机定位 umask 根因，形成 Bootfix1；保留四项开放问题并停止继续测试 | 发布介绍需要同时说清成果和边界，不能把临时恢复写成问题关闭 |
| 11 月 8 日：显示自适应 Test2 | 取消固定帧缓冲、启动前面板数值时序选择、Hall 首样本保护；最终离线核验通过、随后实机显示回归被否决 | old/boe 并不能单独判分辨率，Test2 已停止推荐；离线通过不等于运行验收 |

完整源码构建仍依赖保留的厂商输入，内核/DTB 和部分二进制沿用；这里的“源码构建”不等于全套组件从零重写。

## 适合讲给观众的五个故事

### 没有触屏，常用操作就得重新设计

可以先演示 Home 下拉、十字键选项、Select 鼠标，再回到早期问题：菜单能打开却无法滚到底，焦点进了底层页面，阅读正文能翻页但工具栏需要鼠标。它们解释了为什么移植工作会延伸到 SystemUI、设置、输入法、桌面和辅助导航服务。

鼠标开关曾尝试组合键，后来收敛为 Select 单独长按。使用方式要兼顾系统导航和游戏原有按键，不能只在测试界面里方便。

### ARM64 迁移需要把整条链路接起来

64 位 CPU、64 位可执行文件、完整 64 位 Android，是三个不同层次。项目先做独立执行与图形验证，再跑双 ABI、ART/JNI/Mali，最后推进完整源码产品。可以用 ARM64 与 ARM32 两条应用路径示意兼容关系，避免将它讲成一次属性开关。

### 安全收紧真的会暴露旧依赖

早期 eng/root 便于调试，发行候选则需要独立用户身份、明确权限和签名。RC3 调整属性标签时漏掉已有 Light/Thermal HAL 读取权限，卡在 Android 动画；RC4 补回准确的读权限，并增加能发现旧错误的检查。这个回归应归因于适配改动，不能归因于用户刷卡或硬件。

这段适合说明：安全适配要核对实际消费者，仅看单个应用能否读取是不够的。

### 一个 umask 解释了反复变化的 Wi-Fi 现象

最初只看到“无法创建目录”，后来才保留到底层 EACCES。实际目录为 `0750`，系统服务虽然属于 Wi-Fi 组，却缺少组写权限。继续追查发现，自定义启动交接跳过 Android 第一阶段的 umask 清零，导致要求的 `0770` 被继承的 `0022` 掩掉权限；下次启动已有目录才被 chmod。

可以用三行画面讲清楚：

```text
预期首次创建：0770
继承 umask 022：0750 → 组不可写 → 首次保存失败
恢复 umask 000：0770 → Bootfix1 已离线验证，实机待验
```

这里最有价值的是从模糊异常走到完整因果链。修正版尚未上机，不把根因分析直接讲成用户问题已通过验证。

### 最后阶段最消耗人的往往是偶发恢复问题

聊天里反复出现保留旧镜像、不要从零重编、不要重复已通过测试的要求。编译与刷卡有明确终点，偶发故障却可能在准备取证时消失：USB 恢复不了，按键难以操作，普通重启恢复了连接，也让当时的焦点异常暂时不再出现。

用户随后决定停止继续追查，先整理现状准备发布。这段可以讲开发节奏与取舍；不需要把它包装为所有问题都已解决。已完成的主体工程和当前四项开放缺陷，应同时被看见。

## 最新补充 换卡不等于跨机型兼容

用户把 RG34XXSP 系统卡插入早期开发用的独立机型 ANBERNIC RG SP 后，设备停在厂商 Logo，电脑未发现 Android USB/ADB。RG SP 不是 RG35XXSP 的简称，[官方规格](https://anbernic.com/products/rg-sp)为 H700、1GB RAM、无摇杆。当前启动流程要求 RG34XXSP 摇杆模块成功加载，模块又拒绝低于 1.5GiB 内存的设备，存在与本次现象相符的阻断条件。但未取得启动日志，不能把源码推断讲成实测唯一根因。

这段可以放在结尾解释支持范围：早期 RG SP 跑过旧版本，后来开发转到 RG34XXSP，最新整卡并未因此自动兼容全部 H700 机型。内部 `rgsp` 产品代号也不是自动识别机型的功能。项目目标一直是所有 H700 设备共用同一镜像。目前 RC5 实测覆盖 RG34XXSP 2GB，Bootfix1 尚未上机；跨机型目标尚未达到。这项失败与四项恢复/使用问题分开记录。

扩容审计没有发现按序列号/CID 绑卡；后续迁移把全局 profile 固定到 `rg34xxsp`，并将可选摇杆模块变成启动前强制依赖，才收窄了实现范围。按源码条件，新卡首次在 1GB RG SP 启动也会碰到此阻断，与先在 RG34XXSP 扩容无关。视频应将这段讲成需要修正的兼容回归，不能解释成“其他机型本来就不是目标”。新的 Universal Test1 已移除强制模块依赖并完成离线核验；多机型验证仍需考虑相关服务，并保留模块的硬件保护。

## 最新进展 通用启动修正版离线完成

在用户明确要求恢复全 H700 共用镜像后，独立 boot 层已把强制摇杆模块改为可选扩展。无摇杆、1GB、模块拒绝/缺失、哈希或 ABI 不符时，保留原控制器并继续 Android；模块自身的内存/GPIO/ADC 护栏保持。旧必停负例与新 10 组 shell 路径检查通过，新包 H700 Universal Test1 的整卡封装和独立核验已通过，确切文件与哈希见[发行概览](RELEASE_OVERVIEW.md)；随后用户直接在原 RG SP 刷入新包，1GB/无摇杆首启与 A 解锁、Home 下拉、Select 鼠标、十字键通过，无需先在 RG34XXSP 初始化。约 122 秒进入 Android，未靠现场补丁或安全降级；全系覆盖及同包 RG34XXSP 摇杆复验仍待完成。

视频可补一句：“这次已经在启动层去掉专机扩展的强制依赖，新通用测试包已经完成离线核验；目标仍是全 H700 共用，原 RG SP 的首启和基础操作已经通过，同包 RG34XXSP 摇杆与其他机型还要继续验证。”新包沿用 system/vendor，不需要再全量重编；离线完成不等于已公开上传或取得全系实机验收。

## 最新补充 通用启动之后仍有显示兼容缺口

同一 Universal Test1 换到 640×480 RG35XX H 后黑屏，插 USB 有系统音，但电脑未检测到匹配 USB/ADB，尚不知道 Android 启动到哪一步。实际包内 DTB 仍选 `rg34xxsp_v1` 720×480 面板及其时序，vendor 也固定 720×480 帧缓冲。取消摇杆与内存启动门槛，并没有同时完成面板选择和显示配置适配。

口播可补充：“原 RG SP 的 1GB、无摇杆首启和按键已经通过，但 RG35XX H 这次出现了黑屏。继续检查才看到显示配置仍固定在原来的面板上，所以全 H700 共用镜像还没有完成，显示适配是新的明确缺口。”这段只说明已证实的配置限制和实际反馈，不宣称已经确定唯一黑屏根因，也不把修改逻辑分辨率说成修复。

## 11 月 8 日 Test2 离线通过后被实机否决

DisplayAuto Test2 曾完成整卡封装和独立核验，文件名保留 20261107 起始日期，实际完成于 11 月 8 日。它取消 Android 固定帧缓冲宽高，使用原 U-Boot 的 LCD 探测在进入内核前选择数值时序：old 分支切到 640×480，boe/未知保留 720×480。保留实际注册驱动名，不写回环境、不按内存或摇杆阻断启动。Hall v2 还增加 OPEN→CLOSED 边沿条件，防止无 Hall 机器开机首样本误息屏；3613 项编译类检查通过。

视频可以讲检查如何拦下旧 APK 缓存、旧 system.img、错误驱动别名等问题：编译结束后还必须检查实际打包内容。最终离线包已通过，不能把失败的中间产物当作交付。文件和 SHA 见[发行概览](RELEASE_OVERVIEW.md)。

口播补充：“第二个显示测试包虽然通过了离线检查，实机却暴露了我们选面板的判断错误。原 RG SP 的 720 屏被切到 640，出现了花屏重影；35XX H 和 34XXSP 也有失败反馈，所以这个包已经撤回推荐。old/boe 不能单独用来判断分辨率，接下来需要可靠的硬件或面板识别。”这次是选择逻辑引入的回归，不能归咎于用户刷卡，也不能把离线通过讲成显示适配完成。没有新的显示验收通过包；四项既有问题仍保留。

## 恢复进展 Recovery720 Test3 封装中

Test2 继续撤回；新的 Recovery720 Test3 正在封装，只撤销错误的显示选择，恢复原启动环境、内核与 DTB，保留 Android 原生 framebuffer 尺寸、Hall 首样本修复及可选摇杆扩展。整包和实际引导区的独立核验尚待完成，不写成已经修好 RG35XX H 或所有 H700。

用户确认 RG35XX H 原系统卡能正常启动，后续需对照它真实可启动的固件资料，再推进可靠的全系方案。视频可将这一步解释为先隔离错误、恢复已有 720 屏路径，再核查面板识别；不能用更改 Android 画布代替底层面板适配。

## 视频结构

建议按 8—10 分钟准备，实际时长以口播为准。

| 时间 | 内容 | 画面建议 |
| --- | --- | --- |
| 0:00—0:40 | 成果开场：H700 掌机运行 Android，名称 ROC OS | 实机桌面与机型；字幕标明实际使用镜像版本 |
| 0:40—1:40 | 项目起点：先启动，再让无触屏操作可用 | 早期截图、按键操作对照；没有旧素材可用时间线代替 |
| 1:40—3:00 | 手柄适配：菜单、下拉栏、鼠标、小屏应用 | 连续展示 Home/Select/D-pad，避免跨版本拼接成同一版演示 |
| 3:00—4:20 | ARM64、双 ABI 与源码构建 | 简单结构图；编译日志只展示脱敏片段 |
| 4:20—5:40 | user、安全策略、签名与 RC3/RC4 回归 | 版本对照与权限读取示意，不展示密钥或设备身份 |
| 5:40—7:00 | Wi-Fi 根因故事 | 目录权限三行图，标明 Bootfix1 实机待验 |
| 7:00—8:20 | 当前能用什么、四项已知问题 | 七入口和四项问题卡；若没有故障录像，用文字，不为拍摄重复复现 |
| 8:20—9:00 | 发布方式与反馈 | 仓库链接、版本/哈希、机型和反馈格式；下载以实际 Release 为准 |

## 第一人称口播草稿

大家好，这次想介绍一下我在 H700 掌机上做的 Android 系统，名字叫 ROC OS。现在主要使用的是 RG34XXSP，H700、2GB 内存、双摇杆。这段时间从启动、显示、按键一路做到 ARM64 和发行候选，终于可以把成果整理出来，完整地讲一讲。

刚开始，任务很直接：先让 Android 稳定启动，能看到桌面，按键有反应，Wi-Fi 能联网。等这些跑通后，真正的使用问题才慢慢显出来。普通安卓默认你有一块触摸屏，但这台机器只有实体按键。一个按钮看得见，十字键可能到不了；一个菜单能打开，焦点可能滚不到最后；应用能启动，横竖屏和小屏布局又不一定合适。

所以后来做了很多和操作有关的适配。桌面用 AT4K，系统加入快捷设置的按键操作，Select 长按可以切换鼠标，让那些只能点击的界面也有办法操作。双摇杆、确认返回、输入法、锁屏，都得一项项串起来。这个阶段最直观的变化，是机器开始能拿在手里使用，而不总是连着电脑调试。

接着，我推进了 ARM64。这里也经历了好几层：先验证 64 位程序能跑，再确认图形能渲染，然后验证双 ABI，让 64 位系统还能运行适合它的 32 位应用，最后做完整源码产品构建。此前解决过的桌面、导航、亮度、声音和存储，还需要在新的系统里逐项对齐。编译结束只是产物出来了，离真正可用还有一段路。

存储上，项目实现了 TF1 统一内部空间、TF2 作为外置存储。界面则逐渐收敛为纯净系统，当前保留 AT4K、图库、文件、设置、日历、时钟和音乐七个入口。早期试用过很多应用，但最终随包带什么，和某个应用曾经测试能启动，是不同的决定。

到准备发布的时候，还要把工程调试环境收紧成 user 系统，保留 Enforcing，使用专用签名和认证 ADB。这个过程也有返工。RC3 有一次属性权限调整漏掉了已有的硬件服务读取，结果卡在启动动画。后来 RC4 修复了准确的读权限，也补了能查出这个遗漏的检查。这样的回归提醒我，改动影响的可能是一整条服务链。

最近一个典型问题是 Wi-Fi。看起来能连接，但重启后密码没保存。最初日志只说无法创建目录，后来增加诊断，才发现真正原因是目录权限。自定义启动流程漏掉了 Android 原本清零 umask 的步骤，导致首次创建目录少了组写权限；等下次启动，已有目录又会被修正，所以现象前后还不一样。现在已经形成 Bootfix1，离线封装和检查通过，但它还没刷进机器，真机效果要留待验证。

这也是目前必须讲清的状态。RC5 的干净首启、基础导航、七项入口、温度服务和固定唤醒锁释放，已经有实际检查结果；扬声器和耳机切换也做过实测。与此同时，Wi-Fi 保存、开盖不自动亮屏、恢复后 USB 不识别，以及设置页面偶发焦点回跳，还没有全部关闭。普通重启能暂时恢复一些现象，但不能因此说已经修好。

反复测试到后面，最难受的是刚想抓现场，连接断了；恢复连接需要重启，重启之后问题又暂时不出现。这个阶段已经花了很多时间，我决定先把现有成果、已知问题和版本边界整理出来，准备以预览候选的状态介绍给大家。

如果你对这个项目感兴趣，可以看看仓库里的说明。它保存适配代码、工具和技术记录，完整上游和部分厂商组件仍是外部输入。我的目标是让所有 H700 设备共用一张系统镜像，目前还没有达到。现在 RC5 的实测覆盖 RG34XXSP 2GB 配置，Bootfix1 还没有上机。我把系统卡换到早期用过的独立机型 RG SP，结果停在厂商 Logo；源码里也存在与内存配置不符的启动阻断条件，但没有启动日志，不能说已经证实唯一原因。早期 RG SP 跑过旧版，不代表最新镜像已经通刷。审计也没有发现扩容按设备绑卡；后续适配把机型配置和可选模块写成了强制路径，收窄了兼容范围，现在已在独立启动层将摇杆模块恢复为可选，新通用包已完成离线核验，之后又直接在原 RG SP 首启通过，A 解锁和 Home、Select、十字键也都确认正常。其他机型与同包 RG34XXSP 摇杆还要继续验证。下载和刷卡方式以最终对应版本的说明为准。反馈时带上机型、镜像版本和操作过程，会比单独说一句“不能用”更容易定位。

做完这段适配，我更能体会到，一个系统从出现桌面到适合日常操作，中间有很多看起来很小、实际绕不开的环节。ROC OS 已经走到了可以展示具体成果的阶段，剩余问题也会如实留在说明里。希望这次分享能让大家看到它目前的样子，也看到这些变化是怎么一点点做出来的。

## 发布时可用的短文案

**视频标题备选**

- 《H700 掌机跑上 Android：ROC OS 的移植与适配记录》
- 《从启动桌面到 ARM64：我在 RG34XXSP 上做安卓的这段时间》
- 《没有触屏，怎么用安卓？ROC OS 掌机系统开发记录》

**简介草稿**

ROC OS 是面向 H700 掌机的 Android 10 适配项目，当前主要在 RG34XXSP 上开发。视频介绍无触屏手柄导航、虚拟鼠标、ARM64 与双 ABI、存储整合，以及从工程系统走向 user/Enforcing 发行候选的过程。目前仍有 Wi-Fi 保存、开盖唤醒、USB 恢复与设置焦点问题，Bootfix1 仅通过离线核验，新 H700 Universal Test1 已把摇杆模块改为可选，整卡离线及独立核验通过。项目目标为全 H700 共用镜像，尚未达成；当前 RC5 实测覆盖 RG34XXSP 2GB，换卡到独立机型 RG SP 出现 Logo 早停，新的通用启动修复已完成离线核验，原 RG SP 的 1GB/无摇杆首启与基础操作已通过，但全系矩阵尚未完成，不能宣传所有机型均已验收。Universal Test1 在 RG35XX H 640×480 上仍黑屏，DisplayAuto Test2 曾通过离线检查，但实际误选原 RG SP 面板导致显示回归，现已拒绝、停止推荐；没有新的显示验收通过包。项目状态、支持范围和后续下载以仓库说明为准。

项目：https://github.com/LPF970915/H700Android

**English summary**

ROC OS brings Android 10 to H700 handhelds, with development focused on the RG34XXSP. The project progressed from boot and display bring-up to controller navigation, a virtual mouse, ARM64 with ARM32 compatibility, storage integration, and a production-signed user build with SELinux Enforcing. The video follows those engineering steps and the setbacks along the way. RC5 still has four open issues affecting Wi-Fi persistence, lid-open wake, USB recovery and Settings focus. Bootfix1 targets the identified startup permission cause of the Wi-Fi failure, but has only passed offline checks. The goal is one image for all H700 devices, but this remains unfinished. Current RC5 hardware results cover only the RG34XXSP 2GB configuration; later adaptation narrowed startup compatibility by making model-specific configuration and a formerly optional module mandatory. The inspected growth path showed no device/card identity binding. Moving the card to the separate RG SP model resulted in a manufacturer-logo stop; a source-level blocker is identified, but no boot log establishes the sole cause. The new H700 Universal Test1 completed offline packaging and independent verification with an optional stick extension, retaining module safety guards and the original controller when the extension is unavailable. Exact image hashes are listed in the release overview; the original 1GB stickless RG SP has now passed direct fresh boot and A/Home/Select/D-pad checks without prior RG34XXSP initialization. Same-image RG34XXSP stick revalidation and the full model matrix remain pending; universal compatibility is not yet established. Universal Test1 showed a black screen on RG35XX H. DisplayAuto Test2 passed historical offline checks but was rejected after physical display regression: its old/boe criterion selected 640×480 for the original RG SP 720 panel. It is no longer recommended; no replacement display package has passed. Refer to the repository for current scope and release status.

## 事实核对索引

以下是视频中关键事实的公开工程记录；较早记录中的待办以新版本结论为准。

- [早期历史查询与标签](HISTORY.md)
- [RG34XXSP 控制器和桌面适配](https://github.com/LPF970915/H700Android/blob/codex/rg34xxsp-at4k-input-lockscreen/docs/RG34XXSP_DEVELOPMENT_20261028.md)
- [ARM64 双 ABI 原型](https://github.com/LPF970915/H700Android/blob/codex/rg34xxsp-at4k-input-lockscreen/docs/RG34XXSP_DUALABI_RUNTIME_P1C_20261031.md)
- [Source64 首轮构建](https://github.com/LPF970915/H700Android/blob/codex/rg34xxsp-at4k-input-lockscreen/docs/ROC_OS_SOURCE64_ROUND1_20261103.md)
- [源码版本差异审计](https://github.com/LPF970915/H700Android/blob/codex/rg34xxsp-at4k-input-lockscreen/docs/ROC_OS_SOURCE64_AUDIT_20261103.md)
- [RC4 修复与真机记录](https://github.com/LPF970915/H700Android/blob/codex/rg34xxsp-at4k-input-lockscreen/docs/ROC_OS_USER_RC4_RUNTIME_20261107.md)
- [最新候选与四项问题](RELEASE_OVERVIEW.md)

录屏时核对版本字幕，隐藏设备标识、网络信息和账号；旧素材注明历史版本。缺少旧素材时使用时间线和示意图，不将今天的画面当作过去的实拍。
