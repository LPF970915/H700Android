# H616 Android 10 主参考来源

日期：2026-09-02  
状态：主线权威输入，校验已完成

## 1. 完整 Android 10 源码

相对路径：

`H700_Android_Example/Orange Pi Zero 2（H616）/H616_Android_Source_Code/android.tar.gz`

- 文件大小：22,273,432,977 bytes；
- MD5：`c5dd785ecd45ca9a2b9c53b1092ee6ec`；
- 厂商 sidecar 与 2026-09-02 本机完整回读结果一致；
- 压缩包顶层目录：`android/`。
- tar 内容：约 904,526 个条目、45.14 GiB 文件载荷。

这是 Android 10 framework、build system、Allwinner `sun50iw9p1` / `cupid`
HAL、Mali-G31、Gralloc、HWC2、Audio HAL 5.0 和 low-RAM 配置的唯一主源码。

## 2. H616/H700 Longan BSP

相对路径：

`H700_Android_Example/Orange Pi Zero 2（H616）/H616_Android_Source_Code/longan.tar.gz`

- 文件大小：1,405,505,469 bytes；
- MD5：`11a2855d8b5c3430e3dd9dff6f40867e`；
- 厂商 sidecar 与 2026-09-02 本机完整回读结果一致。

当前已提取的可检索副本位于：

`work/h700-source-analysis/h616/longan/`

其中已确认包含 H700 Android kernel defconfig：

`device/config/chips/h700/configs/p1/linux/config-4.9`

该配置明确启用 PSI、MEMCG、MEMCG_SWAP 和 ZRAM，可作为 1 GiB low-RAM
策略的内核依据。RGSP 实机 kernel、DTB、面板、PMIC、GPIO 和分区事实仍高于
Orange Pi 板级配置，不能整体复制开发板 DTS 或启动链。

## 3. H616 Android 10 官方镜像

主镜像相对路径：

`H700_Android_Example/Orange Pi Zero 2（H616）/Android/OrangePi_Zero2_Android10_v1.2.tar.gz`

- 文件大小：529,428,875 bytes；
- SHA-256：`07a35c6b60716ff71c4a6392b8b31841363168b7498cc68bc51a0e938922d06a`；
- 用途：二进制 HAL、VINTF、init、audio、graphics 和属性行为对照；
- 不允许复制 Orange Pi bootloader、分区表、DTS、PMIC 或电视产品层。

`Android/backup/OrangePi_Zero2_Android10_v1.1.tar.gz` 仅作为旧版本备份，不是
主线输入。

## 4. H700 Android 10 运行证据

投影仪主板冷启动日志：

`out/logs/uart/projector-h21s700/h21s700_coldboot_20260901_105638_115200.log`

- 文件大小：83,457 bytes；
- SHA-256：`ed5816c59f62b3e78fa22170c4d3af0e951d0a1d086f31ee208fa7b93664e410`；
- 用途：确认 H700 Android 10 的启动阶段、设备注册顺序和音频拓扑；
- 边界：日志是运行证据，不代表投影仪产品服务、DTS 或硬件配置可直接移植。

## 5. 优先级规则

发生冲突时按以下顺序裁决：

1. RGSP 实机只读采集和原厂 kernel/DTB 事实；
2. H616 Android 10 完整源码与官方镜像；
3. H700 投影仪 Android 10 日志中的芯片级运行证据；
4. 已封存的 R36S Android 11 诊断结果；
5. H618 Android 12 精选集。

H618 只允许用于差异对照，任何 H618 文件进入 Android 10 产品目录或构建产物均
视为基线污染。

## 6. 本地构建位置

Ubuntu WSL2 发行版已于 2026-09-02 从 C 盘迁移到：

`D:/Works/H700Android/.wsl/Ubuntu/`

完整源码目标为发行版内的 `/home/lpf/h700-android10/android/`。因此 Linux 权限、
大小写和符号链接语义保留在 ext4 中，而对应 VHDX 物理文件仍位于 D 盘项目目录。
`tools/prepare_h616_android10_source.ps1` 会拒绝向项目外的 WSL 发行版解压。
