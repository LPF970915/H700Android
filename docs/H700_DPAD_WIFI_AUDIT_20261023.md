# RGSP 无触屏导航、Wi-Fi 与 A 解锁检查

日期：2026-10-23—24，Asia/Shanghai。对象：序列号 `5c001089d750c872012`。

## 结论

**不能验收为“所有界面均可仅靠手柄操作”。** 设置的 14 个一级入口已检查，
初测 13 个能进入；“已连接的设备”和开发者选项曾因系统服务缺失退出。
后续已补齐 `usb` / `oem_lock` 并持久化，两个入口复测可进入，详见文末服务修复记录。
一级入口通过不代表其全部深层页面、控件和第三方应用已通过。

21:20 的历史统计中，深层页面已记录 120 个：66 个双向扫描完成、31 个纵向扫描完成，
13 个仍是中断时的 `RUNNING`，23 个存在候选焦点缺口，另有 1 个返回失败。
这些数量混合不同修复版本，不能用作最终覆盖率。截至 24 日 00:55 已执行三次软件整机重启，
最新 v15 导航及其他修复组件、A 解锁、服务和开关均保留；冷启动及整卡刷写未执行。
最新版信息行、双向列表边界、Wi-Fi 开关及 USB 调试开关已实际回归，v5g 候选整卡镜像已生成并完成离线校验。
深层菜单仍有未分类入口与未完成回归，不能宣称所有设置均通过，详见文末。

用户指出原有 Y 解锁，要求改为 A。已完成 RGSP 实体 A 的锁屏处理修复，并持久写入
设备 SystemUI；临时挂载试验和保存后的两次锁屏/唤醒/A 解锁均通过。
实体按钮的机械输入还待用户复核；本次通过 UART 对实际手柄 evdev 节点注入事件。
后续软件整机重启后的 A 解锁也已通过；未执行断电冷启动或整卡刷写。

Wi-Fi 开关、扫描列表、密码键盘、输入/退格、B 收起、A 重开及连接按钮聚焦通过。
已连回原网络，并实际建立 Wi-Fi ADB，执行 `id` 和设备身份核对。
但观察到一次约 10 分 28 秒的重连等待，不能验收重连可靠性。

## 设备和方法

- Android 10 eng，指纹：
  `ROC/h700_rgsp/rgsp:10/QP1A.191105.004/eng.lpf.20260906.180644:eng/test-keys`。
- CH343 `COM4`，115200 8N1、无流控、DTR/RTS 关闭。
  初始命令不通，XON/Ctrl-C/回车后获得完整 root shell；具体通信故障原因未定。
  之后逐字 30 ms 发送以减少丢字。普通 console=stopped，rgsp-console=running。
- 一级菜单均通过桌面入口、方向键、确认和返回进入；没有用直接启动 Activity
  或写入设置值代替入口可达检查。没有使用坐标点击、触摸或滑动完成验收。
- 先用 Android keyevent 检查页面，再对 `/dev/input/event1` 的真实
  `ANBERNIC-keys` 输入节点注入 HAT 和按键事件，补测完整映射路径。
  HAT_X/Y 为 ABS 16/17；A 为 scan 304→ENTER，B 为 scan 305→BUTTON_B。
  每个注入动作都释放按键或轴，避免残留长按。
- ADB 用于截图、日志和文件传输，按键测试通过 UART 发起。
- UIAutomator 曾出现 `could not get idle state`，旧 XML 没有作为后续通过/失败证据。
  改用新截图和当前 Activity 核对，后续 XML 读取先删除旧文件。

## 一级入口检查

| 页面 | 进入结果 | 证据或限制 |
|---|---|---|
| 网络和互联网 | 通过 | WLAN、飞行模式等可见，向下移至飞行模式；没有执行飞行模式 |
| 已连接的设备 | 修复后通过 | 初测缺少 `usb` 导致退出；服务修复后可进入配对、连接偏好设置 |
| 应用和通知 | 通过 | 可聚焦“查看全部 15 个应用”；未逐一安装/卸载 |
| 电池 | 通过 | 可移动至省电模式；未启用省电 |
| 显示 | 通过 | HAT 补测能聚焦深色主题；未改变显示参数 |
| 声音 | 通过 | 能移动至通话音量滑块；未改变音量 |
| 存储 | 通过 | 可见内部存储和 ROMS 96.91 GB；未格式化或弹出 |
| 隐私权 | 通过 | 能聚焦权限管理器 |
| 位置信息 | 通过 | 能聚焦“查看全部” |
| 安全 | 通过 | 可见当前滑动屏幕锁，能聚焦设备管理应用 |
| 帐号 | 通过 | 能聚焦自动同步选项；未添加帐号或改变同步 |
| 无障碍 | 通过 | 可见 RGSP D-pad Navigation 已开启；未改服务状态 |
| 系统 | 通过 | 高级项可展开，开发者选项入口可达 |
| 关于手机 | 通过 | 可滚动到版本号并连续确认 |

上述结果只覆盖入口、基本移动和返回。亮度弹窗、全部权限子页、语言排序、
文件选择器、安装授权、所有滑块、多选、长列表尾项及第三方应用内部页面未全覆盖。

## 初测失败与未解决的问题

以下均为 2026-10-23 上午的初测现象。`usb` / `oem_lock` 已在本日后续补齐，
两个入口复测通过；本节保留原始记录，修复过程见“补齐 Settings 依赖服务”。

### 开发者选项

路径：桌面设置→系统→高级→开发者选项。能聚焦并确认入口，随后白屏并退回设置。

日志：`OemUnlockPreferenceController` 初始化请求 `oem_lock`，
`SystemServiceRegistry` 报 `No service published for: oem_lock`；
随后 `am_wtf`、`Force finishing activity`、`force-crash`。

版本号连按显示“你已处于开发者模式”。本机为 eng，
`development_settings_enabled=null`，`adb_enabled=1`。
**没有证明从关闭状态首次启用，也没有证明开发者总开关或 USB 调试开关可操作。**
不能把串口启用 TCP ADB 当作开发者页面通过。

### 已连接的设备

`ConnectedDeviceDashboardFragment` 请求缺失的 `usb` 服务，随后 Settings
Activity 被强制结束。当前运行服务清单也未列出 `usb` / `oem_lock`。
上述为初测现象。两项服务均已按下文方案修复并在实机保存，页面退出问题已复测消失。

### Wi-Fi 重连与列表刷新

一次快速重新开启后约 7 秒连接成功；另一轮设备日志从 `10:34:20.293` 开启
到 `10:44:48.453` 恢复 CONNECTED，约 10 分 28 秒。
用户确认 Xiaomi_0421 始终开启。驱动日志还出现 SDIO RTO，原因未最终定位。
列表刷新期间还出现过原先选中网络后继续按 A 实际切换总开关的现象，
应专项复测扫描更新是否重置焦点。本次没有修复 Wi-Fi 驱动或列表刷新行为。

系统曾显示“连接受限/无法访问互联网”，联网探测日志有 Google 检测地址超时；
局域网 ADB 实际可用。没有把互联网检测失败等同于 Wi-Fi 未关联。

## A 解锁修复

原 Y 的 `BUTTON_Y` 经 Generic.kcm 回退 SPACE，SystemUI 会处理它。
A 为 ENTER，原锁屏在子视图分发时消费 ENTER。给 ENTER 添加 KCM fallback SPACE
的临时方案未通过，已撤销：没有保留设备专用 KCM，也没有改变最终键布局。

最终修改 `StatusBarWindowView.dispatchKeyEvent`，在子视图处理之前，限定：

- Build.DEVICE 为 rgsp；
- ENTER、scan 304，事件设备名为 ANBERNIC-keys；
- 正显示 Keyguard，且没有显示密码输入 bouncer；
- 未取消的 ACTION_UP 执行原有 `onSpacePressed()`。

普通应用和输入框不经过该分支；沿用系统原有解锁流程，没有清除屏幕锁或凭据。
Y 的原行为未移除。带 PIN/密码的认证路径没有实机配置和回归，不能宣称已验收。

源代码通过 `tools/prepare_rgsp_lock_confirm.py` 的哈希门控应用到本地 AOSP，
SystemUI 用 `tools/build_h700_low_pressure.ps1 -Targets SystemUI -Execute` 编译。
CPU 0-1、总配额一核、-j1、6 GiB RAM、512 MiB swap 限制保留。
构建成功，日志：`out/logs/build/h700-low-pressure-20261023-111427.log`。

安装前，设备 APK 和原本地构建 APK 完全一致。新旧证书 SHA-256 都是
`c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8`。
ZIP 条目对比仅 classes.dex、CERT.RSA、CERT.SF、MANIFEST.MF 内容变化，无资源变化。

| APK | SHA-256 |
|---|---|
| 原 SystemUI | `5b4fa0a16dd502df673c8b4abbdae54452b47ea46c7d86df39020cabd1a373b4` |
| A 解锁版 | `d83ba4fb106c5a3e4ddb3e1d6183572e49a6af44806f1e7c78d26a71f3ebce89` |

先临时绑定 APK、重启 SystemUI 单个进程，确认实体事件 A 解锁成功。
普通 `adb install -r` 因 persistent 系统应用限制被拒绝，没有安装数据分区更新。
随后解除临时绑定，通过 `tools/install_rgsp_lock_confirm.sh` 的设备、哈希、挂载
命名空间和只读根分区门控，原子替换原 SystemUI 文件，恢复其权限/标签和只读根分区。
只重启 SystemUI 进程，没有重启 Android。

保存后两轮电源锁屏→唤醒→实体节点 A 解锁均返回原显示设置页面。
A 普通确认→打开 WLAN、密码键盘输入、连接按钮聚焦也在保存后复测通过。

本次结果是**已写入系统文件且运行时通过**；整机重启后的加载仍未实测。
新的整卡镜像尚未重打包，历史 v5f 镜像不会自动包含这个修复。

## 当前 Wi-Fi 调试与回退

当前连接命令：

```text
adb connect 192.168.31.161:5555
adb -s 192.168.31.161:5555 shell id
```

`service.adb.tcp.port=5555`、adbd=running，已验证 shell 和设备身份。
仅允许电脑 `192.168.31.211` 到 TCP 5555，其他 IPv4 来源和 IPv6 访问该端口被丢弃。
这是本次临时启用，没有设置 persist 属性；重启后需要核对地址并重新开启。

原 APK 已保留在本机 `out/no-touch-audit-20261023/SystemUI.before.apk`
及设备 `/data/local/tmp/rgsp-a-unlock-20261023/SystemUI.before.apk`。
必要时，在此设备 root 串口执行以下明确的单组件回退：

```sh
sh /data/local/tmp/install-rgsp-lock-confirm.sh rollback
```

它检查当前 APK 是上述 A 解锁版，再恢复上述原 APK；不使用会影响其他系统应用的
`pm uninstall-system-updates`。安装/回退脚本在 `tools/install_rgsp_lock_confirm.sh`。

完整私有证据（截图、UART、运行服务、键布局、APK 和 Activity）存放于
`out/no-touch-audit-20261023/`。主要截图为 `a-fixed-persistent-lock.png`、
`a-fixed-persistent-unlock.png`、`a-fixed-second-lock-unlock.png`、
`post-fix-ime-open.png`、`post-fix-ime-text.png`、`post-fix-connect-focus.png`。

未收集保存的网络密码，未删除已有网络，未点击向其他网络实际连接。

## 2026-10-23 后续：补齐 Settings 依赖服务

用户要求先补齐服务，再对所有设置深层菜单进行方向键测试。本节记录已完成的服务修复；
深层菜单结果另按实际页面、控件和限制记录，不能由服务存在推导为全部导航通过。

### 实现与构建

`usb` 原因是产品没有声明 USB host feature，SystemServer 跳过 UsbService。
实机内核已有 EHCI/OHCI host 控制器和 `/dev/bus/usb`。新增
`configs/android.hardware.usb.host.xml` 并加入 `h700_rgsp.mk` 的 vendor permissions 复制项，
启动 Android 原生 UsbService；未伪造 USB 连接或配置状态。

`oem_lock` 原因是 RGSP 没有 OEM Lock HAL，也没有 `ro.frp.pst` 后端。
仅对 `Build.DEVICE=rgsp` 发布原生 OemLockService；无后端时采用
`RgspUnsupportedOemLock`，报告 carrier/device 不允许解锁，拒绝启用解锁。
没有创建 FRP 分区路径或执行 bootloader 解锁。开发者页面能查询能力，不再因服务缺失退出。

准备脚本 `tools/prepare_rgsp_settings_services.py` 对原始与已修改源码做哈希检查，
将产品文件和 OEM 后端复制到本地 AOSP。复现准备命令：

```sh
python3 /mnt/d/Works/H700Android/tools/prepare_rgsp_settings_services.py \
  --source /home/lpf/h700-android10/android
```

使用 `tools/build_h700_low_pressure.ps1 -Targets services -Execute` 编译成功，
保留 CPU 0-1、总配额一核、-j1、6 GiB RAM、512 MiB swap 限制。
日志为 `out/logs/build/h700-low-pressure-20261023-114759.log`。
实际 `OemLock` 基类上的后端测试验证了全 false 查询、启用拒绝和禁用幂等。

| 文件 | SHA-256 |
|---|---|
| 原 services.jar | `299d97f020f97ca4bfc400773870983f52df8fa8b036ae245640cdad58b04413` |
| 新 services.jar | `f370b5c4d80eec9e209fc4ed8592a858e2bc2bbfd5947aaadd847a683a86ad18` |
| USB host feature XML | `201da252a1ed52d5d1019412900d7a1cb530afb4558f9f1ba3d124189a1f9819` |

### 实机部署与验证

先临时 bind 挂载 jar 和 permissions 目录试运行，检查 framework 和两个服务，
再通过真实 HAT/A/B 打开“已连接的设备”与“开发者选项”，截图和运行时查询均通过。
随后用 `tools/install_rgsp_settings_services.sh` 原子保存服务 jar 与 feature 文件，
恢复根分区、vendor 分区只读并解除临时挂载。监视器记录 `watch-install=HEALTHY`。
保存后 `service check usb` 与 `service check oem_lock` 均为 found，文件哈希正确。

只重载 Android framework，没有整机重启。重载必须同时重启 netd，避免旧 netd 的 network ID
和新 system_server 不一致导致 Wi-Fi 有地址却无路由。脚本已包含该处理，并在重建 TCP ADB 前
恢复限定测试电脑来源的防火墙规则。重载后的 Wi-Fi ADB 已恢复，当前菜单测试使用保存后的 framework。

`dumpsys usb` 正常返回，实际报告 disconnected / not configured，host connections 为 0。
OEM binder 查询返回 `rgsp-unsupported` 和 false。USB 外设/数据线枚举没有实测，
OEM 解锁能力未实现，也不应将其标记为已实现。

备份位于本机 `out/settings-deep-audit-20261023/services.before.jar` 和设备
`/data/local/tmp/rgsp-settings-services-20261023/services.before.jar`。需要恢复时，在本机 root 串口运行：

```sh
sh /data/local/tmp/rgsp-settings-services-20261023/install.sh rollback
```

脚本检查序列号、命名空间、新旧哈希并恢复原 jar 和原本不存在的 feature 状态。
整卡镜像尚未重新打包，不能宣称历史镜像已经包含本次服务与 A 解锁修复。

### 深层测试中的误触及恢复（必须保留）

自动测试曾将“加密手机”的最终执行按钮与同名入口混淆，错误确认执行。
framework 随后重启，取证连接中断；后续分类的连接失败不是导航通过结果。
设备报告 `vold.encrypt_progress=error_not_encrypted`，`/data` 仍由原
`/dev/mmcblk0p7` 以 ext4 挂载。未做全量数据一致性校验，不能声称完全没有数据影响。
通过串口联合恢复 netd/framework 后，两个服务、默认路由、原 IP 和 Wi-Fi ADB 恢复。

已停止旧测试，禁止自动确认 Button/ImageButton 类执行按钮，拦截加密等动作，
并移除按任意 XML Intent 自动进入的逻辑。加密、格式化、恢复出厂、确认执行等
代表性按钮的保护检查已通过。剩余菜单使用该保护后的测试程序重测。

### USB 调试实际开关复测

通过真实 HAT/A/B 定位 USB 调试，按 A 关闭，串口读取 `adb_enabled=0`；
再按 A 显示“是否允许 USB 调试？”弹窗，右键先到取消、再次右键到确定，
核对弹窗标题后按 A 确认。串口读取 `adb_enabled=1`、`sys.usb.state=adb`，
adbd=running，Wi-Fi ADB 恢复。关闭期间 USB 状态为 mtp、adbd 停止，
使用串口临时重启 TCP adbd 取证；没有把该临时 TCP 通道算作 USB 开关启用的证据。
截图：`usb-debug-before-toggle-165852_501392.png`、`usb-debug-off-165954_634993.png`、
`usb-debug-confirm-focused-170021_338386.png`、`usb-debug-reenabled-170103_482975.png`，
均位于 `out/settings-deep-audit-20261023/`。

## 共性问题与共享修复（回归进行中，21:20 未收口）

可以在共享层修复多数设置页面的导航问题，但不能据此宣称所有深层界面均已通过。
本轮运行时版本为 `NavigationService.navigationVersion=10`；应用清单仍保留原工作区的
versionCode 4，不能只按清单版本号识别实现。原有鼠标代码保留，默认不接管 Select；
仅 `Settings.Global.rgsp_mouse_enabled=1` 时创建鼠标控制器。

