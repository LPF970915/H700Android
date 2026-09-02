# 交互实现参考源

这些项目仅用于阅读交互和焦点导航实现，不能直接当作 H700 系统镜像刷入。

| 项目 | 定位 | H700 用法 | 注意 |
|---|---|---|---|
| Android TV Navigation / TvSettings | AOSP/官方规范与系统设置 | 作为行为基准 | 与 H700 HAL 无关 |
| AndroidTVLauncher | 原生 Leanback 风格启动器 | 参考 Activity、焦点和应用列表 | 项目较旧，需在目标 Android 版本编译验证 |
| FLauncher | Android TV 风格启动器 | 参考布局和遥控器交互 | Flutter，1 GB 设备不作为首选常驻实现 |
| LTvLauncher | FLauncher 增强分支 | 参考 D-pad 设置与焦点处理 | 仍需评估 Flutter 内存占用 |
| R36S `reference/r36s-device` | RK3326/Lineage device tree | 参考产品配置和启动器集成边界 | 不能复制 kernel、DTB、vendor |
| R36S `reference/r36s-multiboot` | 多系统选择与按键启动 | 参考 TF 分区和启动菜单 | 不能照搬 GPIO/分区命令 |

## 选型决定

第一版 `RGSPNoTouchLauncher` 采用原生 Android View/RecyclerView，先实现四向焦点和生命周期，再考虑是否吸收 Leanback 组件。这样启动器不会把 Flutter 引擎作为 1 GB 设备的基础依赖。

## 许可和版本记录

在复制任何第三方代码前，必须在 `reference/no-touch/` 记录仓库 URL、commit、许可证和实际复制文件。当前项目只保存规范、模板和链接，没有复制第三方源代码。
