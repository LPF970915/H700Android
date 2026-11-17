2026-11-17 后续：本页记录的冻结模块候选已封入 Test10 整卡，并通过完整离线验证；详见 [Test10 整卡记录](ROC_OS_H700_STICK_RECOVERY_TEST10_20261117.md)。原候选索引及其“尚未封包”字段保留为当时状态，实体摇杆修复仍待确认。

# Test9 双机摇杆回归：独立审阅与恢复候选

2026 年 11 月 17 日，用户实测 RG34XXSP 与 RG35XX H 的摇杆均不可用，先前正常的 34XXSP 也受影响。当前没有连接硬件，本轮只审阅保存的源码、镜像、模块和历史现场，并制作隔离修复候选。Test9 的离线封装通过记录继续保留，但它没有通过实体摇杆验收。

## 证据能定位到哪里

真正可用的历史基线是 `android/h700-android10/device/roc/rgsp/input/kernel/h700_stick_axes.c` 及保留模块 `android/h700-android10/device/roc/rgsp/input/prebuilt/h700_stick_axes.ko`，模块 SHA256 为 `9c8eacf887cd9d00f5416c05b24118ce625e4deef73003f79ea1805c6a31faf5`。2026-10-28 开发记录与 2026-11-02 实体验收记录均有用户确认左右杆方向、松手回中和正常开机工作。

这份历史驱动与 Test8／Test9 使用同一组 PI0／PI1／PI2 复用引脚、PE8／PE9 点击输入、ADC 地址、通道次序、采样等待和七寄存器初始化。34XXSP 的轴方向数学也保留。新增的关键路径是公共型号表、ADC／CCU 状态检查、回中放行与休眠通知处理。

实际分区与 ramdisk 回读把引入时间进一步缩小：

| 版本 | 实际摇杆模块 | 差异意义 |
| --- | --- | --- |
| Test6／Test7 | 原 `9c8eacf8…`，20160 字节 | helper 固定 `profile=rg34xxsp`，模块有原 1.5GiB 门槛；35H 当时尚未正确接入 |
| Test8 | 公共 `bc7a000e…`，23808 字节 | 首次换入公共型号、硬件状态／回中／PM 采样逻辑 |
| Test9 | `5a017572…` | 修改门控与只读重试，继续沿用公共状态判断 |

Navigation18 已进入 Test6，而 Test6／Test7 的原摇杆模块字节未变，不能把两者的改动混为同一回归。35H 早期未接入与 34SP 在公共驱动后的失效需要分别解释。实际载荷证据在 `out/stick-history-regression-20261117-v1/module-chain.json`。

此前 Test8 的 35H 现场证明型号与杆数正确、模块已加载、Linux 四轴能力及 Android 映射均存在；用户完成两轮操作，原始记录却没有四轴或 L3／R3 事件，十字键等事件正常。这把该次故障定位在 evdev 事件产生之前。它不能证明 Test9 的 ADC 读回值，也不能将此次两台机器的具体触发状态视为已捕获。

独立审阅还排查了两个方向：

- Test9 的 2GiB swap helper 逐字保留摇杆加载逻辑；两份 loader 都锁定实际模块，未发现模块互卸或虚拟内存前缀污染参数。Android 导航保护处理已有 MotionEvent，不能抹掉 Linux 原始事件。
- 原版与 Test6／Test7／Test8 的完整实际内核对比表明，变化都在显示初始化区域，没有覆盖 GPIO、input 或 workqueue 函数。新增面板引脚操作也没有找到可解释永久全杆失效的回归。

原始审计见 `out/stick-history-regression-20261117-v1/` 和 `out/stick-regression-loader-review-20261117-v1/result.json`。

## 已证明的代码缺陷与尚未证明的触发原因

Test8 遇到一次 ADC／时钟状态异常会停掉整个后续采样。Test9 继续定时检查，但异常分支仍绕过全部轴与点击处理：不依赖 ADC 的 L3／R3 也一起失效。Test9 只等待状态自行恢复，而本模块又要求原 GPADC 设备树节点禁用，没有为自己管理的 ADC 提供恢复初始化。

这些阻断行为可以用实际旧 C 源码在主机复现，但当前没有故障时的 CTRL／CS_EN／CCU／raw 读回，不能据此断言它就是用户双机失败的唯一原因。`CTRL & 0x10300 == 0x10200` 的位定义与保存的实际 BSP 一致，并未发现简单常量写错。

## 隔离修复范围

