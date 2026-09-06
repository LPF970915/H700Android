# H700 Android 10 基线状态

建立日期：2026-09-02；最新核对：2026-09-06 23:22（中国标准时间）。
运行基线：`94ca82e` / Fix67，加上本次归档的 RGSP 产品配置与 A→ENTER 映射。

当前已自动进入 Android 10 Launcher 桌面；不是完整系统功能验收通过。
详细运行证据见 `H700_ANDROID10_FIX67_STABLE_DESKTOP_20260906.md`，
新执行顺序见 `H700_ANDROID10_TV_NETWORK_PLAN_20260906.md`。

## 当前进度

| 项目 | 已确认 | 尚未完成 |
| --- | --- | --- |
| 构建 | system/vendor/ramdisk 已生成并上机 | 两次干净构建复现全部现场修复 |
| 启动/存储 | TF2 `/data` 挂载，framework 自动启动，`boot_completed=1` | 空白 data 初始化、规范化启动触发、ADB 单独验收 |
| 图形 | 720×480 Launcher 截图，Mali-G31 / r20p0 硬件渲染 | 硬件 VSYNC、60 分钟老化、10 次冷启动 |
| 输入 | RGSP 短按已采集并映射，A 为临时 ENTER | TV 前端兼容、游戏语义恢复、多机型校准、虚拟鼠标 |
| 网络 framework | 实机 `wifi` / `wifiscanner` / `connectivity` / `netd` 已发布 | Settings 页面完整回归 |
| Wi-Fi 硬件 | Realtek 产品配置和 HAL 进程存在 | 未见 `8821cs` / `wlan0`，驱动、固件、扫描与联网待修 |
| 系统体验 | Launcher3 可用，作为恢复入口保留 | TV 前端、屏幕键盘、设置、音频、电源、无线闭环 |

23:22 只读检查时 uptime 为 1242.20 秒，五个核心 PID 仍为
`1494/1504/1912/2090/2230`，与 Fix67 初次截图启动相同。这是约 20 分钟时的
重复采样，不是 60 分钟持续监控或多次冷启动验收。
本机正在使用的 keylayout SHA-256 与仓库文件一致：
`99b729a799e47db82a389527e4cc232e186d4a1c431f119326fb093a9def9056`。

## 历史准备工作

- 主线固定为 H616 Android 10 / API 29，RGSP H700 kernel、DTB 和板级 overlay；
- R36S Android 11 fix6-fix58 脚本、ramdisk 和产品文件已集中封存；
- H618 Android 12 只保留约 133 MiB 精选对照资料，不进入产品目录；
- 清理 98 个重复文件或目录，回收 82.71 GiB；
- H616 `android.tar.gz` 和 `longan.tar.gz` 已完成 MD5 回读验证；
- 完整 Android+Longan 源码已解到 D 盘项目内的 Ubuntu WSL2 VHDX；
- 原厂 `cupid_perf1-eng` 与新 `h700_rgsp-eng` 均通过 `lunch`；
- 两个产品均通过 `m nothing` 全量 Soong/Make 构建图解析；
- 安卓 10 产品目录未发现 `r36s`、`rk3326`、`rk30board` 或 H618 引用。

## 本地位置

- Windows 项目：`D:/Works/H700Android/`；
- Ubuntu VHDX：`D:/Works/H700Android/.wsl/Ubuntu/ext4.vhdx`；
- Linux 构建根：`/home/lpf/h700-android10/`；
- Android 源码：`/home/lpf/h700-android10/android/`；
- Longan BSP：`/home/lpf/h700-android10/longan/`；
- 主线 overlay：`android/h700-android10/device/roc/`。

完整源码和未来构建输出不得迁回 C 盘。准备脚本会验证 Ubuntu 发行版必须位于本项目
`.wsl` 目录，并同时检查宿主 D 盘与 Linux 文件系统余量。

2026-09-02 最终复核：Ubuntu 注册 `BasePath` 为
`D:/Works/H700Android/.wsl/Ubuntu`，D 盘 `ext4.vhdx` 约 119.81 GiB；Linux 内
`/home/lpf/h700-android10` 约 52 GiB。C 盘未发现本项目的源码压缩包、失败解压目录
或旧 Ubuntu VHDX，可用空间约 117.86 GiB；D 盘可用空间约 230.53 GiB。

## 主线已切断的依赖

新产品不继承 `device/softwinner/cupid-common/cupid-common.mk`，因此不会自动带入：

- HDMI-CEC、电视启动动画和 4K 显示默认值；
- AC100/AC107、HDMI/SPDIF 作为默认音频端点；
- PPPoE、电视 Launcher、PlayReady/Widevine 产品包；
- 投影仪服务、Orange Pi 分区表、DTS、PMIC 或启动链。

`cupid` 和 H616 board selector 只用于选择 Android 10 HAL 代际。Widevine L3 变量仅
作为全志全局 Makefile 的源码目录解析守卫，产品没有请求 DRM 包。

## 复现边界

2026-09-06 构建记录见 `H700_ANDROID10_BUILD_20260906.md`。system/vendor
写入后又通过 Fix65-67 修复 EGL、Mali 模块、data 挂载和 framework 触发；
不能把未打补丁的原始镜像称为最终可用整包。当前部署还依赖已有 TF2 data，
不是空白卡安装器。

Git 保存产品配置、修复脚本、文档和 Fix67 payload 校验清单。
镜像、专有 GPU/模块、截图、原始串口日志和用户提供的 APK 保留在本地，
不作为源码上传。`docs/baselines/fix67-payload.sha256` 固化已测试的小包清单，
大文件仍需按来源和哈希单独恢复。

## 下一执行队列

详细计划已更新为 `docs/H700_ANDROID10_NEXT_DEVELOPMENT_PLAN_20260902.md`。

1. 冻结 Fix67 和 RGSP 基础按键；不重复长按采集，不改变安全回退；
2. 普通应用方式试装 TV 前端，验证离线、无 GMS、720×480 和 DPAD+A/B 操作；
3. 补齐 RTL8821CS 驱动加载链，回归 Settings 网络页与无触摸密码输入；
4. 达到扫描、认证、DHCP、DNS、联网和重连闭环后，再设新前端为默认 HOME；
5. 推进剩余设置服务、虚拟鼠标、音频、电源和产品化；交叉完成稳定性与构建复现。

更换默认桌面与保留 Linux 一次性回退是两件不同的事。当前没有改变默认启动系统。
