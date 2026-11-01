# ARM64 发布收尾：离线亮度候选与首启集成

2026-11-02。父镜像为不可变的 `baseline/rg34xxsp-arm64-defaults-test2a-20261101`，对象仅 RG34XXSP / H700 / 2GB。

用户暂时不在设备旁，要求先推进无需人工确认的高优先级工作。本轮开始和结束时电脑均没有 ADB transport；此前 WLAN 地址的 5555 端口也未连通。现卡身份守卫拒绝后续操作，没有对其他设备改用旧守卫，没有注入输入、重启、改写系统或刷卡。

**本轮完成的是亮度候选组件及其离线集成，不是亮度真机修复验收。** 最新已交付整卡镜像仍是 Test2a；没有生成新的整卡 IMG/gzip。

## 完成的工程工作

### 独立 ARM64 Light 服务

Test2a 离线 system/vendor 中没有可用的 Light 服务、实现或 VINTF 声明，这与此前亮度设置变化但驱动背光不变的记录一致；缺失链路尚不能被称为唯一根因。

新增自有模块 `android.hardware.light@2.0-service.h700`，使用 Android HIDL Light 2.0，仅声明 BACKLIGHT：

- 必须同时满足 `ro.product.device=rgsp` 与明确的 `rg34xxsp` profile。
- 标准 RGB 亮度换算得到 0…255，经 `/dev/disp` 的 `0x102`、screen 0 和四个 `unsigned long` 参数访问背光；包含真正的 0 请求，不设置人为最低亮度。
- 对照保留的厂商 Light 源码和 disp2 驱动接口，使用 `O_RDONLY` 打开设备，沿用父 vendor policy 已有的 read/open/ioctl 规则；不新增写权限或放宽策略。
- 只公布 BACKLIGHT，低持续显示模式返回不支持，设备或 ioctl 错误向框架返回失败。
- 不接管 LED、振动、电池扩展属性或唤醒锁。

新增 RC 使用独立服务名和路径，避免覆盖 AOSP 原有模块；新增路径沿用 `hal_light_default_exec`，候选 vendor contexts 增加对应精确规则。父策略中已找到该类型、init domain transition 和显示设备访问规则，但**没有完成 SELinux enforcing 真机验收**。

### 首启任务低优先级纳入离线候选

此前首启卡顿定位产生的 `priority 19` 与 `ioprio idle 0` 已实际写入本轮候选分区的 setup RC。不是只修改原始源码后假定会被继承。

新离线阶段标记为 `dualabi-readiness-r1-20261102`，release 为 `arm64-readiness-r1-20261102`；setup 的 image guard 与 preinstall 的独立 release guard 同步更新。中文、AT4K 默认 HOME、七款 ARM64 应用、主题/模拟器配置和关键 GSI 运行时保持。没有增加 AYASpace 试验应用，也没有加入 ROM、账号或存档。

当前卡未应用这些文件，新优先级的首次安装实际效果仍待干净首启测试。

### 合盖与待机的只读排查

从与 Test2a 镜像锁完全匹配的 prefix 中读取 boot/DTB，而非直接用历史 `input/boot-live.img` 代替当前引导输入。确认 powerkey 节点的 `hall_key` 指向主 PIO 的 **PE7 / gpio_in**，并有 powerkey 的 rising/falling wakeup 属性。本地 sun50iw9p1 pinctrl 源码也列有 PE7 的 IRQ 功能。

这些事实不能证明现机 Hall 已注册 IRQ、设置 IRQ wake 或能在内核挂起后唤醒。下一轮需在守卫通过后核对 GPIO 持有者、实际 IRQ、wakeup_sources 与电源生命周期。未改 DTB/内核、未申请 GPIO、未解除 `rgsp_android_bringup`，也没有无人值守强制挂起。

## 验证结果

| 检查 | 结果及边界 |
| --- | --- |
| 背光主机测试 | 256 档灰度、off、RGB/alpha 换算、四参数 ABI、设备不可用与 IO 错误返回通过；使用替代 IO，不访问真实屏幕 |
| Android 编译 | 新服务实际 ELF64 / AArch64，低压力模块构建通过；不是整套 BSP64 重建 |
| 动态依赖 | 服务及 20 个依赖对象通过；按父 `ld.config.29.txt` 分别跟踪 vendor、VNDK29、system 的依赖和每个对象的强导入符号；不需要新增或替换运行库 |
| VINTF | 父镜像无 Light 冲突；候选合并 XML 经 Android `assemble_vintf` 解析通过；不等于整机 VINTF/运行注册通过 |
| 新增量 | system 5 项、vendor 4 项，逐项 SHA、mode、root 属主与 SELinux 标签回读通过 |
| 原有覆盖层 | 候选中共 3,747 项 system、5 项 vendor 锁定文件 SHA 回读通过；其中包含本轮增量 |
| 关键运行时 | 原锁定 10 项 GSI 关键运行库 SHA 保持 |
| 文件系统 | 新 system/vendor 的 `e2fsck -f -n` 均退出 0 |
| 冻结父输入 | 本轮结束再次核对 system/vendor SHA，均仍匹配 Test2a；原镜像/标签不改 |
| 真机/首启 | 未安装、未注册服务、未刷卡；真实亮度、显示开关、待机和新优先级首启均未验收 |

两轮早期候选被拦下并保留：第一次因与 AOSP 服务安装路径重名，随后改为独立路径；第二次虽编译成功，审计拒绝了 `O_RDWR` 原型，随后改为沿用原有只读访问权限。静态依赖审计的早期短列表还曾误分类系统内部加载器库和 LLNDK 库；最终改用父链接器配置和命名空间依赖图，没有通过拷入 BSP 库绕过检查。

## 复现与产物

见 [工具说明](../tools/readiness/README.md) 与 [脱敏结果锁](baselines/rg34xxsp-arm64-offline-readiness-20261102/result-lock.json)。

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700ReadinessBuild -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700ReadinessStage -Execute
```

构建和阶段处理始终使用合计一核、CPU 0–1、`-j1`、nice19、6GiB RAM、512MiB swap、idle IO，未调整电压或提高限制。未取得主机电压测量，不把资源限制当作电气测量。

本轮通过的阶段是 WSL `/home/lpf/h700-readiness-20261102/stage-v1/`，元数据在 `out/rg34xxsp-readiness-20261102/candidate-stage-v1.json`；新 system/vendor 的 SHA 见结果锁。该阶段不是可直接刷入的整卡镜像，不自动替代 Test2a 封装入口。

保护 `out/rg34xxsp-readiness-20261102/`、WSL `/home/lpf/h700-readiness-20261102/` 的全部失败/候选/回读/源备份和日志。Git 只保存自有源码与脱敏锁，不保存 raw、服务二进制、DTB、设备身份或原始日志。用户既有 `docs/SPACE_REVIEW_20261028.md` 修改未纳入本轮提交。

后续优先在设备连接后验证 HIDL 注册、受支持类型、设置到驱动的多档亮度读回及回退，再安排实体亮度/背光确认；待机唤醒源、合盖循环、充电温控和正式发行门槛继续开放。