| 共性 | 共享处理 | 验证边界 |
|---|---|---|
| 只依赖原生手机焦点，遗漏行内按钮/开关 | 设置、权限管理器、键盘设置、媒体设置统一收集可操作语义节点，并保留次级控件 | 按真实 HAT/A/B 遍历；未使用坐标点击补通过结果 |
| 列表滚动后跳回顶部栏 | 保留跨异步布局的滚动状态，从新内容边缘恢复焦点 | v10 主列表 90 步、80 个焦点签名到最终“图标形状”；总开关只出现在起始步骤，途中不再回跳 |
| RecyclerView/ListView 复用节点，同 ID 或同名控件混淆 | 稳定标题/文字结合 CollectionItemInfo 行列位置；唯一语义项移位时可保留焦点，歧义同名项不任意重绑定 | v8 证书列表覆盖 138 行，行号 0–137，无缺行；仅聚焦，未切换证书开关 |
| 一整屏禁用项目阻断后续菜单 | 设置中的禁用控件可聚焦阅读和继续滚动，确认与调值均明确拦截 | v10 聚焦禁用“日志记录级别”后 A 无跳转；可继续到强调色、字体和图标形状 |
| 确认键在旧节点上执行 | A 按下时记录语义身份，未取消的松开事件重新核对后才执行 | 列表更新时身份变化会拒绝此次确认 |
| 字号/密度变化导致旧值缓存、焦点丢失或重复调整 | 刷新节点、一次按键只执行一个范围动作、界面重建保留范围焦点、配置/窗口变化取消重复键 | v5 属性实测：字号 1.0→0.85→1.0；密度默认213→180→默认213，无残留覆盖；后续版本待最终回归 |
| 无导航栏造成菜单假设不合适；Fragment 声明菜单但工具栏为空 | RGSP 优先显示屏幕菜单；Settings 共享 Activity 只在菜单缺失时从当前可见 Fragment 补齐菜单 | VPN 添加入口已出现，右、右、A 可打开配置表单；未保存 VPN |
| 控制器被视为硬键盘；浮层交还焦点与 IME 请求竞争 | 允许有硬键盘时显示软键盘；输入框确认延迟到焦点交接后，重新校验实际输入焦点 | v6 VPN 名称框输入 Y、B 收起、A 重开均成功；退出时丢弃表单 |

Select 的 Generic.kcm 已有 Menu fallback，不能说设备完全没有菜单键功能。
旧鼠标试验逻辑会消耗 Select 短按，本轮改为显式启用，默认保留原系统后备映射。

### 菜单补丁的构建、安装和边界

新增 `RgspDpadMenuBridge.java`，由 `tools/prepare_rgsp_settings_navigation.py`
以已知原始哈希校验后应用到原生 SettingsBaseActivity。已有正常菜单时不补齐；
菜单项由原 Fragment 创建/准备/处理，保留它原有的权限与限制判断。
构建时还发现 AndroidX Provider authority 被 Settings/SystemUI 共用，更新安装被
`INSTALL_FAILED_CONFLICTING_PROVIDER` 拒绝。已将 Settings 的 authority 改为
`com.android.settings.lifecycle-process`，原生重编译及更新安装通过。

成功构建日志：

- Settings：`out/logs/build/h700-low-pressure-20261023-180843.log`。
- RGSPNavigation v7：`out/logs/build/h700-low-pressure-20261023-183147.log`。
- Settings 菜单和小屏弹窗策略：`out/logs/build/h700-low-pressure-20261023-184535.log`。
- RGSPNavigation v10：`out/logs/build/h700-low-pressure-20261023-185808.log`。

保持原有一核总配额、CPU 0-1、-j1、6 GiB RAM、512 MiB swap 限制。
SDK 构建附带的 10 项方向几何测试、7 项回收节点身份测试和指针尺寸测试通过；
它们不能代替实机菜单验证。新增源码触发旧版 Soong 内存节流时，停止该次构建，
将 Go 回收频率 GOGC 调至 50 后重试成功，没有放宽资源限制。

当前 Settings 和 RGSPNavigation 已安装由原生 Android 10 构建产生的平台签名数据分区更新包，原系统 APK 保留。
框架菜单配置使用已启用的运行时 overlay，且同一默认配置已写入 RGSP 产品 overlay；
软键盘设置已在实机保存为 1，产品 SettingsProvider 默认 overlay 同步为 true。
没有重新刷写整卡，也没有验证冷启动。

构建输入准备会检查已有源码，拒绝覆盖无法识别的改动，并在原生源码的
`out/rgsp-settings-navigation-inputs.json` 记录本次同步哈希，以供后续增量校验。

```powershell
py tools/prepare_rgsp_settings_navigation.py --source \\wsl.localhost\Ubuntu\home\lpf\h700-android10\android
./tools/build_h700_low_pressure.ps1 -Targets Settings,RGSPNavigation -Execute
```

本轮备份及更新包的 SHA-256 见 `out/settings-deep-audit-20261023/universal-artifacts.json`。
原包为 `Settings.before-menu-bridge.apk`、`RGSPNavigation.before-universal.apk`。
导航包可通过平台签名原包 `adb install --no-incremental -r -d` 回退。
Settings 原包带冲突 authority，不能依赖重新安装该原包回退；Android 10 源码确认
不带 `--user` 的 `pm uninstall -k com.android.settings` 会回退该系统应用的更新并保留数据，
但本轮没有执行回退验证。不要使用清除 Settings 数据或卸载全部系统更新的命令。
运行时菜单 overlay 可用 `cmd overlay disable --user 0 com.roc.rgsp.dpad.frameworkoverlay` 停用；
本轮前 `show_ime_with_hard_keyboard` 为 0。

### 尚未解决或不能泛化的界面

- 图案锁是绘制控件，当前方向键扫描只能到“重新绘制”，不能记为图案输入可用；未设置锁屏凭据。
- VPN 小屏横向弹窗已加 pan 适配，名称框在键盘展开时可输入、可见；多字段弹窗加键盘的极端布局未逐一回归。
- **存储页焦点缺陷，v11 已修复，回归未全收口**：原焦点落到只提供 RangeInfo、
  没有调节动作的 `android:id/progress` 上，触发 `Vertical walk limit`。
  共享规则现只把 SeekBar 或声明调节动作的范围控件作为滑块目标，保留禁用滑块的只读可达性。
  实机已到达各存储分类和底部“系统”；四方向图仍有待验证边，不记整页完全通过。
- **存储加密状态未收口**：自动测试曾误确认“加密手机”执行按钮，framework 随后重启。
  设备现报 `vold.encrypt_progress=error_not_encrypted`，`/data` 仍由 `/dev/mmcblk0p7`
  以 ext4 挂载；但未做全量数据一致性校验，“加密手机”入口也仍在，未加拦截。
- **蓝牙软件组件缺失**：设备声明蓝牙 feature，但未安装 `com.android.bluetooth`；
  仅“通过蓝牙收到的文件”入口已按 Activity 能力隐藏。配对入口仍在，硬件能力未验证，
  不能据软件包缺失直接认定硬件不支持。
- Wi-Fi 曾出现长时间重连，属于连接可靠性问题，不能由焦点修复推断已解决。
- 当前深层扫描包含旧版本、不完整页面和失败记录；总页数或 `BIDIRECTIONAL_SCAN_DONE`
  都不是“全部控件可达”的验收结论。最终须核对候选缺口、横向控件、动态子菜单和共享修复后的回归。

取证程序已改为遇到转换/恢复/传输错误立即停止。字号/密度变化时等待 Activity 控件树重建；
只因中间树为空出现的失败仍保留原记录，并用实际系统属性区分是否真的没有恢复。

### 列表尾部结论修正与可复核证据

此前把“气泡”当作开发者选项尾部是不完整的。其后还有禁用的自动填充分区和主题选项。
v9 保留滚动状态后消除了中途跳回总开关，但禁用项目仍让焦点集合为空；v10 允许只读聚焦
禁用条目并阻止其操作后，实际到达最终的“图标形状”。

- `cert-v8-row-coverage.json`：138 行全部聚焦，缺行集合为空。
- `developer-v10-walk.json`：90 步、80 个焦点签名，最终图标形状；途中总开关回跳次数为 0。
- `developer-disabled-v10.log`：禁用条目确认无跳转，随后完整经过自动填充和主题区域。

v7 在 GlobalSign 同名项处的停止是取证签名歧义，补充行号后证明实际从第 61 行移动到第 62 行。
这些旧记录保留，不据其宣称完整列表通过。

## 2026-10-23 21:20 收尾状态快照

本节是对设备的只读核对，作为“重启验证”和镜像打包的基线。
设备自 10:20 起未重启（`uptime` 显示 10:50），下列运行时行为都来自同一次开机，
**不能代表冷启动后的状态**。

| 项目 | 实测值 | 存放位置 |
|---|---|---|
| 设备 | `5c001089d750c872012`，`rgsp`，Android 10 | — |
| Wi-Fi | `192.168.31.161/24` | 运行时 |
| ADB | `service.adb.tcp.port=5555`，`init.svc.adbd=running` | 临时 `setprop`，重启丢失 |
| SystemUI | `d83ba4fb…`（A 解锁版） | `/system/product/priv-app/SystemUI/` |
| services.jar | `f370b5c4…` | `/system/framework/services.jar` |
| USB host feature | `201da252…` | `/vendor/etc/permissions/android.hardware.usb.host.xml` |
| Settings | `a8b18d83…`（能力兜底版） | `/data/app/com.android.settings-…/base.apk` |
| RGSPNavigation | `16a712aa…`（v10） | `/data/app/com.roc.rgsp.navtrial-…/base.apk` |
| 菜单 overlay | 已启用 | `com.roc.rgsp.dpad.frameworkoverlay` |
| 开关 | `adb_enabled=1`、`show_ime_with_hard_keyboard=1`、`development_settings_enabled=1` | `settings` |
| 存储加密 | `vold.encrypt_progress=error_not_encrypted` | `/data` = `/dev/mmcblk0p7` ext4 rw |

结论仍然是：**一级入口和主要深层页面可用，但不能宣称“所有界面均可仅靠手柄操作”**。
重启验证、冷启动、整卡镜像打包三项均未执行。

## 目标缺失时的设置退出（能力兜底）

“已连接的设备 → 通过蓝牙收到的文件”调用 `com.android.bluetooth.action.TransferHistory`，
但本机没有安装 `com.android.bluetooth`，点击后 Settings 进程被强制结束并退回上一层。

修复分两层：

- `BluetoothFilesPreferenceController` 在展示入口前检查目标 Activity 是否存在，
  不存在时隐藏该入口，不再把缺失功能显示成可用菜单。
- Settings 共享 Activity 兜底 `ActivityNotFoundException`：保留当前页面并提示不可用，
  不再整页退出。

验证方式不是只读代码：临时安装一个无权限的故障接收组件
`com.roc.rgsp.audit.missingtarget`，让入口先判断为存在、点击前再卸载目标，
复现“检查与启动之间目标消失”。按 A 后 Settings 进程未变、停留在原页面。
测试包随后移除。证据为 `bt-missing-activity-native-check.json/.log`，
原包为 `Settings.before-capability-guard.apk`。

边界：这只解决“点击即退出”，**不补蓝牙功能**。设备仍无 `com.android.bluetooth`。

## 深层扫描中断原因与 ADB 调用方式

20:25 的保护后重扫在“存储 → 内部共享存储空间”中断，实际日志为
`Vertical walk limit`，是装饰进度条参与焦点顺序导致的导航缺陷。
此前本节把它写成 `CalledProcessError`，与 `postcap-categories.log` 不符，现已纠正。
本机还另有 ADB server 随短命令进程树结束被清理的现象，应与此次导航错误区分。

因此新增 `tools/rgsp_adb.ps1`，把三步合并在一次调用里，并等待设备进入 `device` 状态：

```powershell
.\tools\rgsp_adb.ps1 status
.\tools\rgsp_adb.ps1 shell 'id; getprop ro.serialno'
.\tools\rgsp_adb.ps1 push .\out\x.apk /data/local/tmp/x.apk
```

长任务的 `audit.py` 现会在操作前检查连接，必要时在自身进程树启动 server、连接并核对设备序列号。
操作发出后若失败则停止，不自动重放可能改变状态的命令。也可先在同一命令中建立连接：

```powershell
.\tools\rgsp_adb.ps1 status | Out-Null
py tools/settings_nav_probe/explore.py --categories 电池 显示
```

该脚本只处理连接生命周期，不改变任何设备状态。设备侧仍需 `service.adb.tcp.port=5555`
且 adbd 正在运行；重启后要重新设置。

### 重启前后的可比快照

`tools/rgsp_snapshot.ps1` 读取本次修复依赖的全部字段（服务、文件哈希、开关、
加密状态、Wi‑Fi 地址、ADB 端口）并写成 JSON，便于重启后逐项对比：

```powershell
.\tools\rgsp_snapshot.ps1 -Out .\out\settings-deep-audit-20261023\snapshot-before-reboot.json
# 重启并恢复串口 / ADB 后
.\tools\rgsp_snapshot.ps1 -Diff .\out\settings-deep-audit-20261023\snapshot-before-reboot.json
```

当前基线为 `snapshot-baseline-20261023-2125.json`（21:25，未重启）。
同日 21:10–21:25，本会话的工作区写权限两次被 Windows 拒绝，已用诊断脚本恢复，
回退记录保留在 `out/acl-repair-20261023/`；这是本机工具问题，与设备状态无关。

## 对外部收尾建议的核对与采用（21:52 更新）

建议作为待核实意见处理，未将截图中的结论直接当作实测结果。

| 建议 | 采用情况与边界 |
|---|---|
| 稳定 ADB、写状态快照、明确未全通过 | 已采用。短任务用一条连接命令，长测试在自身进程树建立连接；不重放已发出的操作。 |
| 排除装饰进度条后回归 | 已采用 v11 共享规则；SeekBar 和有调节动作的控件继续保留。存储四方向图仍有未验证边。 |
| 整机重启验证 | 已执行一次软件重启，内核 boot_id 已改变，非仅重启 framework；断电冷启动尚未执行。 |
| 将更新打入镜像 | 原生源码已同步，system/vendor 镜像正在构建；尚未生成并验收新整卡镜像。 |
| 永久 Wi-Fi ADB 与来源限制绑定 | 采用安全边界，暂不写 persistent 端口。新增串口恢复脚本先建立 IPv4/IPv6 限制，再启动临时 TCP 端口。 |
| 不支持／不在范围清单 | 改为“确认缺陷／组件缺失／未测试／范围外”的事实分类，不能用范围声明掩盖已发现故障。 |
| Wi-Fi 重连计时和 SDIO 调查 | 本次重启后 50 秒快照时已自动连接 Xiaomi_0421；既有 628 秒延迟仍未解决，待单独重复开关回归。 |

软件重启前后：`snapshot-before-reboot-v11.json`、`snapshot-after-reboot-v11.json`。
SystemUI、services.jar、USB feature、Settings、导航 APK 哈希完全一致；两个服务均 found，
菜单 overlay、开发者设置、USB 调试及带硬键盘显示 IME 的开关保留。
Wi-Fi 自动回到原 SSID/IP，受限 TCP ADB 由 UART 显式恢复；不能记成 Wi-Fi ADB 自动持久化。
`unlock-after-reboot-v11.json` 证明唤醒后真实 evdev A 将 keyguard showing 从 true 改为 false，
实体按键机械操作仍未由用户复测。

`vold.encrypt_progress` 从 `error_not_encrypted` 变为空，这是重启清除了临时属性，
不能当作全量数据一致性验证。`/data` 仍是原分区的 ext4 挂载。
当前 fstab 的 /data 没有 encryptable/forceencrypt 标记；未继续执行加密或写加密元数据。

本次启动发现 MediaProvider 处理 ROMS 挂载通知时报告 `Volume 7e99-7141 currently unavailable`
并退出。之后卷已挂载，对 ROMS 和 external_primary 的只读 provider 查询均成功返回空结果，
进程恢复，但启动故障尚未归因或修复；**不能记为无异常启动**。
证据：`reboot-214836.uart.log`、`media-after-reboot.txt`、`crash-after-reboot-v11.txt`。

能力与测试边界：图案锁为已确认不能仅靠十字键绘制；蓝牙主 APK 为组件缺失且硬件未验证；
加密为配置与产品入口不一致且存在先前测试事件，不能标为通过；USB 外设枚举、首次启用开发者模式、
断电冷启动均未验证。互联网可达性不属于本轮局域网调试接入验收，不能由此判断 WLAN 关联失败。

22:04 补充：显示主列表末尾的“色温调节”滑块暴露第二个焦点回环。
垂直方向无候选时，原逻辑横向寻找滑块同排控件，但也接受了上方工具栏搜索作为斜向候选，
造成尾部反复跳回工具栏。已停止当前扫描；v12 将这一特殊横向回退限制为同排重叠候选。
方向计算回归含本次真实几何关系：允许正常方向导航、禁止末尾滑块跳工具栏、保留同排按钮。
旧 `postboot-core-categories.log` 中电池已扫描完成，显示主列表未完成，不能因其子页已扫描而记整类通过。

同步准备的产品修复还包括：依据现有无加密标记的 /data fstab，将 Settings 的
`config_show_encryption_and_credentials_encryption_status` 设为 false，仅隐藏不可用的加密执行入口，
保留凭据菜单；MediaProvider 在 RGSP 的 MEDIA_MOUNTED 分支刷新真实卷缓存后再执行原挂载校验。
两项仍待更新安装及回归，不将源码修改当作实机通过。

