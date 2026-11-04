# 当前基线与接手状态

2026-11-04 发行准备基线：`baseline/roc-os-release-prep-r1-20261104`。新增隔离user候选配置、发行安全门禁、离线userdata恢复工具及全量Native内容/构建命令清单，10项测试通过。未切换现机安全模式、未编出user系统、未封装镜像；当前工程产物被发行门禁拒绝。见[交付与剩余缺口](ROC_OS_RELEASE_PREP_20261104.md)。

2026-11-04 最新 Thermal 基线：`baseline/roc-os-source64-thermal-r1-20261104`。Thermal HAL2已连接框架，真实5温区/2冷却设备、缓存回调及服务重连通过；123项审计、22项主机用例通过。当前后台启动，冷启init自启和真实保护仍待验。见[本轮完整边界](ROC_OS_SOURCE64_THERMAL_20261104.md)。TF2保持卸载，旧镜像未重封。

2026-11-04 最新无人验收基线：`baseline/roc-os-source64-unattended-r1-20261104`。独立ARM64应用、内部文档提供器读取、3轮Wi-Fi恢复及软件息屏恢复通过；亮度255回落200已在独立Light以最高档映射254兼容修正，增量构建/120项复审/21项主机用例通过并应用现卡。用户暂离机器，TF2保持卸载，物理验收集中延期。见[本轮证据及剩余工作](ROC_OS_SOURCE64_UNATTENDED_20261104.md)。旧gzip未重封，镜像不上传。

2026-11-04 TF2 增量：用户确认 Select 有效；TF2 FAT 数据卷 66 文件读写/改名/删除、带卡正常重启保留及全部已挂载卷安全卸载通过，实体拔出/重插待测。见 [TF2 实测](ROC_OS_SOURCE64_TF2_20261104.md)。此前“TF2缺卡/实体Select待确认”是历史状态。

2026-11-04 当前开发基线：`baseline/roc-os-source64-live-fix1-20261104`，修复源码 `03362c3`，见[七步计划与后续顺序](ROC_OS_PLAN_PROGRESS_20261104.md)及[存储增量证明](baselines/roc-os-source64-live-baseline-20261104/acceptance.json)。128GB 统一内部存储的 66 个文件跨正常重启哈希保持，当前主线为第 3 步 TF2/存储闭环；实体鼠标复测待确认。镜像不上传，旧 Test1 gzip 未包含运行修复。以下日期条目为历史检查点，不能当作最新待办。

2026-11-04 Source64 128GB 首启及运行修正：扩容、ARM64/Mali、Wi-Fi 联网已观察，补齐 supplicant、HOME 角色、Navigation16、字体预加载与 devpts；当前卡已修改，旧 Test1 gzip 未重新封装。新分区构建及 120 项复审通过，最新物理鼠标复测待确认。见 [运行修正记录](ROC_OS_SOURCE64_FIRSTBOOT_128G_20261104.md)。

2026-11-04 Source64 Clean Test1 整卡镜像已完成：596,398,309 字节 gzip、完整解压/分段哈希/空白 userdata/启动保护校验通过。用户已明确授权本轮封装，未授权刷卡且本轮未操作设备。最低 64GB TF 卡，实机首启仍待验收。见 [交付及烧录说明](ROC_OS_SOURCE64_CARD_TEST1_20261104.md)。

2026-11-04 Source64 第二轮：差异修正、增量编译和最终离线复审通过；118 项分区检查、20 项主机检查及实际 ARM64 扩容工具模拟执行通过。545 ELF 启动依赖无缺项。尚未制作启动/整卡镜像、未操作设备，等待用户确认后才进入封装与备用卡验收。见 [修正与复审记录](ROC_OS_SOURCE64_ROUND2_20261103.md) 和 [完成证明](baselines/roc-os-source64-round2-20261103/completion.json)。旧版本、失败材料及 SPACE_REVIEW 用户修改保留。


