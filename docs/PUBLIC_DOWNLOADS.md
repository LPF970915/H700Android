# 镜像下载与文件校验

当前正式版为 **0.0.4**。维护者将镜像同步至长期网盘，提取码 **H700**。网盘保留历史版和测试版，请按完整文件名下载。[H700 镜像网盘](https://pan.baidu.com/s/12mIL9R38oy65ldhGujHWuw?pwd=H700) · [首次开机按键表](H700_BOOT_GUIDE_0.0.4_zh-CN.md)

| 项目 | 值 |
| --- | --- |
| 镜像文件 | ROC_OS_ARM64_ver0.0.4.img.gz |
| 压缩大小 | 735,536,681 字节 |
| 压缩包 SHA-256 | `4a4e9fd4e980b7d9effd3d23f4d423bedd8a615705de3175d6bb333b4df0e53e` |
| 解压大小 | 32,434,554,368 字节 |
| 整卡 SHA-256 | `f71c6ada45033c9b57f1de1f3d0c536847c9df21f585378a89ab6bad42862fe4` |

[0.0.4 发行说明](ROC_OS_0.0.4_20261122.md) · [历史 0.0.3 的校验信息](../build-support/releases/0.0.3.json)

## 历史 0.0.1 与公共构建固定输入

- 位置：上方长期更新的镜像网盘中的历史版本。
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

公共入口重编 Android 用户空间并保留指定 0.0.1 启动资产。其验证范围和作者增量封装链的区别见 [PUBLIC_BUILD_STATUS.md](PUBLIC_BUILD_STATUS.md)，当前实现的源文件入口见[源码地图](TEST10_SOURCE_MAP.md)。
