# H700 Android单卡系统 v4 焦点导航修复版 - 烧录指南

## 版本信息
- **版本号**: v4_FocusFix
- **构建日期**: 2026-09-12
- **镜像文件**: `out/H700_Android_SingleCard_v4_FocusFix.img` (57.96 GB)
- **目标设备**: RGSP H700 (ANBERNIC)

## 修复内容

本版本通过重新编译Android系统并集成overlay配置，**永久修复**了以下问题：

### ✅ 核心修复
1. **Settings应用十字键焦点导航** - 系统设置中可以使用十字键上下左右导航
2. **DocumentsUI文件管理器焦点导航** - 文件应用中可以使用十字键导航
3. **TV UI模式默认启用** - 系统启动时自动进入TV模式 (uiMode=0x13)
4. **永久D-pad支持** - 硬件十字键被系统识别为主要输入设备
5. **AT4K启动器预装** - 小屏幕优化版AT4K作为默认桌面

### 🔧 技术实现
- 通过 `device/roc/rgsp/overlay/` 配置文件固化修复
- 完整重编译 `framework-res`, `Settings`, `DocumentsUI` 模块
- 修复在system.img中永久生效，无需每次启动后手动设置

## 硬件要求
- **TF卡**: 64GB 及以上容量（推荐Class 10或以上速度）
- **读卡器**: USB 3.0或以上（提高烧录速度）
- **电脑**: Windows 10/11（已测试）

## 烧录步骤

### 方法1: 使用Rufus烧录（推荐）

1. **下载Rufus**
   - 官网: https://rufus.ie/
   - 下载便携版或安装版均可

2. **准备TF卡**
   - 插入64GB TF卡到读卡器
   - 连接读卡器到电脑USB接口（推荐USB 3.0）

3. **启动Rufus烧录**
   - 运行Rufus（可能需要管理员权限）
   - **设备**: 选择你的TF卡（⚠️ 确认选对设备，烧录会清空所有数据！）
   - **引导类型选择**: 点击"选择"按钮，选择 `H700_Android_SingleCard_v4_FocusFix.img`
   - **分区类型**: GPT
   - **文件系统**: 不修改（Rufus会自动识别）
   - 点击"开始"按钮

4. **等待烧录完成**
   - 烧录时间约15-30分钟（取决于读卡器速度）
   - 进度条显示100%后，点击"关闭"

5. **安全弹出TF卡**
   - 右键点击任务栏USB图标，选择"弹出TF卡"
   - 拔出读卡器

### 方法2: 使用dd命令烧录（Linux/WSL）

```bash
# 查找TF卡设备名（例如 /dev/sdb）
lsblk

# 烧录镜像（⚠️ 确认of=后面的设备名正确！）
sudo dd if=out/H700_Android_SingleCard_v4_FocusFix.img of=/dev/sdX bs=4M status=progress

# 同步缓存
sudo sync
```

## 上机测试

1. **插卡启动**
   - 关闭RGSP设备电源
   - 将烧录好的TF卡插入TF1卡槽（主卡槽）
   - 按电源键开机

2. **预期行为**
   - 设备正常启动进入Android系统
   - 默认桌面为AT4K启动器
   - 进入Settings应用，十字键可以上下导航菜单项，焦点框清晰可见
   - 进入Files文件管理器，十字键可以导航文件列表

3. **验证TV模式**
   - 通过串口或ADB执行: `dumpsys uimode`
   - 应显示: `mCurUiMode=0x13` (TV模式)

## 故障排查
- **按电源键无反应**: 检查TF卡是否插入TF1卡槽，尝试重新拔插
- **无法启动系统**: 检查烧录是否完整，尝试重新烧录
- **焦点导航仍不可用**: 通过串口检查uiMode，如为0x11则系统镜像未正确烧录
