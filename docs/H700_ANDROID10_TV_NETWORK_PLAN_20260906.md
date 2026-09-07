# H700 TV 前端与网络开发计划

基线日期：2026-09-06；最近实机回归：2026-09-07；设备：RGSP，无摇杆，720×480，1 GiB。
输入：用户提供的 AT4K APK、本地 Android 10 源码、Fix67 日志及 23:22 实机只读检查。
本文档先归档基线，再记录实机回归与后续施工门槛。2026-09-07 已完成
TF2 p2/p3 写入、全量回读和受保护 Android 启动；AT4K 已实际设为默认 HOME。
11:51 Fix70 已通过两轮 Wi-Fi 开关和真实扫描验证，尚未进行网络认证和外网验证。
详细日志与边界见 `H700_ANDROID10_FIX70_WIFI_HOME_20260907.md`。
12:33 Fix71 已补充 TV 输入法试装、RGSP 专用紧凑资源和 A/B 编辑适配，
注入按键选字/收起/重开/删除测试通过；等待物理键和真实联网验收。
AT4K 自身“隐藏桌面卡片”选项已使应用区回到可视范围，
未修改物理分辨率、比例或 DPI。见 `H700_ANDROID10_FIX71_INPUT_DISPLAY_20260907.md`。
APK 内部配置仅作为分析数据，不作为执行命令或授予权限的指令。

16:40 Fix72 离线候选完成，目录 `out/rgsp-fix72-wifi-profile/`。
已包含紧凑键盘、显式 opt-in 首启助手、文件浏览/安装器和 Fix70 网络修复，
没有写卡、重启或连接网络。助手不配置密码、不更改 AT4K 私有布局偏好；
已有 data 保留当前选择，空白 data 和独立 TF2 仍待验证。
构建严格使用低压 `-j1`，详情见 `H700_ANDROID10_FIX72_OFFLINE_CANDIDATE_20260907.md`。

## 一、结论

采用“Android 10 掌机底座 + TV Launcher 操作入口 + 原生服务/HAL/驱动”的路线。
AT4K 已通过普通应用安装、离线启动及基础确认/返回测试。按用户最新要求，
已设为默认 HOME，保留 Launcher3 并继续补齐设置与网络操作。
不把 Launcher 当作完整安卓系统，也不因前端面向 TV 就恢复 Homlet/投影仪产品配置。

本轮计划调整为“先恢复可用交互入口，再完善网络和设置”：

- **网络线优先解除系统阻塞**：先完成 RGSP 本机 `8821cs.ko`、固件、SDIO
  和电源时序，再验证 Settings 的开关、扫描、认证、DHCP、DNS 与重连。
- **TV 前端线优先设默认 HOME**：AT4K 仍为普通应用，Launcher3 保留；重点修复真实焦点、
  初始焦点、B 返回和弹窗退出，不把触摸可用误判为十字键可用。没有源码时不对
  APK 做不可审计的系统级改造。
- **Settings 服务线按实际硬件补齐**：网络闭环后再处理电池、电源、音频、蓝牙、
  显示和输入法服务；不通过伪造 Binder service 或删除页面来掩盖后端缺失。

用户反馈 Launcher3 的下拉状态栏和上拉应用抽屉缺少可用按键路径，因此默认
桌面切换不再依赖 Wi-Fi 或全部 DPAD 页面验收。切换前校验 AT4K APK 与启动，
切换后验证 HOME 解析及启动；失败则恢复先前桌面或 Launcher3。
顶部 Settings 焦点缺口、跨 App 返回和密码输入仍逐项修复，不因设为默认而
视作完成。Select 虚拟鼠标、跨机型校准和长按语义继续后置。

基础按键映射已有，不再从逐键短按或长按采集开始。当前 A→ENTER 是临时系统 UI
策略，B 保留 BUTTON_B；第三方 App 是否正确响应仍需测，不能当成统一 BACK 已实现。
后续映射工具再分离桌面与游戏语义，游戏中恢复标准 BUTTON_A/B/HAT/Select。

## 二、当前实际进度

