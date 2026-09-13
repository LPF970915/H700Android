# H700 Android 独立系统卡制作成功指南

> **流程基线更新（2026-09-13）**：本文保留 v3b 的构建和分区背景；
> 实际物理写卡请以 `docs/H700_DIRECT_FLASH_SUCCESS_PATH_20260913.md`
> 为准。已验证成功的是完整镜像直接写入并完整回读，不是本文旧的
> 分段 v3b 写卡脚本。旧分段脚本已废弃。

## 概述
本文档记录了成功制作 H700 Android 10 独立系统卡（单卡启动）的完整流程和关键经验。

**目标硬件**：H700 掌机（720×480 @ 213 DPI）  
**Android版本**：Android 10（基于全志H616 BSP）  
**启动方式**：TF1卡槽单卡启动（无需Linux系统卡）  
**默认启动器**：AT4K启动器（小屏幕适配版）

---

## 一、关键成功因素

### 1.1 分区表配置
**文件位置**：`/home/lpf/h700-android10/android/device/roc/rgsp/h700_partition_2card.txt`

**关键要求**：
- bootloader 分区必须在 **20480** 扇区（10MB）起始
- env 分区紧跟其后，大小 **20480** 扇区
- boot 分区必须设置 `downloadfile="boot.fex"` 才能被 u-boot 识别
- vendor 分区必须配置 `verify=1` 启用 dm-verity

**正确的分区配置**：
```ini
[partition]
    name         = bootloader
    size         = 32768        ; 16MB
    downloadfile = "u-boot.fex"
    user_type    = 0x8000

[partition]
    name      = env
    size      = 20480          ; 10MB
    user_type = 0x8000

[partition]
    name         = boot
    size         = 65536        ; 32MB
    downloadfile = "boot.fex"
    user_type    = 0x8000

[partition]
    name         = system
    size         = 2097152     ; 1GB
    downloadfile = "system.fex"
    user_type    = 0x8000

[partition]
    name         = vendor
    size         = 536870912   ; 256MB
    downloadfile = "vendor.fex"
    verify       = 1
    user_type    = 0x8000
```

### 1.2 U-Boot 环境变量
**文件位置**：`/home/lpf/h700-android10/android/device/roc/rgsp/env-2card.cfg`

**关键配置**：
```bash
# 从 boot 分区加载内核和 ramdisk
setenv bootcmd 'ext4load mmc 0:3 0x44000000 Image; ext4load mmc 0:3 0x4e000000 ramdisk.img; setenv bootargs console=ttyS0,115200 androidboot.hardware=sun50iw9p1 init=/init root=/dev/mmcblk0p4 rootwait ro androidboot.selinux=permissive androidboot.verifiedbootstate=orange; booti 0x44000000 0x4e000000 0x48000000'
```

**注意事项**：
- `mmc 0:3` 是 boot 分区（第3分区）
- `root=/dev/mmcblk0p4` 是 system 分区（第4分区）
- 必须设置 `androidboot.selinux=permissive`
- `ramdisk.img` 的加载地址必须正确（0x4e000000）

### 1.3 写卡脚本配置
**脚本位置**：`D:\Works\H700Android\tools\write_rgsp_single_card_v3b.ps1`

**关键参数**：
- bootloader 写入位置：扇区 **16** (8KB起始)
- env 写入位置：扇区 **53248** (bootloader之后26MB)
- 必须使用 `-ConfirmWrite` 参数执行
- 目标设备通过 Serial Number 识别：`000000001539`

---

## 二、AT4K 启动器小屏幕适配

### 2.1 布局修改位置
**源APK**：`AT4K启动器专业版汉化版V1.2.apk`  
**修改目录**：`D:\Works\H700Android\out\at4k-h700-adapt\decoded\smali\R3\`

### 2.2 具体修改内容

#### 文件1：`J7.smali` (设置面板布局)
| 行号 | 原值 | 新值 | 说明 |
|------|------|------|------|
| 8894 | `0x1a` (26sp) | `0x12` (18sp) | 标题字体大小 |
| 8902 | `0x18` (24dp) | `0x8` (8dp) | 标题底部间距 |
| 8808 | `0xc` (12dp) | `0x6` (6dp) | 项目垂直间距 |
| 9319 | `0xa` (10dp) | `0x6` (6dp) | 条目内边距 |
| 9416 | `0x14` (20sp) | `0xe` (14sp) | 条目文字大小 |

#### 文件2：`T5.smali` (桌面布局)
| 行号 | 原值 | 新值 | 说明 |
|------|------|------|------|
| 828 | `0xa` (10dp) | `0x8` (8dp) | 左右内边距 |
| 832 | `0x18` (24dp) | `0xc` (12dp) | 顶部内边距 |
| 836 | `0x44` (68dp) | `0x20` (32dp) | 底部内边距 |

#### 文件3：`Z4.smali` (图标几何布局)
| 行号 | 原值 | 新值 | 说明 |
|------|------|------|------|
| 229 | `0x12` (18dp) | `0xc` (12dp) | 行间距 |
| 284 | `0x16` (22dp) | `0x10` (16dp) | 水平间隙 |

### 2.3 重新打包流程
```powershell
# 1. 使用 Apktool 重新编译
java -jar tools/apktool/apktool.jar b out/at4k-h700-adapt/decoded -o out/at4k-h700-adapt/AT4K_h700_unsigned.apk

