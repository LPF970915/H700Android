# 外部下载与文件校验

更新日期：2026-11-17。当前最新本地测试镜像为 **0.0.2 Test10**，已完成整卡封装、完整独立验证和 Windows SHA256 核对，尚未上传。下方网盘仍提供 **0.0.1**。当前功能、机型选择和待验证项目见[当前版本说明](CURRENT_STATUS.md)。

大型镜像、Android／Longan 基础源码通过网盘分发；Git 保存源码差异、配置、工具和校验信息。

## 最新本地测试镜像：0.0.2 Test10

同一份镜像开放十二种 H700 机型，包含新摇杆恢复候选、Navigation18、三档面板试屏、加载提示及默认 2GiB 虚拟内存。实体摇杆修复与全机型覆盖尚未验收，详见 [Test10 说明](ROC_OS_H700_STICK_RECOVERY_TEST10_20261117.md)。

| 项目 | 值 |
| --- | --- |
| 文件 | `ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test10_StickRecovery_20261117.img.gz` |
| gzip 大小 | 591,771,367 字节 |
| gzip SHA256 | `ad6cec97dafc641cc4729273f3aea40dc4a4047cef32080bbbfbb88b056f8535` |
| 解压大小 | 32,434,554,368 字节 |
| raw SHA256 | `b200fc3fe65cecc1bbf5d8fdf68e6643060c3e6faec499f276a4c4192ec44afe` |
| 建议测试卡 | 至少 64GB TF1，TF2 留空 |
| 分发状态 | 已在本地交付，尚无公开下载地址 |

校验与验收见[机器可读记录](baselines/roc-os-h700-stick-recovery-test10-20261117/acceptance.json)。本页没有将旧网盘链接当作 Test10 下载地址；上传后应以实际文件名和 SHA256 核对。

## ROC OS ARM64 ver0.0.1

- [H700_Android 镜像分享](https://pan.baidu.com/s/12mIL9R38oy65ldhGujHWuw?pwd=H700)
- 提取码：`H700`
- 文件：`ROC_OS_ARM64_ver0.0.1.img.gz`
- gzip 大小：591,043,813 字节。
- gzip SHA256：`e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346`。
- 解压大小：32,434,554,368 字节。
- raw SHA256：`09935c4935ca579d6956388b2a3af509b4d6c4763e36a047091373a4218208e3`。

0.0.1 是早期 720×480 启动路径的公开测试版本，不含 Test10 的十二机型菜单、Navigation18 或本次摇杆恢复候选，也不代表全 H700 面板均已通过。USB 默认配置为 `mtp,adb`；其已有诊断 userdata 与公共自编镜像的新建空 userdata 不同，见构建指南。旧版本的测试问题保留在历史记录，不作为 Test10 的当前故障清单。

0.0.1 镜像也作为公共构建流程的硬件启动资产与必要二进制提取来源。`extract.py` 不导入其 userdata，`pack.py` 为自编镜像新建空 userdata。

## H616 Android 基础源码与参考镜像

- [H700_Android_Example 分享](https://pan.baidu.com/s/1carfBOv4uB0bM9LoRLqmrw?pwd=H616)
- 提取码：`H616`
- Android、Longan 的准确目录、大小和已有校验见 [H616 来源记录](H616_ANDROID10_PROVENANCE_20260902.md)。

分享链接由维护者提供；发布链接不等于重新下载网盘文件完成校验。应对实际下载文件运行 [公共构建指南](PUBLIC_BUILD.md) 的校验步骤，机器可读规格见 [external-inputs.json](../build-support/public/external-inputs.json)。H616 参考镜像不能直接当作 H700 掌机烧录包。

## 自行构建

当前 Git 仓库、H616 分享中的 `android.tar.gz` 和上述指定 0.0.1 镜像已覆盖现有构建流程的已知输入，核对未发现仍须补传的必要文件。请使用 [PUBLIC_BUILD.md](PUBLIC_BUILD.md)，构建者生成自己的签名，无须官方私钥。输入准备与工具检查已通过，干净环境完整重编和自编镜像实机验收仍待完成，详见 [PUBLIC_BUILD_STATUS.md](PUBLIC_BUILD_STATUS.md)。kernel、DTB、bootloader 和基础 ramdisk 沿用 0.0.1；这些组件全部从源码重编的版本锁定、配置和步骤仍需补齐。
