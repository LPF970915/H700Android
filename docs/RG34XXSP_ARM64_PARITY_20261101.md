# RG34XXSP ARM64 Parity Test2（2026-11-01）

本轮按用户要求，将最新 ARM32 掌机行为逐项迁入独立 ARM64/GSI10 候选，并把第三方预装改为 ARM64。仅供 **RG34XXSP / H700 / 2GB** 测试。不是完整 BSP64 全源码 framework/ART 重建，也尚未完成新镜像刷卡首启验收。原64GB工作卡、ARM32 v6b、ARM64 Test1及各冻结标签不变。

## 交付与使用

最终文件、精确字节数及 SHA256 以本目录的 [image-lock.json](baselines/rg34xxsp-arm64-parity-test2-20261101/image-lock.json) 为准；镜像只留本地，不上传 Git。最终输出目录为 `out/dualabi-parity-test2-20261101-final/`。同名前缀但没有 `-final` 的目录是保留的中断压缩草稿，不能刷写。

建议专用 **64GB或更大TF卡**，解压后的原始镜像为32,434,554,368字节，部分标称32GB卡无法容纳。整卡刷写会覆盖所选目标卡，请保留原工作卡；本轮没有代用户写卡、格式化或清数据。首启保持供电，等扩容可能的自动重启及七款应用安装结束，再验收。此前在已有Test1上的运行测试不能代替这一步。

离线封装已全部通过，检查点 `baseline/rg34xxsp-arm64-parity-test2-20261101`：

- 文件：`out/dualabi-parity-test2-20261101-final/H700_RG34XXSP_2GB_ARM64_Parity_Test2_20261101_NoROM.img.gz`
- gzip：3,625,312,847字节（约3.63GB / 3.38GiB）；SHA256：`c78592fe8ae9c39870f632d37ee4bcb9f504847fac080cd27fbb8c489777ba39`
- 解压后：32,434,554,368字节；SHA256：`d5771037065c7ddc8beb6f35f8568aa470f2dd2740643e16cfd5b86366d1233a`
- 3,746项文件/权限/标签回读、system/vendor e2fsck、APK签名/共享UID、关键运行库保护、4段范围与完整gzip解压通过；没有新的32GB整卡raw副本。

## 已封装的系统行为

| 范围 | 本次集成 |
| --- | --- |
| 锁屏与电源菜单 | GSI SystemUI仅移植两个窗口类的A解锁、原生焦点、HAT/方向事件；其余资源及类经比对保留。Navigation12检测原生补丁标记后将锁屏A/电源焦点交还SystemUI，避免重复代理边框；保留B取消及旧Test1回退路径 |
| AT4K | 保留最新93041269…锁定APK，包括菜单字号、滚动和原生按钮焦点；锁屏/桌面壁纸初始化链路保留 |
| Menu与鼠标 | Menu短释放回桌面，单独长按约700ms展开快捷设置；十字键分页、A确认、B收起。Select单独长按至少2秒后释放呼出鼠标，十字键/双杆移动、A点击、B退出；旧肩键组合不恢复 |
| 设置与系统应用 | Settings、DocumentsUI、LatinIME、权限、安装器、搜索、日历、联系人、Traceur、MediaProvider按GSI资源符号重定位；Settings三处FaceManager调用另按实际GSI API补userId。无面部硬件支持声明 |
| 输入法与资源 | native35 Leanback设为默认，硬件键盘存在时仍显示软键盘；迁入TV/永久十字键/非触摸默认/导航栏/溢出菜单/应用选择器布局。静态RRO通过实际idmap2映射且未关闭策略检查，首启启用情况仍待验证 |
| 框架服务 | services局部移植横屏、语言切换保留Leanback、ROMS可见性和不支持OEM解锁的后端；其余6088类比较通过。GSI framework.jar、ART32/64、JNI32/64、Mali/SurfaceFlinger和bootstrap保持原件 |
| 存储 | 单独编译ARM64 vold，冻结的p8几何/名称/GPT类型保护保留；动态依赖闭包与Binder协议审计通过，没有替换全局GSI库。恢复vold发现及ROMS交接；新卡上实际挂载、天马G首次部署仍待验收 |
| 横屏、合盖 | 集成H700Rotation默认开及偏好保留、H700Lid真实Hall电源API链路；bringup唤醒锁保留，不能称为内核深度待机通过 |
| 视频框架 | 只补已有OMX及OMXStore的VINTF声明，保持软件解码配置。当前Test1增量上NOVA此前的MediaCodecList崩溃经此修复后正常重启并启动；未声称硬解完成 |

原ARM32/GSI有4347个同名framework资源ID不同、平台签名也不同，因此没有整体复制旧SystemUI/framework，或把旧签名包强装到现机GSI上。新离线候选统一项目开发签名角色，保留原GSI SELinux签名映射并增加项目证书别名；所有系统APK在API29验证，共享UID证书集合一致。两项GSI CTS夹具不纳入镜像，其中私有shim原件缺完整签名块；未降低其他包的验证要求。原型测试APK、RA32测试载荷、诊断核心与cube不预装。

## 七款ARM64预装

