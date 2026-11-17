# ROC OS 发行概览

更新日期：2026-11-17。当前正式版本为 **0.0.3**，通过手动机型菜单供十二种 H700 设备共用。用户确认 Test11 的 RG35XX H 摇杆修复有效后，本次保留该实现并将镜像内部版本更新为 0.0.3。

当前说明以该版本为准。早期 RC、面板识别试验和中间测试包的过程保留在[历史记录](HISTORY.md)及对应日期文档中。

## 版本与分发

| 项目 | 当前状态 |
| --- | --- |
| 正式镜像 | `ROC_OS_ARM64_ver0.0.3.img.gz` |
| 压缩大小 | 591,772,793 字节 |
| gzip SHA256 | `34dcf5f43c0a75675530ff9b6c052351985d51b379a6e6189b388f331c6aaa52` |
| 解压大小 | 32,434,554,368 字节 |
| raw SHA256 | `42e08665eeeb953dba41eac8978b0c8fb8707e041dede5495409f4787bac8e5e` |
| 包内版本 | `ROC_OS_ARM64_ver0.0.3`／`ro.roc.os.version=0.0.3` |
| 本地交付 | 至少 64GB TF1，首次测试 TF2 留空 |
| 公开网盘 | 仍提供 0.0.1，0.0.3 尚未上传；[下载与校验](PUBLIC_DOWNLOADS.md) |

发布身份见 [0.0.3.json](../build-support/releases/0.0.3.json)，详细校验见 [0.0.3 发行说明](ROC_OS_0.0.3_20261117.md)。Git 同步源码和说明不等于镜像资产已上传。

## 主要变化

0.0.3 保留十二机型启动菜单、三档面板试屏、保存默认／重选和“加载中，请稍后”提示。720×480 包括 34XX、34XXSP、RGSP，720×720 为 CubeXX，其余八项为 640×480；各机型使用对应面板初始化。首次菜单以 35XX H 640×480 开始，音量键在 35XX H、34XXSP、CubeXX 三个代表配置间切换，看到菜单后选择实际型号。步骤见[当前状态](CURRENT_STATUS.md)。

Navigation18 及框架导航保护处理熄屏／窗口变化后的旧输入，短按立即响应，长按 400ms 后每 160ms 连发，同一会话最多 10 秒；松开或轴回中后重新放行。真实生产构建的 framework、双 ABI ART 和依赖 preopt 产物继续保留。

公共摇杆驱动修正 ADC 模式位检查，解决 Test10 的 35XX H“L3／R3 正常但方向无事件”。新实现保留 ADC 所有权、校准中心、回中和有界恢复保护。用户已确认 Test11 的本次修复有效，0.0.3 沿用同一驱动与加载脚本。

默认 2GiB TF1 交换空间首次分配、后续复用，失败继续启动 Android。Lid4、时间默认源、USB、生产签名与 user／Enforcing 配置继续保留。

## 验证范围

| 范围 | 当前结论 |
| --- | --- |
| 摇杆根因与实现 | Test10 的 USB 原始输入和 ADC 诊断定位模式位误判；新实际 C 的 38 个正向场景、6 个旧代码负控及 1846 项检查通过 |
| 模块与加载 | 410 个参考 CRC、418 个本地 CRC、43 项导入及实际内核导出／重定位匹配；45 个加载脚本场景通过 |
| RG35XX H 实体反馈 | 用户确认 Test11 修复有效；本次未追加 USB 原始输入取证 |
| 正式 0.0.3 封装 | 以精确 Test11 为父包，只更新 system 版本属性；完整验证与文件身份见发行说明 |
| 新包及全机型 | 0.0.3 新封装包未另行刷机验收；十二机型完整覆盖仍在进行 |

后续按实际新包验证恢复后导航、其他机型显示／摇杆，以及交换空间、翻盖／休眠、USB 与校时等表现。不把历史测试故障直接列作 0.0.3 已确认缺陷，也不把单机修复扩大成全机型验收。

## 源码与构建

公共 Android 覆盖层包含 1,759 个目标、626 个仓库输入，已包含 Navigation18 与 ViewRoot 保护。公共 Android 用户空间构建入口保留指定 0.0.1 启动资产；作者的十二机型启动与 0.0.3 增量链入口见[源码地图](TEST10_SOURCE_MAP.md)。

可执行入口与其验证范围见[构建指南](PUBLIC_BUILD.md)和[构建状态](PUBLIC_BUILD_STATUS.md)。当前没有声称干净克隆能一步逐字重现作者正式整卡。

## English summary

As of November 17, 2026, **0.0.3** is the current release. It retains the Test11 stick repair confirmed by the user on RG35XX H, manual selection for twelve models, three panel trials, loading feedback, Navigation18 and framework guards, default 2GiB swap and Lid4.

The release package updates the embedded system version from the exact Test11 parent. The newly packaged 0.0.3 image has not had a separate hardware acceptance run, and complete coverage of all twelve models remains in progress. The public external download is still 0.0.1; 0.0.3 has not been uploaded. See the [release notes](ROC_OS_0.0.3_20261117.md), [current status](CURRENT_STATUS.md), [downloads](PUBLIC_DOWNLOADS.md) and [build validation scope](PUBLIC_BUILD_STATUS.md).