首轮全镜像构建因上述新增修复主动中止，尚未产出新候选；已完成的增量产物保留。
构建入口新增完成标记检查，避免 systemd 的主动终止返回状态被误当作构建成功。

本轮源码准备可重复执行；各准备脚本拒绝覆盖无法识别的原生改动：

```powershell
py tools/prepare_rgsp_lock_confirm.py --source \\wsl.localhost\Ubuntu\home\lpf\h700-android10\android
py tools/prepare_rgsp_settings_services.py --source \\wsl.localhost\Ubuntu\home\lpf\h700-android10\android
py tools/prepare_rgsp_settings_navigation.py --source \\wsl.localhost\Ubuntu\home\lpf\h700-android10\android
py tools/prepare_rgsp_media_mount.py --source \\wsl.localhost\Ubuntu\home\lpf\h700-android10\android
.\tools\build_h700_low_pressure.ps1 -Targets RGSPNavigation,Settings,MediaProvider -Execute
```

紧急停止按键注入：在审计输出目录创建 `STOP_AUDIT` 文件；新测试进程每次发按键前检查，
退出时仍执行已声明的状态清理。继续前由操作者移除该标记。启动单次探针前也会优先识别并复用
已有常驻探针，避免 UiAutomation 双连接互相终止。本轮显式停止的旧扫描没有这一新增停止接口。

22:37 更新：v12 的 `tail-check-v12.json` 已通过，显示末尾滑块连续五次 DOWN 保持原目标和值，
UP 可退出；存储共 11 步到达并停在“系统”，无装饰 ProgressBar 焦点，UP 可返回。
旧四方向图仍保留 pending edges，此项仅证明列表边界修复，不替代完整四向覆盖。
`encryption-menu-policy-check.json` 已证明加密执行入口不再提供、其余凭据入口可达；
未执行清除凭据或加密。`keyboard-v12-return.json` 已证明键盘设置六项及返回父页可用。

另发现首页最后“关于手机”仍被裁在屏幕外，外层 ScrollView 已不再提供向下滚动。
结合浮动 AppBar 布局，已准备 RGSP 固定搜索栏＋真实剩余高度滚动区，并取消原首页顶部重复留白，
待当前 Settings 原生构建后实测。`about-v12.log` 的失败保留，不能记成通过。

### ADB 默认回退问题及修复

本机没有 `/dev/usb-ffs/adb/ep0`。原生 Android 10 `daemon/main.cpp` 在没有此端点且端口无效时，
会自动监听 5555，**包括 service.adb.tcp.port=-1**。因此先前仅称“临时属性重启丢失”不足以说明
启动时没有 TCP 监听；原版存在默认回退路径。RGSP 现取消此默认回退，只接受显式正数端口。
其他产品的原行为不变，USB 端点存在时的初始化也不改动。

已实际测试空端口、-1 均无监听，adbd 进程仍运行；恢复来源限制并显式设 5555 后可连接。
首次从 data bind 执行试运行被系统拒绝执行，自动回退原版并恢复连接；改用 system 内暂存文件后通过。
证据：`adbd-optin-trial-system-stage.json`、`adbd-optin-persist.json`，原失败 UART 记录也保留。
修复已保存到 `/system/bin/adbd`，哈希 `958fc1252bdc75c01d4915f87d08a57dbe2a894dc175b8e825e1a0067a8028a0`，
根分区已恢复只读，未设置持久化 TCP 端口；尚待下一次软件重启检查默认无监听。

原版备份 `adbd.before`，远端回退命令：
`sh /data/local/tmp/rgsp-adbd-optin-20261023/install.sh rollback`（从 UART 执行）。
串口恢复受限临时 Wi-Fi 调试的一条命令为 `py tools/rgsp_debug_session.py`。
新产品镜像同时加入 `/system/bin/rgsp-wifi-adb-session.sh`，避免依赖旧 /data 调试文件；
该脚本不会自动运行，默认仍只允许测试电脑 `192.168.31.211`，IPv6 5555 全部拒绝。
主机审计工具仍核对本机序列号；产品脚本按 RGSP 型号限定，不把本台序列号写为产品限制。

## 第二次软件重启与继续回归（23:25 更新）

`reboot-230008.json` 证明内核再次重启，显式恢复调试之前，两个端口属性均为空，
`BOOT_TCP_LISTENING=0`；随后从 UART 恢复受限临时调试。
`snapshot-before-reboot-v13.json` 与 `snapshot-after-reboot-v13.json` 除时长与 boot_id 外完全一致：
服务、SystemUI、Settings、导航、MediaProvider、adbd 哈希及开关均保留。
`postboot-v13.json` 证明 A 解锁、Xiaomi_0421 自动回连、两个媒体卷的只读查询成功，
本次 crash buffer 为空；这支持挂载缓存修复有效，不替代断电冷启动或反复挂载验证。

固定首页布局已在实机显示正常，搜索功能保留，“关于手机”已能从首页末尾用按键进入。
设备名称弹窗原先连续 B 不能返回，而选“取消”再 A 可以返回。
v13 在键盘已隐藏时将 B 对应到当前弹窗明确的负向“取消”按钮；键盘显示时先收起键盘，
不选择确认或中立动作。`back-dialog-v13.json` 已证明第一次 B 只收起真实 IME，
第二次 B 取消弹窗并返回关于手机，设备名称不变。

同次取证曾因内核日志插入数字完成标记旁而中断，实际设备命令返回 0。
原失败保留为 `back-dialog-v13.uart-interleaving.*`；修复 UART 标记解析后，
`test_uart_marker.py` 三组回归通过，含原始插入方式及不误认命令回显。

随后发现另一共性问题：关于手机的 IP/MAC/已开机时间均是不可点击的信息行，
原导航只剩工具栏焦点，无法继续滚动。v14 增加带标题的 collection 信息行只读焦点，
A 明确不产生动作；有滑块、开关等子目标时不再额外生成父行焦点，装饰进度条仍不单独选中。
v14 已原生构建并安装，信息行实机回归进行中，不能提前记为通过。

首份 v13 离线打包在发现信息行缺陷后主动中止，未生成可交付整卡镜像，
仅本任务未完成的 `.partial` 已清理；v13 原生分区及 fsck 证据仍保留在
`out/h700-v5g-dpad-20261023/`。v14 系统分区已重新构建，待关键回归后重新打包。
原生构建日志分别为 `...-230017.log`（v13 整分区）和 `...-232018.log`（v14 导航＋系统分区）。

## 2026-10-24 00:55 实测与候选镜像

当前导航实现为 v15，APK SHA-256：
`59b28bcb17ec520507728460cf8cf0f8cc38dcd1799b74f2c06a906d1daaebf1`。
原生构建 `out/logs/build/h700-low-pressure-20261023-233153.log` 成功，资源限制保持不变。

| 项目 | 最新证据与结果 |
|---|---|
| 标准信息行 | `information-rows-v15.json`：IP/MAC/开机时间可达；A 不调用操作，方向键可离开。 |
| 关于手机行号 | `about-v15-row-coverage.json`：标准标题行 1–10 无内部缺行；展示页头及工具栏另计，不能把焦点总数当行数。 |
| 向上回滚 | v14 曾在内容未到顶时进入工具栏；v15 离开滚动容器前先尝试滚动，已能从末尾回到先前信息行。 |
| 显示/存储边界 | `tail-check-v15.json`：真实滑块连续 DOWN 稳定、UP 可离开；存储可达“系统”并向上返回，无裸进度条焦点。 |
| Wi-Fi 实际开关 | `wifi-cycle-v15.json`：实际按键关闭/开启，至首次确认原 SSID COMPLETED 且有 IP 的上界 10.34 秒，ADB 及防火墙规则仍在。原 628 秒异常仍保留。 |
| USB 调试实际开关 | `usb-debug-v15.json`：关闭后 adb_enabled=0、adbd 自然 stopped；由串口读取真实确认弹窗、按键确认后恢复 1/running。未测 USB 线缆枚举。 |
| 最新版跨重启 | `snapshot-before-reboot-v15.json` 与 `snapshot-after-reboot-v15.json` 仅 uptime/boot_id 改变，包括 USB 配置字段在内其余字段一致。 |
| 默认无 TCP 监听 | 与最新 boot_id 对应的 `reboot-*.json`：恢复调试前 TCP 5555 无监听；之后由 UART 显式恢复来源限制和端口。 |
| 解锁/媒体挂载 | `postboot-v15.json`：A 解锁、两个媒体卷只读查询成功、crash buffer 为空。挂载缓存修复后两次软件启动未再见原 Java 崩溃，冷启动/热插拔压力未测。 |

两类取证问题与产品故障分开保存：

- 首次 v15 滑块边界检查选中了同名“色温调节”章节标题，见 `tail-check-v15.heading-ambiguity.*`。
  改为核对 RangeInfo 后重新验证真实滑块通过，未据此错误修改产品代码。
- USB 调试关闭后，临时 ADB 观察通道不可用，见 `usb-debug-v15.adb-probe-failure.*`。
  后续关闭期间完全通过 UART 读取现有被动探针与焦点，确认后才恢复 Wi-Fi ADB。
- 页头滚入/滚出可见区域曾被旧 page_key 判成换页。新探针输出实际 window_id，
  页面保护使用窗口 ID 与对话框/窗口标题，模板去重单独处理；不因页头可见性改变退出测试。
  `test_page_identity.py` 四项、按钮分类五组、UART 标记三组回归均通过。

新被动探针 `probe/nav-probe.jar` SHA-256 为
`b193d7ccf980ed499e07a25e8161a05e4322f1f3b39caa19742f5adae68cd277`，
实机证据 `probe-windowid-live.log`。旧探针已等待退出后再替换，没有并行抢占 UiAutomation。

窗口身份修正后的最新回归：关于手机及四个子页完成双向扫描；声音记录 18 个页面，
包括外部入口和重复模板，不能直接换算成 18 页功能全部通过。
“添加更多”、第三方许可、系统 WebView 许可等未分类分支继续单独补测。

### 候选整卡镜像

- 文件：`out/H700_Android_SingleCard_v5g_Dpad.img`，32,434,554,368 字节。
- SHA-256：`d73616900666a0e66c0b3d33b653df981e2f289bcd0ef0f2b19b9f4311830430`。
- 元数据：同名 `.json`；原生输入、源文件指纹和 fsck 记录在 `out/h700-v5g-dpad15-20261023/`。
- 基于完整哈希校验的 v5f 镜像，保留启动链、工厂空 data、ROMS 与 GPT，仅替换 system/vendor。
  没有把当前设备用户数据打入候选镜像，也没有对物理卡执行写入。
- system/vendor 只读 fsck 均为 0；校验了内置组件哈希与菜单、D-pad、IME、加密入口、首页布局资源，
  全部输出范围重新回读，最后计算完整镜像 SHA-256。
- 实机测试过的 SystemUI、services.jar、Settings、导航、MediaProvider、adbd、USB feature 七项，
  与镜像内组件逐项哈希一致。运行时菜单 RRO 的配置已直接编入镜像 framework 资源，工厂系统不依赖旧 data 中的 RRO。
- 状态为 `PACKAGED_COMPONENTS_AND_FILESYSTEMS_VERIFIED_PENDING_PHYSICAL_TEST`；尚未做首刷、断电冷启动或物理按键机械复测。

仍需保留的事实边界：图案绘制不支持仅靠十字键；蓝牙主组件缺失且硬件未验证；
加密入口按当前无加密后端的产品配置隐藏；首次启用开发者模式及总开关关闭/开启未测；
互联网连通性不纳入本轮局域网调试接入验收。已发现故障不因这些边界而自动改记通过。

## 2026-10-24 02:00 用户重启后的独立复核

操作者确认重启过设备。串口恢复后（此前 COM4 因一次探测进程被强制终止而卡住，
拔插 USB‑TTL 后恢复），读取到：

- `date` 01:59，`uptime` 31 分钟，即约 01:28 启动；`boot_id=9aaba880-0867-4968-ae70-42615dc64676`。
- `service.adb.tcp.port` 为空、`init.svc.adbd=running`、5555 无监听，与 adbd 取消默认回退后的预期一致。
- `wlan0` 已自动回连 `192.168.31.161/24`；`sm list-volumes` 显示 public `7E99-7141 mounted`。
- 当前前台为 `com.overdevs.at4k/.MainActivity`，`showing=false`（已解锁）。
- `logcat -b crash` 为空；`navigationVersion=15`。

**启动原因存在两种读数**：内核 cmdline 为 `bootreason=button`（类似按键开机/冷启动），
Android 属性 `ro.boot.bootreason` 与 `sys.boot.reason` 均为 `reboot`（类似软件重启）。
两者矛盾，未据此判定“冷启动已通过”，需操作者说明重启方式。

### 重启后与重启前一致

`snapshot-coldboot-20261024-0200.json` 对比 `snapshot-before-reboot-v15.json`，
仅 `uptime_s`、`boot_id` 两个字段变化，其余（服务、开关、组件哈希、Wi‑Fi、加密状态）全部一致。

运行时组件与候选镜像逐项一致：

| 组件 | SHA-256 | 位置 |
|---|---|---|
| SystemUI | `d83ba4fb…` | /system/product |
| services.jar | `f370b5c4…` | /system/framework |
| USB host feature | `201da252…` | /vendor/etc/permissions |
| Settings | `1ae2d582…` | /data/app 更新包 |
| RGSPNavigation | `59b28bcb…` | /data/app 更新包 |
| MediaProvider | `409f45f7…` | /data/app 更新包 |
| adbd | `958fc125…` | /system/bin |
| vold | `9869fa1e…` | /system/bin |

由 UART 执行 `py tools/rgsp_debug_session.py` 恢复受限临时 ADB：
仅允许 `192.168.31.211` 访问 5555，IPv6 该端口全部拒绝，并核对序列号后才判成功。

### 必须保留的一项差异：设备是“系统旧 + data 新”

设备 `/system/product/priv-app/Settings/Settings.apk` 仍是 `f1756b7d…`（旧），
RGSPNavigation 系统包仍是 `d6e417bb…`（旧），MediaProvider 系统包仍是 `04f478e9…`（旧）；
三者当前生效的是 `/data/app` 下的更新包。也就是说，本次多项修复在设备上依赖 data 分区更新，
**重启可保留，但恢复出厂设置或清 data 会退回旧组件**。
候选镜像已把上述组件编入 system，刷入后才不依赖 data 更新；这一点在镜像验收前必须写清。

冷启动与物理按键机械复测仍需按实际操作方式判定：若本次为按键冷启动，
则运行时修复已通过一次冷启动；若为软件重启，则冷启动仍待测。

## 2026-10-24 14:35 v5h 候选整卡镜像打包

在 Windows 侧直接调用 `tools/package_rgsp_v5g.py` 完成打包，输入为
`out/h700-v5h-dpad-files-20261024-final-stage/`（system/vendor raw，fsck 均 0），
`--navigation-version 25`。

- 输出：`out/H700_Android_SingleCard_v5h_DpadFiles.img`，32,434,554,368 字节。
- SHA-256：`824177a498fca777ce19f4dd3aa4c9ebc91883d112a84d738da457cdde1a4bdd`，
  已用独立 `sha256sum` 复核一致。
- 回执：同名 `.json`，含分区表、四段 ranges、system/vendor 组件逐项哈希。
- 状态 `PACKAGED_COMPONENTS_AND_FILESYSTEMS_VERIFIED_PENDING_PHYSICAL_TEST`；未写任何物理卡。

打包环境注意：脚本里的 `aapt2 dump resources` 必须使用 Linux 版 aapt2
（`/home/lpf/h700-android10/android/out/host/linux-x86/bin/aapt2`）。
在 WSL 中调用 Windows 的 `aapt2.exe` 时，参数里的 Linux 临时路径无法解析，
会返回 1；首次尝试即因此失败，改用 Linux aapt2 后通过。

**该镜像仍是 RGSP 单产品镜像**：开机链、DTB/面板配置、`ANBERNIC-keys.kl`、
以及 `Build.DEVICE == "rgsp"` 的十余处补丁门槛都针对 RGSP。RG34XXSP 使用
`rg34xxsp_v1` 面板、带翻盖霍尔与双摇杆，不能把它当作跨机型通用镜像。

## 2026-10-24 重新连接后扩充的验收范围

用户要求在现有设置菜单测试之外，增加系统文件管理器的全部菜单；完成这批修复并编入镜像后才进行首刷验证。
因此 00:55 的 v5g 镜像保留为上一阶段候选，不能把它当作本次扩充范围的最终交付。

- `py tools/rgsp_debug_session.py` 已恢复 COM4 与仅允许 192.168.31.211 的 Wi-Fi ADB。
- `snapshot-replug-resume-20261024.json` 对比 02:00 快照，只有运行时间改变；服务和关键组件哈希保持一致。
- 重启前被动探针的 ready 文件残留，但进程已不存在。核对进程后清理此探针自己的状态并重新启动，保持单个 UiAutomation 连接。
- `licenses-v15.json` 的两组截图已经人工复核：按下/上方向键后文档内容改变，B 返回真实父窗口。
  这是原生方向键滚动抽样及返回验证，不代表逐个激活了许可文档中的全部链接。
- `dnd-add-v15.json` 已补测“添加更多”实际弹窗及三个目标的方向边；返回后 zen 配置保持不变。
- 扫描工具增加真实 Toolbar 范围内的横向扫描，覆盖与返回按钮并排的搜索、更多选项；
  返回后先被动等待页面完成切换，再决定是否发送下一次 B。12 组取证工具测试通过。