# 2. 签名 APK
C:\Users\LPF\AppData\Local\Android\Sdk\build-tools\34.0.0\apksigner.bat sign `
    --ks .tmp\at4k-test.keystore `
    --ks-key-alias at4k `
    --ks-pass pass:android `
    --key-pass pass:android `
    --out out/at4k-h700-adapt/AT4K_h700_signed.apk `
    out/at4k-h700-adapt/AT4K_h700_unsigned.apk
```

### 2.4 集成到系统
```bash
# 1. 复制到 WSL 预置目录
cp AT4K_h700_signed.apk /home/lpf/h700-android10/android/device/roc/rgsp/prebuilt/AT4K/AT4K.apk

# 2. 计算 SHA256
sha256sum device/roc/rgsp/prebuilt/AT4K/AT4K.apk

# 3. 更新 firstboot 脚本
# 编辑 device/roc/rgsp/rgsp-firstboot.sh，更新 at4k_sha 值

# 4. 低压力模式构建系统
cd /home/lpf/h700-android10/android
# 在 PowerShell 中执行：
# .\tools\build_h700_low_pressure.ps1 -Execute
```

---

## 三、完整制作流程

### 3.1 准备阶段
1. 确保 WSL Ubuntu 中有完整的 Android 10 源码
2. 准备 AT4K APK 并完成布局适配
3. 准备目标 SD 卡（最小 16GB）

### 3.2 构建系统镜像
```powershell
# 在 Windows PowerShell 中执行
cd D:\Works\H700Android
.\tools\build_h700_low_pressure.ps1 -Execute
```

**构建时间**：约 30 秒（低压力模式，CPU 0-1，-j1）  
**输出文件**：
- `/home/lpf/h700-android10/android/out/target/product/rgsp/system.img` (765MB)
- `/home/lpf/h700-android10/android/out/target/product/rgsp/vendor.img`
- `/home/lpf/h700-android10/android/out/target/product/rgsp/boot.img`

### 3.3 写入SD卡
```powershell
# 1. 插入 SD 卡到读卡器

# 2. 确认设备
Get-PhysicalDisk | Where-Object { $_.BusType -eq "USB" -and $_.SerialNumber -eq "000000001539" }

# 3. 执行写卡（需要管理员权限）
.\tools\write_rgsp_single_card_v3b.ps1 -ConfirmWrite
```

### 3.4 上机测试
1. **插卡**：将制作好的 SD 卡插入 H700 的 **TF1 卡槽**
2. **连接串口**：使用 USB-TTL 连接 UTRA 串口监控启动过程
3. **开机**：按电源键，观察串口输出
4. **选择启动器**：首次启动会弹出启动器选择对话框
   - 选择 **AT4K** 
   - 如果误选 RG HOME，可通过串口执行重置命令

---

## 四、故障排除

### 4.1 按电源键无响应
**可能原因**：
- bootloader 写入位置错误（必须是扇区16）
- env 分区配置错误
- SD 卡未正确插入 TF1 卡槽

### 4.2 卡在 U-Boot 阶段
**可能原因**：
- `bootcmd` 环境变量错误
- boot 分区的 `Image` 或 `ramdisk.img` 缺失
- 分区号不匹配（检查 `mmc 0:3` 是否对应 boot 分区）

### 4.3 启动到 Android 但无法进入 AT4K
**解决方案**：
```bash
# 通过串口执行
pm clear com.android.launcher3
pm clear com.overdevs.at4k
reboot
```

### 4.4 AT4K 布局显示不全
**解决方案**：
- 检查 Smali 修改是否正确应用
- 重新编译 APK 并更新系统镜像
- 确认 SHA256 哈希已更新到 firstboot 脚本

---

## 五、验证清单

- [ ] 分区表 bootloader 起始于扇区 20480
- [ ] env.cfg 的 bootcmd 正确配置
- [ ] AT4K 布局修改已应用（3个 Smali 文件）
- [ ] AT4K SHA256 哈希匹配 firstboot 脚本
- [ ] system.img 包含 AT4K 在 `/system/priv-app/AT4K/`
- [ ] 写卡脚本 bootloader 写入扇区 16
- [ ] SD 卡插入 TF1 卡槽
- [ ] 串口连接正常，可监控启动日志

---

**文档版本**：1.0  
**最后更新**：2026-09-12  
**验证状态**：✅ 已在真机上验证成功
