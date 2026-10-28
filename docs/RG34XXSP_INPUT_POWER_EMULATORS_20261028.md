# 控制器鼠标与后续开发检查点

日期：2026-10-28。基于 `03c3cbef9c9ab24ad21dff1dbf0829541f2ad0ba` / `baseline/rg34xxsp-at4k-input-lockscreen-20261028`，新检查点为 `baseline/rg34xxsp-controller-mouse-20261028`。本记录覆盖随后的鼠标、电源只读盘点及模拟器初测。原 364 文件冻结层和原交付 IMG 均未更新。

后续 v7 已按用户反馈改为 **Select 单独按住至少 2 秒后松开**，旧三键组合已移除，见 [当前呼出方式与验证](RG34XXSP_SELECT_HOLD_20261028.md)。下文鼠标表和 v6 测试结果保留本检查点的历史含义。

## 当前鼠标操作

| 操作 | 按键 |
| --- | --- |
| 呼出 / 关闭 | 按住 L1、R1，再按 Start；只在新的 Start 按下时切换一次 |
| 退出鼠标 | B，或再次使用上述组合 |
| 移动 | 十字键、左摇杆或右摇杆；无摇杆机型可全程用十字键 |
| 点击 / 原地长按 | A 短按 / 长按 |
| 连续拖动 | 按住 X，再用十字键或摇杆移动；松开 X 抬起触点 |
| 滚动 | 按住 Y，加方向；方向表示内容滚动方向，触摸滑动方向相反 |

Select 短按和长按均不再被系统鼠标保留，原事件及 downTime 直接交给应用。L1、R1 平时也正常传递；识别组合时只接管 Start 的这一对按下/抬起。因此这是低占用的系统组合，仍可能与某个应用自己设置的相同组合冲突。肩键在识别前已传给应用，组合不是游戏输入的原子隔离。

同一设备的组合状态单独记录，重复 Start、取消、失焦和禁用均处理。已消耗的方向按下在模式退出后仍保留抬起所有权，避免孤立的松开事件漏入应用。

拖动采用 Android 10 AccessibilityGesture 的连续 stroke，最长 30 秒后结束。修复了两个实测问题：静止的 `willContinue=true` 延续不产生 MotionEvent，Android 10 会取消但可能留下旧触点；已完成点击的延迟超时也可能误伤后续拖动。现实现等待真实像素移动或最后 UP，并用新的代次隔离旧超时。

## 验证与构建