- `deep-v15-system-replug.log` 为本轮系统分类回归，目前仍在进行；不能将 RUNNING 的父页记为通过。
- 系统文件管理器为 `com.android.documentsui`。`files-audit-plan.json` 列出浏览、侧栏、搜索、排序、
  视图切换、新建、选择、复制、移动、重命名、删除、详情、分享/打开方式选择器和文件/文件夹选择模式。
  文件变更仅在新建的 `Download/DPAD_AUDIT_20261024` 测试目录进行，当前尚未判定文件管理器通过。

### 本轮已复现并修复的问题（仍在扩展回归）

1. 键盘语言页清掉上级任务栈。`ime-return-baseline.json` 独立复现：进入该页前 Settings 任务有
   首页、三层 SubSettings、LatinIME 设置五个 Activity；打开后只剩首页和语言页，B 回到首页。
   原因是 `InputMethodSettingsImpl` 的 NEW_TASK/RESET_TASK_IF_NEEDED/CLEAR_TOP 标志。
   `prepare_rgsp_ime_task.py` 仅在 RGSP 且调用 Context 是 Activity 时保留当前任务，其他设备/非 Activity 调用不变。
   原生 LatinIME 构建 `h700-low-pressure-20261024-022408.log` 成功，更新包 SHA-256
   `e6f8d0865d637e17b5de89bc29e5cd7649330476a884f9daa8f445367166a5a2`。
   `ime-return-fixed.json` 已验证语言页 B 返回原键盘窗口，第二次 B 回到虚拟键盘。
2. DocumentsUI 文件项提供 ACTION_CLICK/ACTION_LONG_CLICK，但 clickable/longClickable 均为 false。
   `files-v15-item-confirm-baseline.log` 证明 A 焦点停在测试目录，无法进入。
   导航 v16 对 DocumentsUI 的 item_root 按其真实动作列表允许确认；短按 A 打开，长按 A 调用原生选择动作，
   释放时消费短按。该放行只针对文件项，未把设置中的只读信息行改成可操作。
3. 文件搜索框被旧 files 收集器直接排除。`files-v15-search-hidden-graph.log` 中隐藏键盘后只有收起和四个类型，
   v16 同页方向图增加“搜索…”输入框，A 可再次打开真实 LeanbackIME。

`files-v16-open-ime-long-a.json` 已 PASS：进入测试目录/source、重开键盘、长按 A 选择 sample.txt，
actionCount 仅由 4 增至 5，没有释放时额外打开文件。系统实际输入法为
`com.android.inputmethod.leanback/.service.LeanbackImeService`；本轮 LatinIME 修改针对它的设置入口，未更换当前输入法。

选择模式另暴露出被新工具栏覆盖的旧工具栏仍在无障碍树中，旧导航甚至可聚焦“搜索”等不可见图标。
v17 增加对实际 action mode 工具栏覆盖范围的过滤，保留其自身按钮与下方文件内容；目前编译完成，等待实机回归。
编译日志 `h700-low-pressure-20261024-024137.log`。这项验证完成前不把选择模式判为通过。

本轮新增 LatinIME、DocumentsUI 的镜像组件哈希校验和 LatinIME 源码指纹；封装工具必须显式指定已测的导航版本。
上一阶段 v5g 镜像仍未包含这些后续修改，当前不应作为本批修复的最终刷机候选。

### 03:23 继续扩展中的状态

当前实机是导航 v19 的 data 更新包（SHA-256
`e69f08ecdb40908d89bf3b8a8ce9ad224f54f8329a782d5083bfc82eda1fe8b3`），
LatinIME `e6f8d086…`、LeanbackIME `6f29e76a…`、DocumentsUI `bbde93d9…`。
后两项均已有原生构建产物及安装后哈希比对，尚未重新封装 system/vendor 镜像。

- v17 选择模式方向图完成，10 个目标/54 条采样方向边，完成/分享/删除/更多选项可达；
  不再包含被覆盖的搜索、根目录、路径栏。v16 的隐形“搜索”截图中焦点框实际罩在删除图标上，证据单独保留。
- v17 单文件更多菜单方向图完成，包含打开方式、排序、全选、复制、移动、压缩、重命名、获取信息。
  这是入口/方向验证，不能代替每个文件操作的结果校验。
- `files-v18-rename.json`：实际电视键盘输入把 sample.txt 改为 T.txt，文件内容 SHA-256 保持一致。
  后续视觉复核发现输入框仍无可读文字，故没有将整项编辑体验判为完成。
- DocumentsUI 共享 Rename/New Folder 弹窗加入小屏横向 PAN；原生构建日志 `025257`。
  再加入 `dialog_file_name.xml` 产品覆盖，显式使用随主题变化的 colorOnSurface、16sp 与 48dp 最小高度，
  原生构建日志 `031239`，当前正在验证可读性与 B 返回。
- LeanbackIME 原逻辑在打开带选区的输入框时，用光标前后文本重写整个字段，遗漏选中的文件名主体。
  基线打开重命名后 sample.txt 会变成 .txt，未按确认、原文件未改名；新增
  `prepare_rgsp_ime_preserve_editor.py` 在 RGSP 上避免打开键盘本身写入编辑器。
  `files-v18-rename.json` 已证明打开后 sample.txt 完整保留，再通过实际按键改名。
- 新 IME SHA `6f29e76aeb91d5caba1690325f9e4dd22d29f2f1acd713dd14f95f3c867e2efd`，
  相应更新工厂首次启动的 leanback.sha256。封装前必须同时核对 APK 与初始化文件，避免首刷时初始化被旧哈希挡住。
- `locale-remove-confirm-baseline.json` 复现移除语言模式中 A 无法切换复选框；v18 改为收集实际复选框。
  `locale-remove-confirm-fixed.json` PASS：勾选英语、再取消、退出，system_locales 未变；没有移除语言。
- v19 对非文档行继续收集次级按钮，目标包括存储侧栏的退出/弹出控件。
  基线 `files-root-eject-baseline.json` 证明从 ROMS 行向右仍停原行；修复后尚待验证，绝不实际弹出当前启动卡。
- 串口直接创建的空 destination 文件夹在“下载”提供器中未列出，复制尚未执行；
  `files-v18-copy.json` 已标为未完成并取消该选择器。
  `files-internal-empty-directory.json` 证明同一空目录通过完整存储根 RGSP H700 → Download → 测试目录可正常进入。
 该差异不记为按键故障，后续真实文件操作改用完整存储提供器。

原 v5g 镜像及其哈希保留作阶段快照；本批最终镜像仍未生成。设置系统分类大部分深层菜单、文件管理器的
复制/移动/删除/压缩/解压/详情/分享选择器等仍需继续，不能宣称全部界面通过。


### 2026-10-24 10:12 继续：文件管理输入、视野与锁定方式

- 用户确认关闭图案锁入口，保留 PIN 和密码。`prepare_rgsp_controller_lock.py` 对已核验原始 `ChooseLockGenericController` 仅增加 RGSP 限定；不改变已有凭据，不执行重置。Settings 低压力编译已完成，等待安装与菜单验证。
- 文件管理的复制、移动、压缩和从压缩包成员解压均经实际 HAT/A/B 操作完成，结果 SHA/ZIP CRC 已核对。新建目录的原生编辑对话框实际输入可见，LeanbackIME 不再在弹出时丢失原选中文字。详见 `files-native-create.json`、`files-v19-copy.json`、`files-v19-move.json`、`files-v19-compress.json`、`files-v19-extract.json`。
- `DocumentsUI.fixed-viewport.apk`（75af7e81008dc543bfe85a31f2d33071484b0d725600a3d1441d0eeec4e91907）配合导航 v20（34f03cd4f4b0be0128154c02d4cb646e22f760b0be5a58df173088c43d223671）将信息页预览头缩至 64dp，并把只读 ScrollView 纳入导航，实际可滚动到下方 URI/开发者信息，截图已查看。
- 必须保留失败结论：v20 的目录 appbar `noScroll` 单独不足以解决混合目录下文件卡片标题裁切；`files20-viewport.json` 明确记录文件名 visible=false。正在修复文件行的语义 SHOW_ON_SCREEN 通路，不能把焦点抵达当作视觉通过。
- v19 ROMS 侧栏可达性复测在等待用户回复期间未成功完成，`files19-sidebar.json` 记录 unreachable，仍待修复版本重测；此前只是增加了次级按钮收集，不宣称侧栏通过。
- 本轮全程只操作专用 `Download/DPAD_AUDIT_20261024` 文件；分享只打开选择器，不发送。危险系统操作只验证焦点和取消。
- 04:53 和 10:08 均有 LOW_PRESSURE_COMPLETE 记录。04:48 的资源编译因 flags 要求枚举 `noScroll` 而拒绝数值 `0`；已纠正并成功重编。没有放宽资源限制。
- 待完成：文件管理剩余菜单、设置未完成页、Wi-Fi 多轮计时、开发者启用/USB调试状态、最终重启验证和新镜像制作。旧 v5g 不包含本轮修复，不应刷写为最终验收版本。


### 2026-10-24 11:00 开发者启用链路与镜像阶段记录

- `developer-first-enable-immediate-daemon-assertion.json` 已真实记录：开发者总开关关闭，development_settings_enabled=0、adb_enabled=0、adbd=stopped；全程经 HAT/A/B 从首页进入关于手机，对版本号确认 7 次，得到 development_settings_enabled=1、adb_enabled=0；随后进入开发者选项，A 确认 USB 调试对话框，得到 development_settings_enabled=1、adb_enabled=1。没有把恢复命令视为这些 UI 状态变化的证据。
- 该脚本最后立即断言 adbd=running，实际此时仍是 stopped，原始结论保留为 ERROR。另开的 USB 开关回归增加等待，尚不能先写成整条通过。UsbDeviceManager 日志显示 mtp,adb 状态等待失败后回退至 adb；当前 /dev/usb-ffs/adb 和 android0/state/functions 均缺失，USB 物理数据枚举未验证。
- 前两次测试工具中断分别保存在 `developer-first-enable-transport-failed.*`（控制台日志插入 JSON）和 `developer-first-enable-slow-uart-stopped.*`（主动安全停止并恢复基线）。现纯 UART 使用 gzip/base64 + 原始 JSON SHA256 + 请求 token 校验，只重试观测，不重放按键；与 ADB 同页同焦点对照通过（probe-compressed-uart-vs-adb.json）。安全/传输单元测试 18 项通过。
- 当前已安装 Settings.controller-lock.apk：f1b071b61ef40ebe2268369940637d5ca5f27aa87b4eea02aa77ba38ea9d5362；图案入口隐藏仍需实际菜单复核。
- 当前已安装 DocumentsUI.static-bar.apk：f4f27aa6475254026a106ddce198a5a0e6037d274f5cce2bb7f29631acca3f4b。源码同时固定 NavigationViewManager 的运行时 appbar flags（单改 XML 会被覆盖），并限制目录 RecyclerView 绘制到 padding 内；最终混合目录视觉复核待做。
- 导航 v22 已编译，待安装；文档行也继续收集独立的预览次级按钮，避免继存储侧栏 Eject 之后，文件行再次吞掉子按钮。是否显示预览仍由原生 QuickViewer 能力决定。
- systemimage/vendorimage 在 10:22:58 构建完成，`out/h700-v5h-dpad-files-20261024` 阶段目录的 system/vendor 只读 fsck 均为 0；该目录含 v21，后续 v22/修复必须重构建并重新阶段化，不能当作最终输入。没有创建本轮完整镜像、没有向物理卡写入。

### 2026-10-24 12:23 文件管理与开发者验证进展

- 开发者首次启用：通过实际手柄键从关闭状态进入关于手机，七次按版本号后启用开发者选项，再通过确认框启用 USB 调试。首次脚本立即检查 adbd 时遇到 USB 功能回退的延时，原 ERROR 证据保留；后续实际关闭/启用并有界等待，adbd 自然停/启通过。组合证据 developer-first-enable-validation.json 明确引用两份原始记录。当前没有物理 USB gadget 枚举证据。
- DocumentsUI 57ca44f8…加入 RGSP 专用“刷新”，复用原生 onRefresh；真实按键打开并确认、返回目录及文件哈希检查通过。测试前新文件已被观察器显示，因此不声称这次出现由手动刷新独立导致。
- 中文和空格文件名在打开电视键盘后保持完整；B 先收键盘再取消重命名，内容哈希未变；列表/网格切换和列表方向图通过。排序弹窗的触摸关闭遮罩已从按键候选排除，八个选项均可达。
- 分享和 ZIP 打开方式可打开/取消；当前没有相应接收程序，保留原生“没有应用可执行此操作”说明。PNG 可通过真正 clickable 的图库条目打开并 B 返回；截图复核显示四颜色测试图片。之前按到非 clickable 列表容器的失败属于测试脚本误选；v24 实验没有安装，已撤回并重构建 v23，哈希与原 v23 一致。
- v25 导航 APK 116ece476afdce1ae663ea751d142981ef1b9408b1254cf0ab823c3de028da47 已原生构建并安装。目录内目标按 appbar 与保存栏实际可见区域过滤和绘制，保留原始 selectedBounds 供观察对应。正在逐项正反遍历 64 文件，首行截图焦点框与正文正确对齐。
- 日历背景崩溃来自没有 AppWidget 服务却调用 getAppWidgetIds；已给接收器和数据回调加入空值保护并原生构建。Calendar APK ca1f0c9f5c3837674c31acd996b24432d81d1f03e3bddfc3717006df67a7a713 已安装并核对。接收器烟测无新增崩溃；Android 阻止直接后台启动服务，保留首次失败记录，异步数据回调覆盖仍未证明。
- 工具的 UART 帧校验、分类器、页面标识共 18 项测试通过。覆盖表仅是证据清单，不等同于全部菜单功能通过。仍须完成文件管理余项、设置未完分支、Wi-Fi 重连重复回归、最终重启及系统镜像重封装。10:22 的阶段 system/vendor 和旧 v5g 整镜像都不是本批最终产物。未写入任何物理卡。

### 2026-10-24 16:24 — 首启输入法、中文默认及电源菜单补漏

- 用户要求：新镜像首次开机默认简体中文；已添加语言可以用 A 切为首选；关机菜单可用十字键选择关机/重启。继续原有设置、文件管理和显示排查目标。
- 发现首启输入法实错：`ime list -s` 仅列已启用方法，因而无法发现尚未启用的 LeanbackIME。已改为 `ime list -a -s`，随后显式 enable/set。
- 隔离首启夹具从 LatinIME-only 状态运行当前候选脚本，成功启用/选中 Leanback，第二次运行保留用户选择。证据：`factory-ime-latin-only-current-helper-1620.json`。夹具仅替换状态目录、IME 校验文件路径和 HOME helper 路径，不清除真实首启标记或用户数据。第一次夹具因设备上的旧 HOME helper 不认可当前 AT4K hash 而退出，原始错误保留；候选 helper 的 hash 与 native staging 文件一致。
- 产品配置新增 `PRODUCT_LOCALES`，zh_CN 优先，只设置 factory 默认，不在每次开机覆写 persist.sys.locale。需检查最终 system/build.prop 与镜像内该属性。
- Settings 原生语言行增加 click -> onItemMove(position,0) + doTheUpdate；移除模式保持 checkbox 操作。Nav v26 优先调用原生 click，保留旧 Settings move-top action 兼容。
- SystemUI GlobalActions 原生 action view 增加 focusable / focusableInTouchMode 和可见焦点前景；保留现有真实 onClick 关机/重启逻辑及 A 解锁补丁。编译中的代码尚未完成设备回归，不计为通过。
- 首启 HOME 选择原生焦点边界：设备静态试验 overlay 的“仅此一次”和“始终”均实际 A 确认成功；源码 board overlay 已加入 native staging 白名单。16:05 full build 成功。当前临时静态 overlay 与最终 framework 编译资源须分别核验。
- 显示：RGSP 当前无肉眼闪烁复现。250 次基线采样实际 51.07 秒（4.876 Hz），PWM/亮度恒定、LCD IRQ 持续，VSYNC uevent 计数停 3；不能宣称历史黑闪或 34xxsp 亮暗闪烁已解决。已准备 HWC 分数刷新周期与副屏电源接口修复，尚未应用/设备验证。面板实际周期以 framebuffer 参数和硬件观测为准，不采用截图中硬编码 16906000ns。保持 boot/kernel/DTB 不变。
- 包装校验已加入最终默认语言、首启 IME installed-list 参数、HOME helper 与 HWC HAL 的组件检查，防止 data 更新或漏入镜像再次造成测试差异。

#### 16:39 构建输入调整与新增实测

- 默认中文最终采用 `device/roc/rgsp/system.prop` 中 `ro.product.locale=zh-CN`，由系统 build.prop 烘入；不设置 PRODUCT_LOCALES 过滤翻译资源。16:12 的构建因调整默认语言实现被主动停止，不能计为完成。当前有效构建为 `h700-low-pressure-20261024-162943`，待完成标记。
- HWC 分数周期及 RGSP 副屏 power 接口隔离已通过有原始 SHA 门禁的 prepare 脚本落到 native source，正在编译。独立周期换算 C++ 测试覆盖分数刷新率、零/异常输入、溢出上界，已通过。尚未进行 HAL 设备替换，不计为闪烁修复通过。
- 文件管理：完整详情 120 条方向边已闭合；内部存储隐藏/显示遍历全侧栏验证通过；新建窗口及 B 返回原窗口通过。首轮内部存储脚本误把侧栏首屏没有 RGSP 根目录当成失败，原始 false-failure 保存，补测确实遍历全部侧栏后通过。ROMS 根方向图已扫描闭合（23 节点、140 条实际方向边），仍等待该测试返回路径完成。

