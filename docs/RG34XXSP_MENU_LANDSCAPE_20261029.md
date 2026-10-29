# Menu 下拉入口与默认强制横屏

日期：2026-10-29。检查点：`baseline/rg34xxsp-menu-landscape-20261029`。

当前开发卡已安装 Navigation v8、H700Rotation 1.0 和匹配的系统旋转补丁。原 v5i IMG、364 文件冻结覆盖层和旧标签保持原样。`main` 仍是整理基线，日常开发在 `codex/rg34xxsp-at4k-input-lockscreen`。

## 使用方法

| 操作 | 效果 |
| --- | --- |
| 短按 Menu，松开 | 回到 AT4K 桌面 |
| 单独按住 Menu 约 0.7 秒 | 展开完整快捷设置；松手不会再回桌面 |
| 十字键 | 在磁贴、亮度条和下方按钮之间移动；磁贴行左右到边界后翻页 |
| A | 确认当前控件，例如切换“强制横屏” |
| B | 收起下拉面板，回到原应用 |
| Select 单独按住至少 2 秒后松开 | 原有虚拟鼠标，十字键/双摇杆移动，B 退出鼠标 |

“强制横屏”首次默认开启，自动加入快捷设置第一项；以后记住用户的开关状态。关闭后恢复应用方向和启用前的旋转设置。用户移除磁贴后不会每次启动都强行加回来，可通过系统编辑入口重新添加。此版本没有把短按 Select 绑定为打开下拉面板。

当前机器的物理 Menu 为 scan 312 / BUTTON_MODE 110，原来由 Generic.kcm 回退成 HOME。Android MENU 82 也可能来自 Select 的回退，因此不能把两者混用。Menu 的计时按输入设备隔离，重复 DOWN 不重新计时；同一设备按其他键会取消这一轮 Menu 动作，避免组合键误触。无需摇杆。

## 已验证

- 主机测试覆盖 Menu 699/700ms 边界、定时触发后松手、重复/孤立 UP、组合键先后顺序、设备隔离、取消/重置，以及原来的方向选择、动态鼠标坐标、Select 2 秒逻辑。
- 通过当前控制器输入节点注入与实物相同的 Menu、A、B 和 HAT 事件：短按回桌面；长按只展开一次，松手不回桌面；A 切换横屏；B 直接收起。这里是远程控制器事件验收，尚待用户肉眼复核手感。
- 720×480 下快捷设置三页均能左右到达；边界翻页后焦点落在新页磁贴，亮度条及下方按钮可以上下到达。没有把亮度条可达性认定为物理亮度已修复，也没有启用录屏/飞行模式等功能来验证其业务能力。
- 微信读书墨水屏 2.1.2 原先固定竖屏；现在正文按完整 720×480 横屏重排，没有仅把 320×480 竖屏窗口居中留黑边。应用请求仍保留 PORTRAIT，关闭系统开关后恢复竖屏，再开启恢复横屏；正文加载后画面稳定。
- 一次完整内核重启验证默认开启、USB ADB 恢复；另一次在关闭状态重启，开关保持关闭，Navigation v8 自动恢复。随后已通过面板 A 键重新开启，当前状态为开启。
- Select 长按鼠标呼出、HAT 移动和 B 退出通过回归；双摇杆算法未改动，本轮没有新增实体摇杆采样。
- 系统分区重启后只读，APK 与 services.jar 读回哈希匹配。原有 A 解锁和 AT4K HOME 路径可用。

## 实现边界

Navigation 仅在解锁且可见的 SystemUI 快捷设置面板内接管方向键；不接管锁屏。它通过无障碍全局动作打开完整快捷设置，B 使用 StatusBarManager 的收起接口，需要普通权限 `EXPAND_STATUS_BAR`。控制器的 Select 鼠标热键和 AT4K 原有按钮样式不变。

H700Rotation 是平台签名组件，通过系统 WindowManager 的固定旋转策略和主屏旋转 0 实现横屏，不用常驻覆盖窗口或轮询服务。组件保存原来的旋转配置，通过设备保护存储记住回退值，开关偏好保存在 secure 设置 `h700_force_landscape`。启动广播恢复偏好，磁贴点击串行执行，外部广播入口有权限保护。只支持 rgsp 产品和主用户。

