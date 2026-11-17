# 外部下载与文件校验

更新日期：2026-11-17。当前正式包为 **0.0.3**，保留用户已确认在 RG35XX H 上有效的 Test11 摇杆修复。新包在本地交付，尚未上传；下方公开网盘仍提供 **0.0.1**。当前功能与机型选择见[版本说明](CURRENT_STATUS.md)。

大型镜像、Android／Longan 基础源码通过网盘分发；Git 保存源码差异、配置、工具和校验信息。

## 正式镜像：0.0.3

同一份整卡镜像开放十二种 H700 机型，包含三档面板试屏、加载提示、Navigation18 与框架导航保护、ADC 模式位修复及默认 2GiB TF1 交换空间。

| 项目 | 值 |
| --- | --- |
| 文件 | `ROC_OS_ARM64_ver0.0.3.img.gz` |
| gzip 大小 | 591,772,793 字节 |
| gzip SHA256 | `34dcf5f43c0a75675530ff9b6c052351985d51b379a6e6189b388f331c6aaa52` |
| 解压大小 | 32,434,554,368 字节 |
| raw SHA256 | `42e08665eeeb953dba41eac8978b0c8fb8707e041dede5495409f4787bac8e5e` |
| 包内显示标识 | `ROC_OS_ARM64_ver0.0.3` |
| 版本属性 | `ro.roc.os.version=0.0.3` |
| 建议系统卡 | 至少 64GB TF1，首次测试 TF2 留空 |
| 分发状态 | 本地交付，尚无新包的公开下载地址 |

完整变化与验收见 [0.0.3 发行说明](ROC_OS_0.0.3_20261117.md)，机器可读文件身份见 [0.0.3.json](../build-support/releases/0.0.3.json)。Test11 的 RG35XX H 用户实测结果与新包的离线验证分别记录，不扩大为十二机型全部实测通过。

下方旧网盘链接对应 0.0.1。新包上传后，请按实际文件名和 SHA256 核对。

## ROC OS ARM64 ver0.0.1

- [H700_Android 镜像分享](https://pan.baidu.com/s/12mIL9R38oy65ldhGujHWuw?pwd=H700)
- 提取码：`H700`
- 文件：`ROC_OS_ARM64_ver0.0.1.img.gz`
- gzip 大小：591,043,813 字节。
- gzip SHA256：`e72580e8c4e4afc8b08b50570ad6beebf46a435ee6e8b32b7a943f21786a6346`。
- 解压大小：32,434,554,368 字节。
- raw SHA256：`09935c4935ca579d6956388b2a3af509b4d6c4763e36a047091373a4218208e3`。

0.0.1 是早期 720×480 启动路径的公开测试版本，不含 0.0.3 的十二机型菜单、Navigation18 或本次摇杆修复，也不代表全 H700 面板均已通过。USB 默认配置为 `mtp,adb`；其已有诊断 userdata 与公共自编镜像的新建空 userdata 不同，见构建指南。

0.0.1 镜像继续作为公共构建流程的硬件启动资产与必要二进制提取来源。`extract.py` 不导入其 userdata，`pack.py` 为自编镜像新建空 userdata。

## H616 Android 基础源码与参考镜像

- [H700_Android_Example 分享](https://pan.baidu.com/s/1carfBOv4uB0bM9LoRLqmrw?pwd=H616)
- 提取码：`H616`
- Android、Longan 的准确目录、大小和已有校验见 [H616 来源记录](H616_ANDROID10_PROVENANCE_20260902.md)。

分享链接由维护者提供；发布链接不等于重新下载网盘文件完成校验。应对实际下载文件运行 [公共构建指南](PUBLIC_BUILD.md) 的校验步骤，机器可读规格见 [external-inputs.json](../build-support/public/external-inputs.json)。H616 参考镜像不能直接当作 H700 掌机烧录包。

## 自行构建

当前 Git 仓库、H616 分享中的 `android.tar.gz` 和上述指定 0.0.1 镜像已覆盖现有公共构建流程的已知输入。请使用 [PUBLIC_BUILD.md](PUBLIC_BUILD.md)，构建者生成自己的签名，无须官方私钥。

公共入口重编 Android 用户空间并保留指定 0.0.1 启动资产。其验证范围和作者 0.0.3 增量封装链的区别见 [PUBLIC_BUILD_STATUS.md](PUBLIC_BUILD_STATUS.md)，当前实现的源文件入口见[源码地图](TEST10_SOURCE_MAP.md)。
