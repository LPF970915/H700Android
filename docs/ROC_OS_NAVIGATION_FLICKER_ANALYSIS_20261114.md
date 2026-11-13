# 0.0.1 导航持续滚动与低概率频闪分析

分析日期：2026-11-14（Asia/Shanghai）。用户报告发布后多人在多种机型遇到“不碰按键，选框持续上下滚动，无法控制，重启暂时恢复”；具体触发条件未知。当前 USB 连接的 34XXSP 由用户明确确认处于正常态。本轮只读采集和离线源码/实际 APK 反汇编，没有复现故障、重启、注入按键、修改设置、安装、刷写或构建系统。

## 结论及证据等级

1. **0.0.1 继承了尚未关闭的导航问题。** 它从 Recovery720 Test3 派生，仅换 USB init RC，导航 APK 没有修正。本机实际 APK 与 RC5 静态收据完全一致。
2. **导航服务的方向轴连发状态，是目前优先级最高的公共软件候选。** 实际 APK 中，方向轴一旦被记入 `axisKey`，400ms 后开始每 160ms 自行导航；只要状态未清除，就可在没有新物理事件时继续。当前状态没有按设备/来源隔离，也没有物理轴状态复核。代码机制已证实；“什么事件导致它在故障时未清除”尚未抓到，不能写成已确诊唯一根因。
3. **异常也可能来自更下层的轴状态持续非零，或 Android 原生重复链路。** 无新 evdev 事件、`KeyDowns=0`、日志最后为 UP，都不能单独排除它们。必须同时看当前 HAT/摇杆绝对轴状态，而不只是等新增事件。
4. **旧频闪缓解逻辑在本次启动已触发，没有证据显示补丁遗漏。** 本次启动成功保留了首个 720×480 buffer；日志未出现旧 crop/framebuffer 错误。旧实现只是隔离首个异常分配，并未定位最终写坏共享元数据的环节。网友新频闪尚不能与旧问题等同。
5. **两种病症暂时分开定性。** 导航连发可能增加图形更新负荷，但这不是共同根因证据。当前无故障态输入、网友频闪同刻日志或物理录像，因此本轮不宣布修复或全机型结论。

## 发布身份与历史问题

规范 0.0.1 gzip：591,043,813 字节，SHA-256 `e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346`。它仅替换 `/system/etc/init/h700-usb-configfs.rc`，其余 Android 主体继承原产物。见 [发行概览](RELEASE_OVERVIEW.md)；精确0.0.1身份亦见[公开下载](PUBLIC_DOWNLOADS.md)。本轮没有重新读取整个 32GB 镜像或整卡；组件匹配不能冒充整卡逐字节身份验证。

历史上不是第一次出现输入异常：

| 时间/范围 | 已有事实 | 不能据此证明的事 |
| --- | --- | --- |
| 2026-11-04 Navigation16 | 处理过 Settings 叠加层焦点释放、重复投递、热键回退和遗留状态；受控 HAT 松手测试通过 | 不能覆盖之后长期偶发、丢归零、设备变化或跨机型问题 |
| 2026-11-07 RC4 | 用户报告十字键自行跳动，普通重启后消失；之后 10 秒原始输入为零 | 记录采于恢复之后，不是故障现场 |
| 2026-11-07 RC5 | Settings/开发者选项按 DOWN 回到右上；当时 USB 不通，重启后才开始记录 | 未证明与本次空闲持续滚动完全同根；也没有根因/修复闭环 |
| 本次发布反馈 | 多人、多种机型、不碰按键仍持续滚动，重启只能临时恢复 | 触发场景、轴状态、重复频率、是否真正上下交替仍未知 |

历史候选与已知运行问题的公开记录见[发行概览](RELEASE_OVERVIEW.md)；详细本地记录保持原有时间和采集范围。

## 当前正常机采集到了什么