| 范围 | 已完成 | 未完成 |
| --- | --- | --- |
| 启动与图形 | Fix67 自动到 Launcher；Mali r20p0 实机渲染；原 TF1 boot 回退 | 60 分钟老化、10 次冷启动、硬件 VSYNC |
| 构建 | Fix72 低压增量构建及 Fix67/Fix70/键盘候选合包通过，ext4 和文件哈希检查通过 | 原始镜像一次性包含全部修复、两次干净构建、空白 data、候选实机回归 |
| 输入 | 本 RGSP 短按和临时 keylayout；A 可作为直接确认 | 跨 App 返回、虚拟鼠标、跨机型校准 |
| 网络 framework | 服务已发布；Fix70 连续两轮开关通过，HAL/supplicant running，Settings 真实扫描通过 | 认证、DHCP、DNS、HTTPS、重连 |
| 网络硬件 | `8821cs` 实机加载；`wlan0/p2p0` 可由 HAL 重载恢复；修复状态属性和接口名不匹配 | 修复后的完整重启、连接稳定性、电源管理 |
| 前端 | AT4K 已设默认 HOME；Launcher3 保留；Fix71 布局调整及键盘注入测试通过 | 完整物理 DPAD 焦点/输入法、低内存、冷启动持久性 |
| 安装入口 | Fix72 已包含 DocumentsUI、PackageInstaller、PermissionController；已有 UART 安装实测 | 文件浏览到安装授权的实体按键闭环、存储访问、第三方 APK 兼容性 |

实机检查：`out/logs/uart/rgsp/rgsp_serial_exec_20260906_232208_115200.log`。
uptime 1242.20 秒时 `boot_completed=1`，五个核心 PID 仍是
`1494/1504/1912/2090/2230`。这不能替代持续老化和多次启动验收。

2026-09-07 已确认正确串口为 `USB-Enhanced-SERIAL CH343 (COM4)`。
原厂 Linux 可登录，且已完成一次受控重启和完整 U-Boot/Linux 启动日志采集。
live CID、分区几何、TF2 p2/p3 写入回读和 TF1 boot/env 恢复已复核；
当前门槛转为网络认证、输入法和重启持久性。

## 三、AT4K APK 审核与实机回归

本地文件：
`C:/Users/LPF/Downloads/AT4K启动器专业版汉化版V1.2/AT4K启动器专业版汉化版V1.2.apk`

| 项目 | 静态检查结果 |
| --- | --- |
| 文件大小 | 8,374,207 bytes |
| SHA-256 | `1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9` |
| 包名 / 版本 | `com.overdevs.at4k` / `1.2` / versionCode `17` |
| 最低 / 目标 SDK | `27` / `36`，当前设备为 `29` |
| 原生 ABI | 含 `armeabi-v7a`，另含 arm64-v8a/x86/x86_64 |
| ARM32 原生库 | `libandroidx.graphics.path.so` |
| 主 Activity | `com.overdevs.at4k.MainActivity`，横屏 |
| 桌面入口 | MAIN + HOME + DEFAULT，同时有 LAUNCHER/LEANBACK_LAUNCHER |
| 功能声明 | Leanback required=true，touchscreen required=false |
| GMS 痕迹 | `GoogleApiActivity` 与 `com.google.android.gms.version` 元数据 |
| 无障碍 | `com.overdevs.at4k.Hra`，可请求按键过滤，不读取窗口内容 |
| 网络配置 | INTERNET、ACCESS_NETWORK_STATE；允许明文流量，系统证书信任 |
| TV 数据 | 请求 TV listings/channels/EPG 权限，实际依赖未运行验证 |
| 签名检查 | 针对 API29 的 apksigner 校验通过，使用 v3 签名 |

签名证书 SHA-256：
`a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc`。
该值与本地 AOSP `build/target/product/security/testkey.x509.pem` 完全相同。
不能把此 APK 的签名通过等同于官方来源或安全审计通过。
没有取得其官方签名对照、源码或再分发授权，不将这个汉化包加入 Git 或发布镜像。

无障碍 XML 列出的窗口包包括 Google TV/Leanback Launcher 与 Amazon Launcher。
这提示该服务可能用于接管其他电视桌面的入口，但未经代码审计和实测不能确定。
首次试装不启用无障碍、不授予 root、不加入 priv-app，也不禁用 Launcher3。
本项目控制默认 HOME，应先用正常 HOME 解析机制，避免额外的按键拦截层。

最低 SDK 与 ARM32 条件相符，只说明具备测试资格，不保证启动成功：

- targetSdk=36 不等于最低需要 Android 16；但新 API 的兼容分支仍需 API29 实测。
- 存在 Google API 组件不等于必须依赖 GMS；必须测试无 GMS、无网络的首次启动。
- 当前 RGSP feature 清单未列出 Leanback；先记录安装及运行的真实结果，不先修改 APK
  或笼统宣告整机 TV 能力。本地 SystemServer 在 FEATURE_LEANBACK 下会启动
  TvInputManager/TvRemote 等服务，增加声明必须一并审计这些依赖。