2026-11-03源码产物离线审计完成：[差异报告](ROC_OS_SOURCE64_AUDIT_20261103.md)及[审计锁](baselines/roc-os-source64-audit-20261103/audit-lock.json)。双分区只读fsck、启动DT_NEEDED与选定APK签名检查通过，A解锁/电源焦点已在实际DEX中保留；但Navigation滑条、Light、音频混音、OMX声明和初始化/品牌尚未对齐，TF1统一userdata/TF2外置布局也未实施。当前仅审计，原三镜像/源码输入/设备卡未修改，没有重新编译或制作整卡镜像；等待用户确认后才进入镜像制作。

2026-11-03 18:55源码构建第一轮已完成：独立`roc_os_source64-eng`的system/vendor/ramdisk构建退出0，三镜像SHA和371项原输入、57项独立产品文件、2项ABI5主机库复核通过；10项实际ELF证明ARM64/ARM32的应用进程、加载器、ART、JNI运行库及私有Gralloc产物。完整结果见[本轮交付记录](ROC_OS_SOURCE64_ROUND1_20261103.md)与[完成锁](baselines/roc-os-source64-round1-20261103/completion.json)。定时跟进已暂停，没有刷卡或整卡IMG；新源码产物启动、现行补丁一致性、纯净预装及新存储布局仍待后续独立阶段。

2026-11-03源码构建第一轮已启动：独立`roc_os_source64-eng`及全新输出目录，371项关键源输入与私有Gralloc副本锁定，ARM64主架构/ARM32兼容/API29确认。完整依赖图已通过；system/vendor/ramdisk实际编译正在运行，尚无整镜像或启动通过结论。使用原单核/6GiB/512MiB/nice19限制，不刷现卡、不改分区。见[首轮进度锁](baselines/roc-os-source64-round1-20261103/result-lock.json)。

2026-11-03最新需求与实测：[分项验收](RG34XXSP_PHYSICAL_ACCEPTANCE_20261102.md)已确认亮度、合盖息屏/开盖恢复、A解锁、电源菜单、鼠标、耳机基本切换、WLAN、正常重启及一次关机重开。系统命名为ROC OS；后续改为纯净系统与TF1统一userdata、TF2外置存储。现卡Test2a+Light+data Nav13仍带七应用/独立ROMS，仅保存名称已更改；ROC OS r4 stage-v5已通过离线属性/文件/fsck/VINTF和名称迁移检查，完整型号/USB尚未写卡；新命名候选不等于新IMG，纯净/新分区及整机发行验收仍待完成。

2026-11-02 [快捷设置亮度条修复](RG34XXSP_QS_BRIGHTNESS_20261102.md)：Navigation13 data更新已安装，修正shade被排除的滑条动作；长按Menu后选中亮度条，左右进度/设置/多档驱动读回、上下离开和B关闭通过受控事件验证。恢复亮度102/超时60000。上端设置255但驱动200差异保留待查，实体手感/重启未重验。当前是Test2a+Light+data Nav13，使用新守卫核对已安装APK。Nav13已进入r3独立离线阶段并通过签名/文件/关键库/fsck/VINTF检查，未封装新IMG。

2026-11-02 [ARM64 背光运行验证](RG34XXSP_ARM64_LIGHT_RUNTIME_20261102.md)：原64GB卡现为Test2a加四项vendor增量，必须用本轮身份+文件SHA守卫。五档设置/驱动读回、两次正常重启保留、受控A解锁、息屏背光0与唤醒102通过；肉眼亮度、实体输入/合盖和深睡仍待测。原亮度/超时/USB常亮设置已恢复。Hall GPIO135已由hall switch持有，有真实IRQ条目，但IRQ wake未证明，不解除bringup锁。七款APK哈希及ARM64安装标记匹配，未重验全部业务。r2离线阶段通过且vendor四文件与现卡相同；当前system/marker仍是Test2a，不包含r2首启低优先级RC，也未生成新IMG。

2026-11-02 [ARM64 离线发布收尾](RG34XXSP_ARM64_OFFLINE_READINESS_20261102.md)：设备未连接，现卡与 Test2a 镜像不变。新 ARM64 背光 Light 服务完成模块构建、主机测试和按父配置划分命名空间的依赖审计；独立离线阶段集成 nice19/idle0 首启 RC。9 项增量、3,752 项锁定文件 SHA、10 项关键库及双分区 fsck 通过，父分区 SHA 保持。没有生成整卡镜像、没有安装或实测亮度。固定 prefix 的 DTB 明确 Hall=PE7，但 IRQ wake/深睡仍待真机核对；不解除 bringup 锁。下一轮从该候选元数据继续验证，不能把它当作已经刷入的版本。