### 2026-10-25 04:18 — 恢复连接与观察工具稳定性

- USB-TTL 重新插接后，UART 与仅允许 192.168.31.211 的临时 Wi-Fi ADB 已恢复；设备序列号仍为 RGSP，usb/oem_lock found、旧 A-unlock SystemUI hash 和默认 Leanback 均保持。客户端日期为 2026-10-25。
- 10 月 24 日 16:29 构建停在后段且无 LOW_PRESSURE_COMPLETE，不作为完成构建。当前构建 `h700-low-pressure-20261025-035257` 包括 system/vendor、Settings、SystemUI、Nav、HWC/probe。电源 HAT/native-focus v2 已写 native source，Java 编译通过；产品目录的 APK 尚未更新时不拿旧 APK 冒充新结果。
- 电源 v2：适配器 action root 设焦点高亮及私有 tag；ActionsDialog 自己处理 ANBERNIC HAT 轴，原生方向键也只在 action 列表间移动；onStart 焦点落到首项。A 继续原生 onClick，B 继续 native dismiss，不加入导航辅助服务的 SystemUI 全局接管。
- Settings Search 已实际确认：空查询左键可到返回按钮；默认电视键盘可输入；输入 w 后，右键到“清除查询”，实际 A 清空并 B 返回。Native Search 已能完成这些交互，未加无根据的包级导航补丁。
- framebuffer 实测：720x480，pixclock=38461 ps、ht=820、vt=536 -> nominal 16904379 ns / 59.156270488 Hz。120 次 FBIO_WAITFORVSYNC 总计 265125 ns，3 秒 VSYNC uevent 为 0。该 nominal 周期与先前真实 IRQ/present-fence 约 16.786 ms 仍有差别；分数周期修复不是硬件 VSYNC 已恢复的证据。
- 存储扫描两次在电子邮件详情相近位置丢失被动观察进程，日志仅为 Killed；未查明具体终止原因，不误判菜单/进度条产品故障。此时自动按键已停，未执行清数据。
- 被动 Dump 新增每 64 次观察释放连接/退出、每 8 次 GC；最后一次响应前撤销 ready，客户端等待旧观察进程退出再启动下一实例。保持 DONT_SUPPRESS_ACCESSIBILITY_SERVICES，观察工具不发按键。新 jar `ba6469578726ce58f43c40d660f97c6a6d5abaa7360349c17a760aac9b6293bb`，路径 `/data/local/tmp/nav-probe-bounded-v2.jar`；旧 jar 保留。70 次连续无按键观察跨进程切换成功，详见 probe-bounded-smoke-20261025.json、probe-rotation-events.jsonl。仍需长菜单扫描验证稳定性。
- 扫描支持显式 pinned Settings SHA + live fingerprint 的完成页复用；仅 BIDIRECTIONAL_SCAN_DONE 可用，未完成页继续实测。加入实际中文标题“影视应用”，修正进度条被分类为滑块而跳过整行的观察脚本问题。19 条安全/观测单测通过。

### 2026-10-25 04:54 — 新构建、存储补测与关机菜单

- main build `h700-low-pressure-20261025-035257.log` 于 04:30:38 完成。最终检查发现 donor 已设 TARGET_SYSTEM_PROP，单放 system.prop 未入产物；BoardConfig 显式追加 `device/roc/rgsp/system.prop`，增量构建 04:37:50 完成，最终 system/build.prop 实际包含 `ro.product.locale=zh-CN`。两次均保留原有低压力限制。
- 内部存储扫描 `exploration-afb319584b.json` 38 页完成；涵盖照片、音乐、游戏、影视、其他应用与应用存储详情、文件分支、系统说明。被动观察器 64 次轮换在本次长扫描中正常工作；未把外部 Search 入口自动记成完整搜索功能通过。
- SystemUI 新 APK 0232e8f4…已替换。首次安装脚本在终止旧进程前 remount RO 失败；保留失败记录，随后核对新 APK 哈希、终止旧 SystemUI 后成功恢复根分区 RO。vendor 始终 RO。脚本已调整顺序，不能把首次失败擦成通过。
- power-menu-native-hat-v2-cancel-check.json：真实 ANBERNIC HAT 32 次方向操作覆盖关机、重新启动、屏幕截图、紧急呼救，B 关闭菜单通过；截图确认蓝色焦点框。前一次测试仅因返回锁屏仍属于 SystemUI 而误判 B 失败，记录保留。未确认关机/重启动作，后续单独实际重启验证。
- Settings 1ec716cd…和 Nav v26 14ef9642…已通过 adb install -r 安装，新服务 dump 确认 navigationVersion=26；语言 A 切换回归正在进行。
- 新 v5i staging 的 system/vendor 只读 fsck 均成功。尚未创建整镜像，尚未对物理卡写入。

### 2026-10-25 05:07 — 语言切换的输入法回退共性问题

- Settings 新版实际 A 将 English (United States) 提升为 en-US 成功，但 IMMS 的 ACTION_LOCALE_CHANGED 处理无条件 resetDefaultImeLocked，随后默认输入法变成 LatinIME。原始截图/属性与恢复记录见 locale-native-v26-ime-regression.json。最初匹配英文/中文时出现翻译无障碍标签不一致，属于测试定位问题；已使用原生语言行内文字定位，清理逻辑也保证保留失败收据。
- 已用实际 HAT/A 将中文恢复首选，并恢复 TV IME；没有通过属性命令冒充语言 A 测试通过。
- prepare_rgsp_locale_ime.py 以 IMMS 原始 SHA 88f99d3d…为门禁：仅 RGSP 当前已选且仍安装/启用 LeanbackIME 时，locale change 保留该输入法；被卸载/禁用时仍走原有 fallback。其他设备和输入法按原逻辑处理。services 编译产物新 SHA 07b2f948…，完整 system/vendor 低压力构建 04:57:12 正在继续。
- Wi-Fi 输入补测组合结论：实际 Add Network -> WPA/WPA2-Personal -> password A 打开真正 LeanbackIME；Down+A 后界面出现一个遮掩字符，Show password 实际 A 显示自有测试字符 g。实际 Dpad Down 可到取消，A 返回 WLAN，Xiaomi_0421 连接保持。组合收据 wifi-password-native-v26-validation.json 明确引用原始脱敏误判和补测。未保存测试网络、未读取现有密码。
- 通用 files.focus BFS 在滚动布局返回假不可达，实际 18 次 D/U 诊断证明取消可达；没有因此改坏产品方向逻辑。后续该用例以实际向下遍历和严格取消 ID 校验定位。
- 先前 04:54 v5i staging 不包含刚发现的 IMMS 修复，明确为中间产物，不能作为最终镜像输入。待完整构建和实机回归后新建阶段目录。

#### 05:11 框架与显示实装、网络排查

- 04:57 低压力构建于 05:05:59 LOW_PRESSURE_COMPLETE 完成。services.jar 07b2f948…已实际装入 RGSP，Framework/SystemUI 连续稳定，usb/oem_lock found，根分区和 vendor 为 RO。首次后台启动 UART 命令因工具拼接成 `&;` 语法错误而没有执行；修正为 `& echo …` 后成功，失败记录保留。
- HWC eac4cb95…实际加载并稳定，日志确认 `LCD timing pixel_ps=38461 frame_period_ns=16904379` 和 software VSYNC 周期 16904379ns；旧日志 16949152ns。硬件 VSYNC 和肉眼闪烁尚待复核。
- HWC 试验脚本只重启 framework/graphics 而保留 netd，造成其 wlan0 路由表缓存仍 1009，但新接口 index=13、路由落到 1013；规则查旧表、networkCreatePhysical EEXIST。Wi-Fi 实际关联和到网关 ping 正常，ADB 无法回程。此为本次热替换流程错误，有独立 UART 证据 hwc-framework-network-stale-route.json，不能当作路由器关闭或用户操作故障。脚本已修正为同时 stop/start netd；通过实际电源菜单重启进行持久化和网络重建验证，不把手工添加路由作为产品修复。

#### 05:15 电源菜单真实重启及显示复核

- reboot-051205.json / UART log：先唤醒，实际 A 解锁，再打开电源菜单，实际 HAT 选中“重新启动”并 A；观察新 kernel/boot_id 与 boot_completed。首轮从非交互状态直接注入长 POWER 只唤醒，没有菜单，未发送重启 A；错误记录 reboot-051104.json 保留。补充唤醒/锁屏判据后通过。
- 启动时 service/persist TCP port 均为空、5555 未监听；UART 显式恢复 guarded ADB 后连接成功。之前 netd 旧路由缓存问题随完整重启消失。native-fixes-persistence-after-power-reboot-20261025.json 核对新 services/SystemUI/HWC exact SHA、两分区 RO、usb/oem_lock found、TV 默认和 guards。
- 新 HWC 重启后日志周期 16904379ns，确认修复已加载。FBWAIT 120 次总 274625ns、3 秒 0 条 VSYNC uevent，硬件 VSYNC 仍未恢复。不能声称分数定时器等于硬件同步，或 34xxsp 轻微闪烁已修复。
- 新最终阶段目录 h700-v5i-dpad-20261025-locale-ime-final-stage：system/vendor 只读 fsck=0；services.jar 07b2f948…、IMMS source dc986f8a…；保留早先不含 IMMS 的阶段目录但禁止用于最终包装。

### 2026-10-25 05:24 — 语言与 Wi-Fi 联动通过，锁屏补测

- locale-confirm-framework-retained-after-reboot.json：实际 A 从中文切英文、再切回中文，两次均保留 TV IME，通过。最终 zh-Hans-CN,en-US，没有以 settings put 等命令代替语言切换。
- wifi-password-after-locale-retention.json：上述语言回归之后再完整进入 WPA/WPA2 Add Network，实际 Down/A 输入、Show password 核对自有字符、B 收键盘、Dpad 到取消并 A、返回 WLAN/原网络仍 COMPLETED，通过。无测试网络被保存。
- 锁屏方式页面实际只见无/滑动/PIN码/密码，图案入口已隐藏；PIN/密码页面可到输入框、清除、下一步且 B 返回。首个脚本错误把 TV 字母键连按当作 PIN 输入，数字框拒绝字母，Next 仍禁用；因此 controller-locks-native-20261025.json 的 input PASS 字样不足以证明 PIN 有效输入，独立 validation-review 明确降级解释。正在补测真实数字行、非连续四位夹具和 Next-enabled 断言，绝不确认保存凭据。
- 新 HWC 重启后 250 次/51.48秒采样：背光50、PWM20000/3906ns均恒定，LCD IRQ约59.5571Hz，vsync仍3不增；power事件/显示错误日志均空。本次没有同步肉眼复现记录，保留症状结论未验证。

### 2026-10-25 05:45 — 两个新增共性根因

- controller-locks-valid-input-after-reboot.json 已通过真实数字行四位 PIN 和密码输入；两种方式均 Next-enabled、完整焦点图与 B 取消，凭据未保存。此前字母误输 PIN 的降级解释继续保留。
- 日期与时钟圆盘的虚拟 AX 子节点有 ACTION_CLICK（actions=80）但 isClickable/isFocusable=false，v26 排除，旧日期图闭合不等于日期格子可达。DatePicker 的上个月节点还会被 AX 声明 visible，坐标实际在 pager 外。Nav v27 通用修复：Settings 识别明确声明的 CLICK；焦点裁切到祖先 ViewPager/List/Scroll 实际边界，空区域不参与选择。Files 规则保持原有专用 viewport，滑块仍依精确 RangeInfo 动作调节。v27 APK 98fcf77e…，05:35:41 低压力构建完成，正在安装与实际格子 A 回归。旧 datetime-manual 的 PASS 仅能证明原有按钮/取消，不能证明虚拟格子。
- Wi-Fi 重复回归：cycle1 10.38秒、cycle2 10.27秒恢复；cycle3 180秒未恢复，失败收据保留。全量 UART gzip+SHA 捕获 wifi/logcat/kernel，目录 wifi-third-cycle-failure-20261025；没有按键改变取证现场。
- 明确软件根因：Xiaomi_0421 被 NETWORK_SELECTION_DISABLED_NO_INTERNET_TEMPORARY 禁用，numNoInternetAccessReports=4，noInternetAccessExpected=false。源码 WifiConfigManager 该理由超时恰为 10 分钟。SSID 始终可扫描，真实手柄 A 手动选择后立即重连；证据 wifi-third-cycle-manual-connect-entry / manual-reconnection-state。不是路由器关闭，不据此指责 SDIO 驱动。
- prepare_rgsp_local_wifi.py 有原始 SHA 门禁，仅 RGSP 且无 TELEPHONY feature 时跳过 WAN 验证失败造成的自动临时禁连；仍保留真实验证报告/无外网提示、密码/DHCP等失败处理以及用户明确拒绝连接的永久禁连。没有伪造已验证互联网状态，没有改变验证服务器或关闭网络验证。05:44:12 低压力构建已开始，待 Wi-Fi JAR 实装及带验证等待的三轮回归。
- 现有早先 v5i 阶段目录均不含最终 v27 + 本次 Wi-Fi 修复，禁止用于最终镜像包装；待源代码收敛后重新阶段化。

#### 05:58 日历边界修正与本地 WLAN 策略实装

- v27 实际虚拟日期 A 已能选中，但整图测试检测到未闭合。进一步核对原始节点证明方向遍历混入十一月：ViewPager 被误判为纵向滚动，在日期格子边缘的通用 scroll fallback 意外换月，不能把汇总 1..31 当成十月全部通过。失败 virtual-pickers-native-v27.json 保留；取消对话框、恢复自动时间，无系统日期提交。
- Nav v28：ViewPager 识别为横向；含独立选择子项的 Settings pager 不通过格子边缘隐式翻页，保留明确的上/下月按钮；actionableDescendant 同步识别声明 CLICK 的虚拟子项。图测试增加每个方向后检查实际月份的 guard，发现换月立即失败，不混用月份数据。v28 原生 APK 7aa385ea…，05:56:05 完成。
- Settings 日历绘制隔离版 005a3094…于 05:53 构建完成并安装；仅小屏横向日历的 day_picker_view_pager 使用软件 layer 和裁切，保留原生日期语义。实际绘图改善尚待截图，不先写为视觉通过。
- Wi-Fi 本地连接策略原生 JAR c39709de…，05:46:11 完成并实际替换；wifi/usb/oem_lock found、Framework/SystemUI 稳定、两分区 RO、IP 恢复，记录 local-wifi-framework-20261025/live-install.json，原始 efcec42b…备份保留可自动回退。
- 正在安装 v28 后做三轮 Wi-Fi 开关，每轮连接后额外等35秒，让真实 WAN 验证失败有机会发生；必须同时见新策略日志、无外网报告和 NETWORK_SELECTION_ENABLED，才算根因回归覆盖，不仅比较快速 off/on。

### 2026-10-25 06:08 — Wi-Fi 根因回归通过

- wifi-repeated-local-policy-v28-stable-read.json 三轮真实 HAT/A off/on 均成功，重连上界 10.23/10.25/10.28 秒；每轮再等35秒，config 状态均 NETWORK_SELECTION_ENABLED，同时 numNoInternetAccessReports 为6/8/10，实际命中新 ClientModeImpl 策略日志。无外网提示/验证失败仍真实存在，不伪造互联网可达，debug guards 均在。
- 前次 local-policy-v28 首轮实际上10.14秒已重连，但紧接的只读 id 请求碰到 ADB closed，原失败保存。脚本仅对这个只读检查增加有界重试，不重放任何开关按键；随后上述完整三轮通过。
- pm list features 未显示 TELEPHONY，确认产品限定条件确实命中。Wi-Fi JAR c39709de…、Nav v28 7aa385ea…、Settings 005a3094…当前实机应用中；完整重启持久化仍需在本轮最终收敛后再核对一次。

### 2026-10-26 11:55 — 继续未完成的时钟与深层菜单测试

- UART / guarded Wi-Fi ADB 恢复，目标仍为 RGSP。上次 virtual-pickers-native-v28-month-guard.json 的日期子测试确实闭合：31日全部可达，无越出 pager 的日期，A 选日/选2027年及取消均通过；随后在时钟目标查找停止，不把整体写成 PASS。日历软件 layer 截图 virtual-date-entry-061301_639966.png 已人工查看，标题上的相邻月份文字消失，视觉修复通过。
- 测试图的候选指纹原先只含 clickable，忽略 action-only 数字，时针/分针复用标签时可能混淆。已将明确 CLICK 动作纳入观测状态；方向寻找器也包含可见候选几何，区分两种表盘。
- 时钟实测还发现产品交互问题：A 选分钟25，随后移焦会恢复初始分钟41。源码 NumericTextView.onFocusChanged(false) 在没有直接键入数字时恢复 mPreviousValue，覆盖虚拟表盘刚选的值。Nav v29 在明确的非 clickable/focusable 虚拟 CLICK 前先结束旧的非编辑输入焦点，再执行原生点击；Settings 仅请求节点实际声明的 FOCUS 动作。Files 的焦点请求路径不变。
- v29 低压力构建于 2026-10-26 11:54:16 完成，正在安装后验证小时/分钟 A、移焦保留、两种表盘、文字输入模式及取消，禁止提交系统时间。
- 基线 v5f data 分区使用只读 loop + debugfs 核对根目录，确实仅 lost+found，没有旧用户数据/locale/首启标记；loop 已卸载。证据 factory-baseline-data-readonly-20261025.json。因此新 image 中 ro.product.locale=zh-CN 不会被基线旧 persist locale 覆盖。
- 包装工具新增完成的可达性报告门禁，并比较实机测试的 Settings/Nav/services/Wi-Fi/SystemUI/TV IME/DocumentsUI/HWC 精确 SHA，防止用旧阶段输入包装成最终镜像。尚未生成新完整镜像，尚未写物理卡。