- 文件名“汉化版”和小体积不能证明中文页面覆盖、720×480 可读性、焦点完整或低内存。

检查工具：本地 AOSP `aapt2 dump badging`、`aapt2 dump xmltree`、
`java -jar apksigner.jar verify --min-sdk-version 29 --max-sdk-version 29 --print-certs`，
以及 OpenSSL 对本地 testkey 的证书指纹比较。外部检索本轮未返回可用资料，
以上结论仅针对该 SHA-256 的本地文件，不代表所有 AT4K 版本。

### 2026-09-07 实机结果

| 项目 | 结果 |
| --- | --- |
| 传输与安装 | APK 经 UART 校验上传；设备端 `pm install -r` 成功；未授予 root、特权或无障碍权限 |
| 启动 | `com.overdevs.at4k/.MainActivity` 显式启动成功；无网络、无 GMS 条件下可进入 |
| 运行稳定性 | 运行期间未观察到 AT4K crash；总 PSS 约 `38943 KB` |
| 基础按键 | ENTER/A 能打开选中应用；BUTTON_B/B 能从第三方应用返回 AT4K |
| Settings 入口 | 触摸坐标点击顶部“设置”可进入原生 Settings；该入口在 UI 树中不可聚焦，DPAD 一次右移后确认曾进入 Calendar，不能视为设置入口已通过 |
| HOME 策略 | 初次试装未修改；后续 11:34 已设 AT4K 默认 HOME，Launcher3 保留 |

实机证据：

- `out/h700-android10-b2/at4k-launch.png`
- `out/h700-android10-b2/at4k-after-enter.png`
- `out/h700-android10-b2/at4k-after-b.png`
- `out/logs/uart/rgsp/rgsp_android_probe_20260907_021404_115200.log`
- `out/logs/uart/rgsp/rgsp_android_probe_20260907_021642_115200.log`
- `out/logs/uart/rgsp/rgsp_android_probe_20260907_021736_115200.log`

结论：AT4K 可作为候选 TV 前端继续评估，但当前不能直接承担“十字键完成系统操作”的主入口职责。
顶部按钮的真实焦点节点、初始焦点、B 返回和弹窗退出仍需补验；
后续按用户要求已提前设为默认 HOME，不再等待全部焦点问题解决。

## 四、前端验收顺序

1. **并存试装**：留存包 SHA，普通应用安装并显式启动，不先改变默认 HOME。
2. **基础运行**：离线、无 GMS 首次启动，应用列表、中文、图标、设置入口、壁纸静态显示；
   TV channel/推荐等可选功能失败不得阻塞应用启动。
3. **无触摸操作**：DPAD 焦点可见，A 确认，B 返回，菜单/弹窗可退出；
   X/Y 只在界面有对应动作时使用，不假设第三方已实现完整 ABXY。
4. **键盘闭环**：选择网络、输入含大小写/数字/符号的密码、删除、提交、取消均能用按键完成。
   TV Launcher 自带输入框不等于系统已经有可用 DPAD 输入法。
5. **低内存**：记录 Launcher3 与候选的 PSS、启动耗时、帧时间、后台增长和系统剩余内存；
   先关闭动态壁纸、视频预览、联网推荐等可选负载，再按实测决定保留。
6. **默认 HOME（按最新要求提前）**：在普通应用可启动后优先切换；测试 HOME、返回、
   崩溃恢复与下一次受保护 Android 启动。Launcher3、UART 和 Linux 回退保持可用。

“前端作为主系统”在此仅指默认交互入口。应用管理、输入法、Settings、SystemUI、
网络 framework 和各硬件 HAL 继续独立存在。第三方前端失败可换，不牵动 GPU 和存储底座。

最新切换工具为 `tools/set_rgsp_home.sh`，仅在运行中的 Android 通过 Package
Manager 修改用户 0 的 HOME 角色，不离线编辑 data 中的包管理数据库：

```sh
sh /rgsp-persist/set_rgsp_home.sh status
sh /rgsp-persist/set_rgsp_home.sh at4k
sh /rgsp-persist/set_rgsp_home.sh launcher3
```

上述路径是待部署位置，当前脚本仅在电脑端准备；还未复制到 TF2 或实机执行。
此优先级覆盖下方历史施工记录中“联网后才切换 HOME”的安排。

