# RG34XXSP 开发增量（2026-10-28）

本轮在 `baseline/h700-storage-trim-20261028` 上开发。不可变的 364 文件冻结层保持原样；下列增量位于日常产品目录和 `tools/`。旧 v5i 完整 IMG 没有重封装，不含这些修改。

## AT4K 菜单

`tools/at4k/patch_rg34xxsp.py` 以冻结标签中的 `b2fa0343…` APK 为唯一输入，承接此前小屏布局和内置壁纸。菜单及通用二级行的正文统一为 14sp，与一级菜单正文一致；标题保留独立层级。

通用二级行此前只有原生按键回调，没有无障碍点击语义。补丁复用原来的选择回调增加标准 CLICK，导航服务仅在 AT4K 的窄幅设置滚动面板接管方向、确认和返回，HOME 继续使用桌面原生导航。按钮使用 AT4K 原来的选中效果，不再额外绘制导航边框。

应用/频道管理等全宽弹窗仍向无障碍暴露底层菜单。导航服务识别这些叠层后将焦点交回弹窗原生网格，防止选到底层。弹窗正文和默认 Material 文本也统一为 14sp；应用管理器的四列缩至 64dp 并收紧空白，给应用名称和可滚动列表留下空间。

实机已通过主题和外观长列表的末项滚动、控制与图标子菜单、帮助长文滚动、应用管理的跨行/跨列和 A 切换复选框、频道管理与颜色面板的 B 返回。颜色网格的右/下移动由原生按钮焦点确认，未执行改色。复选框切换后已还原并取消，未保存测试偏好。其余页面的记录在本地验收证据目录；入口可达不等同于执行购买、恢复备份、卸载或其他破坏性业务。观察使用 `Dump.java` 的 DONT_SUPPRESS 模式，避免系统 uiautomator dump 暂停实际导航服务。

## 同一控制器上的双摇杆

ROCreader 的 `DEVICE_MODEL_MAPPING.md` 和 `src/input_manager.cpp` 仅作为只读参考，ROCreader 保留且未修改。SDL 轴编号不能直接作为 Linux ABS 或 Android MotionEvent 编号。

原 BSP 的 `ANBERNIC-keys` 只上报方向帽和三个 -1…1 的旧信号，未读取实体摇杆。内核增量 `input/kernel/h700_stick_axes.c` 使用已有控制器，补上四个空闲 ABS 轴及 L3/R3；不抓取、转发或替换原按键与震动驱动。

| 实体输入 | 原始 ADC 通道 | Linux 轴 | Android 轴 |
| --- | --- | --- | --- |
| 左横轴 | 3 | ABS_X / 0 | X |
| 左纵轴 | 2 | ABS_Y / 1 | Y |
| 右横轴 | 1 | ABS_Z / 2 | Z |
| 右纵轴 | 0 | ABS_RUDDER / 7 | RZ |
| 左/右按下 | PE8 / PE9 | BTN_THUMBL / BTN_THUMBR | BUTTON_THUMBL / BUTTON_THUMBR |

PI0 为低有效使能，PI1/PI2 选择四通道；通过 GPIO 子系统取得独占引脚所有权。根据上游 RG34XXSP DTS 四轴反向。模块启动时采集中心，异常中心拒绝接入；ADC 死区 32、归一化到 ±32767，Android flat=4096。用户已确认实体左右摇杆、十字键、鼠标移动、回中停止及 A/B 正常。量化端点与 L3/R3 实体按压仍未单独验收，不能由中心读数或软件注入测试推定。