### 2026-10-26 — 时钟原生标题焦点修复与深层扫描继续

- v29 复测只解决分钟回退，小时仍恢复旧值；原失败 clock-controls-focus-handoff-v29-20261026.json 保留。已移除这段不充分的先清焦点逻辑。
- Settings 原生 RgspDpadDialogPolicy 对非文本编辑器的 NumericTextView 数字标题关闭原生数字编辑焦点，保留标题 CLICK 切换表盘；直接数字输入仍使用原生文字模式。Nav v30 仅请求 Settings 节点确实声明的 FOCUS，显式虚拟 CLICK、日期 viewport/分页修复保留，Files 逻辑不变。
- 低压力构建 h700-low-pressure-20261026-120408.log 于12:08:48完成；实装 Settings df0a981784b3523e9267624b8b1a2dd22e721d3fa03c4acdbce1df574e0dae3b、Nav30 336b698bd5eea075bca9a91618f3ee0c295404c99579151356d7a096e9d8077d。
- clock-controls-native-header-v30-20261026.json 通过：实际 A 选小时7/分钟25，移焦不回退；时针、分针分别遍历全部暴露的12个虚拟选项，方向 guard 未改变表盘和值；文字模式两编辑框、AM/PM、切换/取消/确定均可达；B取消且系统时间未被提交，自动网络时间已用实际 A 恢复。
- 继续最终组件上的系统、应用和通知、显示深层扫描。完成扫描不自动代表全部功能通过，危险操作只检查焦点及取消。

- native30 新阶段 out/h700-v5i-dpad-20261026-native30-stage 已完成，system/vendor 只读 e2fsck 均0。native30-stage-live-component-match-20261026.json 核对八个 staged 组件与实机活动版本完全一致；TV IME 通过 PackageManager 解析实际 /data 更新版本，不能拿旧 /system 路径当作当前活动 APK。此目录仍只是输入，未包装完整镜像。
- 系统添加语言列表正向超过原脚本420总步数可覆盖的半程；为避免到上限后重测，保存 exploration-system-checkpoint-20261026.json 并在下一按键前由自有 STOP_AUDIT 安全暂停。已移除自有标记，继续同一 window_id、同一 Settings SHA 的未完成列表；保留正向前缀，续扫尾部再反向到顶部。该暂停不属于产品菜单故障。工具步数上限扩为1000，分类/页面标识/UART19项测试仍通过。
- 焦点图增加真实焦点 bounds，区分同标签/无标签、同 ID 的多个 RadioButton，避免多个单选按钮被错误合并。

- 添加语言续测 exploration-b8a2f42e3c.json 已 BIDIRECTIONAL_SCAN_DONE，194个不同控件，原正向前缀+列表尾部+全反向遍历有连续来源 SHA。可复用完成页整合在 native30-completed-system-reuse-20261026.json，不改写旧停止记录。
- dnd-duration-native30-20261026.json 通过全部3个 RadioButton 的实际 bounds 可达性、独立内容选择行、加减按钮与两页脚；实际 A 选择“每次都询问”和“直到您将其关闭”均核对 checked，A 增加后再 A 减少回原时长，A 取消返回勿扰模式；secure zen_duration、zen_mode/config etag 均未改变。
- 新显示只读线索见 out/flicker-investigation-20261026/vsync-consumer-inventory.json：实际内核含 vsync_thread/drv_disp_vsync_event 符号，但 /proc comm 未找到 vsync/disp/fence 线程，成功计数3而 vsync_skip 持续增加。本地源码 VSYNC_NUM=4 的环形队列可容纳3条，消费线程路径存在。只构成“消费线程缺失/未运行”的候选，尚未证明此源码与运行内核完全一致；没有改写内核/寄存器，也未声称34亮暗闪烁解决。

### 2026-10-26 12:58 — 只读详情的通用滚动缺漏

- credentials-native30-20261026.json 完成系统 CA 列表到 XRamp 末尾、证书选择器及停用/确定页脚、用户页签、从存储安装的 DocumentsUI 选择器及取消，未改信任状态。但独立核对原始详情/方向图发现 ScrollView 正文不是候选，只有选择器和两页脚；初始只显示颁发给/序列号，下面有效期/指纹不可达。validation-review 将原收据明确限定为部分通过。
- Native31 在 collectSettings 对“scrollable ScrollView 且无 actionableDescendant”加入方向操作目标；A 不成为 CLICK，不把正文每个 TextView 变成一排按钮。既有 scrollSelection 在正文到底后才能移出到页脚，上移先滚回顶部。Files 原有同类逻辑不变。
- native31-source-delta-review.json 对新源码逆向移除唯一新增代码块和版本号，SHA 严格等于 native30 stage 的原源码证明，确认未混入其他行为改动。
- 低压力 h700-low-pressure-20261026-125445.log 于12:55:59成功完成 Nav+systemimage。实装31 APK SHA 3c139420b75d6bab87d7bcbaa3bcddb2a662ed4a88229cf6803d22131a4d0e3e，服务已重绑定。native30 阶段因此再次失效，不能用于最终镜像；待本轮回归完成后重新阶段化。

- certificate-scroll-native31-20261026.json 已通过：19个焦点/正文 viewport 状态、127次实际方向操作闭合，issued_on/expires_on/sha256_fingerprint/sha1_fingerprint 均真正可见；正文非 CLICK，实际 A 不增加 actionCount、不换窗；停用/确定页脚可达，B 返回信任凭据列表。未停用任何证书。

### 2026-10-26 13:10 — 设置搜索结果的真实焦点缺漏

- settings-search-native31-20261026.json 通过真实 TV IME 几何选择器逐字输入 wlan 并看到实际 WLAN 结果，但方向无法进入结果。初始 helper 跳过编辑框左右键，随后独立 search-native31-direction-diagnostic.json 实际连续左键移出光标到返回按钮，再6次Down仍停在返回按钮；右键回输入框也仍无法Down进结果。原始失败与诊断保留。
- 结果 AX 行确实 clickable/focusable=true，当前 Nav 仅因未包含 com.android.settings.intelligence 而 inactive。Native32 将这个系统设置搜索包纳入现有 Settings 选择/确认/滚动范围；IME显示时仍走原 editor scope，不接管电视键盘。Audit被动匹配同步加入该包，未新增测试点击途径。
- native32-source-delta-review.json 逆向去掉唯一 scope 条件和版本号，SHA 严格等于已验证31源码；原有包行为未改。构建和新版全流程回归仍待完成。
- 搜索测试工具识别空框AX hint与真实查询文本、处理清除按钮原生自动呼出键盘的两阶段B，所有输入和选择仍实际HAT/A/B；19项安全/页面/UART测试仍通过。

- Native32 APK 9208ee87c814e56ab59a89c491b3278b965f1ce4a412fbd90fee0a5e356c2818 于13:11:10构建完成并实装。实际TV输入wlan、WLAN结果A打开、B回搜索均通过，但原泛用定位器跳过Editable左右方向而找不到清除；在下一键前安全暂停，原错误保留。明确 query->Right 路径补测已证明清除按钮可达且A清空。
- settings-search-native32-20261026-clear-continuation.json 最终B返回断言失败。原始窗口证明键盘已经收起，但再B仍留在搜索空框；SearchAutoComplete清焦点/overlay refresh重新聚焦会消耗返回。此为scope扩展后的实际退出缺陷，不将整个搜索写成通过。
- Native33 在IME隐藏的搜索页B路径调用唯一原生 search_toolbar 直接 ImageButton 的Up CLICK；源码 SearchActivity.onNavigateUp 明确finish()。IME显示时仍只发正常Back收键盘。按可见/启用/可点击、明确class、toolbar及包名、唯一性限定，不匹配清除ImageView、不执行结果行。假返回值也不跟发第二次Back。native33-source-delta-review逆向SHA确认其他既有包路径未变；待新构建与全流程重测。

### 2026-10-26 13:43 — 搜索完整链路通过，WLAN高级表单开始

- Search原产物与设备APK哈希同为8f697e5e…，排除误用不同APK。稳定诊断 search-native33-back-stability-diagnostic.json 证明键盘隐藏时B确实触发一次返回CLICK并增加actionCount，但未退出且重新显示IME，因而不能把Nav33本身当成已解决退出。
- prepare_rgsp_settings_search.py 以SearchFragment原SHA 0651021c…为门禁，在RGSP的 setActionBar 后给 search_toolbar 配置明确 activity.finish() 原生导航回调；保持原有搜索/索引/输入行为。ActionBar菜单准备分发是源码中的候选原因，不声称已直接读出内部 mMenuPrepared 状态。
- 构建目标增加SettingsIntelligence，两处允许列表同步；没有放宽CPU/RAM/IO限制。13:31首轮仅因shell目标列表未同步而立即拒绝，原失败保留；13:32:18轮于13:34:14成功完成。新原生SettingsIntelligence SHA70541876e27c2211dd981735fb4126823c8d297bfb5d40cdc639f276c5b1a233，实装/data更新且pm活动路径核对。
- native-search-up-callback-b-smoke-20261026.json 已实际B退出到Settings。第一次完整重测因输入框聚焦后异步弹IME，测试多发的开键盘A输入了t，使夹具变成twlan；原失败保留，属于测试准备问题。测试改为聚焦后观察IME、有界等待后才决定是否A，且输入夹具前严格断言空框。
- settings-search-native33-searchup-settle-20261026.json 全流程PASS：实际TV逐字wlan、真实WLAN结果A打开、B回搜索、明确Query->Right选清除并A、B收键盘再B退出设置。Native33 SHA07303d534446d83c458a14136c2cc9daf3228c5852f6c8a88254424e92f11bbb，13:19:51构建于13:21:11完成。
- staging/packager新增SettingsIntelligence必需组件、SearchFragment/SearchActivity源码证明，以及第九个精确实测组件哈希门禁，避免只装/data却遗漏整镜像。新的native33-searchup阶段开始；所有旧阶段不再用于最终包装。WLAN手动代理/静态IP/PAC/EAP表单随后继续，未保存测试网络。

### 2026-10-26 16:52 — WLAN复杂表单通过，系统扫描继续

- 13:46的精确viewport图最终命中650步上限，13个必需字段都已到达但没有闭合所有状态边；原 wifi-forms-native33-searchup-settle-20261026.json 保留。改用按语义控件的有界上下遍历，独立检查SSID二维码右/左、取消/禁用保存右/左，并逐个打开下拉菜单做上/下/上遍历与B取消，避免把每个像素滚动偏移当成新的按钮。
- 等待期间设备锁屏，16:19的续测页面门禁在任何导航键之前停下。唤醒+A解锁后仍是原Add Network window79、手动代理/静态IP未改变，继续原未保存表单。无测试网络提交。
- 手动代理+静态IP及PAC两份表单均完成并实际A取消。EAP安全类型有首屏之外选项，设备实际标签为WPA/WPA2/WPA3-Enterprise；此前按EAP或WPA/WPA2-Enterprise查找失败属于测试标签/滚动假设，保留全部原始收据。企业模式原生不显示SSID二维码，不能把隐藏控件当作不可达，条件化检查后继续。
- wifi-forms-native33-enterprise-v3-20261026.json 完成三类表单和所有暴露下拉菜单、输入框、次级/页脚控件与实际取消，原Xiaomi_0421仍COMPLETED。Manual/PAC通过页从相同组件/同一表单的前序收据保留，续测链含来源SHA；未抹掉旧GRAPH_LIMIT及准备失败。
- 系统/应用和通知/显示扫描继续，完成的添加语言ListView页按相同Settings SHA和live指纹复用；Nav30->31仅纯文本ScrollView、31->32仅Search包、32->33仅Search返回路径，逆向SHA审查证明确认该ListView路径未改，不把原30按键记录冒充33实测。
- 新阶段h700-v5i-dpad-20261026-native33-searchup-stage完成，system/vendor只读fsck=0；native33-searchup-stage-live-component-match-20261026.json 核对九个活动组件精确一致。整镜像尚未包装，尚未写物理卡。


### 2026-10-26 17:25：继续系统深层菜单和 GPU 故障隔离

- Wi-Fi 高级表单最终结果：`wifi-forms-native33-enterprise-v3-20261026.json`，手动代理/静态 IP、PAC、PEAP/EAP 表单的语义控件、选择器、页脚和取消通过；未保存测试网络。旧 GRAPH_LIMIT 和准备失败记录保留，未改写为通过。
- 系统扫描继续进入开发者选项；应用和通知、显示类别仍在同一串口独占任务后续队列，尚未声明整类通过。
- 核对 DeepSeek 新证据：当前日志确实有 Mali crop 错误和 RenderEngine bind-framebuffer 失败（`current-gpu-import-evidence.json`）。SurfaceFlinger 当前忽略 drawLayers 返回值是实际错误处理缺口，但仅返回 false 会漏掉已 dequeue 的缓冲区释放，且可能反复命中坏槽；不直接采用不完整的 S1 补丁，也不在能力未核实前强制所有层 DEVICE。
- 离屏探针 v3 实际 clear/viewport/glFinish 后重新导入 25 项均正常；v4 在跨尺寸重用同一纹理/FBO 的 25 项也正常；v5 的请求 ES2/ES3/Pbuffer/Surfaceless 三组共 75 项均正常。驱动实际都返回 GLES 3.2，因此这些结果不能当成不同实际 GLES 版本的对照。探针只使用自有离屏缓冲区，不进行显示提交，且未列入 PRODUCT_PACKAGES。
- 对日志中失败的 client target 作只读描述符核对：原生 ANativeWindowBuffer 与 private handle 均为 720x480、stride720、RGBA8888、usage0x1a00（`current-native-buffer-geometry-base64.json`）。只保留匹配对象的几何信息，原始堆数据未落盘。早先 exec-out 失败/二进制被终端换行转换的读取不作结论依据。
- 仅为下一轮隔离编译了有次数上限、属性开关控制的 HWC 只读元数据诊断版本 f5eca82d…；暂未安装，生产源码和产品安装目录中的 eac4cb95… 已按哈希恢复。诊断版本不用于最终镜像。下一步在当前菜单扫描安全结束后，读取真实 client target 的 crop 属性，以区分分配/复用问题。
- RG34XXSP 未连接，轻微亮暗闪烁仍缺少实体对照；硬件 VSYNC 缺失仍是已记录问题，不能把离屏通过解释为屏幕问题修复。


### 2026-10-26 17:43：发现并纠正同窗口子页的扫描漏判

复核当前 AOSP 键盘根页时，发现“偏好设置”实际打开了自动大写/按键音效页面，但旧 fingerprint 只统计 native focusable=true 的 clickable 节点；旧 PreferenceActivity 的条目为 clickable=true/focusable=false，所以标题与 window ID 不变时被误记 NO_TRANSITION，后续条目没有继续扫描。这是扫描工具漏判，不能据此声称这些入口不支持十字键。

- 旧根页结果已通过 `legacy-keyboard-page-identity-validation-review-20261026.json` 降级，明确要求重扫根及所有实际子页；保留旧记录。
- fingerprint 改为纳入所有可见 clickable 条目；打开后短暂等待异步 Fragment 事务；同窗口子页返回时必须核对原父页内容，不能只看 window ID。
- 20 项工具检查通过，新增的实际同窗口菜单测试仍待独占串口任务交接后执行。
- 已准备 `native33-supplement-plan-20261026.json`（AOSP 键盘、指针速度、快捷键帮助、默认拼写工具、三个字典列表、WLAN 偏好/已保存网络/已连接详情、私人 DNS）。APK 安装器专用补测仅使用自有 fixture，确认按钮只聚焦、实际 A 仅用于取消，临时 AppOp 需恢复；尚未运行，不算通过。
- HWC 诊断 v2 f27e00ea… 支持按 debug 属性 ticket 分批最多 12 条只读记录，已上传校验但尚未安装；生产源文件和产品安装 artifact 仍为原版本。


### 2026-10-26 17:52：检查点续测与安全边界

旧批任务 82327 已用自有 STOP_AUDIT 标记安全结束，完整快照保存为 `native33-system-checkpoint-harness-refresh-20261026.json`。停在开发者选项所属“窗口动画缩放”弹窗，只按 B 取消并核对回到同一 window152；`native33-harness-refresh-parent-return-20261026.json` 记录全过程。自有停止标记按确切字节移除。

新批 `continue_list.py --tag native33-dev-fragment-refresh-20261026`（`exploration-885041dc40.json`）保留原前向前缀，继续未完成的开发者页面。续测规则现在不会跳过已聚焦但 A 尚未执行或子页尚未完成的入口。竖直 CheckedTextView 选择列表使用完整前后遍历；同排页脚按钮仍检查水平通路。所有行为通过 HAT/A/B，选择器只遍历和取消，不确认修改。


### 2026-10-26 19:00：Nav34 行可见性、开发者完成与显示诊断状态