## 五、网络分层修复

**N0：Settings/framework 回归，已完成。**
Fix64 的 Settings 曾因 `No service published for: wifi` 退出；Fix67 23:22 已找到
该服务。2026-09-07 已重新打开 Settings 首页和 Wi-Fi 页面，均未复现该退出；
`logcat -b crash` 未见新的应用崩溃。Jar 存在、Binder 发布、HAL 进程存活、
`wlan0` 存在、真正联网是不同的完成条件。

本次 Wi-Fi 回归结果：页面可启动，状态为 `Wi-Fi is disabled`，扫描时间为 0，
`ip link show wlan0` 返回设备不存在。当前网络问题已从 Settings framework 收敛到驱动/
固件/SDIO 绑定和电源时序，不再优先修改 Settings 页面。

**N1：本机模块、固件与加载路径。**
当前常用三处未见 `8821cs.ko`，也未见加载记录或 wlan0。先从 RGSP 原厂 Linux
核对模块、固件、SDIO 绑定及电源时序，记录哈希、vermagic、依赖和参数。
模块须匹配当前 H700 4.9.170 内核，不复制投影仪的 rtl8822bs 或其他 SoC 模块。
Android 用户空间 ARM32 不改变内核模块必须匹配 AArch64 内核的要求。

源码中已确认路径配置风险：当前 Android 10 分支的 BoardConfig 为
`BOARD_WIFI_VENDOR := realtek`、`WIFI_DRIVER_MODULE_PATH := /vendor/modules/8821cs.ko`。
`frameworks/opt/net/wifi/libwifi_hal/wifi_hal_common.cpp` 的非 COMMON 分支把
该宏直接交给 `finit_module`，只有 COMMON 分支会拼接模块名。现已将本机
原厂文件放入 RGSP 设备 overlay，并复制到 `/vendor/modules/8821cs.ko`
和 `/vendor/firmware/rtlbt/`。这只是离线配置完成，不能替代实机加载结果。

已保存的来源与指纹：

- `out/reference/rgsp-linux-wifi/8821cs.ko`
  SHA-256 `59933ce6ca29c88d5c8382e0aa7bf794b1fb42c2595b03f2694901bbfa206a72`
- `out/reference/rgsp-linux-wifi/rtl8821c_config`
  SHA-256 `dec80607c1bb6cbbcf59e085997bfc32fe6aa3dd3919c95b827778254805a37f`
- `out/reference/rgsp-linux-wifi/rtl8821c_fw`
  SHA-256 `897698b5aa750afa20db1a984bf66ac60dca06e896e32748f9b0cf7f3492fa2a`

模块 vermagic 为 `4.9.170 SMP preempt mod_unload modversions aarch64`，
与 RGSP 当前内核 ABI 记录一致；仍需在设备上确认 probe、固件请求及电源/
SDIO 时序。

门槛：模块正确加载、SDIO 绑定且 wlan0 出现，无符号/固件/电源错误。

**N2：HAL 和 supplicant。**
核对当前实际编译分支、libwifi-hal 依赖、VINTF、init、权限/标签、
`/data/vendor/wifi` 和控制 socket。进程 running 不证明 HIDL 方法或 STA 创建成功。
保持现有 Wi-Fi framework，不用永久手动启动 supplicant 替代 Android Wi-Fi 管理链。

门槛：Framework 能通过 HAL/supplicant 完成开关及扫描，Settings 正常显示结果。

**N3：完整联网。**
完成选择 AP、密码认证、DHCP 地址/路由、DNS、HTTPS 连通、网络状态显示与重新连接。
用户在密码阶段输入凭据，不把真实 SSID、口令、BSSID 或完整网络配置推送 Git。
优先完成常用 WPA2 STA；热点、P2P、WPA3 等另列验收，不默认随 feature 声明而完成。

门槛：从 Settings 连接一次，断开再连一次，重启后的受保护 Android 启动能恢复连接。
网络通后才考虑受限的开发用 ADB 传输；不把未认证的网络 ADB 暴露到任意网络。

## 六、Settings 及多机型后续

- 先测首页、网络、应用、存储、显示及输入法，再分别补齐电池、音频、电源与蓝牙后端。
- 不为消除报错伪造 service、捕获全部异常或删除 SystemServer 的真实服务。
  不具备的硬件功能需有准确 feature/VINTF 声明；关闭无后端入口应记录原因。
