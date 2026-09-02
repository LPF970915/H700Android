# H700 Android 最小参考材料

准备日期：2026-08-26  
存放位置：`D:\Works\H700Android\reference`  
策略：浅克隆、部分克隆和稀疏检出；没有下载完整 AOSP、Android 整卡镜像或 H616 SDK。

## 已准备内容

| 目录 | 分支/标签 | 固定提交 | 用途 |
|---|---|---|---|
| `aosp-platform-manifest-android10` | `android-10.0.0_r47` | `aaf063a1ac9b5dd39b891350c5a4bf06b905a7f6` | Android 10 官方项目清单参考 |
| `lineage-manifest-18.1` | `lineage-18.1` | `fed547c557daea86389b10bf3e25ad6ae13114e2` | LineageOS 18.1 项目清单参考 |
| `r36s-device` | `lineage-18.1` | `9b0194568c1359ccd385df498836f2de790205ad` | R36S Android device tree、ramdisk、镜像构建结构参考 |
| `r36s-multiboot` | `main` | `05171c9d71f38c80580e67f26368bb81c47d1b45` | Android 分区安装、fstab 改写和按键 multiboot 参考 |
| `andr36oid-docker-build` | `main` | `02d9131726f27d2b170b61f903222af7ced5acd5` | Andr36oid 构建环境和依赖说明参考 |

这些提交是当前本地材料的版本锁。其他窗口分析时应先记录当前 `HEAD`，不要无提示
地执行 `git pull` 或切换分支。

## 稀疏检出范围

`r36s-device` 只保留：

- Android product/device 配置；
- `BoardConfig.mk` 和 `device.mk`；
- `BOOT/boot.ini*`；
- `ramdisk/`；
- `overlay/`；
- `mkimg.sh` 和 `mkota.sh`。

没有检出 R36S 的 bootloader、预编译 DTB 和面板二进制，因为它们不能用于 H700。

`r36s-multiboot` 只保留：

- 根目录说明和 `buildimg.sh`；
- `andr36oid/` 安装脚本、boot 配置和 `fstab`；
- 启动按键及公共选择配置。

没有检出该仓库内的大型系统包、ROM 存储包、其他 Linux 系统和图片资源。

## 当前不能做什么

- `aosp-platform-manifest-android10` 和 `lineage-manifest-18.1` 只是 manifest，当前没有
  完整源码，不能直接执行 Android 编译。
- 当前没有 H700 Android device tree、Android vendor HAL 或 Android system image。
- 当前没有下载 Orange Pi/H616 Android SDK，因为其体积较大且版本匹配尚未确认。
- 任何 R36S 文件都不能直接写入 RG34XXSP/H700 的 TF 卡或 boot 分区。
- 当前产物不是可刷镜像。

## 推荐阅读顺序

1. `..\docs\R36S_TO_H700_ANDROID_PORTING_BASELINE_20260826.md`
2. `r36s-device\BOOT\boot.ini`
3. `r36s-device\mkimg.sh`
4. `r36s-multiboot\andr36oid\install-os.sh`
5. `r36s-multiboot\andr36oid\boot.andr36oid.ini`
6. `r36s-multiboot\andr36oid\fstab.rk30board`
7. `andr36oid-docker-build\README.md`

## 下一步材料门槛

在下载完整 AOSP 或 H616 Android SDK 前，应先完成 UART 下的只读验证：

- U-Boot 能否枚举 TF2；
- TF2 在 U-Boot 中对应哪个 MMC 编号；
- U-Boot 能否从 TF2 FAT/ext4 分区读取测试文件；
- H700 boot image 的 DTB 装载位置和实际启动命令。

这些结果决定后续只下载 Android ramdisk 所需源码，还是建立完整 Android 10 工作区。

## 存储约束

本项目后续所有下载和临时文件应继续使用：

```text
D:\Works\H700Android\reference   小型外部参考代码
D:\Works\H700Android\input       原始输入和设备导出文件
D:\Works\H700Android\work        解包、编译和中间产物
D:\Works\H700Android\out         可复现的最终测试产物
D:\Works\H700Android\.tmp        下载和工具临时目录
```

不要把 AOSP checkout、SDK、镜像或编译输出放入 C 盘。