2026-11-01 [Test2a 64GB首启与UI卡顿定位](RG34XXSP_TEST2A_FIRSTBOOT_UI_PERF_20261101.md)：新卡已进Android并获实体AT4K确认，默认中文/HOME解析和p8扩容挂载通过观察。用户要求优先查卡顿：已证明Mali64/Skia OpenGL硬件路径工作，首启cp占满单核是主要负载；后台结束后桌面卡顿帧约51%→4.3%、SystemUI约71%→1.9%，用户确认明显改善。源码已为下一镜像将初始化设nice19/IO idle，并补显式RC集成；尚未写入现机或重封IMG，新优先级首启效果未验收。应用、实体A/电源菜单和重启回归按用户要求暂缓；首启蓝牙HCI异常保留，不称为零错误首启。

2026-11-01 [Test2a写入原64GB卡并校验通过](RG34XXSP_ARM64_TEST2A_FLASH_64G_20261101.md)：用户授权覆盖旧32位工作卡并手动完成Rufus写入。全部32.43GB镜像范围已回读；system/vendor/userdata精确保持来源，GPT规范化与Windows SVI引起的198字节FAT元数据增量均独立审查并重算匹配。紧凑GPT及引导几何检查通过，原始mismatch和综合通过回执都保留。卡尚待安全弹出、装入TF1并保持TF2空进行新首启；不代表开机/扩容/UI/apps验收。原64GB不再是32位回退，v6b镜像和128GB旧开发卡保留。

2026-11-01 用户明确选定 **ARM64 Test2a作为后续修复与镜像封装的开发基线**，对应`baseline/rg34xxsp-arm64-defaults-test2a-20261101`。镜像为`zygote64_32`，主ABI为`arm64-v8a`，保留ARM32兼容；同源实机已验证ART64/JNI/Mali、七款应用实际ELF64进程及RA/PPSSPP的64位渲染。开发基线采用GSI10 ARM64加H700厂商适配，完整BSP64源码重建另计；Test2a干净刷卡首启和整套实体回归仍待验收，不等于正式稳定发行。后续增量以该镜像/组件锁和受保护本地阶段为父输入，原镜像/标签不回改，原64GB与ARM32 v6b保留回退。

2026-11-01 [ARM64 Test2a 默认值增量](RG34XXSP_ARM64_DEFAULTS_TEST2A_20261101.md)：修正GSI build.prop英语默认值对prop.default的覆盖，并安装AT4K工厂HOME首选配置，避免只在boot_completed后选择桌面的时间窗口。六项文件/标签、fsck、关键运行库及属性顺序检查通过；最终镜像完整解压/分段SHA通过，首启无选择框仍待实卡确认。七款应用、vendor/硬件前缀/干净尾部不变，现机未操作。

2026-11-01 [ARM64 Parity Test2](RG34XXSP_ARM64_PARITY_20261101.md)：最新ARM32系统行为按GSI资源/API迁移，七款第三方应用改ARM64，QQ音乐TV无官方ARM64包暂不纳入；原生SystemUI锁屏/电源焦点、Navigation12、ARM64受保护vold及ROMS交接、Leanback/资源覆盖、横屏/合盖、天马G配置已进入独立候选。分区回读/fsck/签名/API检查通过；最终3.63GB整卡gzip已通过4段范围及完整解压SHA，见镜像锁，新镜像未刷卡、首启/实体组合回归待验收。用户已确认Navigation运行更新后实体A解锁通过；旧power-nav冻结记录不修改。当前128GB仍为带运行增量的Test1，原64GB卡保存，v6b/Test1不替代。