| 应用 | 锁定版本/方式 |
| --- | --- |
| Animeko TV | 6.4.0，官方arm64-v8a |
| NOVA | 6.6.2，官方arm64-v8a；预设手机/平板模式 |
| KOReader | 2026.07.1，官方ARM64；保留可选十字键用户补丁 |
| 天马G / Pegasus | alpha16-112-g2a13b4f4，同提交官方android64；主题/媒体/604条元数据保留 |
| RetroArch | 1.22.2 aarch64，包名com.retroarch.aarch64；ARM64 mGBA/gpSP/VBA-M、控制器配置、LCD3x设置和启动元数据同步 |
| PPSSPP | 1.20.4，官方通用包，安装时强制arm64-v8a |
| MT管理器 | 2.26.10，官方通用包，安装时强制arm64-v8a；部分入口仍需虚拟鼠标 |

[APK来源/签名/ABI锁](../config/pegasus/preinstall-apks-arm64-test2.json)、[ARM64核心锁](baselines/rg34xxsp-arm64-parity-test2-20261101/arm64-cores-lock.json)。QQ音乐官方TV9.0.0.39目前取得的包只有armeabi-v7a，按用户“直接安装64位”的要求暂不预装，不自动换手机版或回退32位。旧ARM32八款预装锁不修改。

无游戏ROM、BIOS、账号、阅读数据或存档。媒体是既有锁定工厂资源，不能据604条目录元数据推断有604个游戏。应用在首启从只读payload安装至data，并核对安装APK哈希及primaryCpuAbi；配置只补缺失文件，后续用户选择不覆盖。

## 已检查与尚未检查

离线分区逐文件SHA、root属主、mode、SELinux标签、两分区e2fsck退出0、系统APK签名/共享UID、关键GSI运行库/链接、最终API符号检查零缺失均通过。压缩包完成情况只以最终镜像锁为准。开发始终使用低压力包装器：CPU0-1、合计单核、-j1、nice19、RAM6GiB、swap512MiB、idle I/O，没有调整电压或超频；主机没有可读取的电压测量。

已有Test1增量上的检查（**不是新Test2首启**）：七款应用实际进程均观察到ELF64与启动画面；NOVA修复后手机模式启动；RA64官方2048核心实际渲染、scan311 Start与HAT下移动通过，切到PPSSPP再返回保持相同进程/核心且无新增RA崩溃；PPSSPP64官方cube三秒画面变化130461像素，RA仍驻留。诊断文件不在镜像。RA首次默认配置曾有一次后台SIGSEGV，绝对路径/完整工厂资源复测通过，但尚不能认定该崩溃唯一根因已定位。PPSSPP/MT探针中的旧RA崩溃缓存不应误记为它们自身崩溃。

用户已确认Navigation运行更新后物理A能解锁；此前“仍需Y”的冻结记录保留。新的SystemUI原生解锁路径、电源菜单、全部移植系统APK及其组合必须在这张新镜像上复核，不能沿用旧增量的通过结论。

刷机后优先验收：

1. 干净首启扩容、AT4K与七应用安装/ABI、ROMS挂载、默认中文/输入法/手机模式、重启后配置保持。
2. 物理A解锁；长按电源四项的十字键/A/B；设置、文件选择器、权限、安装器及键盘焦点。
3. Menu短按/长按快捷设置；Select长按鼠标、十字键及双杆方向/松手停止；桌面菜单滚动、字号与按钮焦点。
4. 横屏开关/偏好、锁屏同壁纸、合盖睡眠/开盖唤醒、实体声音与耳机、冷启动和安装中断恢复。

亮度、蓝牙、Google登录/组件集成、硬件视频解码、内核深睡、1GB机型和完整游戏性能/长时间稳定性仍未完成。MT部分控件焦点缺口保留。Test2是可刷写测试候选，不能称为正式发行验收完成。

## 构建、证据和保全

工具入口均为 `tools/build_h700_low_pressure.ps1 -Targets <目标> -Execute`。本轮依次进行Parity输入比较、Apps/Ui/Services/Overlay、Vold及审计、SettingsApi/Linkage、Payload/Stage、Interaction12、Final、Seal、Image；不是把历史prepare脚本按日期盲重放。保全目录已存在时工具拒绝覆盖，重新构建需另外明确新工作目录，不能删除现有目录来重跑。

此次Stage2的system已回读通过，但旧debugfs工具重复mkdir已存在vendor目录导致孤立inode，fsck拦下。Final新阶段重用已验证system、从精确父原件重新生成vendor，修正mkdir和标签文件命名，全部重新回读；未对失败vendor做自动修复来绕过检查。新的Stage3入口包含该修正。随后Seal另拷贝system，只修安装complete标记在重启后恢复运行属性的窗口，host分支测试及fsck通过；完整断电恢复仍未实测。中断压缩草稿、错误exec-out/CRLF读取、早期APK/API/overlay失败候选均留存，不能混入交付目录。

保护 `out/dualabi-interaction-20261101/`、`out/dualabi-parity-20261101/`、`out/dualabi-parity-test2-20261101/`、`out/dualabi-parity-test2-20261101-final/` 及WSL `/home/lpf/h700-dualabi-interaction-20261101/`、`/home/lpf/h700-dualabi-parity-20261101/`。当前实体128GB仍是已有Test1加运行增量（Navigation11/Leanback/七ARM64应用/媒体声明修复），不是Test2；未卸载其RA32比较安装。原64GB在设备外保存。诊断trace和USB常亮恢复0。原始身份、日志、截图、APK/JAR、私钥及镜像不提交，只发布自有工具和脱敏锁。
