# 熄屏解锁后导航乱跳：源码修复与离线验证

日期：2026-11-15。针对其他用户报告的 0.0.2 熄屏、亮屏解锁后，在不操作按键时持续横向导航。本轮没有连接物理设备；原始异常输入、UP 是否丢失及最初异常轴的来源仍未取得现场证据。

## 判断与修复范围

加入按下、长按连发和松开时序限制是有效的保护，但旧版并非完全没有限制。Navigation17 已限制部分服务内轴导航；Android `ViewRootImpl.SyntheticJoystickHandler` 自己生成的方向键连发，以及服务自身选框窗口收到的方向键，仍有独立入口。只调整一个入口的连发速度不能覆盖这些路径。

已核对的原版框架机制允许一个没有后续回中样本的轴状态持续触发连发，并存在 HAT、摇杆及设备间状态共享。AT4K 的首尾环绕会使同一个方向的持续移动看起来左右来回跳。该机制能解释症状如何持续，并不能单独证明视频中的第一条异常输入来自哪里。既有调查见 [横向导航分析](ROC_OS_HORIZONTAL_NAVIGATION_20261114.md)。

修复同时覆盖三条路径：

1. 框架摇杆转方向键：按设备、source 和轴分开记录会话与回中要求，HAT 在对应维度优先；一个持续会话的截止时间不随新 MOVE、反向或接管延长。
2. 四个导航界面的框架方向键：接管外部重复 DOWN，以本地定时器控制连发，并在实际 post-IME 交付时再次检查有效性。
3. Navigation 服务及自身选框窗口：方向键由本地会话控制，避免无障碍过滤之前的原始重复事件或自身窗口的框架连发绕过限制。服务管理范围之外的游戏输入继续沿用原行为。

框架精确作用于 `com.overdevs.at4k`、`com.android.settings`、`com.android.documentsui`、`com.android.systemui`。没有扩大为所有应用的全局输入限制。

## 输入时序

| 条件 | 处理 |
| --- | --- |
| 第一次有效按下 | 立即移动一次，不加入短按等待 |
| 持续按下 400 ms | 开始长按连发 |
| 长按连发 | 间隔 160 ms |
| 收到对应的有效松开或轴回中 | 停止该次操作 |
| 同一会话持续达到 10 s | 强制停止；重复输入和方向切换不能续期 |
| 超时后继续输入 | 必须先收到对应真实非取消 UP 或有效轴回中，才恢复 |
| 熄屏、失焦、停止或窗口销毁 | 取消旧会话及旧回调；排队的旧 DOWN 也必须通过交付有效性检查 |

十字键为数字输入，这里限制的是按下持续时间与连发间隔，不是机械键程。没有加入固定的解锁后等待时间来掩盖异常。

时间戳晚于当前时间、早于停止边界或乱序的旧事件不能解除保护。框架为自产事件保留队列来源及代次记录，在真实事件回收前清理记录；仅有 `FLAG_FALLBACK` 不足以跳过方向键检查。正常排队的短按 DOWN/UP 保留，跨熄屏周期或超出截止时间的旧 DOWN 拒绝交付。

## 已完成的框架验证

- 原始 `ViewRootImpl.java` SHA256：`0eadf38bc8ceb599dcf57eb2d6a8b9e818a19ecedca1143b3a361682c0e64639`。
- 合并修复后的完整文件 SHA256：`e8110bc34ac032346b2da3fb625799420a72b278cc9e58e7d4b2aadf2b2044b3`。
- 实际修复源码的摇杆 host 检查：17 个场景、6,754 项通过，保留未管理应用的 legacy handler，并有原始源码哈希错误拒绝检查。
- 合并源码中的方向键 guard 检查：11 个场景、144 项通过，覆盖延迟交付、UP 平衡、上游消费和队列复用。
- 完整修改后的 `ViewRootImpl.java` 使用保留的真实 Android 依赖编译通过，生成 51 个 class。它是编译检查，不是生产 `framework.jar` 或 ART 预编译产物。

原始收据、命令和日志保存在本地 `out/nav-resume-fix-20261115/framework-final-v1/`。所有编译与测试使用既有资源限制和全局锁，未修改原始 BSP、Native、Source64 或签名身份。

## 集成与交付边界

Navigation18（`2.4-resume-guard`，diagnostics39）的最终 13 文件候选已完成平台生产签名构建。实际 Android API 编译、8 组 helper、DEX 完整性、Android 10 签名、zipalign 和签名前后载荷一致检查均通过；未安装到设备。

最终 APK 为 94,687 字节，SHA256：`2fc26c6b7a171355586480a03748f5ec1141a668ecddf706d12a56b20ef34749`。构建收据位于本地 `out/nav-resume-fix-20261115/apk-build/builds/20261115-093908-157640/`。此前 12 文件候选的 APK 保留为中间产物，不作为最终修复。

修复已纳入公共覆盖层的 Navigation manifest、AxisNavigation、MouseController、NavigationService、新增 KeyNavigation，以及完整 ViewRootImpl，共 6 个目标载荷变更。其余清单目标保持原身份。当前 `source-manifest.json` 有 1,759 个目标、626 个仓库输入，SHA256 为 `c48f7f5dd07c73916ad5b5b10b0c215ab87e254a81453749393a15575761d8b9`。

公共入口以当前清单重新解析并快照全部 13 个 Navigation 输入，实际运行 8 组 helper 和服务片段检查通过：轴状态机 79 项、原服务允许态回归 32 项、恢复保护 58 项／9 场景、新方向键状态机 163 项、实际服务入口 73 项／7 场景。新增入口检查覆盖缺失 UP、原始重复 DOWN、持续上限、游戏放行、旧回调失效，以及关屏 Ring 和鼠标提前消费 UP 的恢复。测试边界使用虚拟 Android 状态与调度，并非物理故障复现。

公共清单输入闭合和既有 11 项公共工具测试结果见 [本轮验证记录](../build-support/public/validation-20261115.json)。可复查的源码入口为 [KeyNavigation](../build-support/public/overlay/device/roc/roc_os_source64/Navigation/src/com/roc/rgsp/navtrial/KeyNavigation.java)、[NavigationService](../build-support/public/overlay/device/roc/roc_os_source64/Navigation/src/com/roc/rgsp/navtrial/NavigationService.java) 和 [ViewRootImpl](../build-support/public/overlay/frameworks/base/core/java/android/view/ViewRootImpl.java)。

后续真实增量生产构建已完成修复后的 framework、双 ABI ART 和完整依赖 preopt，并将同一构建图的 Navigation18 与框架合入共用 Test6。生产与合并后 ART 依赖审计通过，Test6 整卡封装、独立镜像验收及 Windows 哈希核对通过，尚未执行实机验收，详见 [Test6 说明](ROC_OS_H700_MANUAL_SELECTOR_TEST6_20261115.md)。单独安装 Navigation APK 不能覆盖 HOME 的框架摇杆路径；不能使用此前的 compile-check JAR 替换系统框架。

故障现场尚未取得，不能宣称已证实唯一硬件根因或全机型故障已经消失。显示 Test5 的待实测状态独立保留，本轮不改变显示启动链路。
