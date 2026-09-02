# RGSP H700 无触摸 Android 交互方案

准备日期：2026-08-27  
适用目标：RG34XXSP-class / Allwinner H700 (`sun50iw9`)、720x480、约 1 GB RAM、无触摸屏。

## 结论

首阶段采用 **Android TV/Leanback 风格的 DPAD 焦点交互**。它只依赖方向、确认、返回和主页，不依赖触摸注入，也不需要完整 Android TV 固件或 Google 服务。投影仪遥控器、USB/Bluetooth HID 键盘和掌机实体键都可以汇聚到同一套 Android `KeyEvent`。

不建议把任意 Android 投影仪镜像、R36S/RK3326 Android 镜像或 Flutter 启动器直接刷入 H700。可复用的是交互模式、焦点规则、键值约定和设置界面结构；内核、DTB、HAL、分区布局必须使用 H700 自己的版本。

## 推荐分层

```text
实体按键 / USB-BT 遥控器 / USB 键盘
        |
Linux evdev + Android EventHub/InputReader
        |
H700 .kl/.kcm 映射（只在确认 getevent 后安装）
        |
Android KeyEvent：DPAD_* / ENTER / BACK / HOME / MENU
        |
RGSPNoTouchLauncher（原生轻量 Activity）
        |
设置、文件管理、模拟器、普通 Android 应用
```

启动器应使用原生 View/RecyclerView 或 AOSP Leanback 风格控件，避免 Flutter 运行时在 1 GB 设备上成为常驻内存负担。720x480 下保持大焦点框、短文本和少量并列项目。

## 默认物理键语义

这是产品层语义，不是未经验证的内核码表：

| 物理键 | Android 语义 | 用途 |
|---|---|---|
| D-pad 上/下/左/右 | `DPAD_UP/DOWN/LEFT/RIGHT` | 焦点移动、列表滚动 |
| A | `DPAD_CENTER` 或 `ENTER` | 确认/打开 |
| B | `BACK` | 返回/关闭弹层 |
| Start | `HOME`（长按可留给电源菜单） | 返回启动器 |
| Select | `MENU` 或 `APP_SWITCH` | 上下文菜单/最近任务 |
| L1/R1 | `PAGEUP/PAGEDOWN` 或横向页切换 | 大列表快速翻页 |
| L2/R2 | 音量减/加（若内核提供独立键） | 音量 |
| Power | `POWER` | 交给系统电源策略 |

A/B 与确认/返回的最终绑定可在启动器中提供“交换 A/B”设置，但底层 `.kl` 应保持稳定。

## 当前 H700 输入事实

来自 `docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md`：

- `event0`：`axp2202-pek`，PMIC 电源键。
- `event1`：`ANBERNIC-keys`，主游戏键和 D-pad；同时有 `js0`。
- `event2`：`dierct-keys-polled`，直接/音量辅助键。
- 方向键当前报告为 `ABS_HAT0X` (`0x10`) / `ABS_HAT0Y` (`0x11`)；A/B 等报告为 `BTN_*`。

因此第一轮 Android bring-up 必须先执行：

```sh
adb shell getevent -lp
adb shell getevent -t /dev/input/event1
adb shell dumpsys input
```

逐个按键记录实际 `EV_KEY`、`EV_ABS`、设备名称和重复行为。只有确认 Android 是否已把 HAT 轴转换成 DPAD 后，才决定 `.kl` 是否需要新增轴映射或在内核/输入设备层修正。

## 遥控器和外接输入

1. **USB HID 遥控器/键盘**：优先支持标准 HID；Android 通常能直接产生 DPAD、ENTER、BACK、HOME。
2. **Bluetooth HID**：第一阶段只要求系统配对后可产生标准 `KeyEvent`；不要把厂商专用扫描码写死在启动器里。
3. **掌机按键**：通过设备名/能力位匹配，不依赖 `event1` 这个编号恒定不变。
4. **文字输入**：使用 AOSP/Leanback 屏幕键盘，或临时接 USB 键盘；不要把触摸键盘作为启动器启动条件。

## 启动器最低功能

- 启动后焦点始终可见，并有明确的焦点边框/反差。
- 所有主要动作可由 DPAD 完成；不能要求滑动、长按拖拽或触摸边缘手势。
- `BACK` 按层级返回：弹层 -> 页面 -> 启动器；根页面再按一次才退出/显示电源菜单。
- 允许从启动器打开 Android 设置、文件管理器、模拟器和普通应用。
- 应用无法获得焦点时显示可返回的错误状态，不阻塞主界面。
- 启动器常驻内存目标：尽量控制在 50 MiB 级别，不预加载大型图片和完整应用列表图标。

## 触摸应用兼容路线（第二阶段）

不要一开始依赖 Accessibility 注入。待 DPAD 启动器稳定后，再增加可选“鼠标模式”：

- 摇杆移动指针；A 为左键；B 为右键/返回；Start 切换模式。
- 注入优先使用系统允许的虚拟鼠标/键盘设备；若只能走 Accessibility，必须明确用户授权并提供失效回退。
- 鼠标模式不改变普通 DPAD 模式，避免游戏和设置界面行为漂移。

## 分阶段验收

### A. Input bring-up

- [ ] `dumpsys input` 能看到三个本机输入设备。
- [ ] 上下左右、A、B、Start、Select 每个动作均能稳定产生事件。
- [ ] USB/Bluetooth HID 遥控器至少能完成方向、确认、返回、主页。

### B. Launcher

- [ ] 冷启动后焦点落在第一个可操作项目。
- [ ] 全部页面可只用 DPAD + A/B 完成。
- [ ] 屏幕键盘可打开、输入、确认、返回。
- [ ] 720x480 横屏无文字裁切和焦点越界。

### C. 应用兼容

- [ ] 设置、文件管理器、模拟器可启动和返回。
- [ ] 至少一个依赖触摸的应用在鼠标模式下可完成登录/设置。
- [ ] 应用退出后能回到启动器，显示/音频/input 句柄被释放。

## 参考入口

- Android TV 导航：<https://developer.android.com/training/tv/start/navigation>
- Android TV 应用质量：<https://developer.android.com/docs/quality-guidelines/tv-app-quality>
- AOSP TvSettings：<https://android.googlesource.com/platform/packages/apps/TvSettings/>
- Android `KeyEvent`：<https://developer.android.com/reference/android/view/KeyEvent>
- 本项目 R36S 参考：`reference/r36s-device/`、`reference/r36s-multiboot/`

## 明确边界

本方案只解决“无触摸情况下如何操作 Android”。它不等于 H700 图形、音频、Wi-Fi、电源 HAL 已完成，也不产生可直接刷入的 Android TV 镜像。所有测试继续使用 TF2；不要写入 `mmcblk0`、boot0、SPL/U-Boot 或 U-Boot env。
