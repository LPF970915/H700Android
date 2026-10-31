# ARM64 原型实体输入与系统导航迁移（2026-11-01）

用户在 Test1 首启/两次重启检查后反馈：实体仍需 Y 解锁，长按电源的菜单不能用十字键选择。这覆盖了新的实际交互证据：不能把此前注入 A 的通过等同于实体 A 通过，也不能把架构、安装和生命周期检查当作完整 ARM32 掌机体验迁移验收。

Test1 镜像、标签和旧回执保持不变。当前只对精确身份的128GB原型卡做可回退的导航 APK 更新，原64GB工作卡不动；没有重刷或格式化。所有诊断和修改结果另归此增量。

## 已确认的迁移边界

| 组件/路径 | Test1 实际状态 | 本轮处理 |
| --- | --- | --- |
| AT4K 菜单/字号/原生按钮焦点 | 已携带原确认 APK | 保留；不因框架换64位而重做或假定失效 |
| Navigation v8 的设置/文件/权限对话框通用几何导航、Menu、Select 鼠标 | 已携带，服务仍正常绑定 | 在 GSI 上重新验证关键流程 |
| SystemUI 锁屏 A/Enter | ARM32 的 StatusBarWindowView 源码补丁没有移植到 GSI；Test1 新增 APK 桥接仅受控通过 | 捕获实体底层及 Java 事件后修正，实体确认单列 |
| SystemUI 电源菜单 | ARM32 GlobalActionsDialog 的焦点、HAT/按键处理没有移入 GSI；原导航服务仅识别 SystemUI 下拉面板 | 新增仅匹配原生 global_actions_view 的代理焦点与确认/返回，保留系统动作 |
| Settings 原生菜单/对话框策略 | GSI APK，不是旧版修改后的 APK | 通用服务覆盖不能代替原生补丁全部验收；列入分项回归 |
| DocumentsUI 文件名/焦点/预览补丁 | GSI APK，不是旧版修改后的 APK | 分项检查；不直接用旧 APK 覆盖 GSI |
| LeanbackIME 与 LatinIME 设置页适配 | 旧版 IME 原生修改未随 GSI 全量迁移 | 必须另行移植/验证，不能宣称整套输入法导航已恢复 |
| 强制横屏 framework/磁贴、合盖、八款正式预装 | Test1 尚未全量集成 | 保持此前边界，不应用旧版 DEX 到新的 GSI 或重复套补丁 |

快照包含完整上游目录，文件数不等于补丁数；上述按组件和行为核对。无需、也没有恢复整个旧仓库树。

## 当前诊断与候选

诊断前已核对实际 TF1 CID、Test1 标记、profile、USB 和 root。Navigation9 仍绑定，最近的实体输入记录为 Y（key100/scan306），没有导航服务崩溃。电源菜单的原生视图已用保持其他无障碍服务的被动观察器读取：SystemUI `global_actions_view` 内有 Power off、Restart、Screenshot 和 Emergency 四个独立原生按钮。

新增导航诊断变体10，单独构建/输出，原 Test1 的 Navigation9 APK及源码保留。仅在无密码的原型、显式开启诊断开关、ANBERNIC 控制器上记录游戏按键的 action/key/scan/flags/repeat/downTime、锁屏状态和配对状态；不记录文本或凭据。底层 getevent 同时记录，不能用新注入覆盖用户采样。

电源菜单处理只在可信 SystemUI 系统窗口及特定根视图出现时生效。锁屏下只允许这个系统菜单成为代理目标，不暴露其下方应用；A 解锁桥接在电源菜单显示时暂停，避免把电源菜单确认误作解锁。默认选项、焦点到达、实际动作和实体操作分别记录，不因按钮有 ACTION_CLICK 就宣称已实测关机。

诊断版10之后构建并安装 Navigation11（`1.7-interaction-power-safe`）。额外隔离主动返回后的500ms窗口，避免 B 处理重新截获自身全局返回动作。A 解锁桥接仍保留原配对逻辑，尚无新实体事件可据以修正；不能宣称 A 问题已修复。

## Navigation11 受控结果

| 检查 | 结果与范围 |
| --- | --- |
| 电源菜单初始焦点 | Power off 原生按钮；不执行关机 |
| 右→下→右→上 | Restart→Screenshot→Emergency→Screenshot，四项均到达，方向与线性菜单策略相符 |
| 注入控制器 scan304/A | 原生 Screenshot ACTION_CLICK 成功，系统生成一张截图；动作计数只增1，锁屏仍为锁定，未被解锁桥接截获 |
| B | 菜单关闭，系统回到锁屏；没有执行关机/重启/紧急呼叫 |
| 原桥接 scan304/A | 注入解锁成功，但它不能推翻用户实体 A 失败结论 |
| Settings / Menu | 设置页 Down 进入代理焦点；scan312短按返回AT4K，约0.9s长按展开完整快捷设置；方向键移动、B收起通过 |
| Select 鼠标 | scan310按住约2.2s后松开呼出、右移、B退出通过；没有新增摇杆实体确认 |
| 运行状态 | 受控检查结束时 crash buffer 为空；临时 USB 常亮恢复0、诊断开关恢复0，最后熄屏 |

以上为远程注入和节点/状态观察，不是实体验收；没有按下实体关机。首轮实体采样文件为空，不能把“没有事件”当作 A 键没有上报的结论。下次采样需在亮着的锁屏同步记录底层与 Java 层，明确真实 A 的 down/up、scan、flags、配对与 Keyguard 状态。

## 构建与增量身份

检查点 `baseline/rg34xxsp-arm64-power-nav-20261101`，版本锁见 [manifest.json](baselines/rg34xxsp-arm64-power-nav-20261101/manifest.json)。

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiInteraction -Execute
```

构建保持CPU affinity0-1、合计1核、nice19、6GiB RAM/512MiB swap及单任务。Navigation11签名检查通过；APK为78,303字节，SHA256 `a886e2edec521241becd498fa5ff8426099cecc97207ef663390dcf90c26cd3c`。固定输出已存在时工具拒绝覆盖；需要新版本必须新label/version，保留旧候选与工作源码。

更新只安装在已核对精确CID/运行标记的128GB原型卡 `/data/app`，系统 Navigation9 和 Test1 gzip 不变。未重刷、未替换旧 SystemUI/Settings/JAR、未影响原64GB卡。Test1审计工具新增安装路径守卫，存在运行 APK 更新时直接拒绝称为“未修改 Test1”。后续是否打包新镜像另行处理；目前仍需实体 A 和电源菜单确认，以及表中其余原生组件迁移。

## 保全

保护 `out/dualabi-interaction-20261101/`、WSL `/home/lpf/h700-dualabi-interaction-20261101/`、卡内 `/data/local/tmp/h700-interaction-20261101/`，包括9版原件、10版候选、所有失败尝试、按键/窗口/日志原始记录与回退信息。只发布工具、源码和脱敏结论；原始日志、卡身份、APK、截图不上传。此目录不作为普通缓存清理。
