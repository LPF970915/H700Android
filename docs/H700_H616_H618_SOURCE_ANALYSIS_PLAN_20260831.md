# H700 对 H616/H618 Android 资料分析基线

日期：2026-08-31  
适用设备：RGSP/RG34XXSP，Allwinner H700 / `sun50iw9`，Linux 4.9.170

## 1. 决策

H616 和 H618 的完整 Android 源码、源码包和镜像都应保留并纳入分析，但不需要先
完整编译两套，也不应把任意单个库直接复制到 H700。

当前项目已经进入 Android 11 headless framework：`zygote64` 和 `system_server`
可以启动，fix42 的首个长期停点是缺少 SurfaceFlinger 时的 LightsService 同步查询。
因此资料分析的首要目标是寻找 **与 H700 4.9.170、sun50iw9、fbdev/disp/ION、
`mali_kbase` 成套匹配的 Android 用户态实现**。

## 2. 两套资料的优先级

| 资料 | 主要用途 | 与当前 H700 的预期相关性 |
|---|---|---|
| H616 Android 10 | Longan/4.9 时代的 init、ION、disp、Gralloc/HWC、Mali 和打包流程 | 高，优先分析 |
| H618 Android 12 | 较新 Android framework、HWC/Gralloc 服务接口、Audio/Power HAL 对照 | 中，作为结构参考 |
| 任意单板 boot/vendor 镜像 | 提取成套二进制、属性、rc、DTB、权限和版本信息 | 取决于 kernel/显示/内存配置 |

H618 Android 12 的价值主要是比较实现方式，不能假设其 Linux 5.4、DRM、GBM 或
Mali 用户库可以运行在当前 H700 内核上。H616 Android 10 也只有在 kernel ABI、
显示控制器、ION heap 和 panel 路径接近时才可能成为二进制候选。

## 2.1 按当前网盘目录的下载顺序

**第一批：必须下载 H616 Orange Pi Zero 2 全套。**

- `H616_Android_Source_Code/android.tar.gz`（约 20.74 GB）及对应 `android.tar.gz.md5sum`；
- `H616_Android_Source_Code/longan.tar.gz`（约 1.31 GB）及对应 `longan.tar.gz.md5sum`；
- `Android/OrangePi_Zero2_Android10_v1.2.tar.gz`（约 504.90 MB）。

`android.tar.gz` 和 `longan.tar.gz` 是源码主体，不能只下载其中一个；两个 md5 文件
也应保留。`backup` 目录暂不作为第一批下载目标，除非其中包含额外脚本或校验文件。

**第二批：下载 H618 Orange Pi Zero 3 全套。**

- `H618_Android12源码` 目录中的全部 19 个分卷文件；
- `Android/OrangePi_Zero3_Android12_v1.0.tar.gz`（约 548.83 MB）。

分卷必须全部下载后再合并/解压，不能只取首个分卷。Zero 3 的 Android 12 资料足以
作为 H618 结构和 HAL 对照样本。

**第三批：H618 Orange Pi Zero 2W 暂缓。**

- `H618_Android12源码` 目录的 20 个分卷和
  `Android/Orangepi_zero2w_android12_tv_v1.0.tar.gz`（约 551.48 MB）只有在需要比较
  Zero 2W 的 Wi-Fi/BT、板级 DTB 或 TV 产品差异时再下载。

当前 H700 掌机主线不需要同时分析 Zero 3 和 Zero 2W 两套 H618 Android 12；Zero 2W
镜像带有 TV 产品配置，对 720x480 无触摸掌机的直接参考价值较低。

## 3. 首轮只读 inventory

每个源码树和镜像都先记录：

- 文件名、来源、版本、发布日期、SHA-256；
- Android 版本、kernel 版本、架构、RAM/存储布局；
- DTB model/compatible、LCD 分辨率/接口、PMIC、音频 codec；
- `CONFIG_ANDROID_BINDER_IPC`、`CONFIG_ASHMEM`、`CONFIG_ION`、`CONFIG_DRM`、
  `CONFIG_MALI`/`mali_kbase`；
- `/vendor/lib64/hw`、`/vendor/lib64/egl`、`/system/lib64/egl`、
  `gralloc*`、`hwcomposer*`、`android.hardware.graphics*`；
- `init*.rc`、`fstab*`、`ueventd*.rc`、`property_contexts`、VNDK/APEX 版本；
- Audio、Health、Power、Lights、Vibrator、Wi-Fi/BT HAL 和固件；
- boot header、kernel/ramdisk/DTB 的 SHA-256 与加载地址。

## 4. 对当前几大卡点的帮助

### 4.1 图形/SF/GPU：帮助最大

重点寻找以下成套关系：

```text
mali_kbase kernel ABI
  + libmali/libEGL/libGLES
  + gralloc/mapper/allocator
  + hwcomposer/composer
  + ION heap 与 /dev/disp 接口
```

必须把这些文件作为一个版本组对待。只找到 `libGLES_mali.so`，但没有匹配的
Gralloc/HWC 或 kernel ABI，不能解决当前 SurfaceFlinger 卡点。

