# ARM64 背光链路实机验证与 r2 候选

2026-11-02。承接[离线准备](RG34XXSP_ARM64_OFFLINE_READINESS_20261102.md)。对象为原64GB卡上的 RG34XXSP / H700 / 2GB / Android10 ARM64 Test2a。

**背光软件链路已在当前机器上通过受控验证，并在两次正常 Android 重启后保留。** 这是 Test2a 加四项 vendor 文件增量；不是整卡刷写或新的工厂镜像验收。实际肉眼亮度、背光供电、实体按键/合盖和内核深睡仍另计。

## 写入范围与回退

每次控制先核对原卡 serial/CID/profile/容量/Test2a marker，原两项 vendor 配置和十项关键系统文件 SHA 与冻结输入匹配后才写入。原 vendor 配置另存设备与电脑，备份字节再次比对。

只新增/替换四项 vendor 文件：

- `/vendor/bin/hw/android.hardware.light@2.0-service.h700`
- `/vendor/etc/init/h700-light.rc`
- `/vendor/etc/vintf/manifest.xml`
- `/vendor/etc/selinux/vendor_file_contexts`

没有改写 boot、kernel、DTB、GPT、分区布局、system 文件或应用数据。写入窗口结束即恢复 vendor 只读；system/root 也保持只读。冻结 Test2a IMG、既有标签和旧回退镜像不变。

首次测试 RC 带有独立的240秒超时回退服务：未接受时恢复两份原配置、撤回新增服务并正常重启。首轮有界检查通过后，写回不含测试段的常规 RC、创建接受标记并停止回退服务；第二次重启没有该测试服务。**回退脚本实际未触发，不把它算作异常启动恢复验收通过。** 原脚本、备份和全部中间证据仍保留，不应盲目重放。

## 亮度与重启结果

首次核对仍没有 Light HAL，设置值102、驱动背光50。Android10 Lights JNI在找不到服务后会记住不支持，因此按正常启动顺序接入并重启验证。

新服务实际运行 ELF64 / AArch64，`/proc/<pid>/exe` SHA 与已审计组件匹配，并加载64位运行库；`lshal`可见 `ILight/default` 声明。其PID列没有提供有效值，本轮进程证明来自 init 状态、`/proc` 和框架到驱动的实际调用，不伪称 lshal 给出了服务PID。

| 检查 | 结果与边界 |
| --- | --- |
| 首次正常重启 | 新内核 boot ID、`boot_completed=1`、Light running；带临时回退服务 |
| 五档设置到驱动 | 正常 BRIGHT 策略下，32→32、64→64、128→128、192→192、224→224，最后恢复设置102 |
| 第二次正常重启 | 又一个不同的内核 boot ID，Light running；临时回退服务不再定义，四项常规文件保持 |
| 重启后复测 | BRIGHT策略下64→64、192→192，再恢复102；系统/图形进程在该段测试中保持 |
| 受控A解锁 | 根据当前 ANBERNIC-keys handler注入一次scan304，锁屏显示由true变false、焦点回AT4K；不是用户实体A确认 |
| 息屏/唤醒 | Android SLEEP/WAKEUP事件受控调用：Asleep/OFF时背光读回0，Awake/ON时恢复102；boot ID、system_server、SurfaceFlinger与Light PID保持 |
| 持久设置 | 亮度102、手动模式0、息屏超时60000、USB常亮7均恢复并核对；未更改原有trace设置 |
| 桌面与语言 | zh-CN属性、HOME解析为AT4K；不代表实体全流程已验收 |
| 系统文件 | 十项锁定关键系统文件SHA保持 |
| 预装 | 七款已安装APK SHA全部匹配、primaryCpuAbi均为arm64-v8a；没有逐个重做业务/存档/性能流程 |

这些重启是两次正常 Android reboot，不是十次断电冷启，也不是干净数据首启。第二次重启后最终采样的 crash buffer为空，不据此宣称系统零错误或长期稳定。

### 调暗策略与失败样本