仅打开 Android 10 原生固定旋转，会让微信读书进入竖屏兼容窗口。因此增加 `ActivityRecord` 的小范围补丁：仅 rgsp 主屏、原生 fixed-to-user-rotation 生效时，使用横屏配置并绕过固定方向/宽高比的兼容边界；关闭策略后走原逻辑，副屏不受影响。

本轮采用锁定原始 services.jar 的单类 DEX 增量，没有重新构建完整 AOSP：只有 ActivityRecord 的四个既有方法和一个新增辅助方法改变。重组后的 classes2.dex 共 728 个类逐项核对；其他方法按等价指令与默认静态 false 值规范化比较，classes.dex 和其他 ZIP 条目逐字节不变。部署前另一个 ART 进程已验证类和成员链接，部署后经过真实启动。对应 Java 源码补丁已同步到本地 AOSP 树，但完整源码重编译后的 services.jar 尚未验收。

应用自行绘制的固定布局仍可能在横屏下拥挤；这一系统能力不代表所有应用自动适配小屏。微信读书工具栏、目录的全程十字键操作仍有独立缺口。快捷设置编辑页的拖拽重排没有全流程验收。

## 复现与保留

脱敏哈希和源码锁见 [版本锁](baselines/rg34xxsp-menu-landscape-20261029/manifest.json)。平台私钥、原始 APK/JAR、设备身份、书架/正文截图和完整日志只在本地。

```powershell
# 编译及主机测试；保持仓库规定的资源限制
.\tools\test_navigation_geometry.ps1
.\tools\build_h700_low_pressure.ps1 -Targets H700Navigation -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700Rotation -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700RotationFramework -Execute
```

最后一项需要本地锁定的原始 `out/force-landscape-20261029/services.before.jar`、既有 APKtool 和 AOSP 工具链。工具按类定位 DEX，不假定 ActivityRecord 在 classes.dex；生成往返比较和原输入哈希凭据。不要在现有已打补丁的 JAR 上重复应用。

未来完整源码构建，应先用 `tools/apply_h700_force_landscape_source.py --source <独立AOSP目录>` 查看计划；确认原文件哈希后，再提供源码树外全新 `--backup <目录> --apply`。补丁为 `android/h700-android10/patches/force-landscape/ActivityRecord.java.patch`；本地当前树已应用，不能再次覆盖。该工具不会连接设备。

本地重要输入：

- `LOCAL_PRESERVE_H700_BASELINE_20261028/force-landscape-20261029/`：原系统 JAR、原 Navigation v7、旋转配置、原生源码备份和私有回退脚本。
- `out/force-landscape-20261029/`：当前 APK/JAR、构建凭据、独立 ART 检查、重启与按键证据、截图；不上传。
- `/home/lpf/h700-rotation-20261029/`：受限构建工作目录；保留成功及失败诊断，尚未授权清理。

部署使用同一文件系统内的临时文件、权限/SELinux 标记校验和原子替换，避免截断正在映射的系统 JAR。替换后即时重挂只读曾返回 EBUSY；确认哈希并同步后正常重启，启动后根分区只读已验证。没有修改 boot、GPT、用户应用数据或整卡镜像。

回退先按私有会话记录确认 USB 序列号/产品/输入 profile，再使用本地保全的精确旧文件。设备上的专用回退脚本在 `/data/local/tmp/rg34-dev/rotation-backup-20261029/rollback.sh`，仅接受已知 JAR 哈希；设置 `persist.sys.h700.rotation_safe_mode=1` 阻止组件启动时重新开启，然后恢复 JAR/显示策略并重启。这个属性是专用维护入口，不是正常开关。回退后另按保存值恢复旋转设置、移除/停用新磁贴；Navigation 可使用 `tools/update_h700_navigation.py` 和本地 `navigation-update.json` 保留数据降回 v7。不要直接重放历史整分区补丁。