- 当前 Gatekeeper HIDL 移除和软件回退仅用于 bring-up，不是可信锁屏或生产安全验收。
- Select 虚拟鼠标在前端/键盘闭环存在缺口时再实现：进入和退出必须对称，切换时释放
  已按下事件，避免重复注入；游戏内默认保留 Select，支持机型自定义和紧急退出。
- 多机型流程在进入普通桌面前选择/校准配置；仅靠 H700 型号或共享 VID/PID 不足以识别
  真实按键语义。带摇杆机型另做中心、量程、死区，RGSP 不生成虚构摇杆。

## 七、下一执行批次

| 批次 | 操作 | 完成门槛 |
| --- | --- | --- |
| 0 | Git 基线/进度同步、APK 静态审核、只读网络检查 | Fix69 已推送；COM4 与 Android UART 正常 |
| 1 | AT4K 普通应用与默认 HOME + Settings 回归 | 安装、启动、HOME 解析和注入 B 返回通过；完整物理焦点待验收 |
| 2 | 8821cs 模块/路径/固件/SDIO 修复 | Fix70 两轮 HAL 管理的开关与扫描通过 |
| 3 | Settings + DPAD 输入法 + 网络闭环 | 认证、DHCP、DNS、HTTPS、重连 |
| 4 | HOME 持久性与 TF2 启动路线 | 重启保留 AT4K；独立启动与 Linux 恢复另行验证，不等同当前 handoff |
| 5 | 剩余服务、多机型、鼠标、音频和电源 | 每项独立验收，不回退图形基线 |

正式 60 分钟老化、10 次冷启动、日志容量、内存和干净构建复现贯穿后续批次，
不因为前端看起来完整就将项目标记为整机完成。

## 八、施工记录

以下按施工时序保留历史状态；早期“暂不切换 HOME”门槛已被用户后续
“优先 AT4K”决定取代。当前默认 HOME 和网络状态以本文顶部及 Fix70 文档为准。

- 已通过 UART 启动 `com.android.settings/.homepage.SettingsHomepageActivity`；
  Settings 首页未复现旧的 `No service published for: wifi` 退出。
- 已通过 UART 启动 `com.android.settings/.Settings$WifiSettingsActivity`；
  Wi-Fi 页面可显示开关和“打开 Wi-Fi 后扫描”的正常空状态，截图为
  `out/h700-android10-b2/fix68-settings-wifi.png`，SHA-256 为
  `da256ccfe8563aa6f6328f7c2742867c9cc89f8065555ccfc753f9611bbf849e`。
  这只证明页面和 framework 入口可启动，不证明驱动或扫描已工作。
- 2026-09-06 已完成 Fix67 基线推送；之后修正 UART 校验上传工具的接收超时计算，
  将 115200 8N1 的实际线路传输时间计入大文件超时，并保留 raw 接收时的 `-isig`/大小写行为。
- 2026-09-07 设备重启后重新进入 Android 10；AT4K 已安全上传、安装并显式启动。
  测试未切换默认 HOME、未启用无障碍，未改动 TF1/TF2。
- AT4K 的顶部“设置”按钮可通过触摸诊断进入原生 Settings，但 UI 树未提供可聚焦入口；
  一次 DPAD 右移后确认进入 Calendar。该问题列为前端焦点/操作闭环缺口，不能用触摸结果替代。
- 2026-09-07 已回归 Settings 首页和 Wi-Fi 页面；旧的 Wi-Fi service 崩溃未复现，
  但 Wi-Fi 仍 disabled，设备无 `wlan0`，下一施工批次转入 RGSP 原厂 Linux 的
  `8821cs` 模块、固件、SDIO 和电源时序核对。
- 已将 RGSP 原厂 `8821cs.ko`、`rtl8821c_config`、`rtl8821c_fw` 纳入
  `android/h700-android10/device/roc/rgsp/prebuilts/wifi/`；BoardConfig
  已改为完整 `.ko` 路径，`h700_rgsp.mk` 已增加 vendor 复制规则，
  `ueventd.rgsp.rc` 已声明 Android firmware 搜索目录。
- 本轮施工后的下一门槛是离线镜像检查和 Android 设备实测；在该门槛通过
  前不切换 AT4K 默认 HOME，也不把 Wi-Fi 页面显示为“已联网”。
