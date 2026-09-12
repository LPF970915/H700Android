# H700 Android单卡系统 v4 焦点导航修复版 - 完成报告

## 构建信息
- **版本**: v4_FocusFix
- **构建日期**: 2026-09-12
- **基础版本**: v3b (验证可启动)
- **镜像大小**: 57.96 GB (62239277056 bytes)
- **输出路径**: `out/H700_Android_SingleCard_v4_FocusFix.img`

## 问题背景

v3b版本虽然成功启动进入Android系统，但存在严重的十字键焦点导航问题：
1. Settings应用无法使用十字键导航（焦点不可见）
2. DocumentsUI文件管理器无法使用十字键导航
3. AT4K启动器顶部菜单无法十字键向下滚动
4. 系统UI模式为普通模式(0x11)而非TV模式(0x13)

**根本原因**: 系统未配置为TV UI模式，导致应用不启用焦点导航支持。

## 修复方案

### 尝试的运行时修复（失败）
通过ADB运行时设置 `ui_mode_type=4` 可以临时修复，但重启后失效。

### 最终方案：系统级overlay配置

在 `device/roc/rgsp/overlay/` 创建配置文件，永久修复：

#### 1. frameworks/base/core/res/res/values/config.xml
```xml
<bool name="config_defaultUiModeTypeIsTelevision">true</bool>
<bool name="config_hasPermanentDpad">true</bool>
<bool name="config_defaultInTouchMode">false</bool>
```

#### 2. packages/apps/Settings/res/values/bools.xml
```xml
<bool name="config_show_focusable_items">true</bool>
```

#### 3. packages/apps/DocumentsUI/res/values/config.xml
```xml
<bool name="show_focus_indicator">true</bool>
```

## 编译过程

### 环境
- **编译环境**: WSL Ubuntu + Android 10源码
- **编译方式**: 低压力构建 (1核心, 6GB内存限制)
- **模块**: 完整system + vendor重编译

### 步骤
1. 清理受影响模块的编译缓存
   - framework-res
   - Settings
   - DocumentsUI
2. 触发完整系统构建 (1920+ tasks)
3. 提取编译产物：
   - system.img → system.raw.img (8GB)
   - vendor.img → vendor.raw.img (2GB)
   - 新建data.raw.img (16GB)
4. 与v3b的bootloader和分区表组合
5. 生成最终可烧录镜像

### 镜像结构
| 偏移(MB) | 大小(GB) | 组件 | 来源 |
|---------|---------|------|------|
| 0 | 0.21 | Bootloader + 前4分区 | v3b |
| 212 | 8.0 | System (焦点导航修复) | 新编译 |
| 8404 | 2.0 | Vendor | 新编译 |
| 10452 | 16.0 | Data (用户数据) | 新建空分区 |
| 26836 | 0.009 | ROMS元数据 | v3b |
| 59356 | - | GPT备份表 | v3b |

## 验证计划

### 启动验证
1. 使用Rufus烧录到64GB TF卡
2. 插入RGSP H700 TF1卡槽
3. 开机进入系统

### 焦点导航验证
- [ ] Settings应用显示焦点框，十字键可导航
- [ ] DocumentsUI显示焦点框，十字键可导航
- [ ] AT4K菜单十字键可向下滚动
- [ ] 串口/ADB验证：`dumpsys uimode` 显示 `mCurUiMode=0x13`

## 技术优势

### vs v3b版本
- ✅ 十字键焦点导航**永久生效**（无需每次启动后手动设置）
- ✅ 系统级修复，所有应用自动继承TV模式行为
- ✅ 可作为后续开发的稳定基线

### vs 运行时修复
- ✅ 重启后配置保持
- ✅ 出厂默认即为正确状态
- ✅ 符合Android系统配置最佳实践

## 文件清单

### 新增文件
- `out/H700_Android_SingleCard_v4_FocusFix.img` - 可烧录镜像
- `out/rgsp-focus-fix-20260912-172444/manifest.json` - 镜像构建清单
- `out/rgsp-focus-fix-20260912-172444/system.raw.img` - 修复后system分区
- `out/rgsp-focus-fix-20260912-172444/vendor.raw.img` - 修复后vendor分区
- `out/rgsp-focus-fix-20260912-172444/data.raw.img` - 干净用户数据分区
- `docs/H700_v4_FocusFix_烧录指南.md` - 用户烧录指南

### 关键配置文件
- `android/h700-android10/device/roc/rgsp/overlay/frameworks/base/core/res/res/values/config.xml`
- `android/h700-android10/device/roc/rgsp/overlay/packages/apps/Settings/res/values/bools.xml`
- `android/h700-android10/device/roc/rgsp/overlay/packages/apps/DocumentsUI/res/values/config.xml`

## 后续任务

1. **实机验证** - 烧录v4到TF卡并验证所有焦点导航功能
2. **AT4K布局优化** - 修改AT4K启动器适配小屏幕（当前尚未完成）
3. **其他硬件适配** - 按键映射、音频、GPU等（按原计划继续）

## 版本历史
- **v1-v2**: 早期探索版本（已废弃）
- **v3b**: 首个成功启动版本（2台RGSP验证），但焦点导航不可用
- **v4_FocusFix**: 焦点导航系统级修复版（当前版本）

## 成功标志

✅ 镜像生成成功  
⏳ 等待实机验证  
⏳ 等待AT4K布局适配  

---
**构建时间**: 2026-09-12 17:01 - 17:50 (49分钟)  
**编译耗时**: ~44分钟 (1920 tasks)  
**镜像生成**: ~5分钟
