# ROC OS 发行概览

更新日期：2026-11-17。当前最新本地候选为 **0.0.2 Test10**，已完成整卡封装、完整独立验证和 Windows SHA256 核对。它通过手动机型菜单供十二种 H700 设备共用；实体摇杆恢复、同包导航恢复及完整机型覆盖仍待确认。

本页以当前候选为准。早期 RC、自动面板试验和中间测试包的故障过程保留在[历史记录](HISTORY.md)及对应日期文档，不再逐项列作当前版本问题。旧问题没有被删除或冒写成已修复。

## 版本与分发

| 项目 | 当前状态 |
| --- | --- |
| 最新本地候选 | `ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test10_StickRecovery_20261117.img.gz` |
| 压缩大小 | 591,771,367 字节 |
| gzip SHA256 | `ad6cec97dafc641cc4729273f3aea40dc4a4047cef32080bbbfbb88b056f8535` |
| 解压大小 | 32,434,554,368 字节 |
| raw SHA256 | `b200fc3fe65cecc1bbf5d8fdf68e6643060c3e6faec499f276a4c4192ec44afe` |
| 本地交付 | Test10 已完成，建议至少 64GB 测试 TF1、TF2 留空 |
| 公开网盘 | 仍提供 0.0.1，Test10 尚未上传；[公开下载与校验](PUBLIC_DOWNLOADS.md) |
| 版本定位 | 测试候选，未提升正式稳定版或历史接受基线 |

完整证明见 [Test10 工程说明](ROC_OS_H700_STICK_RECOVERY_TEST10_20261117.md)与[验收记录](baselines/roc-os-h700-stick-recovery-test10-20261117/acceptance.json)。Git 同步源码和说明不等于上传镜像资产。

## 当前候选的变化

Test10 保留十二机型启动菜单、三档面板试屏、保存默认／重选和“加载中，请稍后”提示。720×480 包括 34XX、34XXSP、RGSP，720×720 为 CubeXX，其余八项使用 640×480；各型号仍有各自的电气配置。首次菜单以 35XX H 640×480 开始，音量键在 35XX H、34XXSP、CubeXX 三个代表配置间切换，看到菜单后再选实际型号。具体步骤见[当前状态](CURRENT_STATUS.md)。

Navigation18 及框架连发／唤醒保护已进入真实生产系统：短按立即响应，长按 400ms 后每 160ms 连发，同一会话最多 10 秒，需真实松开或轴回中重新放行；熄屏与窗口变化取消旧会话。此前完成的 framework、双 ABI ART 和依赖 preopt 产物继续包含在 Test10。

针对 Test9 的双机摇杆反馈，本包更新公共摇杆模块及两份加载脚本。新候选分开处理 ADC 轴与 L3／R3 点击，对本模块已管理且没有争用迹象的 ADC 做受限恢复，保留中心和回中保护。默认 2GiB TF1 交换空间代码逐字保留，首次分配、后续复用，失败继续启动 Android。Lid4、时间默认源、USB 及生产签名／user／Enforcing 配置保持。

## 验证范围

| 范围 | 结论 |
| --- | --- |
| 整卡文件 | 完整 gzip 解压与 raw 逐字比较、完整父包回读、GPT 和各分区范围通过 |
| 变更边界 | 相对固定 Test8 仅变更一个 ramdisk helper、vendor 摇杆模块及加载脚本；其余启动和系统内容按字节保留 |
| 文件元数据 | CPIO 成员、vendor 511 个节点及属主／模式／标签／时间检查通过 |
| 新摇杆软件检查 | 实际 C 的 26 个正向场景、5 个旧代码负面对照、802 项检查及 45 个加载脚本场景通过 |
| 模块匹配 | 410 个参考 CRC、418 个本地 CRC、43 项导入，以及实际内核导出／重定位匹配通过 |
| 默认交换空间 | 继承 22 个脚本场景，前缀字节与 Test9 一致；主机未启用 swap |
| 实体使用 | 当前没有连接硬件，不用离线通过代替摇杆、导航恢复、swap 或全机型验收 |

## 当前待验证事项

优先验证 34XXSP 与 35XX H 的摇杆方向、回中、L3／R3 和熄屏恢复后的输入；同时确认 Navigation18 是否阻止此前解锁后持续导航的问题。旧反馈没有故障时完整 ADC／原始事件读回，因此唯一物理触发原因尚未证明。

十二机型菜单均已放行，但全部实物的显示／启动没有完成覆盖。实际 SwapTotal、首次分配等待和应用表现，以及同包 Wi-Fi、翻盖／休眠、USB 恢复、校时／RTC 保时及低概率频闪需分别验证。它们是当前验收边界，不能直接把早期 RC 的表现当作 Test10 已确认故障。

## 源码与构建范围

当前公共 Android 覆盖层含 1,759 个目标、626 个仓库输入，已包括 Navigation18 和 ViewRoot 保护。作者已完成真实 framework／双 ABI ART 生产构建并将其合入本包；公开 Android 用户空间构建入口仍采用指定 0.0.1 的启动资产。最新源文件与作者增量链见 [Test10 源码地图](TEST10_SOURCE_MAP.md)，可执行公共入口及其边界见[构建指南](PUBLIC_BUILD.md)和[构建状态](PUBLIC_BUILD_STATUS.md)。

## English summary

As of November 17, 2026, **0.0.2 Test10** is the latest local twelve-model candidate. Whole-card packaging, independent verification and Windows SHA256 checks passed. It includes manual model selection, three panel trials, loading feedback, Navigation18 and framework guards, a shared stick recovery candidate, default 2GiB swap and Lid4. Hardware acceptance of the new stick repair, navigation after resume, swap and all twelve models remains pending. The public external download is still 0.0.1; Test10 has not been uploaded.

Historical candidate failures remain in their dated records instead of being presented as confirmed defects in Test10. The public Android overlay contains 1,759 targets and 626 repository inputs, while its build entry retains the pinned 0.0.1 boot assets. It does not establish a clean-clone reproduction of the author's incremental Test10 packaging chain. See the [source map](TEST10_SOURCE_MAP.md), [current status](CURRENT_STATUS.md), [downloads](PUBLIC_DOWNLOADS.md) and [build validation scope](PUBLIC_BUILD_STATUS.md).