接线依据为 [ROCKNIX H700 DTS](https://github.com/ROCKNIX/distribution/tree/next/projects/ROCKNIX/devices/H700/linux/dts/allwinner) 与 [rocknix-singleadc-joypad.c](https://github.com/hackbar/rocknix-joypad/blob/005033d1ddd8746c771f2c81f1174f2d892541c9/rocknix-singleadc-joypad.c)。所读 RG34XXSP DTS Git blob 为 `395be5f5afcf7eb91ddc9881f5371224ceb45467`；寄存器定义核对保留的 Allwinner 4.9 BSP。

模块只接受显式 `profile=rg34xxsp`，要求对应 H616/H700 DT、至少 1.5GiB 内存、DT 中 GPADC 禁用且时钟已准备。GPIO 请求失败、活动 ADC 驱动或已有目标轴均拒绝接入。卸载测试已确认原能力和 ADC/引脚寄存器恢复。

开机仅当 `persist.vendor.rgsp.input_profile=rg34xxsp` 时加载，旧设备默认不启用。`input/rgsp-stick-axes.rc` 在 early-boot 同步执行，实测先于 zygote/SystemServer 打开 evdev。完整内核重启后仍只有一个 ANBERNIC 控制器，四个 Android 轴均为 -1…1，原 HAT 与 FF 能力保留。

## 虚拟鼠标与锁屏

长按 Select 600ms 呼出/关闭鼠标，十字键与任意摇杆移动，A 点击/长按，B 退出。摇杆优先采用 Android X/Y 和 Z/RZ，并兼容 RX/RY；保留模拟量速度、死区、对角线限速、取消及失焦复位。默认启用鼠标，显式 `rgsp_mouse_enabled=0` 仍尊重。Select 短按继续由现有实现保留，暂不转交应用。

本轮通过真实控制器 Select/HAT 事件验证呼出和十字键移动；有界软件 MotionEvent 夹具验证 X/Y/Z/RZ 四轴分别移动及回中停止，A 的真实手势完成、B 退出均通过。夹具仅证明 Android 事件至鼠标的链路，不证明实体摇杆的接线方向。

保留原生按 A 解锁。AT4K 在自定义图片变化时同步系统和锁屏 WallpaperManager，保持原 URI 权限与现有设置；重复启动不重复写同一壁纸。系统默认 `ro.config.wallpaper` 指向内置原图，以覆盖首次 HOME 运行前的默认背景。动态视频/在线轮播不承诺锁屏同步。

本机原 AT4K 测试签名私钥未找到。后续 APK 使用现有本地平台证书；首次通过系统包更新及正常重启迁移，PackageManager 明确记录 retaining data，UID 和原偏好不变。没有卸载、清数据或编辑 packages.xml。私钥与应用数据备份均未公开。此迁移方式仅适用于当前系统包，不能据此给普通用户应用强行更换签名。

## 构建及 ABI

所有设备构建通过低压力入口（一个 CPU、亲和性 0–1、6GiB RAM、512MiB swap、nice19、空闲 I/O）：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700Apps -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700Navigation -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700Input -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700KernelInput -Execute
```

H700Apps 从不可变 Git 标签提取并验证基线 APK/apktool 2.9.3，使用现有 AOSP SDK29、Java9、D8 和本地平台密钥；不依赖已清理的 AOSP out。H700Navigation 只重建导航 APK。H700Input 构建固定寄存器诊断采样器、被动观察器和有界摇杆 MotionEvent 夹具，不自动部署。

H700KernelInput 使用保留 Longan 4.9.170、实机配置、本地已有 Linaro 5.3.1 工具链包，在 `/home/lpf/h700-input-kbuild` 单独生成中间文件，不能在原 Longan 源码树内构建。配置输入为产品 `input/kernel/h700-4.9.170.config`，已检查不含设备身份或地址；基础 boot 和 Wi-Fi/Mali 参考模块也必须保留。

`h700_kernel_abi.py` 仅支持 SHA-256 为 `3328c2fab9f19f7ea6a80e34b0a76238cf594bc631f77e05fec32f8adabad042` 的 kernel Image。它核对 Image 导出表、已工作 Wi-Fi/Mali 的 410 个 CRC、本地生成的 414 个 CRC 和模块所有 39 个版本化导入，遇到不一致立即失败。不改版本、不强制加载、不写 boot。实机 boot 读回内核 SHA 与该输入一致。

已通过只探测加载、完整加载/卸载、GPIO/ADC 恢复、重启自动加载、四轴能力检查，以及 20,480 组范围/单调性与死区数学检查。模块及 ABI 摘要位于产品 `input/prebuilt/`，源码和工具同时入 Git；私有会话配置、读回 boot、原始日志留在被忽略的本地目录。

额外通过：37 项项目主机回归、29 项被动观察器检查、4 组 Java 方向/指针/身份/摇杆程序，以及原 364 文件冻结层核验。人工破坏模块的 module_layout CRC 时，ABI 工具明确拒绝，未将该夹具传入设备。

最终组件提升到系统后再次正常内核重启，核对了 APK/模块 SHA、同一控制器四轴、只读 system/vendor、AT4K HOME 与原 UID、A 解锁、Select 呼出及 B 退出、网络 VALIDATED。[组件锁](baselines/rg34xxsp-development-20261028/component-lock.json) 和 [17 文件源码增量锁](baselines/rg34xxsp-development-20261028/source-lock.json) 记录本检查点；旧冻结层的树对象仍为 `c243044ffb43fd45dd33e4145c3c9b79d3d2a3d1`。

## 回退和边界

关闭本机附加轴：通过已核对身份的 ADB 设置 `persist.vendor.rgsp.input_profile=off` 后正常重启。原有按键、HAT 和 A 解锁继续工作。运行中卸载模块会使 Android 的能力缓存暂时保留旧轴，正式回退优先重启。

APK、偏好、输入布局和原系统属性均有本地部署前备份。需要回退时使用对应备份与当前状态核对，不重放旧整卡块补丁。Git 不替代镜像、上游包、签名和私有原始证据；本轮未重封装或刷写整卡、boot0/GPT。
