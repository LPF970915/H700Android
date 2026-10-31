# RG34XXSP 独立双 ABI 原型 P1（2026-10-31）

本原型只用于 RG34XXSP / H700 / 2GB 的启动、ARM64 APK 与现有 ARM32 模拟器共存验证。生产候选仍是 v6b；不把本原型称为完成迁移的 64 位正式系统。窗口前置结果见 [双 ABI 窗口记录](RG34XXSP_DUALABI_PROTOTYPE_20261031.md)。

## 输入和隔离范围

使用已锁定 SHA 的 Google 官方 Android 10 ARM64/ARM32 GSI `QJR1.191112.001-6004257`，保持其 framework、ART、32/64 Bionic 配套。结合 v6b 同源的 H700 启动前段、厂商分区、输入和 GPU 内核模块，加入独立源码产品构建的 ARM64 init/adbd、Gralloc/mapper 与已通过窗口测试的 Mali64。没有将旧 services.jar DEX 补丁套到 GSI framework 上。

init/adbd 使用自有 `/system/bin/h700-bootstrap/` 命名空间与 `/system/lib64/bootstrap/` 依赖池，普通 GSI 应用仍使用原配 APEX 运行时。ARM64-only ABI 检测 APK 与 MT 管理器用于 64 位测试；现有 RetroArch ra32、PPSSPP 强制使用 armeabi-v7a。另带既有 AT4K、Navigation v8 与基础键位。未承诺锁屏、强制横屏、合盖、媒体、网络或八款正式预装的完整功能等价。

原型标识：`ro.h700.prototype=rg34xxsp-dualabi-gsi10-p1-20261031`，Zygote 为 `zygote64_32`。首次完成系统启动后，专用一次性服务校验四个测试 APK 的 SHA，按指定 ABI 安装，选择 AT4K Home 并启用导航服务。此安装流程尚需首启验收，失败日志留在原型卡的 `/data/local/h700-prototype/setup.log`。不复制现机 userdata、账号、存档或 ROM/BIOS。

## 卡与存储

用户明确允许格式化卡槽2中的128GB备用卡。卡身份、容量、原分区和挂载证据仅存本地。原约64GB工作卡的 root、vendor、data 仍是当前运行来源。写卡工具必须逐次核对精确 USB、机型 profile、root、备用卡 CID/容量、块设备主次号、无挂载/无 holder，并拒绝当前工作卡。

保留 H700 的八项紧凑 GPT；普通128项 GPT 会覆盖8KiB处的 Boot0，禁止替换。原型另设磁盘及分区 GUID，并同步 vendor fstab，避免双卡标识碰撞。映像保持既有32,434,554,368字节几何；写入备用卡时仅将备份 GPT 放到物理卡尾，不扩大分区或文件系统。原型 GSI vold 不枚举启动卡的硬件分区，测试使用内部仿真存储。

不在旧卡增加第二 Zygote、不修改旧系统 ABI。保持原 bringup wake lock；本检查点不测深度休眠。卡写入和完整读回是独立门槛，成功也不代表已启动。

## 构建与验证入口