私有原始证据：`out/nav-flicker-analysis-20261114/`。设备身份、boot ID、原始日志留在该目录，不复制到公开摘要。

| 检查 | 结果与边界 |
| --- | --- |
| 运行状态 | user、Enforcing、boot_completed=1、mtp,adb；继承的 `ro.roc.user.candidate=rc5` 本身不能区分 RC5 与 0.0.1 |
| 实际导航位置 | `/system/app/ROCNavigation/ROCNavigation.apk`；无 `/data/app` 覆盖；采集前后服务 PID 相同 |
| 实际导航版本 | versionCode 16 / versionName `2.2-source64-select-fallback`；服务 dump `navigationVersion=36` |
| 导航 APK SHA-256 | `a5460ba1ad4956ca759797df561b19250110bc7626a351478c30d56492f0f5a6`；与旧 RC5 / Universal 静态收据相同 |
| 实际输入设备 | `ANBERNIC-keys` 同时提供 HAT_X/Y 和附加四摇杆轴；`h700_stick_axes` 已加载；采集到的能力/当前值快照各轴为零 |
| 第一段 25 秒记录 | 有一组 `ABS_HAT0Y=1`，约 150ms 后归零；导航 keyDownCount 10→11。来源未确认，不能把它写成“25 秒零事件”或故障证据 |
| 后一段 30.29 秒记录 | 无 EV_KEY/EV_ABS/SYN 输入记录，计数稳定 11、callbacks 稳定 15；期间设备已按原超时自动息屏，mode=inactive，因此不是亮屏长时间稳定性验收 |
| 采集错误保留 | 一次多设备参数 `getevent` 打印 Usage，未观察 30 秒；随后用不带设备参数的全节点读取纠正。失败原件保留，不把失败当零事件 |
| 收尾 | boot ID 未变；没有 getevent/timeout/常驻 logcat 观察进程遗留；没有设备文件写入或安全设置变化 |

实际 APK 已拉取到本地并反汇编 `classes.dex`。`ROCNavigation.dexdump.txt` 中 `FocusRing$1.run` 对应源码 1321–1325 行，确有 160ms `postDelayed`；`onGenericMotionEvent` 确有 400ms 首次延迟。这里不是只看同名、可能错误的旧源码。

另外完成了一项仅在电脑执行的状态机验证：从锁定源码原样提取 repeat / stopRepeat / navigate / onGenericMotionEvent 四段方法，以虚拟时钟和框架替身执行。只给一次 HAT_DOWN、后续不提供中立，在虚拟 60 秒内生成 **374 对合成 DOWN/UP**；提供中立、CANCEL 或显式 stopRepeat 均能停止。HAT 为零但摇杆为 UP 时仍会导航；另一设备的中立也会清掉共享状态。原片段没有重写。收据为 `out/nav-flicker-analysis-20261114/navigation-host-probe/receipt.json`。这证明保存状态和调度的行为，不是 Android 分发、驱动故障、归零丢失或真实硬件复现；没有安装 APK、修改源码或编译系统镜像。

## 导航的具体可疑机制

与实际 APK 相关实现匹配的保留源码为 `build-support/public/overlay/device/roc/roc_os_source64/Navigation/src/com/roc/rgsp/navtrial/NavigationService.java`，SHA-256 `26010678339217441cae7f0a610c2c7a1f2704db6b0c7ca78da9d6b84cb05464`。实际 DEX 对应方法和行号已核对，但没有重新完整构建并证明整个 APK 逐字节复现。不要误用普通 RGSP 路径中版本号为 37 的另一份 NavigationService。