- `exploration-885041dc40.json` 完成开发者列表前后遍历，103 个不同控件；保留 native33 原前缀及 30 个续测页面记录。系统界面演示模式、运行服务详情仍列为专门补测，未把未展开入口当通过。
- 新版 Nav34 `076f03cc81be3e095f2cc9cf10bb46e1d052b16b18514e194a367ec5bd0325f9` 已 native 编译、安装并核对实际服务版本。唯一功能增量是在 Settings 的 ListView/RecyclerView 中，对非编辑目标调用其声明的 SHOW_ON_SCREEN；ViewPager 日历日期排除，Files/locale/IME/激活/返回/候选收集保持原代码。`out/native-settings-list-visible-v34-20261026/source-delta-review.json` 逆变换精确匹配 native33 原源码。
- `settings-list-visible-native34-20261026.json` 最初用整个64px行背景高度作严格判据，拦住顶边56px行；截图确认首行文字及单选框完整，只有8px空白边距裁切。失败保留。`settings-list-visible-native34-v2-20261026.json` 在同一受控未保存弹窗续测，七项全部前后可达，中间行完整64px、边界内容完整可见，实际取消且动画值1.0不变；边界截图人工核对。不要把原先3px中间行问题与这项边距区别混淆。
- `native33-system-developer-completed-reuse-20261026.json` 保存66个完成页及原始源哈希，排除已知错误的旧AOSP键盘根页。随后 `exploration-1a1f6dff78.json` 用 native34 完成系统主列表、已完成子页重入/返回；缓存保留原 native33 内容记录与版本，未声称所有深层内容在34重跑。
- 搜索工具栏统一由 SearchMenuController 启动同一搜索实现，宏扫描仍逐个核对按钮可聚焦，完整搜索输入/结果/清除/返回用专门用例；避免每页重复同一搜索流程。原 full native33/705 搜索通过记录保留，最终34搜索回归仍待做。
- 图形诊断 f27e00ea… 两次临时加载均恢复为正式 HWC eac4cb95…，/vendor 已回只读。前两次未得到有效元数据记录，不作驱动结论。第一轮后还做了一次完整内核重启，`reboot-*.json` 保留 boot_id 及默认TCP无监听验证，恢复受限调试连接。
- 锁屏诊断发现窗口给出的 userActivityTimeoutOverride=10000ms，虽然系统 screen_off_timeout=1800000。首次观察程序启动/串口等待会耗尽锁屏10秒，造成采样前再次休眠，A无法解锁；不能把这个黑屏当作原GPU频闪。`a-unlock-awake-retest.json` 在临时保持唤醒条件下，实际POWER关/开 + scan304 A 完成解锁，原stay_on=0已恢复。`wm dismiss-keyguard` 仅用于恢复诊断环境，从不计作A解锁通过。
- Audit.wake 现先预热被动观察程序，再依据真实休眠状态发送短POWER，仅在PM Awake、Display ON、SystemUI interactive后允许下一步。未修改已通过的SystemUI锁屏逻辑。
- HWC v3 诊断已编译为 ab02da7014b4bc0b6d3743d1fbfcaecd59ee562ac9321cb6102959f5bd20cd88，位于 `out/flicker-investigation-20261026/hwc-client-metadata-v3`，**尚未安装**。直接在client-target入口记录首24次元数据、校验native-handle结构及4KiB元数据fd，映射PROT_READ，另向预建自有日志文件留存，便于完整重启早期取证。生产源码与产品安装目录已恢复原HWC。
- 当前失败缓冲区曾有 backing-store counter低32位为0，而服务热重启后旧分配器仍存活且新缓冲区编号继续增长；“首个分配缓冲区/编号0”只是待验证假设，尚未据此添加跳号、预分配或驱动补丁。
- 原 native33 stage 已因34增量标为STALE，最终镜像仍未打包。设置输入法、应用通知、显示、网络尾页、文件APK取消流程、最终回归/重启和镜像打包仍需完成。RG34XXSP轻微亮暗闪烁没有连接实体复测。


### 2026-10-26 22:25 — 黑闪的受控复现与启动缓冲区候选修复

- 临时 HWC 元数据记录器仅以只读方式映射 client-target 属性，暖重启和整机内核重启使用同一显示组件：暖重启全部缓冲正常，GPU 错误0；整机重启后的 buffer counter0 裁剪字段为0,0,0,0，另外两块为正常 unset 的-1,-1,-1,-1。冷启动收集258行错误（129次失败合成），与错误缓冲反复轮转相符。证据见 hwc-client-metadata-v3/live-warm-cold-trial.json 及原始日志。旧诊断只导出属性前128字节，实际 crop 从128字节开始，因此旧导出不能证明 crop 正常。
- 临时记录器已卸载，生产 HWC eac4cb95…恢复；生产源码和包装器都禁止 RGSP_CLIENT_META_V3 / RGSP_METADATA_DIAG 诊断标记进入镜像。
- FramebufferSurface.cpp 候选修复在 rgsp/cupid 的720×480内部屏首次建队列前，持有一块同几何/usage的启动缓冲作为进程生命周期 reserve，不将其排入显示队列。额外约1.4MB内存，不改面板时序、PWM或内核。尚未证明最底层是谁改坏首块属性，不能将规避称为驱动根因修复。
- libsurfaceflinger候选 SHA7f26f9a5e021001028e94315aa4996671b657cabc4e2a30829c1fc2030ec39ea。首次内核重启实测 reserve 在分配器中、实际HAT遍历设置后错误0。首轮第二次重启虽完成，观察器初始化的ADB shell断流导致整轮未通过，自动回滚到原SHA d873a1cb…；该失败记录完整保留。新增可重复两次重启试验，仅读取连接允许有界重试，按键/写入不重放，正在验证。
- Nav34及候选显示库对应的原生systemimage/vendorimage构建22:18:55成功；新的native34-reserve阶段化正在进行。候选验证未通过前不得将阶段目录当作验收镜像；实体断电启动和RG34XXSP轻微亮暗闪烁仍待刷写后实测。

- 22:30 两次新内核重启验证均通过：live-two-boot-v2-222358.json。每次 allocator reserve 实际在场、候选 SHA 持久、设置实际HAT 60次方向压力操作后 GPU crop/bind/abort错误0；两次 boot_id 不同。保留候选显示库，恢复stay awake=0、系统根分区只读并回桌面。这是软件重启证据，未替代实体断电和34xxsp肉眼验收。其余最终按键批次开始。

- 22:45 native34-reserve阶段完成，system/vendor fsck0，native34-reserve-live-stage-match-20261026.json 对10个活动实机组件与阶段原生组件逐一匹配，无差异。最终镜像未包装。输入法legacy fragment深扫的被动观察器64次轮换存在ready检查/请求竞态，增加最多3次仅观察重试，22项测试通过；方向/确认不重放。另将同一方向/同一真实边界的长按检查限为一次，避免原生循环列表反复绕回。保留原停止和连续来源SHA，继续未完成键盘深扫。

- 22:47 15分钟实际控制器UI操作监测通过：final-ui-stress-20261026-223122/receipt.json，SF PID1511全程不变，GPU错误0。1529次显示驱动采样的 backlight 均50、mgr err均0；本机没有 /sys/class/backlight 节点，因此背光证据来自disp状态，不能当作实测PWM电压或34xxsp肉眼结果。
- Legacy子片段返回会恢复父列表滚动位置，原先仅比较可见前8行会误判并多按B。现在限定相同包/窗口标题/对话框头/实体头，并要求出现父页独有控件且当前行均属于已观察父页；纯共享工具栏和子页本身均不能被接受。24项测试通过，保留RETURN_FAILED原记录并重新实际进入/返回复核。INPUT_METHOD_SETTINGS在本机构建解析到管理键盘，补测的父页setup改用清单核实的LanguageAndInputSettingsActivity；所有其余菜单仍走HAT/A/B。

### 2026-10-26 23:05 — 深层原生下拉框旧值回填修复

- Legacy键盘根菜单复核exploration-24abf121ee.json已通过；原观察器读取失败/循环列表/过严返回判定收据及来源SHA保留，不抹掉旧RETURN_FAILED。
- 自定义输入样式现有“德语 (QWERTY)”打开却显示“南非荷兰语”，截图nested-style-editor-225524_897503.png。原CustomInputStylePreference.setSpinnerPosition对新构造的SubtypeLocaleItem/KeyboardLayoutSetItem做Object.equals，而两类未覆写equals，所以总匹配失败并停在首项。新增prepare_rgsp_latin_style_restore.py只把该处改为localeString比较和layoutName比较，原/新源码完整保存及逆向SHA门禁；未改IME输入路由、生命周期、写入时机。
- 原未保存弹窗已B取消下拉框、真实A取消样式，原德语/法语两项保留并回桌面。23:00:14受限构建LatinIME+systemimage成功，新APK0109375e241ed53ff69d71d5f6abc2797d4618967753d925052a54118eae14be实装，TV IME不变。新德语弹窗初值检查通过，双下拉列表/法语QWERTZ/空白字典编辑测试继续。
- 新native34-reserve-style-stage完成，system/vendor fsck0；native34-reserve-style-live-stage-match-20261026.json核对11个活动组件全部一致。所有此前stage保留但失效，包装门禁也增加LatinIME实测SHA。


### 2026-10-26 23:57 — 默认应用共用主题与可选服务缺失

- 应用信息“主屏幕应用”真实触发PermissionController NPE。values-television/Settings继承Leanback无原生ActionBar，而DefaultAppActivity/List仍创建handheld SettingsFragment并无条件调用getActionBar。新增prepare_rgsp_role_settings_theme.py：只在TV为这两类Activity应用显式有ActionBar的主题，Role SettingsFragment加空值保护；原4源码SHA门禁，未改权限授予或默认角色选择逻辑。23:34:14受限PermissionController+systemimage构建成功，新APK6335844edbf0be9d9e6feeacfcabfd38608c24b8016625bb73943389d344270c实装。默认HOME不变。
- 默认HOME真实图遍历3个候选+Up闭合；A点已选AT4K后进入桌面，HomeRoleBehavior.onHolderSelectedAsUser源码明确启动HOME，原“必须仍回AppInfo”断言错误保留。独立B返AppInfo已通过；默认浏览器、默认HOME从列表进入/方向/返回通过。打开链接后进入日历条目又出现独立进程退出，不能将整个默认应用列表扫描写成通过。
- out/native-open-links-widget-20261026/repro.json/repro.log 控制复现Settings PID16756->17839：ClearDefaultsPreference构造时无条件获取AppWidgetManager；本机未声明FEATURE_APP_WIDGETS、appwidget服务不存在，SystemServiceRegistry.wtf被系统策略视为严重错误而SIGKILL9，ManageDomainUrls/SubSettings均force-crash。新增prepare_rgsp_optional_widget_defaults.py先判断可选feature再获取manager，读取/清理widget绑定权限均null保护；保留浏览器/USB/默认活动处理。正在构建Settings+systemimage。
- 审计工具对RecentApp卡片使用唯一app_title，去掉分钟变化对页面指纹的影响。新Java crash、am_wtf/crash/anr事件和前后台设置/权限进程PID变化均在菜单A后验证，防止把崩溃后的上层页面误记为成功跳转；27项单元检查通过。原错误嵌套在“主屏幕应用”下面的扫描记录全部排除复用；仅6个崩溃前完成且源码未受影响的子页保留来源SHA和路径规范化说明。
- native34-reserve-style-role-stage已fsck0并与12个实机活动组件匹配，但在本次Settings补修后失效，必须新建最终stage；旧目录/原失败收据不删除。15分钟输入记录因getevent只接受一个设备而打印Usage，标记为不可用，不作POWER事件结论；GPU/SF/disp/backlight采样仍有效。采集脚本已改为两个独立getevent进程。


### 2026-10-27 00:17 — 可选widget缺失保护实测通过、最终主批次继续

- Settings+systemimage23:59:03构建完成，新Settings SHA c5bb61836da4e3884dc3dbfe7afa30c6c385d0a1142e089aca0400cfc23830c3实装。新native34-reserve-style-role-widget-stage转换及system/vendor fsck0，12个活动组件与阶段匹配。此前阶段全部保留但不用于包装。
- Calendar默认打开详情能稳定进入，PID18251全程不变；所有语义控件含屏幕下方“其他默认设置/清除默认操作”已实际到达，两个列表分别完成三种支持链接状态、域名行/取消按钮的正反方向和B返回，最后真实B回原打开链接window81。最终证据out/native-open-links-widget-20261026/live-validation-v4.json。未清除任何默认操作，未选择URL或改变链接状态。
- 原按完整focus bounds生成的像素图在Recycler滚动位置上细分大量状态，111条实际边被保留为采样，未声称闭合全像素图；按语义控件补齐可达性和真实菜单交互。首轮误要求尚在折叠区域下方的clear按钮、第二轮完整像素图停止、第三轮旧故障日志滚动误报均保留。故障判定现在按新增日志行比较，避免环形日志头部淘汰时把旧WTF认作新增；28项工具检查通过。初始widget严重错误的原进程16756与修复后18251明确区分。
- 主批次已继续应用和通知、显示、补充菜单、Files APK、搜索/语言/WLAN密码/电源菜单，遇到任何未知故障停下。6个未受ClearDefaults/Role改动影响的已完成应用子页保留来源SHA、旧APK身份及当前源码兼容说明，进入/返回仍现场复核。完整镜像尚未封装，RG34xxSP肉眼亮暗变化、实体冷启动/首次刷入仍留给后续物理验收。


### 2026-10-27 03:28 应用列表末尾续测及串口恢复

- 原批次 `exploration-9cd8901a44.json` 保留204页原记录：应用详情分支及应用列表正反向已执行；最终“更多选项→重置应用偏好设置”后，原弹出菜单自然关闭，B回到应用列表。旧工具错误地期待返回旧弹出窗口并多发B，属于返回模型错误，不能写成产品返回故障，也不能直接把旧记录改成通过。
- Explorer现仅对同一父列表、同一语义溢出菜单，用真实HAT/A重新打开弹出菜单，并核对菜单指纹；其余返回规则不放宽。重置正向按钮只聚焦，单独验证取消按钮A。分类、页面标识、UART及被动观察重试29项测试通过。
- 新尾部测试初次串口初始化被CH343驱动阻塞，尚未进入按键步骤。Windows拒绝重启该驱动；用户重新拔插后COM4无写入打开/关闭检查通过。当前尾部遍历使用显式ADB控制传输，仍由相同nav-hat.sh向真实手柄事件节点发送HAT/A/B，证据单独标明。后续重启日志仍使用UART。
- 当前有效stage仍为 `out/h700-v5i-dpad-20261027-native34-reserve-style-role-widget-stage`，12项组件与实机已核对；尚未生成v5i整镜像。原失败收据与旧镜像不覆盖。


### 2026-10-27 03:43 通知页可选教学视频导致原生崩溃

- `apps-list-tail-closure-native34-20261027.json` 已通过：实际A取消重置、自然关闭溢出菜单后重新用HAT/A打开、系统应用视图104个不同焦点项、正反向各120步，最后A隐藏系统程序并确认菜单恢复。原204页中断记录保持原样，新 `apps-tail-reviewed-completed-reuse-20261027.json` 仅组合已完成正文和新的尾部实测证据。
- 新批次 `native34-final-20261027-033104` 在实际A进入“通知”主页面时检测到原生崩溃。`libVE.so VeRelease → libMemAdapter ion_alloc_open → libvdecoder InitializeVideoDecoder` 发生SIGSEGV；Settings的`VideoPreference.onViewVisible → MediaPlayer.create → prepare` 随后抛IllegalStateException并退出。这不是焦点返回模型问题。原崩溃日志保存在 `out/native-settings-video-policy-20261027/original-native-crash.log`。
- 新增 `config_enable_settings_video_previews` 默认true，RGSP产品overlay为false；VideoPreference初始化和onViewVisible共用的initMediaPlayer均在创建播放器前检查此能力。仅关闭可选教学视频，不更改通知控件、输入路由或视频解码库；底层厂商视频解码故障仍未修复。源码准备脚本有原SHA和逆变换门禁。
- Settings+systemimage受限编译03:39:44成功。新Settings APK SHA256 `1b6e0430b1432e5ced199af74a7472f666d766d71a867f1faeb65b7e4a97d25f`，aapt2核对该资源false，已安装并核对实际pm path哈希。新stage `h700-v5i-dpad-20261027-native34-reserve-style-role-widget-video-stage` 正在生成，先前stage不包含本修复。
- `native34-final-20261027-034242` 已恢复未完成分类扫描；旧应用正文仅在新实机入口指纹相同的情况下复用，并记录VideoPreference专属差异证明。原失败批次不覆盖。
- 应用列表搜索的专用补测已用TV键盘输入rgsp、出现3个真实结果、A进入RGSP导航详情、B返回原列表。Android会重建选项菜单并折叠搜索框，旧脚本错误要求查询保留，StopIteration收据保留；已按真实父页行为补正，清除按钮完整测试待本批次。
- 文件APK补测先前经DownloadsProvider索引入口未找到ADB新建文件，已暂停并按SHA清理唯一APK夹具；未触发安装。后续改经此前审计过的RGSP H700完整文件系统根入口，排除下载索引依赖。独立真实HAT观察可进入网格文件、滚动到T.txt.zip，暂不把索引/测试查找停点认定为产品导航故障。


### 2026-10-27 04:44 应用分类闭环及显示续测

