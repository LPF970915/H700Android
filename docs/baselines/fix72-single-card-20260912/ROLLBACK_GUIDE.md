# H700 Android 10 回退到原Linux系统操作指南

## 概述

本文档说明如何从单卡Android系统回退到原始的Linux双卡工作环境。

## 前提条件

⚠️ **重要警告**: 回退操作会覆盖当前TF1卡上的所有Android数据。请确保：
- 已备份重要数据
- 持有原始Linux系统卡的完整备份
- 持有原始Android测试卡(TF2)的完整备份

## 回退场景

### 场景1: 保留了原Linux卡和Android测试卡

**这是最简单和推荐的回退方式。**

#### 步骤
1. 关闭H700设备电源
2. 从TF1卡槽取出Android单卡系统卡
3. 将原Linux系统卡插回TF1卡槽
4. 将原Android测试卡插回TF2卡槽
5. 上电启动

#### 验证
- 设备应自动进入Linux系统
- 如需进入Android，通过Linux启动菜单选择TF2的Android系统

---

### 场景2: 丢失了原卡但有完整镜像备份

如果原卡已损坏或丢失，但保留了完整的dd镜像备份：

#### 所需工具
- USB读卡器
- Git Bash (dd工具)
- 管理员权限PowerShell
- 与原卡相同容量的新TF卡

#### Linux系统卡恢复步骤

`powershell
# 1. 识别目标磁盘
Get-Disk | Where-Object BusType -eq USB

# 2. 确认磁盘编号 (假设为PhysicalDrive3)
 = 3

# 3. 使用dd恢复完整镜像
 = "C:\Program Files\Git\usr\bin\dd.exe"
 = "D:\Backups\original-tf1-linux.img"

& "C:\Program Files\Git\bin\bash.exe" -c " if='' of=//./PhysicalDrive bs=4M conv=fsync status=progress"
`

#### Android测试卡恢复步骤

`powershell
# 使用相同方法恢复TF2
 = "D:\Backups\original-tf2-android.img"

& "C:\Program Files\Git\bin\bash.exe" -c " if='' of=//./PhysicalDrive bs=4M conv=fsync status=progress"
`

---

### 场景3: 没有备份，需要重新安装原系统

如果没有任何备份，需要从官方固件重新安装：

⚠️ **此方法超出本文档范围**，请参考：
- H700官方固件刷写指南
- RGSP官方系统镜像下载地址
- 社区论坛的恢复教程

---

## 回退后验证清单

### Linux系统卡(TF1)验证
- [ ] 设备从TF1启动进入Linux
- [ ] Linux系统功能正常
- [ ] 可以识别TF2卡
- [ ] 启动菜单可以选择Android(TF2)

### Android测试卡(TF2)验证
- [ ] 通过Linux启动菜单可进入TF2的Android
- [ ] Android系统功能正常
- [ ] WiFi连接正常
- [ ] 音频播放正常
- [ ] 设置和应用数据完整

---

## 如何避免数据丢失

### 推荐备份策略

#### 1. 在首次尝试单卡系统前，完整备份原卡

**Linux系统卡备份 (TF1)**
`powershell
# 插入原Linux卡到读卡器
 = 3  # 根据实际情况修改
 = "D:\Backups\original-tf1-linux-20260912.img"

& "C:\Program Files\Git\bin\bash.exe" -c "dd if=//./PhysicalDrive of='' bs=4M conv=fsync status=progress"

# 计算校验和
Get-FileHash -Path  -Algorithm SHA256 | Format-List
`

**Android测试卡备份 (TF2)**
`powershell
# 插入原Android测试卡到读卡器
 = 3  # 根据实际情况修改
 = "D:\Backups\original-tf2-android-20260912.img"

& "C:\Program Files\Git\bin\bash.exe" -c "dd if=//./PhysicalDrive of='' bs=4M conv=fsync status=progress"

# 计算校验和
Get-FileHash -Path  -Algorithm SHA256 | Format-List
`

#### 2. 验证备份完整性

`powershell
# 回读验证：比较前1MB数据
 = "C:\Program Files\Git\usr\bin\dd.exe"
 = 3
 = "D:\Backups\original-tf1-linux-20260912.img"

# 从物理磁盘读取
& "C:\Program Files\Git\bin\bash.exe" -c " if=//./PhysicalDrive bs=1M count=1 | sha256sum"

# 从备份镜像读取
& "C:\Program Files\Git\bin\bash.exe" -c " if='' bs=1M count=1 | sha256sum"

# 两个hash应该相同
`

#### 3. 保存备份元数据

创建备份清单文件：
`
备份日期: 2026-09-12
TF1 Linux卡:
  - 文件: original-tf1-linux-20260912.img
  - 大小: 58GB
  - SHA256: [计算的hash值]
  - 序列号: [卡的序列号]

TF2 Android卡:
  - 文件: original-tf2-android-20260912.img
  - 大小: 64GB
  - SHA256: [计算的hash值]
  - 序列号: [卡的序列号]
`

---

## 常见问题

### Q: 回退后Linux无法启动怎么办？
A: 
1. 检查TF1卡是否完全插入
2. 检查卡槽金属触点是否干净
3. 尝试重新插拔卡
4. 通过串口查看U-Boot输出确定问题

### Q: 回退后Android(TF2)无法从Linux启动菜单进入？
A:
1. 确认TF2卡已插入
2. 检查Linux启动配置文件
3. 通过串口查看是否识别到TF2
4. 尝试直接从TF2启动（如果机器支持）

### Q: 备份镜像文件太大，如何压缩？
A:
`powershell
# 使用7-Zip压缩
& "C:\Program Files\7-Zip\7z.exe" a -t7z -mx=9 original-tf1-linux-20260912.img.7z original-tf1-linux-20260912.img

# 压缩后删除原始镜像（确保压缩成功后）
Remove-Item original-tf1-linux-20260912.img
`

### Q: 可以在不影响TF2的情况下只替换TF1吗？
A: 可以。单卡Android系统只使用TF1，不会修改TF2。如果保留了原TF2，只需替换TF1即可回退。

---

## 紧急恢复联系方式

如果按照本指南操作仍无法恢复，请：
1. 检查项目docs目录下的其他相关文档
2. 查看logs目录下的历史操作日志
3. 在社区论坛发帖求助，提供详细的错误信息和串口日志

---

## 维护记录

- 2026-09-12: 初始版本，配合Fix72-Single-Card-20260912 baseline创建

## 相关文档

- docs/ANDROID_SINGLE_CARD_SUCCESS_GUIDE.txt - 单卡系统制作指南
- docs/baselines/fix72-single-card-20260912/BASELINE.md - Baseline说明
- docs/H700_ANDROID10_RELEASE_READINESS_20260911.md - 发布就绪清单
