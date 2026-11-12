# 外部下载与文件校验

更新日期：2026-11-13。大型镜像、Android/Longan 基础源码通过网盘分发，Git 保存必要源码差异、配置、工具和校验信息。

## ROC OS ARM64 ver0.0.1

- [H700_Android 镜像分享](https://pan.baidu.com/s/12mIL9R38oy65ldhGujHWuw?pwd=H700)
- 提取码：`H700`
- 文件：`ROC_OS_ARM64_ver0.0.1.img.gz`
- gzip 大小：591,043,813 字节。
- gzip SHA256：`e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346`。
- 解压大小：32,434,554,368 字节。
- raw SHA256：`09935c4935ca579d6956388b2a3af509b4d6c4763e36a047091373a4218208e3`。

此版本由 Recovery720 Test3 派生，USB 默认配置为 `mtp,adb`；已有离线封装与独立校验记录。它属于 RG SP 原 720 启动路径的测试版本，**不是全部 H700 机型或面板均已通过的正式稳定版**。干净首启、实际 MTP 复制读回及其他运行验收仍需区分记录；网盘公开下载不改变这些验收边界。原有诊断镜像的工作站公钥预授权与公共自编镜像的空数据分区不同，见构建指南。

0.0.1 镜像也作为公共构建流程的硬件启动资产与必要二进制提取来源。`extract.py` 不导入其 userdata，`pack.py` 为自编镜像新建空 userdata。

## H616 Android 基础源码与参考镜像

- [H700_Android_Example 分享](https://pan.baidu.com/s/1carfBOv4uB0bM9LoRLqmrw?pwd=H616)
- 提取码：`H616`
- Android、Longan 的准确目录、大小和已有校验见 [H616 来源记录](H616_ANDROID10_PROVENANCE_20260902.md)。

分享链接由维护者提供；发布链接不等于重新下载网盘文件完成校验。应对实际下载文件运行 [公共构建指南](PUBLIC_BUILD.md) 的校验步骤，机器可读规格见 [external-inputs.json](../build-support/public/external-inputs.json)。H616 参考镜像不能直接当作 H700 掌机烧录包。

## 自行构建

当前 Git 仓库、H616 分享中的 `android.tar.gz` 和上述指定 0.0.1 镜像已覆盖现有构建流程的已知输入，核对未发现仍须补传的必要文件。请使用 [PUBLIC_BUILD.md](PUBLIC_BUILD.md)，构建者生成自己的签名，无须官方私钥。输入准备与工具检查已通过，干净环境完整重编和自编镜像实机验收仍待完成，详见 [PUBLIC_BUILD_STATUS.md](PUBLIC_BUILD_STATUS.md)。kernel、DTB、bootloader 和基础 ramdisk 沿用 0.0.1；这些组件全部从源码重编的版本锁定、配置和步骤仍需补齐。