- 本轮已完成 Android 10 增量构建：`systemimage vendorimage ramdisk`
  成功；vendor 输出已包含上述三个原厂 Wi-Fi 文件，B2 静态检查为 `12/12`。
  `out/h700-android10-preflight/EXT4_CHECKS.json` 记录 system/vendor
  离线 ext4 检查均通过，preflight 脚本明确未执行设备写入。
- 2026-09-07 基线提交 `71cecf3` 已推送到 `origin/main`。随后在唯一枚举的
  `COM1` 上执行只读 UART/U-Boot 探测，未收到提示符；日志为
  `out/logs/uart/rgsp/rgsp_reboot_uboot_mmc_20260907_031225_115200.log`。
  脚本在 Linux shell 提示符之前退出，未发出重启命令，设备写入状态不变。
- preflight 生成器现支持 `-At4kApk`，本地包已包含用户提供的
  `AT4K-launcher.apk`（SHA-256
  `1315ef01d56511a80cb6bb4b9c58bfd3233c0e84cc1e82254cd0898d5dd26ca9`）。
  首启后按普通应用安装并显式启动；在 DPAD、B 返回、弹窗退出和网络
  设置闭环通过前，不设为默认 HOME。
- 2026-09-07 preflight 输出为 `out/h700-android10-preflight/`，其中
  `DEPLOYMENT_MANIFEST.json` 明确记录 `writes_performed=false`；system/vendor
  固定尺寸 raw 镜像分别为 8 GiB 和 2 GiB，目标为 TF2 的 `mmcblk1p2/p3`。
- 最终 `vendor.raw.img` 内容级检查确认存在
  `/modules/8821cs.ko`、`/firmware/rtlbt/rtl8821c_config`、
  `/firmware/rtlbt/rtl8821c_fw`，且 `/etc/init/init.rgsp.rc` 在 Android
  `on boot` 阶段显式执行 `insmod /vendor/modules/8821cs.ko`。该动作是
  为应对 Android 用户空间未自动触发模块加载而增加的 bring-up 诊断措施；
  不能替代实机 probe、固件请求和电源/SDIO 时序验证。
- 原厂 Linux 实测为 Linux `4.9.170`、`sdc1/mmc2` 上的 RTL8821CS，
  初次 probe 返回 `-123` 后重试创建 `wlan0/wlan1`；Android 日志中的
  `get gpio ... failed` 与 `sdc1 RTO` 也必须结合重试行为判断，当前不先
  修改 DT GPIO。下一步在 Android 上分别记录 `/proc/modules`、`dmesg`、
  `ip link`、Wi-Fi HAL 和 Settings 结果。
- 2026-09-07 10:55 Fix69 已完成 TF2 p2/p3 写入及全量回读哈希校验。
  写前发现原始 preflight 未包含全部 Fix67 部署修复，已先补齐并逐文件
  对照旧卡：system 除同值默认属性外与 Fix67 一致；vendor 改动集中于
  Wi-Fi 模块/固件/HAL/加载配置。旧 system/vendor、ANBOOT 和 GPT 均有
  完整本地备份，TF1、data 和 ROM 分区未写入。详细记录见
  `H700_ANDROID10_FIX69_WIFI_DEPLOYMENT_20260907.md`；下一步插回 RGSP
  进行串口启动和联网验证，仍不切换 AT4K 默认 HOME。
- 2026-09-07 11:34 已通过 live Package Manager 将 AT4K 设为默认 HOME，
  校验 APK 哈希、显式启动、HOME resolver 和 HOME intent 均通过。
- 11:50 安装 Fix70 HAL/init（先备份、固定哈希校验、只修改 vendor 两个文件，
  随后恢复只读）；11:51 连续两轮 Wi-Fi 关闭/开启均恢复 `wlan0/p2p0`、
  HAL/supplicant 和 STA enabled，累计扫描统计由 404 增至 430，
  不代表 430 个不同热点。尚未连接任何网络。
- 11:52 注入 BUTTON_B 从 Wi-Fi 设置返回 AT4K；Mali-G31/r20p0 未回退，
  SurfaceFlinger/system_server PID 保持 1492/1936，crash buffer 为空。
  11:54 已将设备停在 Wi-Fi 页，等待用户选择网络并验证密码输入。
- 12:33 Fix71 已构建并试装紧凑 LeanbackIME，保留 LatinIME；两个临时字符
  完成选字和删除，B 只收起键盘、A 可重开，密码框已清空留给用户。
  物理短按/符号切换/实际密码连接仍待用户验证，不把注入测试当作整机完成。