### 4.2 init/APEX/Binder：帮助中等

H616 Android 10 的 init、`fstab`、VNDK、APEX 和 binder 节点配置可用于减少当前
fix11–fix42 的临时补丁，但最终仍需按 RGSP 的分区和 `selinux=0`/SELinux 策略重建。

### 4.3 音频/电源/输入：帮助中等到较大

可以提取 Audio HAL、Health/Power/Lights/Vibrator 服务的接口和属性命名；但 RGSP
实际 PMIC 是 AXP2202、输入设备是 `ANBERNIC-keys`/`axp2202-pek`，必须重新对照
本机 sysfs、evdev 和 ALSA，不可直接套板卡 GPIO 或 codec 配置。

### 4.4 内存优化：帮助有限但有参考价值

可比较 low-RAM、zram、LMKD 和服务裁剪配置；1 GiB RGSP 仍需按实测 RSS/OOM 调参，
不能因为 H618 镜像能启动就推断其适合掌机。

## 5. 资料分析的停止边界

- 不先完整编译 H616/H618 两套源码；只有在确认目标模块和工具链后再做最小模块构建。
- 不把 H618/Android 12 的 DRM/Panfrost 路线强行套到 RGSP 的 `fb0/disp/ION`。
- 不因投影仪没有 UART 就暂停 RGSP 主线；投影仪只读镜像分析可以先做，运行时结论
  等待以后获得 UART、ADB 或其他可观测入口再确认。
- 不修改 RGSP 的 U-Boot、GPT、boot0 或持久 env 来验证资料兼容性。

## 6. 投影仪 UART 不可用时的替代路径

当前 H21S-700-V3.0 主板无法焊接 UART，因此暂时不能获得其 BOOT0/U-Boot/Android
启动日志。这会减少运行时证据，但不会阻止以下工作：

1. 从现有 TF/eMMC 镜像或厂商资料静态提取 boot、vendor、system、DTB 和库；
2. 在主机上比较 kernel strings、DTB compatible、版本号、SONAME、NEEDED 和符号；
3. 用 RGSP 已验证的 `/dev/fb0`、`/dev/disp`、`/dev/ion`、`/dev/mali0` 作为运行时 oracle；
4. 将投影仪标记为“静态 donor，运行时兼容性未证实”，禁止直接刷写其镜像。

投影仪 UART 恢复后只需补采启动日志和运行时节点，不必重做整个源码分析。

## 7. 2026-08-31 本地资料实测结果

已完成的本地资料处理：

- H616 `android.tar.gz`、`longan.tar.gz` 的 MD5 校验通过；
- H618 Android 12 的 18 个分卷已逐个校验，并合并为一个总 tar.gz；
- H616 Android 10、H618 Android 12 镜像已解压为可分析的 `.img`；
- H616 Longan 已在 WSL 中解压，并确认同时包含 `device/config/chips/h616/` 和
  `device/config/chips/h700/`，以及 Linux 4.9、U-Boot、boot0、BL31、打包配置。

已从 H616 Android 10 源码包中提取 `device/softwinner/cupid-perf1` 和
`cupid-common`。其中 `hal.mk` 明确使用 Android graphics allocator/mapper、
composer 2.2、`hwcomposer.cupid`、`gralloc.cupid` 和 `libion`；这组文件是当前
H700 图形卡点最值得继续追踪的 Android 10 参考。

Longan 的 H700 `p1` 配置给出以下事实：

- `LICHEE_CHIP=sun50iw9p1`、Linux 4.9；
- `CONFIG_SUNXI_GPU_TYPE="mali-g31"`；
- `CONFIG_DRM` 未启用，`CONFIG_FB=y`、`CONFIG_ION=y`、`CONFIG_ION_SUNXI=y`、
  `CONFIG_ION_OF=y`；
- Binder 设备为 `binder,hwbinder,vndbinder`；
- 示例 `board.dts` 的 compatible 仍写为 `allwinner,h616`，LCD 默认未启用且是
  1280x800，HDMI 启用，PMIC 为 AXP806。它是 H700 SoC/内核接口参考，不是 RGSP
  掌机可直接刷写的设备树。

因此 Gemini 回答中的“直接放弃 H616、全程使用 H618 Android 12”已修正为：
**H616 Android 10 是主线，H618 Android 12 只做框架/HAL 对照；任何 Mali、Gralloc、
HWC 二进制都必须先验证与 RGSP 的 4.9.170 + fb0/disp/ION ABI 配套。**

## 8. 压缩包保留/删除边界

当前不删除原始源码包。H616 `android.tar.gz`、`longan.tar.gz` 仍是后续按路径重提取
的唯一来源；H618 分卷虽然已有合并总包，也保留分卷和 md5，直到总包完成目标文件提取
与校验。已确认可在完成镜像二次提取后删除的仅包括重复的 H616
`Android/backup/OrangePi_Zero2_Android10_v1.1.tar.gz`，以及已验证、已提取完毕的
镜像压缩包；删除前需记录 SHA-256 和提取清单。