Navigation 版本为 6 / `1.3-controller-mouse`。仍使用固定低压力构建入口：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700Navigation -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700Input -Execute
.\tools\test_navigation_geometry.ps1
```

H700Input 现在额外构建无权限的 `H700InputProbe.apk`。它只记录自身前台窗口收到的控制器和触摸事件，不记录其他应用或文本输入。公开的 `tools/input_probe/verify_controller_mouse.py` 要求显式 USB 会话、唯一 ANBERNIC 控制器、当前机型配置、Navigation v6 和已安装的测试夹具；默认只核对身份，加 `--execute` 才进行注入。

最终 APK 已通过 20 轮组合开关、Select 短/长按透传、普通 Start、L1＋Select、A 点击和长按、X 连续拖动、原地 X 按住后松开、Y＋方向滑动、拖动中 B 退出。测试窗口实际收到 6 个 DOWN 和 6 个 UP/CANCEL，无遗留触点、无手势拒绝。回退再升级后，用公开工具另跑了一轮完整手势测试，也通过。5 组 Java 主机测试包含同设备组合顺序、重复、取消及多设备隔离。

这是远程注入与应用事件验收。此前用户已经确认实体双摇杆/十字键鼠标正常；新的三键组合、X/Y 操作、L3/R3 和摇杆量化端点仍待实体操作验收。软件注入不能代替这部分结论。

日常 AOSP 树已同步本轮 3 个导航源码文件，写入前备份到新的私有保全子目录；没有重放旧 prepare 链。[源码锁](baselines/rg34xxsp-controller-mouse-20261028/source-lock.json) 与 [组件/验证锁](baselines/rg34xxsp-controller-mouse-20261028/component-lock.json) 记录本检查点。上一检查点的锁和标签保留原意。

## 电源与音频盘点

`tools/audit_h700_runtime.py` 仅只读，要求显式 USB 身份。原始 dumpsys/lshal/sysfs 输出保留本地；公开摘要不含序列号、IP、MAC 或应用私有数据。

| 项目 | 当前证据与边界 |
| --- | --- |
| 自动息屏 | 设置为 60,000ms；`stay_on_while_plugged_in=7`，USB 充电时 mStayOn=true，当前 Awake 不能证明休眠成功 |
| 亮度 | 设置 102、手动模式；无 backlight class 节点，当前 VINTF 未声明 Light，所读 lshal 未列出 Light；需核对 Allwinner disp 后端及实际亮度 |
| Power | VINTF 未声明 Power，读到 legacy power.default.so；不能将 legacy 文件存在视为 HIDL 已工作 |
| 温控 | Android Thermal HAL Ready=false；内核有 CPU/GPU/VE/DDR/电池温度节点；两者是不同的观测层，不能据此推定内核没有保护 |
| 音频 | Audio HAL 已注册，AudioFlinger 有 48kHz/PCM16 主混音与扬声器路由；本轮未播放声音、未进行听音验收 |
| 电池与合盖 | 读到 Health、电量 100% 和电池 30°C；输入能力未列 SW_LID，不等于硬件没有合盖功能 |

lshal 返回 72，仅提供部分清单；debug wakeup_sources 不可读。工具保留每项退出码，不把缺失输出当作完整验收。具体物理项目仍为五档亮度、扬声器/耳机、充电切换、合盖/电源键睡眠唤醒、正常关机及断电冷启动。本轮没有远程强制休眠、改变亮度/音量或断电测试。

## 真实应用初测

从 [RetroArch 官方下载页](https://www.retroarch.com/platforms.html) 获取 1.22.2 的 32 位 APK；从 [PPSSPP 官方下载页](https://www.ppsspp.org/download/) 获取 1.20.4。两者均先检查签名、最低 SDK 及 armeabi-v7a，再在确认未有原安装的当前样机安装。APK、核心、测试存档和原始画面留本地，没有加入系统镜像。

- PPSSPP：官方 [cube.elf](https://www.ppsspp.org/legacybuilds/) 成功运行，画面持续变化。实体控制器路径的 A 事件可保存第 3 槽即时存档；结束应用进程、重开 ELF 后，读取该存档成功并有原生提示。读取这一步使用远程触摸选中窄按钮，不能据此声称整条 PPSSPP 流程全程按键可达。小屏默认存档行的载入文字拥挤，后续值得调整应用显示比例。
- RetroArch：使用官方 [2048 无内容核心](https://github.com/libretro/docs/blob/master/docs/library/2048.md)，无需商业 ROM。已实际启动、用 Start 开始、方向移动棋盘、A 确认、B 返回、Select＋Start 打开快捷菜单、保存和读取第 0 槽即时存档。`2048.srm` 在应用重启后保留棋盘/暂停状态；即时存档的保存/读取在同进程验证，尚未把其进程重启闭环单独重跑。

发现并修复 RetroArch 的误识别：该控制器 VID/PID 为 1:1，与内置 Infra-Red 遥控器配置相撞。新增 `config/retroarch/android/H700_ANBERNIC_keys.cfg` 用完整 `ANBERNIC-keys` 名称匹配；实体 A 按现有系统 `.kl` 使用 ENTER/66，不能照搬通用 BUTTON_A/96。方向采用 HAT，四个模拟轴采用该应用 Android 驱动的 0/1/2/3。配置已在本机测试应用的 autoconfig/android 中安装；没有改变 Linux 按键、系统布局或 ROCreader。

`config/retroarch/h700-menu-overrides.cfg` 提供两项合并值：A 确认/B 返回、Select＋Start 打开菜单（RetroArch 1.22.2 的 INPUT_COMBO_START_SELECT=4）。它是合并片段，不能替换用户完整配置。方向注入的较长保持可触发菜单重复，短保持已逐项到达即时存档；实际手感和按键重复节奏仍待实体复核。

本轮只是模拟器初测，不等同于商用游戏兼容性、声音、全部模拟平台和性能验收。另发现原生安装权限弹窗的说明文本被挤为窄列，允许/拒绝按钮仍可操作；该小屏布局缺陷列入下一轮软件修复。

## 小型更新与回退

本地 `out/rg34xxsp-input-power-20261028/H700-navigation-v6-update-rollback.zip` 包含前/后两个签名 APK、SHA 清单和 `update_h700_navigation.py`。不含签名私钥或设备身份；没有上传完整 IMG。

工具默认只计划，`--execute` 通过 PackageManager 保留数据安装，`--rollback --execute` 使用 `-r -d` 恢复 v5。只接受清单所列前/后 APK，遇到未知已安装版本拒绝覆盖；限当前显式识别的 eng/root RG34XXSP。已经在实机执行 **v6 → v5 → v6**，每次读回 SHA 一致，无清数据、无重启。Navigation 当前是 `/data/app` 更新包，系统内置 v5 仍保留；系统基包及当前整卡 IMG 没有被替换。本检查点未增加内核重启证明。

私有保全目录另存本轮 APK、更新包、原始证据和 AOSP 写入前文件。Git 保存源码、配置、工具和脱敏验证摘要，不能替代这些本地输入及已有镜像/源码包的外部备份。

## 按原计划继续的顺序

当前仍是 Android 10 的掌机基础阶段：

1. 输入：本轮已补 Select 兼容、拖动/滑动；待实体新组合、X/Y、L3/R3、四轴端点及重复节奏。
2. 电源/音频：只读盘点已完成；先核对亮度/Power 后端，再在有人在场时逐项测试睡眠、唤醒、合盖、声音和充电。
3. 模拟器：初测通过并补 RetroArch 配置；继续权限弹窗与 PPSSPP 小屏设置、真实游戏的启动/映射/保存/退出/重载，补多轮和进程重启证据。
4. 性能与耐久：仅有真实应用运行的短时记录。2048 当次 TOTAL PSS 68,817KiB、无 swap，CPU 读数约 54.6°C；这不是帧率基准或热稳定性结论。60 分钟负载、冷启和显示观察均未开展。
5. 交付：Navigation 小更新/回退已实测；整镜像仍需解决历史 v5f seed 缺口、重新封装、读回及冷启。不得把旧 v5i IMG 当作当前增量合集。