| 位置 | 实际行为 | 对本病症的意义 |
| --- | --- | --- |
| NavigationService.java:1381 | 先给鼠标处理；否则读 HAT，HAT 中立时退回左右摇杆；大于约 0.5 变成方向 | 用户不动十字键，不代表摇杆或保存的 HAT 状态中立；应记录方向来源 |
| :1395 | 当方向变化才更新单个 `axisKey`，立即导航并安排首个 400ms 连发 | 没有 deviceId/source owner；跨输入设备共享一个方向状态 |
| :1318 | 连发只检查保存的方向及左右滑条条件，每 160ms 再排一次 | 不要求新的物理事件；若归零/取消路径没到达，具有持续导航能力，预期节拍约 6.25 次/秒，实际会受调度影响 |
| :1364 | 每次连发直接调用本服务的 onKeyEvent，生成一对 DOWN/UP | 合成事件没有保留真实设备来源；服务 held 可已清空、lastInput 可为 UP，但 axisKey 仍非零 |
| :1354、:1360、:1383、:141、:146 | 中立方向、ACTION_CANCEL、失焦、窗口状态事件和配置变化已有停止路径 | 不能说“完全没有清理”。需证明故障中哪条路径缺失/被绕过，或状态在清理后又被异常轴值重新置入 |
| :1286 | dump 暴露累计按键/动作/回调、鼠标状态和选框 | 未暴露 axisKey、连发是否排队、原始/上次轴值、来源、最后归零及停止原因；旧诊断存在盲区 |

当前十字键的正常例子是 **EV_ABS / ABS_HAT0Y**，不是 GPIO EV_KEY 的按下保持。因此 Android 的 `KeyDowns=0` 不能证明 HAT 归零；鼠标 dump 中 `stick=0,0` 也主要是鼠标模式缓存，不能替代 FocusRing 的轴状态或内核实时状态。

必须保留一个反例：Linux 绝对轴是有状态的，通常只在值变化时发送事件，正常长按可能没有新增 MOVE。单纯“300ms 没有新事件就停”会破坏合法长按；单纯扩大死区也不能修复已保存的 HAT=±1。内核输入协议说明也要求在 SYN_DROPPED 后重新查询状态。诊断需要 EVIOCGABS/当前轴快照与 Android/导航状态同时对照，不能只计事件行数。

此候选的范围也有限：FocusRing 实际执行导航受 `managed()` 的 locales/files/settings/shade 页面范围约束。`scope()` 会将 Settings、DocumentsUI、Settings intelligence、权限控制器、Latin IME、媒体提供器的部分界面映射到这些范围；AT4K 只托管窄设置面板，普通 HOME 和原生模态界面由应用自己导航。若故障在普通游戏或不受该服务管理的界面同样发生，必须向 Android 原生 joystick→DPAD 重复、InputReader/Dispatcher 或驱动状态追查。本轮没有取得与实际 framework 绑定的 SyntheticJoystickHandler 缺陷证据，原生路径仍是待验证旁路。单个固定 axisKey 也不能自行证明真实 UP/DOWN 正负交替；视觉回跳可能涉及滚动后重选、控件身份变化，需同刻选框和方向记录。

本次正常日志在 Settings 焦点交给叠加层时出现取消 DPAD_UP、丢弃 MOVE 的提示。它证明焦点交接确实存在，但正常交接也可产生该提示，不能把这些行当作本次故障已经复现。

另一条较低优先级公共候选是焦点/无障碍刷新循环：`:968` refresh 重新搜集节点，`:846` select 对变更节点发 ACTION_FOCUS / ACTION_SHOW_ON_SCREEN，后者可以触发滚动和新内容事件；`:866` current 依赖节点与身份匹配。若现场没有新导航调用，选框/列表却往返变化，应查这条链，而不是只修重复器。当前没有抓到这样的循环。

## 附加摇杆模块：次级诱因，不能解释所有机型

`android/h700-android10/device/roc/rgsp/input/kernel/h700_stick_axes.c` 只在装载时配置 ADC/PIO、24 次采样校准；轮询使用 `system_freezable_wq`。没有专门的 suspend/resume 寄存器重配、恢复校验或恢复前归零路径；归零主要在断开时执行。若某种恢复丢失硬件配置，异常端点读数可能按旧中心解释成大幅摇杆，值得后续验证。