2026-11-01 [ARM64 输入迁移复核](RG34XXSP_ARM64_INTERACTION_20261101.md)：用户确认新卡仍需 Y 解锁，电源菜单缺少十字键支持。已确认旧 ARM32 SystemUI 原生补丁未进入 GSI；现以 Navigation11 运行更新补上电源菜单代理导航，四项可达、注入 A 截图、B 取消及锁屏隔离通过受控检查。实体 A 问题仍待双层采样定位，不能标为修复；其余原生组件按迁移表继续核对。Test1 gzip 与 Navigation9 系统原件不变，原64GB卡保留。

2026-10-31 构建的 [首版 ARM64 测试镜像 Test1](RG34XXSP_ARM64_TEST1_20261031.md)：约960MB镜像已通过离线及完整实卡读回，随后完成干净工厂数据首启、四APK的SHA/ABI、扩容、64位渲染、两次正常重启和设置/测试文件/首装标记保留检查。新镜像A解锁受控通过；随后实体反馈失败，以2026-11-01增量为准。已知首启自带Launcher3在自动选择AT4K前出现AppWidgetManager异常，之后及两次重启均无新增崩溃；ROMS已扩容但尚未向vold暴露。当前128GB Test1在TF1，原64GB工作卡与v6b保留，八款正式预装/完整64位源码重建另计。

2026-10-31 [双 ABI 运行修正版 P1c](RG34XXSP_DUALABI_RUNTIME_P1C_20261031.md)：P1b 已连通 USB，进一步补齐显式 VNDK29、原 BSP 堆参数和软件 VSYNC。备用卡正常文件替换后根分区恢复只读，无临时 bind 的受控重启通过；ART64/JNI/Mali、MT64 协议页、RA32 的官方 2048 与 PPSSPP32 的官方 cube、四应用同时驻留及画面往返切换已做受控验证。绿色页已获用户实体确认，其余实体输入、断电冷启、干净镜像首启和完整源码 64 位重建仍待验收；v6b 不变。当前 TF1 为 128GB 实验卡，原 64GB 卡已取下保存；未另封装 P1c gzip。

2026-10-31 [双ABI切根兼容修正版P1b](RG34XXSP_DUALABI_HANDOFF_P1B_20261031.md)：根据真实ramdisk日志，改相对init链接并匹配保留的兼容分区别名。28KiB补丁已应用，system/vendor共10GiB清缓存完整读回通过，原工作系统关键状态不变；实际前缀可执行检查和隔离ELF64 adbd版本加载通过，整卡NoROM gzip完整分段校验通过。仍待物理换卡启动，未验收ART64/MT64及RA32/PPSSPP32共存，不替代v6b。

2026-10-31 [双ABI入口修正版P1a](RG34XXSP_DUALABI_ENTRY_P1A_20261031.md)：32KiB修正、完整8GiB读回及整卡NoROM压缩校验通过，但第二次首启仍静态Logo/无USB。卡上日志证实ramdisk在切根前无法通过绝对软链接的init检查；实际proc已由ramdisk挂载，先前单层入口改良不是当前故障证明。待改相对链接并匹配兼容分区别名；原工作卡和v6b保留，ARM64/模拟器共存未测。

2026-10-31 [独立双ABI备用卡P1](RG34XXSP_DUALABI_SPARE_P1_20261031.md)：约960MB镜像的离线文件系统/覆盖/GPT/完整解压和启动输入检查通过；128G备用卡完整读回及缓存清理后的前段复核通过。首次物理首启停在厂商静态Logo，USB未枚举，尚不可用；待修正init一层软链接的启动命名空间入口。原64G工作卡未覆盖，v6b候选不变，ARM64应用和模拟器共存仍待验收。

2026-10-31 [独立双ABI原型窗口关](RG34XXSP_DUALABI_PROTOTYPE_20261031.md)：新增独立产品/输出，32/64图形组件和ARM64专用验收APK已构建；原机私有namespace内ELF64窗口两次完成Mali-G31/EGL1.4、swap及退出，第二次取得绿色合成截图，原系统关键状态未变。物理面板反馈、ART64应用和模拟器共存仍待测。用户另提供卡槽2的128G卡并允许格式化，仅限该备用卡；尚未写卡，v6b和当前64G工作卡继续保留。

