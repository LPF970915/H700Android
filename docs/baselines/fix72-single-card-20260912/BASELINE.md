# H700 Android 10 单卡系统 - Baseline 清单
# 版本: Fix72-Single-Card-20260912
# 制作时间: 2026-09-12 09:37
# 验证状态: ✓ 已上机成功启动进入Android系统

## 概述

本baseline是H700 Android 10单卡系统的首个成功上机版本，实现了完全独立于TF2的单卡启动。

## 核心组件来源

| 组件 | 来源目录 | 说明 | SHA256 |
|------|---------|------|--------|
| prefix-212m.bin | rgsp-single-card-v3b-20260912 | 包含GPT+boot分区 | BCCA9BA02E60CB34843D88FBE69BE77CE69D309E0D1096421E12829A4B5743F5 |
| system.raw.img | rgsp-fix72-wifi-profile | Fix72 WiFi配置 | 199C03BF5B46A81E26AAB133D8310AE576690C99C926B1835D5F3E8AC3115FAA |
| vendor.raw.img | rgsp-audio-candidate-20260910 | 音频驱动修复 | 9D0C8D4A95B69131A70DB6AEBDFA1D9B3967AFA9DC7DC8E95932872ECB372CC2 |
| data.raw.img | rgsp-single-card-20260911 | 单卡数据分区 | 54A3BC84FB6701B0CAEE5409A1B5EE222E81D9D759F9C8687E06BBF40827C1A1 |
| roms-metadata.bin | rgsp-single-card-v3b-20260912 | ROMS分区元数据 | 836E674B8038FA813EBB4392CFCB391ED2AA230B086A0686C6F5FA3A9A1D7649 |
| gpt-tail.bin | rgsp-single-card-v3b-20260912 | GPT备份表 | 1CC7B395088B92E2EAAD8ADB0D9E1B31E80BB9970CDB7B0C01265D1CD92D95F6 |

## 分区布局

`
分区1: special       (offset 0x2000,      size 8 MB)
分区2: boot-resource (offset 0x802000,    size 24 MB)
分区3: env           (offset 0x2002000,   size 8 MB)
分区4: boot          (offset 0x2802000,   size 160 MB)
分区5: system        (offset 0xC802000,   size 8 GB)
分区6: vendor        (offset 0x20C802000, size 2 GB)
分区7: data          (offset 0x28C802000, size 16 GB)
分区8: ROMS          (offset 0x68C802000, size 9 MB metadata)
`

## 关键特性

✓ **单卡独立启动** - 不依赖TF2安卓测试卡或TF1 Linux卡
✓ **Init脚本修改** - 使用/dev/block/by-name路径挂载分区
✓ **WiFi配置** - 继承Fix72的WiFi自动连接修复
✓ **音频驱动** - 包含持久化的音频权限和codec配置
✓ **GPT分区表** - 完整的主表和备份表

## 验证记录

### 上机测试 (2026-09-12)
- **机器**: H700开发板 (RGSP)
- **插槽**: TF1
- **启动时间**: 约2分钟
- **串口**: COM4, 115200波特率
- **结果**: ✓ 成功进入Android系统
- **UI**: ✓ 桌面选择器正常弹出

### 已验证功能
- ✓ U-Boot识别GPT分区
- ✓ Kernel加载成功
- ✓ Init挂载system/vendor/data
- ✓ Android启动完成
- ✓ 系统UI响应正常

## 已知问题

⚠ **桌面选择** - 用户误选RG HOME为always默认桌面，需通过ADB重置
⚠ **AT4K未集成** - AT4K-launcher.apk未安装到system.img
⚠ **小屏布局** - AT4K需要调整为720x480布局（待后续版本）

## 未完成验证项

根据《H700_ANDROID10_RELEASE_READINESS_20260911.md》，以下项目需要在后续版本完成：

### 阶段1剩余
- [ ] 自动化测试监控p1/data分区异常

### 阶段3剩余
- [ ] 冷启动测试（10次以上）
- [ ] 60分钟持续运行
- [ ] 设置持久化验证
- [ ] WiFi断线重连
- [ ] 休眠唤醒
- [ ] 关机后文件系统检查

### 阶段4剩余
- [ ] A键解锁完整性验证
- [ ] 十字键完整流程测试
- [ ] 纯按键APK安装流程
- [ ] 电源管理验收

## 复现此Baseline

### 准备工作
1. 准备58GB以上TF卡和USB读卡器
2. 以管理员权限运行PowerShell
3. 确认Git Bash已安装

### 源文件位置
`
D:\Works\H700Android\out\rgsp-single-card-v3b-20260912\prefix-212m.bin
D:\Works\H700Android\out\rgsp-fix72-wifi-profile\system.raw.img
D:\Works\H700Android\out\rgsp-audio-candidate-20260910\vendor.raw.img
D:\Works\H700Android\out\rgsp-single-card-20260911\data.raw.img
D:\Works\H700Android\out\rgsp-single-card-v3b-20260912\roms-metadata.bin
D:\Works\H700Android\out\rgsp-single-card-v3b-20260912\gpt-tail.bin
`

### 验证源文件
`powershell
# 使用SHA256SUMS.txt验证所有文件
Get-Content SHA256SUMS.txt | Where-Object {  -match '^[A-F0-9]{64}' } | ForEach-Object {
    ,  =  -split '\s+'
     = (Get-FileHash  -Algorithm SHA256).Hash
    if ( -eq ) { Write-Host "✓ " -ForegroundColor Green }
    else { Write-Host "✗ " -ForegroundColor Red }
}
`

### 执行写卡
`powershell
.\tools\write_rgsp_single_card_v3b.ps1 -TargetDisk 3 -Verify
`

详细写卡步骤参见：ANDROID_SINGLE_CARD_SUCCESS_GUIDE.txt

## 回退操作

如需回退到原Linux双卡系统，参见：ROLLBACK_TO_LINUX_GUIDE.txt（待创建）

## 后续版本规划

**Fix72-Single-Card-20260913** (计划)
- 集成AT4K-launcher到system.img
- 调整AT4K为720x480小屏布局
- 完成冷启动10次验证
- 完成60分钟稳定性测试

## 参考文档

- docs/ANDROID_SINGLE_CARD_SUCCESS_GUIDE.txt - 详细制作经验
- docs/H700_ANDROID10_RELEASE_READINESS_20260911.md - 发布就绪清单
- docs/H700_ANDROID10_SINGLE_CARD_REVIEW_20260912.md - 单卡方案审查
- 	ools/write_rgsp_single_card_v3b.ps1 - 自动化写卡脚本

## 维护者

此baseline由H700 Android 10开发团队维护。
如有问题请参考docs目录下的相关文档。