- `native34-final-20261027-040151/batch.json`：应用和通知扫描04:33:57退出0，根页BIDIRECTIONAL_SCAN_DONE；包含通知、默认应用、权限管理器各类别/系统应用视图、特殊应用权限各可见分支。新视频能力开关修复后通知子树已经完成，无新的Settings进程退出。
- 前一批次034242在通知、默认浏览器/桌面完成后主动STOP_AUDIT保留检查点，非新产品故障。`apps-notification-checkpoint-open-links-alias-reuse-20261027.json` 保存完成记录及源码入口证明：AppOpenByDefaultPreferenceController 与 DomainAppPreferenceController 均启动 AppLaunchSettings，使用同一应用包名/UID；四个实际可见链接应用（日历、图库、音乐、WebView Shell）均重新A进入、核对完整入口指纹后复用正文、B返回，未更改默认链接。
- `app-list-search-native34-final-20261027-040151.json`：真实TV键盘输入rgsp筛出3项、A打开RGSP导航详情、B返回原列表、重新打开原生折叠的SearchView、输入单字夹具、A清除并B收键盘/折叠，通过。先前错误要求查询保留的StopIteration收据不覆盖。
- 显示分类正执行：壁纸、屏幕超时七档、字体大小、显示大小、屏保已逐项扫描，锁屏显示/消息正在检查；不启动屏保、不保存消息、原显示参数保持。
- 后续收尾脚本 `run_post_batch_closure.py` 必须等待导航批次完成，才执行添加通知音选择器取消、PIN/密码第一步Next到空确认页并取消、实际手柄A重启。最后重启将核对12项关键组件及额外6项框架/默认设置/日历/硬件KL，另用真实HAT/A/B从桌面进入设置和WLAN再返回。最终整镜像仍未生成。


### 2026-10-27 05:35 动态统计行与服务生命周期共性修复

- 核对补测发现 `exploration-d3f04142b1.json` 实际停在“正在运行的服务”，不能作为导航服务详情证据。原按A前为14MB，之后列表为15MB；原identity包含实时内存值，会在更新时丢失匹配并回到首项。Native35仅对Settings的GridLayout集合行、同时具有唯一name/size/description/uptime结构者，使用稳定name；窗口、class、父ID、集合位置及重名拒绝规则保留。其他点击、范围、IME、滚动及Files路径逆变换逐字匹配34源码。
- 安装时快速dumpsys暴露另一既有生命周期错误：getServiceInfo在绑定前为null；旧dump读取flags导致导航服务退出，又触发框架resetLocked重复unlinkToDeath的NoSuchElementException，Android框架重启但内核/SF未重启。原崩溃日志已留存。新dump空值保护及框架仅针对不存在death recipient的幂等清理已原生构建、热装。
- 新服务JAR `7015b60d93e1b516378cf91b691cc628305ba37ec7cc872013babf5e8159bff5`；新Nav35 APK `e5bbf9b82710a8c207ba05dfe9da6ca1eb21ebd4ba8309ffe3f6318abc2f4f2a`。Settings仍1b6e...，其余组件不变。`native35-live-row-lifecycle-twelve-match-20261027.json`核对全部12项。最新有效stage为`out/h700-v5i-dpad-20261027-native35-live-row-lifecycle-stage`，system/vendor fsck均0；旧stage均不含本次增量。
- `accessibility-lifecycle-native35-20261027-0525.json`：短暂移除且最终完整恢复原无障碍列表/主开关；未绑定的手动服务实例flags=0正常dump；两次仅终止自有导航进程后自动重新绑定flags=114，system_server PID17915全程不变。原0523因am stopservice成功仍返回1的测试处理错误及人工恢复收据保留。
- `running-service-detail-native35-stable-row-lifecycle-20261027-0527.json`：三次实际A进入“正在运行的应用”，核对left_button后才扫描；两次追加试验不在寻焦与A之间加入设备RPC；B每次回原列表，未停止/报告服务。原34错误未跳转记录不覆盖。
- 快捷键帮助是SystemUI全局窗口，am start设置页不会关闭；原拼写检查setup已安全停止。`followup.py`现在每个独立dialog完成后显式B取消并验证窗口已离开，再进入下一项。快捷键原弹窗已实际B关闭。
- Java回归：14方向案例、动态指针几何及7回收控件身份案例通过；Python分类/窗口标识/UART/被动重试29项通过。剩余9项补充计划由`native35-final-20261027-053142`继续，完成步骤引用旧不可变收据及两个精确源码增量证明，不重跑已验证正文。整镜像仍待全部收尾测试后封装。


### 2026-10-27 08:44 最终回归续测

继续固定 native35/services7015/Settings1b6e 的原生组件集合。文件安装弹窗的初始 buttonPanel ScrollView 同时含取消/继续文字，旧定位辅助函数误把父容器当作目标，导致实际 A 落到默认取消按钮；已仅在安装器测试脚本内改为唯一按钮资源 ID 定位，并严格复核 Button 类型、焦点文字。原始失败和清理记录全部保留，产品组件没有因此修改。补入无障碍服务、隐私权无障碍使用、正常电池提示、错误报告、最小宽度、待机应用及系统跟踪的只读方向遍历与返回测试；不生成报告、不录制、不改密度、不停服务。整卡镜像尚未输出，不能将阶段分区当作最终发布包。


### 2026-10-27 09:02 文件安装边界与最终回归

- `files-apk-cancel-native35-final-20261027-085427.json`通过：两个原生警告按钮各四方向边完整，初始buttonPanel仅为一次性输入焦点而不可回达，原图仍保留REACHED_CONTROLS_WITH_PENDING_EDGES；实际A取消回Files。第二次对自有SHA校验APK按实际“继续”，进入安装确认，安装/取消方向图闭合；安装只寻焦，A取消回Files，包仍未安装，SHA保护清理成功。文件定位改为先对齐真实网格列再纵向行进，避免通用BFS在上方视野往返消耗搜索界限；这只是测试定位修正，Files产品源码未修改。
- 设置搜索最终回归通过：电视键盘实际输入、WLAN结果A、B返回、清空和退出。语言中实际A先切English再切中文，TV IME全程保留。Wi-Fi密码和电源回归继续中。
- `native35-stage-source-recheck-20261027-0901.json`重新核对阶段记录的98个源码文件，全部与当前WSL原生源码一致。追加应用详情和存储页横排按钮逐应用寻焦补测，危险动作不按A；补测收据完成前不宣称全部界面通过。


### 2026-10-27 09:28 横排动作补测

- `app-action-rows-native35-closure-20261027-091426.json`通过：实际列出的22个应用逐个A进入应用信息，并A进入存储和缓存；所有可见启用的button1/2/3逐一真实HAT寻焦，禁用项记录。全部B返回原应用信息和应用列表，没有按打开/停用/强行停止/清除按钮的A。
- 原090734/091143两个失败是纵向寻焦不足：居中的header_details（查看全部应用）位于最近应用卡片中间列下方，向下从左列会按空间导航进入通知，不能把此结果认作入口不可达。改用确切资源ID的四方向寻焦后实际A进入成功；保留原失败与9次实际Up可回达的观察收据。通用top增加了从工具栏进入正文再向上确认的只读方向步骤，但最终决定性修正是精确四方向定位header_details。
- 本轮最终主批次 `native35-final-20261027-085427/batch.json` 5项剩余回归均已完成，原应用/显示/键盘/补充菜单等完成步骤的不可变来源链保留。尚待信息菜单、通知音频选择器、PIN/密码空确认页、整机重启和整卡封装。


### 2026-10-27 17:03 共性根因：无触屏设备误声明触屏

- 通讯录抽屉按钮AX为focusable/clickable，但原生四方向图无法到达。框架ViewGroup.shouldBlockFocusForTouchscreen会在设备声明FEATURE_TOUCHSCREEN时屏蔽工具栏子焦点。当前无触屏RGSP仍从供体继承该feature。
- 仅增加产品vendor权限XML的4个unavailable-feature触屏声明及copy规则，没有修改通讯录、导航服务或其他Java/APK/HWC。源码逆变换匹配；工作区CRLF与原生LF差异已确认并保留各自行尾。第一次源码预检保护停下，未加补丁的短暂构建已显式终止；随后正确的受限构建164503成功。
- live-install.json记录新文件SHA35a31d...与vendor恢复只读；实际电源菜单内核重启reboot-164803后pm has-feature为false（该命令false返回1，首次只读断言误判记录保留）。contacts-native35-policy-v2-20261027.json验证4个可见按钮全部可达，实际A打开抽屉、抽屉图闭合、B关闭。该包不在导航服务接管范围，证明原生焦点修复。
- 新有效stage为h700-v5i-dpad-20261027-native35-notouch-stage：原38项组件与整个system raw逐字节不变；新增3项原有系统应用身份及vendor新XML，共42项。stage-delta-review.json记录source仅mk和新XML变化，system/vendor只读fsck通过。旧stage缺少该共性修复，禁止作为最终封装输入。
- 正在执行fresh post-no-touch五项主回归；随后补齐通讯录设置入口返回、通知音频选择器、凭据空确认与最终重启。整卡镜像仍未生成。


### 2026-10-27 17:32：新无触屏能力策略后的收尾补测

- 当前唯一待封装阶段为 `out/h700-v5i-dpad-20261027-native35-notouch-stage`（42 项组件），system 原始分区与前阶段完全一致；vendor 新增禁用虚假触屏能力的权限声明。
- 新阶段的 Files APK 安装器取消、设置搜索、语言切换、WPA 密码电视键盘和电源菜单五项全新回归均完成：`native35-final-20261027-165849/batch.json`。
- 四处旧清单遗漏的更多选项弹出菜单已实际 HAT/A 进入、方向遍历、B 取消：`followups-171722.json`。继续补查删除时间表确认选择器（不删除）、电池用量、添加打印机/IP 输入（不添加）及本地许可查看器。
- 14 项信息页及安全取消补测完整通过；`remaining-information-menu-return-review-native35-20261027.json` 另外逐项核验了全部原生按钮可达及返回父页面，包括通讯录抽屉按钮不再被触屏焦点策略阻挡。
- 打印服务当前 APK 亦与阶段 system.raw 内文件逐字节一致，SHA256 记录于 `bips-active-stage-match-native35-20261027.json`。
- 当前内核 FTRACE 未启用，Traceur 类别为空是能力限制，未宣称录制可用。RG34XXSP 的肉眼亮暗闪烁仍需本镜像首次刷入后的实体复测。


### 2026-10-27 18:07：镜像与实机附加资源对齐、关闭试验覆盖层

- 通知音添加选择器完成实际HAT/A进入、方向图、B返回及A取消，声音URI不变。前两次脚本遗漏展开高级/目标不在首屏导致的寻路失败保留；已按真正列表向下进入，未修改产品代码。
- PIN和密码有效草稿均可启用Next，实际A仅进入空的二次确认页；确认按钮禁用，方向图闭合，B退出，未保存凭据。
- 最终重启核验扩大到附加10项时发现SettingsProvider和framework-res仍是旧实机文件，其余核心12和附加8项均匹配阶段。`additional-ten-preflight-native35-20261027.json`保留差异。
- 新旧APK由阶段raw提取/实机pull，签名完整校验同证书。SettingsProvider classes.dex及manifest完全一致，仅def_show_ime_with_hard_keyboard false→true；framework-res仅菜单键配置0→2和2份Resolver布局变化。旧有效RRO只有菜单键值2，因此普通菜单/已完成输入回归的实际配置未变；Resolver布局需重新实测。`out/native-foundation-align-20261027/review.json`和compatibility.json保留精确资源与ZIP差异。
- 初次对齐脚本漏停bootanimation：它持有已替换framework-res的旧inode，导致ext4恢复只读失败；回滚在同一原因处中断。此时旧Provider已恢复、新framework在位、zygote停止；失败场景完整记录。补停启动动画后，`live-recovery.json`证明两份候选APK均对齐、框架稳定、系统只读、受限Wi-Fi ADB恢复，未清除用户数据。安装和恢复脚本已补占用处理。
- 框架暖重启后旧root被动Dump仍连旧Binder，首次HOME测试返回空windows而失败，原记录保留；停止自有观察器并重建连接后恢复真实窗口，不重放确认键。
- 旧动态RRO已禁用；`home-first-choice-native-framework-once-v2-20261027.json`实际A确认仅此一次成功，测试后恢复原AT4K默认桌面。继续原生始终确认、更多选项子菜单及最终内核重启核验。


### 2026-10-27 18:35：许可查看器及最后菜单补测

- 原生HOME始终确认亦完成：`home-first-choice-native-framework-always-20261027.json`；两份原生底部按钮截图已人工查看，`native-framework-home-visual-review-20261027.json`保留截图SHA。阶段raw中两处已知试验RRO路径均不存在，`no-experimental-rro-stage.json`证明候选不依赖旧覆盖包。
- 删除时间表、电池用量/更多、添加打印机/IP对话框5项均实际A进入、闭合方向图、所有暴露原生按钮可达、B回正确父页，未执行删除/添加/打印。
- 第三方许可HTML暴露巨大DOM，旧被动工具递归枚举阻塞响应。新被动工具仅对com.android.htmlviewer/com.android.webview的WebView正文标记childrenOmitted=EXTERNAL_LICENSE_DOCUMENT_DOM，保留原生窗口/工具栏/按钮；Settings、Files及其他包的树遍历不变。编译并部署ca2ca383...jar，仅终止自有旧Dump，system_server PID保持4154，原工具保留。29项既有Python测试通过。该工具不进入镜像，不发输入或AX点击。
- 资源暖启动后连接状态仍出现空窗口列表，已用串口完整内核重启`reboot-182529.json`，受限ADB恢复；新内核启动后的A解锁和原生窗口读取烟测通过。新许可查看器B返回实际生效但WebView退出较慢；增加只等待观测的有界settle，不重放B。
- `toolbar-submenus-native35-legal-settle-20261027.json`现完整PASS：保留5项已完成图及哈希连续来源，两份许可查看器重新实际A/四方向/原生按钮检查/B返回法律信息通过。外部HTML正文和链接不枚举为Settings菜单，不宣称整个文档所有内容均遍历。
- 当前执行无破坏的位置信息/电池筛选A反向恢复、打印机有效地址草稿的启用Add寻焦和A取消，随后原生资源条件下最终电源菜单Restart。


### 2026-10-27 19:00：软件收尾通过，开始本地整镜像封装

- 位置信息/电池筛选实际A切换和反向恢复均通过；打印机TV键盘输入g使Add启用。通用测试寻路因主动跳过编辑框左右键而误报，手动只发方向确认原生Right→Cancel→Right→Add可达。补测脚本保留这一原生光标边界路径，实际A Cancel、不添加打印机，`overflow-filters-native35-native-editor-final-20261027.json`为最终通过凭据，原失败保留。
- ADB合成LONG_PRESS标记会在Binder无Looper线程首次构造GlobalActions时记录异常，其延时处理路径随后仍会打开菜单；初次立即观察失败及再次发现旧菜单而拒绝A的保护性退出均保留。改用已核验event0 axp2202-pek的KEY_POWER116按住1秒/释放，走真实计时路径；脚本trap保证释放，不改产品代码。
- `native35-closure-20261027-184933/closure.json`完整通过。实际电源菜单HAT/A Restart后，新内核启动、A解锁、核心12+附加10组件全部匹配；touchscreen=false及XML一致；usb/oem_lock found；zh-Hans-CN优先、Leanback、开发/USB/硬键盘显示IME状态保留、Xiaomi_0421 COMPLETED、PC211IPv4/IPv6限制、root/vendor只读，启动及WLAN正反遍历后GPU错误0。
- 新内核首次真实电源输入节点长按后，四个原生动作32次HAT检查和B取消完成，GPU错误0：`power-menu-native35-first-physical-power-after-kernel-20261027.json`。
- 软件正式核验 `out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx_VALIDATION.json`生成，并输出219条原始复核项的说明清单；原始525路径/3234控件观察清单及历史错误不改写为通过。17类菜单由原始、兼容复用与本轮补测共同覆盖，危险动作仅焦点/取消，外部业务和不具备硬件能力另列范围。
- 被动观察工具已退出，system_server稳定，Nav35 flags114保持。当前正在把42项组件的固定阶段封装为本地v5i IMG，未执行整卡刷写/格式化。RG34XXSP轻微亮暗、首次新卡及断电冷启动仍待实体测试。


### 2026-10-27 22:11：v5i 整镜像交付完成

- `out/H700_Android_SingleCard_v5i_ChineseDpadWifiGfx.img` 已生成，大小 32,434,554,368 字节。封装器完成基线SHA、system/vendor fsck0、42组件提取比对、全部输出范围读回，system/vendor范围SHA与阶段raw相同；boot/GPT/factory-data/ROMS保留范围已读回核对。
- 整镜像SHA-256：`3fd34fef4d5a2275f14023dba5dc488330ab0669a50889e8b748e30c9f3e68cd`。Windows Get-FileHash于22:08–22:09独立完整读取，结果与WSL封装器一致；`.sha256`、`_INDEPENDENT_VERIFY.json`、`_DELIVERY_REVIEW.json`与最终`_README.txt`已生成。原草稿及所有失败证据保留。
- 软件菜单验收与本地封装已完成，未执行整卡刷写或格式化；此前实机组件热更新及自有目录写入已记录。交付仍是待实体验收候选版：备用卡首启/断电冷启动、RG34XXSP轻微亮暗、两台实体手柄及实际USB线调试需由刷新镜像后的测试确认。
