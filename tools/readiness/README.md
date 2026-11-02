# RG34XXSP ARM64 离线硬件候选

这些工具为冻结的 Test2a 准备下一轮候选组件。**不调用 ADB、不打开块设备、不改写现卡，也不生成整卡 IMG。** 离线检查不能代替亮度、待机及实体输入验收。

当前入口生成独立r4阶段（`roc-os-readiness-r4-20261103`），包含r2的背光初始化标签修正、[Navigation13快捷设置滑条修复](../../docs/RG34XXSP_QS_BRIGHTNESS_20261102.md)和ROC OS名称。r1/r2/r3及初始r4执行域草稿全部保留。现卡仍为Test2a加四项vendor运行增量及data Nav13，只更新了保存的设备/蓝牙名称；完整r4及nice19/idle0未写入现卡。实体分项结果、纯净系统和统一userdata要求见[本轮验收](../../docs/RG34XXSP_PHYSICAL_ACCEPTANCE_20261102.md)；这两项布局/预装调整尚未进入r4。

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700ReadinessBuild -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700QsBrightness -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700ReadinessStage -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700ReadinessBrandingAudit -Execute
```

仍使用合计一核、CPU 0–1、`-j1`、nice 19、6GiB RAM、512MiB swap 和 idle IO。每次构建/阶段使用新目录；不要删除失败目录来重试。

## Light 候选

`android/h700-android10/device/roc/rgsp/H700Light/` 提供独立文件名的 ARM64 HIDL Light 2.0 服务，只声明 BACKLIGHT。仅接受 `rgsp` 加明确 `rg34xxsp` profile；使用标准 Android RGB 亮度换算，经 `/dev/disp` 的 `0x102`、四个 `unsigned long` 参数访问 screen 0。不操作电池 brightness 扩展属性、LED、振动、CPU/GPU 频率或唤醒锁。

`prepare.py` 只同步这一新增模块到保留的 native 树，并备份被替换的模块草稿；现有产品列表和厂商 Light 实现不变。主机测试用替代 IO 覆盖 256 档灰度、off、参数布局、设备不可用和 IO 错误，没有访问真实屏幕。

`audit.py` 审查 ELF64、Test2a 的 VNDK29/LLNDK 依赖与强导入符号、VINTF 冲突及既有执行类型。不会把缺失依赖静默替换成整套 BSP 系统库。符号闭包通过不等于 Android linker namespace、HwBinder 注册或 SELinux enforcing 真机通过。

## 离线阶段

`stage.py` 校验父分区 SHA 后复制到新的 WSL 目录，集成 Light 服务、必要接口库、RC、VINTF 和文件标签规则，以及首启 setup 的 nice19/idle0 RC。新增 image marker 与脚本守卫一并更新；冻结 Test2a 不回改。每个新文件回读 SHA/mode/属主/标签，两分区只读 fsck，原有锁定覆盖文件及关键 GSI 运行库再次核对。

`file_contexts` 是该服务独立路径的增量规则。离线阶段将其追加到候选 vendor contexts，并为候选文件设置既有 `hal_light_default_exec`。若以后做原生产品全量集成，应显式选择该模块、排除其他注册 `ILight/default` 的服务，并把此规则纳入产品的 SELinux contexts；本工具不启用整个产品的 enforcing，也不放宽原有策略。

`audit_power.py` 只读取与 Test2a 镜像锁匹配的 prefix，解析其中 boot/DTB。Hall 的 PE7 配置、powerkey wakeup 属性和本地 pinctrl IRQ 功能仅用于下一轮排查；不能据此宣称现机已注册可唤醒中断。它不申请 GPIO、不装模块、不改 DTB，也不解除 bringup 锁。

原始/失败/候选及私有连接检查保存在 `out/rg34xxsp-readiness-20261102/` 和 WSL `/home/lpf/h700-readiness-20261102/`。只将源码与脱敏结果锁入 Git。

## ROC OS 名称

`branding.py`在system默认属性/build.prop、product、vendor与ODM属性文件中统一型号，并设置测试版显示名；保留device/product内部代号、真实硬件/厂商、ABI、VNDK和指纹。USB产品描述使用ROC OS，串号、VID/PID和接口配置保持。`roc-os-branding`仅在本项目启动完成后补默认名称、迁移旧RGSP名称，保留用户自定义名称；当前开发版执行域沿用已有su，不能当作正式enforcing集成。

`audit_branding.py`对独立候选复核属性加载顺序、非品牌属性保持和RC哈希，并在隔离的主机命令替身下验证7种名称输入、重复执行和错误设备拒绝。检查不调用ADB；当前卡保存名称的改动有单独私有备份。型号/USB的实际显示及干净首启仍须新镜像验证，未宣称整机已经完成更名。