所有构建、离线封装及启动输入复核均通过既定低压力入口，保持 CPU0–1、合计单核、`-j1`、nice19、6GiB RAM、512MiB swap：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiBoot -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiImage -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiAudit -Execute
py -3 .\tools\write_h700_dualabi_spare.py
```

最后一条默认仅离线计划。只有用户授权的备用卡、候选镜像完整解压校验与离线启动审计均匹配，`--execute` 才允许写卡。出现已开始的写入记录时拒绝重放；`--execute --verify-only` 仅重新核对、读回，不恢复或重写。每次失败阶段、元数据备份和回执保留本地。

封装核对父输入的完整 SHA；覆盖文件逐项读回 SHA、权限、root属主及 SELinux 标签；system/vendor 运行 e2fsck；镜像 gzip 完整解压核对32GB长度和全量 SHA。紧凑 GPT 另经原 C 检查器验证，覆盖单主表损坏可恢复、主备均损坏拒绝及128GB卡尾重定位。启动审计核对双 Zygote/两个 app_process、GSI framework/ART 一致、ARM64-only JNI、私有 init/adbd loader、Mali32 保留和 Mali64 存在。

本地输出在 `out/dualabi-prototype-image-20261031/`；WSL 当前阶段在 `/home/lpf/h700-dualabi-image-20261031/`，失败阶段为同前缀的 `-before-*` 目录。保留阶段、gzip、原始证据、私有身份、卡写入前后回执，不作为普通缓存。Git 只发布工具、文档和脱敏锁；不上传映像、APK或私有日志。

## 验收边界

| 项目 | 当前状态 |
| --- | --- |
| 原机隔离 ARM64 小窗与 Mali/GLES | 已通过 swap、绿色合成截图、图层清理及旧系统不变检查；肉眼反馈待确认 |
| 独立 init/adbd 与两套 ABI 产品 | 已构建；首启未进入可读取日志的阶段，运行未验收 |
| 原型镜像、离线启动审计 | 已通过；gzip 959,614,367字节，完整解压32,434,554,368字节；全部启动输入复核通过 |
| 备用卡写入及完整读回 | 已通过32,434,554,368字节、物理卡尾GPT及另行清缓存后前256MiB复核 |
| 备用卡冷启动、双 Zygote/ART64 | 已物理换卡首启；停厂商静态Logo，USB未枚举，未通过 |
| ARM64 sentinel/MT 与 RA32/PPSSPP32 共存 | 待测，不由窗口或安装包内容推断 |
| 完整 BSP 源码的 64 位 framework 重建 | 未验证，P1 的 GSI 运行时不代替这一门槛 |

写卡校验完成后，需要完全关机，取下原工作卡妥善保存，将备用卡从槽2移至系统槽1，再开机保持 USB 连接。单纯重启、保留两张卡原位，不会切换到原型。启动后先读精确原型标识和卡 CID，再验双 Zygote、ART64 JNI、Mali 渲染；之后运行 ARM32 RA 的无内容2048核心和 PPSSPP 官方 cube.elf，并做应用往返、进程位数、崩溃和内存记录。测试夹具在启动后另行推入，不放进镜像，也不据此认定商业游戏性能或1GB机型验收。

## 首启阻塞与后续修正

用户已执行换卡，反馈停在最初厂商静态Logo；电脑未枚举ADB。没有读到运行日志，不能断言唯一故障原因。原工作卡未覆盖；换回原卡以修复TF2原型卡。

源码核对发现入口设计问题：`bionic/linker/linker_main.cpp` 的 `get_executable_info()` 在第一阶段尚无proc时，对 `/init` 只执行一次 readlink。P1的链为 `/init -> /system/bin/init -> /system/bin/h700-bootstrap/init`，因此选择链接命名空间时只得到 `/system/bin/init`，没有命中自有h700-bootstrap前缀。其间接依赖可能落入GSI普通库/APEX路径，而APEX尚未挂载。下一轮需令 `/init` 直接指向私有init，并补上这种无proc阶段的检查；此处是已确认的入口缺陷与待实测的故障定位，不把它当作已修复首启。

全量读回开始时完成块缓存清理，清理后采样的读取计数约8.4MB；为覆盖该时间窗口，又单独清缓存后复核前256MiB。完整范围、物理卡尾和前段SHA均匹配，原工作系统的boot、核心PID、挂载表及关键组件哈希也与本轮初始记录一致。最终公开写卡工具已将缓存清理放在读回之前；本轮补充协调回执和原始日志另保留本地。

封装最终单元耗时7分48秒、CPU6分18秒、内存峰值约5GiB、swap为0；后续补充属性加载顺序的启动审计约35秒。卡写入的原始SHA为 `2e9244197b4745a91c885efe3442fe71a1752772b99fff5ceaf9eb4d2147d193`，gzip SHA为 `0870dea1c1e97ea61e3014c52ef3c8df48d06e080253ad19af42d9da7c97da21`。卡尾GPT重定位后前2KiB及整段预期SHA与未重定位的压缩镜像不同，须用专门读回回执比对，不能把该差异误判为整镜像损坏。