2026-10-30 最新候选为 [v6b 含 MT](RG34XXSP_V6B_MT_20261030.md)，检查点 `baseline/rg34xxsp-v6b-mt-norom-20261030`。八款预装，离线文件系统/组件/范围/gzip 校验完成，无 ROM/BIOS/账号/存档；未刷卡、首启和冷启待验收。v6a 保留为上一候选。当前处于总计划 A10-P3 收尾与 P4 初期，未达到正式发行验收，见 [剩余工作对照](DEVELOPMENT_GAP_REVIEW_20261030.md)。

日期：2026-10-28，Asia/Shanghai。标签：`baseline/h700-v5i-usb-network-20261028`。

2026-10-30 新镜像候选：`baseline/rg34xxsp-v6a-norom-20261030`，见 [v6a 封装报告](RG34XXSP_V6A_IMAGE_20261030.md)。专供 RG34XXSP / H700 / 2GB，加入当前系统增量、原六款与天马 G，含主题/媒体/ARM32 配置，**没有 ROM、BIOS、账号或存档**。压缩包约 3.43GB，文件系统、组件、范围和完整解压 SHA 通过；没有刷卡，首次安装与冷启动待验收。此前“旧 IMG 未更新”只描述保留的 v5i；该基底仍不可被说成已内含本轮增量。


2026-10-30 用户实测确认[首批预装名单](FIRST_PREINSTALL_BATCH_20261030.md)：QQ 音乐 TV、Animeko TV、PPSSPP、RetroArch（RA）、NOVA、KOReader。**NOVA 改以手机/平板模式为预装要求，TV 模式显示不全**；旧 TV/mdpi 记录仅描述历史测试。本次只登记名单，没有改设备设置或重封装 IMG，其他应用不纳入首批。

同日[MT 安装与应用清理](RG34XXSP_MT_CLEANUP_20261030.md)：官方 MT 2.26.10 已安装，常用文件操作通过远程控制器事件初测，底栏及侧栏顶部仍有焦点断点，未通过全程十字键验收。备份后卸载 11 款未入选/采样应用，首批六款与系统服务保留，约释放 1.14 GiB 设备空间；没有重封装 IMG。

最新检查点：`baseline/rg34xxsp-menu-landscape-20261029`，见 [Menu 与强制横屏](RG34XXSP_MENU_LANDSCAPE_20261029.md)。Navigation v8：Menu 短按 HOME、长按约 0.7 秒快捷设置，十字键分页、A 确认、B 收起；系统横屏默认开启并记住偏好。微信读书已验证完整 720×480 重排、左右翻页及开关恢复竖屏；两次内核重启覆盖默认开启和关闭偏好保留。原 IMG 未更新，实体按键手感待用户复核。

此前检查点：`baseline/rg34xxsp-select-hold-20261028`，见 [Select 长按鼠标记录](RG34XXSP_SELECT_HOLD_20261028.md)。鼠标现用 **Select 单独按住至少 2 秒后松开**，旧肩键组合已移除；Navigation v7 是保留数据安装的更新包。之前的 v6、模拟器与电源盘点见 [上一轮记录](RG34XXSP_INPUT_POWER_EMULATORS_20261028.md)，各冻结点和测试按各自版本理解。

2026-10-29 用户已确认实体 Select 长按呼出、移动和 B 关闭；四肩键按用户明确顺序采样，与当前 Android 映射一致，本轮未交换肩键。旧三键组合不稳定的根因仍未查明。

2026-10-29 [硬件链路对照与实体验收](RG34XXSP_HARDWARE_CHAIN_20261029.md)：电源键熄屏/唤醒和 A 解锁、QQ 音乐 TV 外放与实体音量键通过；亮度设置、合盖熄屏失败。厂商 hallkey 已实测开合 1→0→1，传感器能报告；Light HAL 与 Bluetooth 主包存在集成缺口，常驻 bringup 锁仍需审查。耳机、拔线/充电、深度挂起和断电冷启待测，原 IMG 未更新。

