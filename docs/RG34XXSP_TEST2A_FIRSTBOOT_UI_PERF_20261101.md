# Test2a 64GB 首启与系统界面卡顿定位

日期：2026-11-01。承接[Test2a写卡](RG34XXSP_ARM64_TEST2A_FLASH_64G_20261101.md)。新64GB卡已实际进入Android，用户确认实体屏幕显示AT4K及樱花壁纸。当前开发卡为原64GB卡上的Test2a，已按私有USB序列号、SD CID、124735488扇区容量、rg34xxsp profile及Test2a标记建立独立守卫；不能复用旧128GB/Test1的控制脚本。

## 首启观察

最初厂商Logo停留时USB ADB已连通，zygote64、次zygote、system_server、SurfaceFlinger、bootanimation都已启动。约75秒时框架尚在生成新的services缓存；约173秒时`sys.boot_completed=1`并进入工厂预装流程，稍后的截图/实体反馈均确认AT4K。不是此前P1/P1a切根入口失败的同一种证据，没有要求用户反复重启或重刷。

当前`ro.product.locale`及`persist.sys.locale`均为zh-CN，预装流程结束后HOME解析为`com.overdevs.at4k/.MainActivity`，Leanback为默认。p8实际69775357扇区，即35,724,982,784字节，public卷已挂载且扩容后FAT容量可见。工厂setup/preinstall两个状态均complete；这只证明自动流程完成，不能代替七应用的独立ABI/工作流验收。用户随后要求优先排查系统卡顿，应用验收、实体A/电源菜单和重启回归暂缓。

首启捕获到已有蓝牙HCI空后端SIGABRT；晚期默认脚本随后关闭蓝牙，未将禁用写成修复，不能宣称零错误首启。大量后台空进程SIGKILL有`empty #5/#6`等缓存回收原因，没有据此误判系统服务崩溃循环。system_server及SurfaceFlinger在本轮观察期间保持运行。

## 卡顿证据

用户感觉系统像未开启硬件加速。实际核对到：

- AT4K、SystemUI和Settings使用`Pipeline=Skia (OpenGL)`，相关进程与SurfaceFlinger均映射`/vendor/lib64/egl/libGLES_mali.so`；SurfaceFlinger报告ARM Mali-G31、EGL1.4 Bifrost r20p0、OpenGL ES3.2。
- HWC enabled，GPU频率采样420MHz，CPU采样1.512GHz，显示周期16,904,379ns（约59.16Hz）。软件VSYNC仍按既有H700适配启用，未改变同步/频率属性。
- 静态界面采样中应用和导航覆盖层为CLIENT/FORCE_GPU，表示交由Mali完成合成，不等于CPU软件绘制。厂商`hwc2/other/debug.cpp::showfps()`在非HOMLET、低于8帧/秒且非secure的静态场景设置forceClient；不能仅凭这一张静态dump认定HWC硬件路径坏了。没有盲改“禁用HW叠加层”、替换Mali或关闭VSYNC。

首次采样时，预装仍在`cp -Rn ...retroarch-private.tar...`阶段，复制进程nice0、约96.6%单核CPU，kswapd约30%单核；四核总空闲仅约22.5%。MemAvailable仍约1.4GiB，大量内存为文件缓存，不能用MemFree很低就判断RAM耗尽。该负载伴随明显UI掉帧。

后台结束后，四核总空闲采样约92.75%。先保存原统计并重置gfxinfo，再请用户在AT4K和设置中移动/滚动；用户明确反馈“已明显改善”。新采样如下：

| 组件 | 首启后台样本的卡顿帧 | 后台结束后的用户操作样本 | 后样本95分位帧耗时 |
| --- | --- | --- | --- |
| AT4K | 325/639，50.86% | 22/514，4.28% | 15ms |
| SystemUI | 219/310，70.65% | 1/52，1.92% | 14ms |
| Settings | 未单列同阶段样本 | 17/263，6.46% | 25ms |

这些是两阶段操作样本，并非相同动作、相同背景的严格基准测试。CPU占用、时间顺序、帧数据和用户反馈共同指向**首启校验/安装/资源解包的竞争是当前观察到的主要卡顿来源，硬件OpenGL已正常工作**。不能把帧时间改善扩展成所有按键到动作的端到端延迟已验收；遗留输入响应问题需另采导航链路。

## 源码处理及生效边界

工厂后台任务当前已经自然完成，现机改善不是由本轮新源码导致。本轮只将后续镜像的初始化服务改为：

```rc
priority 19
ioprio idle 0
```

修改入口为`tools/arm64_probe/prototype_setup.rc`，并在`tools/interaction/prepare_stage.py`显式写入该RC，避免下一轮候选仅继承旧优先级。原生Android init源码`Service::ParsePriority`和`Service::ParseIoprio`支持这些参数，RC保持LF。该变更降低后台CPU/IO竞争，保持前台应用获得资源；不提高主机编译负载，不调电压、CPU/GPU频率或图形属性。

**没有重封装IMG、没有向当前卡写入这项RC，也没有清空data重跑首启。** 新优先级在下一镜像首启的实测效果尚待验证。Test2a冻结镜像和旧标签不改；从冻结Test2a做下一轮增量时必须显式带入该RC，不能宣称已刷卡版本包含它。

## 记录与保全

检查点`baseline/rg34xxsp-test2a-firstboot-ui-perf-20261101`，见[脱敏数据](baselines/rg34xxsp-test2a-firstboot-ui-perf-20261101/result-lock.json)和[修改源码锁](baselines/rg34xxsp-test2a-firstboot-ui-perf-20261101/source-lock.json)。原始身份、首次启动日志、屏幕及三组性能数据保存在`out/test2a-firstboot-64g-20261101/`，不可当缓存清理或上传Git。

本轮只重置了诊断帧计数，没有注入方向/A键、停止导航服务或修改图形配置。当前新卡的USB常亮原值观察为7、交互trace为null/off，均未被本轮修改；不能把旧128GB会话的原值0套用到这张新卡。原128GB开发卡及v6b镜像继续保留，物理A/电源菜单、应用工作流、重启/冷启、完整硬件及长期性能验收仍未完成。