`input/axis_math.h:4` 把中心附近 ±32 归零并对其它值缩放限幅；例如中心 2048 时 raw=0 可成为正满幅。但“恢复后实际读到了 0”没有现场证据，小噪声也不等于越过导航阈值。

该模块只写 X/Y/Z/RUDDER，不直接写 HAT；不能把 HAT 异常直接归因为写错轴。它与 BSP 共用 input_dev，帧可以交错，但共用本身不证明输入损坏。保留 Longan 通用 gpio_keys_polled.c 的归零代码尚未与实际预编译 H700 的 ANBERNIC 驱动匹配，不能作为已找到的根因。用户已确认多种机型，优先分析公共输入链，而不是先围绕 34XXSP 摇杆修改。

## 旧频闪的故障链证据与当前边界

2026-10-26 的冷启动证据记录：首个 GPU client-target buffer 的 crop 属性为 `0,0,0,0`，另两个 buffer 为未设置值 `-1,-1,-1,-1`；同时出现 `Crop rectangle dimensions not equal to logical buffer dimensions` 和 `Failed to bind framebuffer! Aborting GPU composition`。暖重启 SurfaceFlinger 后三块属性正常、错误消失。

原始 allocator 的 `gralloc_buffer_priv.cpp:95` 把共享属性初始化为 `0xff`；谁之后将首块属性改零没有最终定位。实际绕过在冻结 `FramebufferSurface.cpp:77`：针对 rgsp/cupid 内置 720×480 屏，启动额外分配并保留一个 buffer，隔离它、不让它进入显示队列。这只针对已观测启动分配情形；resize 仅改默认尺寸，没有针对这类共享 crop 变零的逐 buffer 修复或失败恢复。

不能泛称“整个栈没有 buffer 校验”：HWC 的 layer->crop 检查、mapper 的 handle 检查确实存在，但它们不是旧问题中的共享属性页 `GRALLOC_ARM_BUFFER_ATTR_CROP_RECT` 检查。Mali 内部行为不能由开源代码完全断言。

本轮实际状态：

- SurfaceFlinger dump 存在 `RGSP startup allocator reserve`，大小 1350KiB、720×480；启动日志 `Retaining startup allocator buffer for RGSP LCD (720x480)`。
- 实际 `/system/lib64/libsurfaceflinger.so` SHA-256 `e46d83a884ec6c2a42072105679415fd1806fca79484f32c63c217e5eb5b7505`，与当前 user 构建缓存一致。保护条件 rgsp/cupid 满足。
- 本次日志旧 crop/bind/aborting 三类签名均为零；这只是当前正常启动的结果。
- 软件 VSYNC 为 16,904,379ns。仅开机时一条 `Faking VSYNC due to driver stall`，不能据此认定频闪；missed-frame 累计数也不能证明整屏黑闪。
- fb0 的部分 sysfs 读权限不足，已保留 Permission denied，没有提权或改标签。

旧“2 次 kernel reboot + 15 分钟压力零 GPU 错误”验收真实存在，但回执明确 `physical_power_cycle=false` / `physical_visual_observation=false`，且当时原始按键采集命令失败。它不覆盖所有面板、断电冷启动、长时间使用和显示重建/休眠恢复。

## 故障现场如何区分，避免再次重启抹掉证据

以下是下一阶段的诊断设计，本轮没有安装记录器或主动制造故障。首先保留同一 boot ID/同一服务 PID，在干预前同时拿到原始输入、当前轴状态、输入分发、导航计数/状态、焦点/滚动和电源/显示日志。获取证据后才做单一恢复动作，否则不能判断是哪一步清掉状态。