盘点先冻结为 `baseline/rg34xxsp-hardware-audit-20261029`。随后单独加入 [合盖控制](RG34XXSP_LID_20261029.md)，当前数据应用已启用真实 Hall 读取；三轮受控信号验证 Android 合盖睡眠、开盖唤醒及重复事件处理。新服务的实体开合仍待用户复核，disp 持续显示背光值和 IRQ、内核 bringup 锁未解除，不能视为深度待机完成。该项不含亮度或蓝牙修复。

最新应用级检查点：`baseline/rg34xxsp-small-screen-apps-20261028`，见 [小屏应用筛选](RG34XXSP_SMALL_SCREEN_APPS_20261028.md)。新增 KOReader 可选用户补丁及 9 个 APK 的初测/版本锁；系统二进制、屏幕密度和原 IMG 未更新。KOReader 的 EPUB/CBZ 常用路径、Nova 预配置后的 MKV 路径有远程事件与画面证据，不表示所有功能或实体使用通过。

2026-10-29 增补[微信读书墨水屏版](RG34XXSP_WEREAD_20261029.md)：官方 2.1.2 / armeabi-v7a 已登录补测，正文字号调到 19、UI 调到“小”；控制器 HAT 左右翻页、B 返回、虚拟鼠标工具栏/目录及进程重启同页续读通过。该应用初测时横屏未跑通，随后已由上述系统横屏补丁解决正文重排；目录焦点仍有缺口，未认定为全程十字键阅读方案。

## 结论与版本边界

当前实机可以继续开发。源码冻结后，按用户指令清理了旧阶段、旧文档和失效工具，又整理了 WSL 空间与镜像无损压缩；当前检查点为 `baseline/h700-storage-trim-20261028`，原源码冻结标签不变。基线仍是 **v5i/native35 + 新机 USB ConfigFS 和网络检测配置**，没有引入新产品功能。首轮清理明细见 [清理记录](CLEANUP_20261028.md)，第二轮见 [空间复核](SPACE_REVIEW_20261028.md)。

原 `out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx.img` 为 32,434,554,368 字节，SHA-256 为 `3fd34fef4d5a2275f14023dba5dc488330ab0669a50889e8b748e30c9f3e68cd`。它未上传、未重新加入 USB/网络修复封装。

## 实机验证

| 项目 | 结果 |
| --- | --- |
| 设备 | 用户提供的 34xxsp / H700 / 2GB / 双摇杆，实际 `MemTotal=2027136 kB` |
| 产品名 | 仍报告 `RGSP H700` / `rgsp`，不能区分新旧实机 |
| USB | UDC `5100000.udc-controller`；ConfigFS + FunctionFS；ADB 与 MTP+ADB 在 Windows 正常枚举 |
| Wi-Fi ADB | 当前开发卡经恢复引导启动，只允许指定电脑 IPv4，拒绝 IPv6 TCP 5555 |
| 网络 | HTTP、HTTPS 均实际返回 204；`VALIDATED`，`partialConnectivity=false` |
| 持久性 | 一次完整内核重启，USB、Wi-Fi ADB 自动恢复，网络再次验证通过 |
| 一致性 | 原 v5i 的 42 项组件 SHA 全部匹配；新增 3 个配置文件；system/vendor 只读 |

真实序列号、MAC、地址、boot ID 和原始日志保存在本地保全目录。旧历史脚本可能保留原实验室地址/身份保护常量，不能直接在新机器执行。此冻结点没有把这些原始身份保护代码改成通用机型配置。

### USB 与网络根因

内核已有 UDC、`CONFIG_USB_CONFIGFS`、`CONFIG_USB_F_FS`，但原初始化使用 `sys.usb.configfs=0` 的旧 `android_usb/android0` 路径，没有 gadget 和 FunctionFS ADB 端点。`h700-usb-configfs.rc` 建立 gadget、FunctionFS、MTP 权限与 Windows OS 描述符，功能切换继续由原生 init 与 UsbDeviceManager 管理。

网络原始证据为 HTTP 204 正常，默认 Google HTTPS 检测连接重置/超时。新地址先在设备上通过真实 HTTP/HTTPS 请求，再写入设置并重连，随后变为 `VALIDATED`。`h700-network-validation-defaults.sh` 只为未设置项提供默认值，不关闭检测、不覆盖已有自定义值。

