# RG34XXSP 独立双 ABI 原型

2026-10-30 开始，跨日继续。本记录先冻结独立产品与 ELF64 窗口关，**ARM64 APK 和双 ABI 整机仍待启动原型后验收**。前置为 [ARM64 隔离 EGL](RG34XXSP_ARM64_ISOLATED_EGL_20261030.md)。v6b、工作卡与源码冻结层继续保留。

## 产品与验证顺序

新增 `device/roc/rgsp64proto`，产品 `h700_rgsp64proto-eng`，独立输出 `/home/lpf/h700-dualabi-prototype-20261030/out`。继承现有硬件配置后，仅在新 BoardConfig 中选择 ARM64 主架构和 ARM32 次架构；产品优先继承 `core_64_bit.mk` 选择 `zygote64_32`，不改现有 ARM32 BoardConfig。构建系统实际识别 API29、arm64-v8a、armeabi-v7a/armeabi 和 64 位 Binder。配置已识别不等于这些运行时已启动。

原型保留 `ro.product.device=rgsp` 供已有输入/导航/合盖服务的明确机型守卫使用，另设 `ro.h700.prototype` 和不同产品型号，避免因为编译产品目录改名导致服务被跳过。仅供 RG34XXSP H700 2GB；不放宽任何旧设备身份守卫。

第一关为自有、最长 30 秒的 256×192 窗口探针，连接现有 SurfaceFlinger，经 EGL window surface、GLES 清屏/读回、eglSwapBuffers，再核对实际合成截图和窗口移除。数据侧隔离 rootfs 使用自建 ELF64 依赖、候选 Mali、64 位 Gralloc/mapper；原系统和 vendor 不替换。文件系统隔离不能隔离 GPU 内核驱动错误。

第二关才是 ARM64 Android 应用。自有 `H700AbiProbe64` APK 仅带 ARM64 JNI，界面打印 ART/JNI 位数，使用 GLSurfaceView 并提供方向键可达的返回按钮；该探针不加入正式八款预装名单。完整验收需要真实 ARM64 ART/应用进程，不把 native ELF64 窗口或单纯 APK 打包成功算成通过。

第三关是在同一双 ABI 环境中验证现有版本 RA ra32 和 PPSSPP ARM32 的启动、渲染、返回、交替运行与内存。原机查询确认 RA 1.22.2_GIT、PPSSPP v1.20.4 当前均为 armeabi-v7a；这只是测试前身份，不是共存通过。原型中安装通用版 PPSSPP 时应明确选择 ARM32，避免默认选到 ARM64 后失去对照意义。不改现有账号/ROM/存档，不把它们放进镜像或 Git。

## 构建入口与保护

`tools/build_h700_low_pressure.ps1 -Targets H700DualAbiWindow -Execute`。准备器只同步新原型目录，对原有产品/关键 Gralloc 源码做写前写后 SHA 比较；原型目录已有不同版本先保留逐文件备份。所有编译经固定低负载入口，合计单核、CPU0–1、-j1、nice19、6GiB RAM、512MiB swap、空闲 I/O、每次最多3小时。

首轮完整 Soong 构建图生成触发持续 MemoryHigh 回收，18分19秒后主动终止，保留日志和中间产物；不是 OOM，也没有成功完成标志。随后仅对新原型目标将 GOGC 从50降到10，维持全部资源上限，不修改基础构建工具源码。主机仍没有可读取的电压测量，不能据负载限制宣称已验证供电安全。

下一轮在1分43秒明确报告旧 NDK r18 不提供 `ndk_crtbegin_so.29`/`ndk_crtend_so.29`；JNI 库改用已核对存在的 API28 NDK CRT，不使用新 native API。Java/APK 仍以 API29 编译并要求 Android10；这项构建修正不代表 APK 已在 ARM64 ART 上运行。

随后 Make 阶段发现厂商无线配置脚本通过 sed 扫描当前 BoardConfig，不求值嵌套 include；原型显式列出 Realtek/RTL8821CS 选择器后，越过错误的旧 wpa_supplicant 路径。仅改原型，不改旧板级配置。准备器跳过字节相同文件，保留 mtime，避免无变化重试反复生成整个图。

实际 ARM64 编译又发现原 Gralloc 四个 `%lld/%llx` 参数类型错误（LP64 的 uint64_t 为 unsigned long）。原型准备器从保留 BSP 复制小型 Gralloc 源码至产品私有 `gralloc-variant`，只修正这些日志格式与参数转换、改模块名为 `gralloc.h700proto`；保留全部上游声明并锁定原始/派生文件 SHA。原源码逐字节未改，保持 -Werror。原型产品通过 `ro.hardware.gralloc=h700proto` 选该模块；当前卡的隔离 rootfs 另提供 cupid 文件名兼容已有属性。ARM64 问题源文件的目标对象已实际编译通过，整体模块/运行时仍待完成。

