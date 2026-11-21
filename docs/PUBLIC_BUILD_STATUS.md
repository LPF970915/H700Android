# 公共构建与当前镜像验证状态

更新于 2026-11-22。当前正式版 0.0.4 由实机验证的五面板 Test20 封装。

## 公共 Android 覆盖层

| 项目 | 当前值 |
| --- | --- |
| 源码清单 | `build-support/public/source-manifest.json` |
| SHA256 | `f29b3f0524eb5f8b89822c02dec74f45a6c1e302ff9276c6b4d6c75dfb0f0ee9` |
| 目标文件 | 1,766 |
| 仓库输入 | 633 |
| 参考镜像输入 | 8 |
| 基础源码输入 | 1,125 |
| 当前内容 | 0.0.4 版本、拼音输入、手柄检测、时间默认源、Navigation18、ViewRoot 导航恢复／连发保护及现有用户空间适配 |
| 固定外部输入 | H616 Android 10 基础源码包与指定 0.0.1 H700 镜像 |

[2026-11-15 验证记录](../build-support/public/validation-20261115.json)保留当时的输入、公共工具和导航源码检查结果。其“未构建生产 framework／ART”等历史字段没有回写；后续生产构建、镜像与实测由各自新记录补充。

0.0.3 的源码版本、清单与工具核对见 [validation-20261117-003.json](../build-support/public/validation-20261117-003.json)。

公共入口使用构建者自己的签名，重编 Android 用户空间并创建空 userdata；不导入作者镜像的诊断数据。步骤见 [PUBLIC_BUILD.md](PUBLIC_BUILD.md)。

## 已完成与仍待完成

| 范围 | 已有证明 | 边界 |
| --- | --- | --- |
| 仓库输入闭合 | 清单绑定覆盖目标和仓库输入的路径／大小／哈希；复制配方可核对 | 不等于完整编译 |
| 公共工具 | 11 项工具测试通过，准备／构建／打包收据绑定源码清单 | 不代表独立环境完整重编通过 |
| 公共导航源码 | Navigation18 状态机与 ViewRoot 实际源码 host/API 编译检查通过 | 硬件输入、时钟等主机边界显式模拟 |
| 作者生产构建 | 修复后的 framework、双 ABI ART、依赖 preopt 和 Navigation18 已实际构建，进入 Test6 并保留至 0.0.3 | 作者缓存链不同于干净环境公共重编 |
| ADC 摇杆修复 | 实际 C 的 38 个正向场景、6 个旧代码负控、1846 项检查及模块匹配核验通过；用户确认 Test11 的 RG35XX H 修复有效 | 单机反馈不能替代全型号验证 |
| 正式 0.0.4 镜像 | 以实测 Test20 为母包，修改两处版本数字，逐字节回读并校验 | 实机反馈来自维护者手头的机器 |
| 干净公开构建 | 公共指南和已知所需输入已提供 | 独立环境完整编译、打包及自编包实机验收尚未完成 |

生产 framework／ART 说明见[导航恢复修复](ROC_OS_NAVIGATION_RESUME_FIX_20261115.md)，ADC 实现见 [Test11 工程记录](ROC_OS_H700_ADC_CONTROL_REPAIR_TEST11_20261117.md)，本次正式封装见 [0.0.4 发行说明](ROC_OS_0.0.4_20261122.md)。

## 公开入口与正式镜像的范围

`tools/public_build/` 从指定 **0.0.1 提取 kernel、DTB、bootloader 和基础 ramdisk**，配合新编译的 Android 分区打包。后续的手动机型启动器、面板补丁、五组面板、交换空间和新摇杆模块已有公开源码，但尚未自动接成一个干净克隆的完整入口。

因此，公共指南生成的 `ROC_OS_ARM64_community.img.gz` 不等同于作者的 0.0.4 逐字镜像，也不能据此推断有完全相同的十二机型启动行为。组件与依赖关系见[源码地图](TEST10_SOURCE_MAP.md)。

独立重编全部 H700 启动组件仍需各组件对应版本、配置和完整流程。目前没有宣称所有 bootloader、kernel 或厂商二进制均由本项目从源码重编。大型源码、镜像和官方私钥不提交 Git。

## 可运行的轻量核对

在仓库根目录使用 Python 3.11+：

```sh
python3 tools/public_build/validate_manifest.py
python3 tools/public_build/test_public_build.py
```

各项检查保留自己的证明范围。当前后续工作为新包和其他机型实测，以及干净公开构建流程的完整执行与移植；旧测试失败继续保留归档。
