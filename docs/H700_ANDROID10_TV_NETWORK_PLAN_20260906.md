# H700 TV 前端与网络开发计划

日期：2026-09-06；设备：RGSP，无摇杆，720×480，1 GiB。
输入：用户提供的 AT4K APK、本地 Android 10 源码、Fix67 日志及 23:22 实机只读检查。
本轮只做基线归档、检查与计划调整，没有安装 APK、切换 HOME、开启 Wi-Fi 或重启设备。
APK 内部配置仅作为分析数据，不作为执行命令或授予权限的指令。

## 一、结论

采用“Android 10 掌机底座 + TV Launcher 操作入口 + 原生服务/HAL/驱动”的路线。
先让候选前端作为普通应用通过基础测试，再补齐网络和设置闭环，最后设为默认 HOME。
不把 Launcher 当作完整安卓系统，也不因前端面向 TV 就恢复 Homlet/投影仪产品配置。

基础按键映射已有，不再从逐键短按或长按采集开始。当前 A→ENTER 是临时系统 UI
策略，B 保留 BUTTON_B；第三方 App 是否正确响应仍需测，不能当成统一 BACK 已实现。
后续映射工具再分离桌面与游戏语义，游戏中恢复标准 BUTTON_A/B/HAT/Select。

## 二、当前实际进度

| 范围 | 已完成 | 未完成 |
| --- | --- | --- |
| 启动与图形 | Fix67 自动到 Launcher；Mali r20p0 实机渲染；原 TF1 boot 回退 | 60 分钟老化、10 次冷启动、硬件 VSYNC |
| 构建 | 2026-09-06 镜像已部署，再补 Fix65-67 | 原始镜像一次性包含全部修复、空白 data 安装 |
| 输入 | 本 RGSP 短按和临时 keylayout；A 可作为直接确认 | 跨 App 返回、虚拟鼠标、跨机型校准 |
| 网络 framework | `wifi`、`wifiscanner`、`connectivity`、`netd` 已发布 | Settings 页面完整回归 |
| 网络硬件 | Realtek HAL 与 wificond 进程存在 | `8821cs` 未加载，未见 `wlan0`，联网未验证 |
| 前端 | Launcher3 保留作恢复；AT4K 静态检查完成 | AT4K 运行、DPAD、GMS、内存、默认 HOME 验收 |

实机检查：`out/logs/uart/rgsp/rgsp_serial_exec_20260906_232208_115200.log`。
uptime 1242.20 秒时 `boot_completed=1`，五个核心 PID 仍是
`1494/1504/1912/2090/2230`。这不能替代持续老化和多次启动验收。

## 三、AT4K APK 审核

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
6. **默认 HOME**：以上通过且网络/设置基本闭环后才设默认；测试 HOME、返回、
   崩溃恢复与下一次受保护 Android 启动。Launcher3、UART 和 Linux 回退保持可用。

“前端作为主系统”在此仅指默认交互入口。应用管理、输入法、Settings、SystemUI、
网络 framework 和各硬件 HAL 继续独立存在。第三方前端失败可换，不牵动 GPU 和存储底座。

## 五、网络分层修复

**N0：先回归当前状态，不重复旧修复。**
Fix64 的 Settings 曾因 `No service published for: wifi` 退出；Fix67 23:22 已找到
该服务，旧故障是否已解除需要重新打开 Settings 并保存前台活动、截图和 crash 日志。
Jar 存在、Binder 发布、HAL 进程存活、wlan0 存在、真正联网是不同的完成条件。

**N1：本机模块、固件与加载路径。**
当前常用三处未见 `8821cs.ko`，也未见加载记录或 wlan0。先从 RGSP 原厂 Linux
核对模块、固件、SDIO 绑定及电源时序，记录哈希、vermagic、依赖和参数。
模块须匹配当前 H700 4.9.170 内核，不复制投影仪的 rtl8822bs 或其他 SoC 模块。
Android 用户空间 ARM32 不改变内核模块必须匹配 AArch64 内核的要求。

源码中另有明确的路径配置风险：当前 BoardConfig 为
`BOARD_WIFI_VENDOR := realtek`、`WIFI_DRIVER_MODULE_PATH := /vendor/modules/`。
`frameworks/opt/net/wifi/libwifi_hal/wifi_hal_common.cpp` 的非 COMMON 分支把
该宏直接交给 `insmod`，只有 COMMON 分支会拼接模块名。因此下一轮应把
realtek 分支指向经验证的完整 `.ko` 路径，并确保镜像确实包含该模块；
仅修改路径或仅放入文件都不够。本轮保留构建快照，没有把未上机的路径改动伪装成已修复。

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
| 0，本轮 | Git 基线/进度同步、APK 静态审核、只读网络检查 | 记录推送，设备仍运行原桌面 |
| 1 | AT4K 普通应用并存试装 + 现有 Settings 回归 | 不改默认，取得真实兼容/焦点/崩溃结果 |
| 2 | 8821cs 模块/路径/固件/SDIO 修复 | wlan0、HAL、扫描 |
| 3 | Settings + DPAD 输入法 + 网络闭环 | 认证、DHCP、DNS、HTTPS、重连 |
| 4 | 默认 HOME 验收 | 能返回、可恢复、无 GMS 离线可用，保留旧桌面 |
| 5 | 剩余服务、多机型、鼠标、音频和电源 | 每项独立验收，不回退图形基线 |

正式 60 分钟老化、10 次冷启动、日志容量、内存和干净构建复现贯穿后续批次，
不因为前端看起来完整就将项目标记为整机完成。