当前卡另保留两个离线恢复文件，用于 USB 修复前恢复 Wi-Fi ADB；它们未加入新的产品出厂复制规则。卡后来增加了其他文件，原 36KiB 调试块补丁的整分区回退前提已不成立，不能直接重放 `before.bin`。

### 冻结点之后的开发

冻结层与上述 42 项比较结果仍描述原检查点。当前分支与实机随后加入 AT4K 菜单、双摇杆和同图锁屏修改，已不再与原 42 项逐项相同；具体源码、签名迁移、构建与验收边界见 [RG34XXSP 开发记录](RG34XXSP_DEVELOPMENT_20261028.md)。这没有更新原交付 IMG，也没有改写冻结快照。

## 原 v5i 完成的软件范围

- 简体中文、语言切换保留电视键盘、硬键盘存在时显示软键盘、Wi-Fi 密码输入。
- A 解锁、首次 HOME 选择器、原生电源菜单的方向/A/B 操作。
- 设置对话框、长列表、搜索、主题、服务行身份及无障碍清理竞态。
- Files 工具栏/侧栏、排序、视图、编辑、复制/移动/压缩；增删改只用自有夹具。
- 修正虚假触屏能力声明，恢复原生工具栏的按键可达性。
- 分数软件 VSYNC、副屏电源隔离、启动异常缓冲隔离；旧 RGSP 有重启与 15 分钟按键压力证据。
- 本地 Wi-Fi 不因互联网检测失败而被临时禁用。

原观察清单含 525 路径、3234 控件、219 项复核记录；219 不是未修复错误数，也不是所有路径都在最后二进制上从头重跑。

## 未验收与限制

- 冻结点未包含双摇杆适配；后续已接入四轴，用户确认双摇杆、十字键和虚拟鼠标正常，量化端点及 L3/R3 按压未单独验收。
- 本轮是正常重启，未验证断电冷启动；首刷中文/IME/HOME 人工流程与两机画面仍需分别记录。
- 硬件 VSYNC 事件未恢复；仍用软件周期。新机亮暗变化不能由日志/截图判定已彻底消失。
- 设置教学视频被关闭以避开硬解崩溃，未修复通用硬件视频解码器。
- 内核 FTRACE 未启用，Traceur 录制未验收。
- MTP 接口枚举通过，完整文件传输未在本轮验收。
- 恢复出厂、格式化、清数据、卸载、保存锁屏凭据等破坏性正向动作没有作为导航验收执行。
- 无硬件功能、外部应用完整业务、认证和全部外网帮助不由设置入口可达性通过推出。

后续优先双摇杆采样、冷启动和显示观察，针对新问题最小修复，不重放已关闭的历史失败。本轮清理仍保留唯一镜像、最终阶段、上游输入与 WSL；独有输入的外部私有备份仍需另外安排。

2026-10-30 增补 [天马 G / GBA 实测与预装](RG34XXSP_PEGASUS_GBA_20261030.md)。官方 ARM32 前端、主题/元数据适配、独立 LCD3x 配置及 NuPlayer 预览修复已在现机验证；新镜像封装另计。`out/pegasus-gba-20261030/` 与本地保全同名子目录保存 APK、原始材料、测试/回退输入，不能按缓存删除；ROM 不上传 Git、不加入新镜像。

2026-10-30 [ARM64 小范围验证](RG34XXSP_ARM64_FEASIBILITY_20261030.md)：静态 AArch64 程序在当前内核真实执行通过，候选 64 位 Mali 与双位数 Gralloc 源码存在；现机标准 64 位运行库路径缺失，尚未通过 ARM64 Android 应用/图形或双 ABI 共存测试。没有改写当前图形栈或 v6b 镜像，风险仍需下一阶段隔离动态加载与 EGL 验证关闭。

2026-10-30 [ARM64 隔离 EGL 验证](RG34XXSP_ARM64_ISOLATED_EGL_20261030.md)：真正共享运行库、Mali dlopen、EGL1.4、Mali-G31 16×16 离屏清屏/读回通过；未替换系统库或改写 v6b。窗口显示、Gralloc/HWC/ART64 和双 ABI 应用共存仍未验收。