窗口控制器 `tools/test_h700_dualabi_window.py` 默认只输出计划；`--execute` 要求 USB 精确身份、rgsp/rg34xxsp profile 与 root 均匹配、逐项 payload SHA 匹配、远端目录不存在。只部署自有 data/local/tmp 路径，先测试挂载守卫，再创建私有挂载 namespace/chroot。等待真正首次 swap 后截图，小窗保持30秒，45秒强制超时后备。通过条件还包括 SurfaceFlinger 窗口存在/消失、截图绿色像素、核心 PID/boot/系统库哈希/父挂载表完全一致。截图是合成窗口证据，面板肉眼观察单独记录。

`out/dualabi-prototype-20261030/` 和上述 WSL 输出保存产物、私有原始证据、源文件备份和失败阶段，不作为普通缓存清理。只发布自有源码、脱敏锁与结论。窗口阶段不写卡、重分区、重置，也不在当前系统增加第二 Zygote 或修改 ABI 属性；后续备用卡授权范围见下文。

用户随后明确提供卡槽2的128G卡并允许格式化。只读确认其为未承载当前系统挂载的第二张卡，当前系统、vendor、data 均在另一张约64G卡上；CID/设备路径/原布局保存在本地私有记录，不公开。该授权仅限这张备用卡，不包括当前工作卡。尚未格式化或写卡，后续必须再次核对设备与卡身份、挂载/占用及候选校验。

## 当前验收状态

| 门槛 | 状态 |
| --- | --- |
| 独立产品配置、主次架构、Binder | 已由构建系统识别 |
| 自建窗口依赖和探针 | ARM32/64 窗口程序、Gralloc、mapper、linker、Bionic 实体库构建完成；ELF64 隔离包69项 |
| 原机隔离 ELF64 窗口、Gralloc/mapper | 两次 Mali-G31 / EGL1.4、RGBA=0/255/0/255、swap和退出通过；第二次取得720×480合成截图，父挂载表/boot/核心PID/关键SHA不变 |
| 物理面板/HWC验收 | 已出现真实SurfaceFlinger图层并取得合成截图，肉眼显示与闪烁反馈待用户确认；截图不代替物理验收 |
| 真正 ARM64 APK/ART64 | 待测 |
| ARM64 应用与 ARM32 RA/PPSSPP 共存 | 待测 |
| 可启动双 ABI 镜像、独立卡首启 | 未完成/未执行 |

这些门槛按顺序关闭；前一项失败则保存证据并定位，不跳过它声称后续通过。

## 窗口结果与排错边界

最初仅构建普通 libc/libdl/libm 名称，得到的是 APEX 链接桩或未安装实体；准备器拒绝缺失依赖，没有将桩部署。改为显式构建 `libc.bootstrap`、`libdl.bootstrap`、`libm.bootstrap`，并补上供 Gralloc/Mali 运行的 GLES1 与 zlib 实体后，递归依赖闭合。所有部署 ELF 为 AArch64，ld-android 链接桩不部署，由真实运行 linker 提供其符号。

APK最初作为系统模块生成，JNI位于APK之外；已启用嵌入JNI。最终APK内仅有 `lib/arm64-v8a/libh700_abi_probe.so`，ELF64，仍没有在现机zygote32上尝试把它当作ARM64应用运行。

第一轮窗口退出0、图层出现/移除、核心状态不变，但截图失败。源代码对照确认旧ADB的exec-out无shell协议时会改用PTY，当前PTY返回No such device；普通shell保存PNG再pull的独立对照成功。保留首轮全部证据，远端逐文件SHA复核后，仅对已成功渲染的同一二进制再运行一次补截图。第二轮正常取得绿色小窗，控制器输出 `ELF64_WINDOW_SWAP_SCREENSHOT_AND_BASELINE_PASS`。没有修改旧系统PTY配置。

最后一次完整窗口准备约9分10秒、CPU7分56秒、内存峰值约5GiB、swap66.1MiB；先前的大量首次编译及失败阶段单独保留，不把此数当作全过程耗时。随后init/adbd目标也构建完成，约7分13秒；尚未用于启动或刷卡。全部编译保持原资源上限，已通过systemd-cgls核对构建子进程仍在该受限单元内。

下一阶段采用已固定SHA的官方Android10双ABI运行时构造独立试验镜像，加入H700启动/厂商输入和必要的64位图形组件，保留已建立的独立源码产品。它用于APK/32位模拟器共存验证；完整源码64位framework重建与系统功能回归另列，不据此认定生产64位迁移完成。