| 故障同时观察到的事实 | 优先调查方向 |
| --- | --- |
| 内核当前 HAT/摇杆轴持续非零，即使没有新事件 | 按键/驱动/ADC/休眠恢复；不能仅因 getevent 安静归为软件空转 |
| 内核轴为零、无新输入，但导航 keyDownCount 以约160ms增加 | FocusRing 状态或重复任务未清；下一诊断版需显式 axisKey/owner/repeat 状态确认 |
| 内核轴为零，却持续有 Android 非导航来源 DPAD repeat | EventHub/InputReader/Dispatcher/原生 joystick 合成状态及焦点取消 |
| 无新输入、导航计数不增，选框和滚动仍往返 | 无障碍刷新/节点身份/原生焦点竞争；需要同刻选框和滚动目标记录 |
| 整屏频闪同时新增 crop/bind GPU 错误 | 旧 client-target 元数据/allocator/import 生命周期 |
| 频闪伴随 sleep/wake/HWC power mode/背光变化 | 输入/电源/Hall/背光链；不能当作 GPU 导入错误 |
| 只有焦点框闪或列表跳，没有整屏亮暗变化 | 先处理导航/焦点层；尚不构成 LCD 频闪证据 |
| 整屏闪、上述签名均无 | 再追 DE/面板时序/提交与 fence/软件 VSYNC；仅截图可能捕不到实际面板异常 |

下一步若做最小诊断增量，优先记录：FocusRing 的 axisKey、原始 HAT/左右摇杆、deviceId/source、最后中立时间、重复次数/排队状态/停止原因、窗口与屏幕状态；明确区分物理输入和服务自行生成的事件。已有诊断 dump 缺这些字段，不应继续仅靠 lastInput/held 判断。

修复应围绕输入所有权、中立重新启用、设备移除/重连、已有生命周期清理的一致性，以及一个页面只保留一个重复动作来源。若需要连续动作上限，必须同时定义合法长按行为，不能以没有 MOVE 简单超时。若证实旧 GPU 异常，先追共享元数据写入者；不能仅增加更多牺牲 buffer，或全局把 crop 重写为全屏而损坏合法视频裁剪和同步。

分析阶段结束时：**导航机制候选已定位，触发根因待故障态证实；频闪新反馈尚未定性。**

## 用户授权后的修复进展（2026-11-14）

用户随后明确要求按推荐方案修复。现已完成 Navigation17 / 诊断版本38 的同包生产签名增量，真实轴状态机79项检查及实际 Service 片段32项检查通过，并安装至当前 USB 连接的 34XXSP；没有重启或重新制作整卡镜像。新增输入所有权、中立门槛、统一生命周期停止、连续轴导航十秒上限；被动刷新不再执行 FOCUS/SHOW，相同描框不再重复重绘。正常长按和松开已取得实体记录，LT/L2、RT/R2 均有本轮完整按下/松开事件。

当前正常机仍未复现原偶发故障；上述修复封闭了可证实的软件无限重复路径，不能等同于已唯一定位所有机型的触发源。整屏频闪仍未定性，未修改 SurfaceFlinger、GPU 或面板驱动。构建、实际安装、采集失败及验收边界详见 [修复与现场记录](ROC_OS_NAVIGATION_FIX_20261114.md)。

用户补充原0.0.1的“熄屏→亮屏→解锁”线索后，进一步确认旧服务缺少三类屏幕广播清理，锁屏时 `applicationRoot()` 返回空也不直接停止重复任务。这是条件机制，尚未证明故障发生时哪条正常清理丢失。v17对应屏幕/焦点/窗口停止已存在；本机一次完整软件循环和用户三次实体恢复均未见持续连发。详见[熄屏路径复核](ROC_OS_NAVIGATION_WAKE_PATH_20261114.md)，原始输入覆盖、Hall恢复及深睡边界均单独记录。

## 0.0.2 集成补充

本文件记录前述分析或原位更新阶段；后续0.0.2已完成本地整卡封装与独立核验，详见[版本说明](ROC_OS_0.0.2_20261114.md)。完整新卡首启、自动校时和低概率频闪仍保留各自验收边界。