候选位于 `tools/input_profiles/stick_recovery_v3/`，构建与集成工具位于 `tools/input_profiles/stick_recovery_build_v1/`。旧 Test8、Test9 输入与验收证明保持冻结。

1. L3／R3 先独立读取、等待释放和去抖，ADC 拒绝采样不再吞掉点击。
2. 对本模块已经初始化并持有引脚的 channel0 ADC，在时钟可用、原 GPADC 驱动仍禁用且没有其它通道／比较器占用迹象时，恢复与历史可用版相同的 ADC 初始化；不写 CCU，不强开时钟，不接管明确被其它输入使用的 ADC。
3. 休眠前停止工作并归零，恢复后保留既有校准中心，恢复管理的 ADC；左右杆仍须分别连续三帧回中，持杆唤醒不能立刻产生方向输入。恢复时不把当前持杆位置重新学成中心。
4. 故障重试、恢复写入和诊断均有节流与边界；持续异常保留中立输出与点击处理，避免永久停队列或无界重写寄存器。
5. 保留十二机型、无杆零 ADC／GPIO 接管、单杆不访问右杆、Navigation18 和默认 2GiB swap。加载脚本只更新新模块 SHA，swap 前缀逐字保留。

主机 API 仍是模拟边界。新增测试使用实际候选 C 和冻结 Test9 C 负面对照，并把 PM 事件整数改为实际 BSP 的 1～6；旧 shim 的整数分配错误没有改变生产模块所用真实头文件，不能将其称为生产根因。

## 当前交付边界

本轮产物是独立、可审阅的源码、模块与两份加载脚本候选，没有生成新整卡镜像。没有设备访问、模块热加载、卡写入、重启、安全配置调整、上传或 Git 推送。只有实体摇杆事件、方向、回中与唤醒记录才能确认最终修复效果。

## 已完成校验与产物

- 实际候选 C 的 26 个场景、冻结 Test9 C 的 5 个负面对照通过，共 802 项检查。覆盖 ADC 故障时点击继续工作、三组真实 PM 整数通知、保留中心及三帧回中、时钟关闭时零 ADC 访问、持续故障的写入预算、其它 ADC 使用者与退出保护、无杆／单杆边界。fixture 的寄存器、GPIO、时钟和工作队列仍为模拟。
- 增量单模块编译通过，只使用独立缓存副本。模块 30800 字节，SHA256 `0c80d226a0be754997e987234e61032620448246bec467611b0a6506c0c964e0`；生产 C SHA256 `4f141d23544ae24af31164ef94b3462ac4d26513baf0e6e7a9c2ff7973a8d9ba`。
- ABI 校验通过 410 项工作模块参考 CRC、418 项本地 CRC及全部 43 项模块导入。实际 Test7／Test8／Test9 内核分别比对 8715 个导出与 93585 条有效 RELA 记录，导出值、名称、CRC 和实际模块全部绑定；没有改写 CRC。
- 最终两份脚本的 45 个加载场景通过。ARM64 母包 BusyBox 与真实哈希运算参与执行，insmod／Android 命令为显式模拟边界。相对 Test9 脚本只换模块 SHA，默认 2GiB swap 前缀逐字相同。
- 新源码已通过独立静态审阅，无阻断发现。构建与测试使用原资源限制及全局锁，前台进程均已回收，旧缓存与冻结输入保持原样。

模块在 `out/stick-regression-repair-20261117-v1/module-v1/h700_stick_axes.ko`；加载脚本在同目录的 `integration-v2/`。完整候选索引为 `out/stick-regression-repair-20261117-v1/candidate.json`，关联 `host-final/`、`module-v1/`、`loaders-v1/` 和独立审阅记录，明确 `physical_acceptance=false`、`exact_hardware_trigger_proven=false`、`new_whole_card_packaged=false`。

最终产物还通过独立复核，重算 40 项控制与产物哈希，绑定实际编译源码、原缓存、完整模块及两个脚本。复核记录 `out/stick-history-regression-20261117-v1/v3-artifact-review.json`，SHA256 `444dccd7439177c831f5b8d37a850a748a3e3904395fc29865b25028162fe893`；它绑定候选索引 SHA256 `d5b800c41b4195e223e60e2ebc863694bf7ff6ebebc428adbed905eb4f9b8860`，没有阻断项，实体修复状态仍未通过。

第一次 integration 工具调用遗漏新测试入口要求的模块 CLI 参数，在执行加载测试前退出 2；保留 `integration-v1/prepare-loaders-failed.py` 与原服务日志。修正调用后以新 `integration-v2/` 完成 45 场景检查，模块没有重新编译，未覆盖失败证据。