早期亮度检查曾读到10，保留了失败记录。随后确认 DisplayPowerController 是 `policy=DIM`、`manual [dim]`，并且锁屏将活动超时覆盖为10000ms。这不是设置请求直接控制背光的 BRIGHT 场景。

WAKEUP事件在已经亮屏时并不能可靠刷新该检查窗口；增加系统超时在锁屏覆盖仍存在时也无效。受控A解锁后，窗口超时覆盖变为-1，测试时临时将系统超时设为1800000以保持BRIGHT，完成复测后恢复60000。部分早期固定等待断言没有记录瞬时驱动值，不把它们当作硬件成功或硬件故障证据；后续结果使用保存的策略和有界观察采样。没有通过永久禁止调暗来掩盖问题。

息屏时仍可看到disp的unblank字段和持续IRQ；虽然新链路已把背光请求降为0，**它不等于实测背光电源完全断开、面板关断或低功耗深睡通过**。bringup锁仍在。

## 新增初始化标签处理

实际启动时 `/dev/disp` 原标签为 `device`，与父 vendor contexts 中已有的 `graphics_device` 规则不符。新 RC 的 `post-fs-data` 执行一次 `restorecon /dev/disp`；两次重启后均确认成为 `graphics_device`，沿用原有 Light read/open/ioctl策略，没有增加宽泛权限或切换SELinux模式。

系统仍为Permissive，`/dev/hwbinder`仍观察到 `device` 标签，并有相关permissive AVC。该问题归入全系统初始化标签/发行安全收口，本轮未扩大范围修改全部Binder节点，也不能称为 enforcing 已通过。

## Hall与待机只读取证

当前运行内核中，`hall switch`已持有GPIO135（与冻结DTB的PE7对应），是输入高电平；`/proc/interrupts`中有对应IRQ条目，hwirq为103。本轮IRQ号为120，后续必须动态发现，不能硬编码或当作空闲GPIO重新申请。

在独立私有挂载命名空间中只读挂载debugfs，读取GPIO、wakeup_sources和可用IRQ信息后卸载；父命名空间与挂载表完全保持。早期工具不支持 `mount --make-rprivate` 时已在挂载前中止；后来使用已校验、拒绝原命名空间的静态syscall助手完成隔离，没有回退到全局挂载。

内核未暴露所需的逐IRQ debug wake状态，已注册中断不能等同 `enable_irq_wake` 或合盖深睡恢复通过。H700Lid继续为真实sensor模式、sample/stable=1、读取及电源错误0；本轮没有实际开合盖，也没有申请GPIO、装新内核模块、改中断配置或解除 `rgsp_android_bringup`。

## 离线 r2 与当前卡的区别

常规 RC 标签修正已回到自有源码并按固定低压力入口重新构建/审计，形成独立 `stage-v2`，marker为 `dualabi-readiness-r2-20261102`。system5项、vendor4项增量；3752项锁定文件SHA、10项关键系统文件、双分区fsck和Android VINTF解析通过，冻结父输入SHA仍保持。

**当前卡四个vendor文件与r2阶段逐项SHA相同**；当前system仍是Test2a，不包含r2的image/release marker和nice19/idle0 setup RC。新优先级首启效果仍需后续镜像的干净首启验证。未封装新的整卡IMG/gzip，r1阶段及失败材料继续保留。

当前控制必须使用 `out/rg34xxsp-brightness-runtime-20261102/device-guard.private.json` 及同目录 `session.py`：它在旧卡身份守卫之外增加四个vendor文件SHA，不能把现机当作未修改Test2a。

源码入口见[工具说明](../tools/readiness/README.md)，脱敏证明见[结果锁](baselines/rg34xxsp-arm64-light-runtime-20261102/result-lock.json)。保护本轮 `out/rg34xxsp-brightness-runtime-20261102/`、WSL `/home/lpf/h700-readiness-20261102/` 及既有离线目录；包含原始身份、备份、回退、失败DIM样本、两次重启、截图、debugfs和配置证明。只发布源码和脱敏元数据，不上传上述原始材料或二进制。
