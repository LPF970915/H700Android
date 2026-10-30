# RG34XXSP v6a 无 ROM 镜像封装

日期：2026-10-30。目标为用户现有 RG34XXSP / H700 / 2GB / 双摇杆，建议 64GB 或更大系统卡。不是旧 RGSP 或所有 H700 机型通用镜像。

## 输入与构建方式

新工具 `tools/package_h700_v6a.py` 接受保留的、完整解压 SHA 为 `3fd34fef4d5a2275f14023dba5dc488330ab0669a50889e8b748e30c9f3e68cd` 的 v5i gzip，逐范围校验后拆分 system/vendor 与硬件前缀、出厂数据/ROMS/GPT。原 v5i、native35 阶段和冻结覆盖层不改写；没有重放旧 prepare 脚本或原 DEX 补丁。

这是对已验证分区的明确增量封装，**没有重编整棵 AOSP**。当前 AT4K、Navigation v8、H700Lid、H700Rotation、已安装验证的 services.jar 横屏增量和摇杆模块按原检查点 SHA 锁定；日常 init、USB ConfigFS、网络检测、键位、默认壁纸与新预装初始化脚本一起进入镜像。全源码 framework rebuild 仍未验收。

唯一执行入口：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700ReleaseImage -Execute
```

保持 CPU 0–1 亲和性、合计一个 CPU、nice 19、单任务、RAM 6GiB、swap 512MiB、空闲 I/O 和单次 3 小时上限；不放宽限制。主机没有可用电压读数，未更改电压、超频或 BIOS；不能把负载限制称为已测量电压安全。

本地依赖包括 v5i gzip、各检查点锁定的 APK/JAR/模块、七款 APK、用户提供的主题/配置/媒体和已提取目录。Git 只保存版本锁、配置及工具，clone 后没有这些受保护本地输入不能直接封装。工作目录为 WSL `/home/lpf/h700-release-v6a-20261030`，输出 `out/h700-v6a-preinstall-20261030/`。已有输出或不完整分区会被拒绝，必须先核对，不能反复覆盖。失败/中断材料保留待查。

## 软件与干净配置

选择 [原六款与天马 G](FIRST_PREINSTALL_BATCH_20261030.md)，APK 保持原签名，放在只读系统资源目录；标记为 v6a 的镜像首次启动时通过 PackageManager 安装到 data。应用可正常更新或卸载，完成标记保留后续用户选择。首次初始化完成前请先等待，不要自行打开这些应用。

- QQ 音乐 TV、Animeko TV、PPSSPP、RA ra32、NOVA、KOReader、官方 ARM32 Pegasus 加天马 G 主题。
- NOVA 预设手机/平板模式；KOReader 配 H700 用户补丁；PPSSPP 仅采用静态按键映射与干净 OpenGL 1 倍配置，无历史/游戏列表。
- RA 的官方 APK 资源和三个 ARM32 GBA 核心从可信本地输入生成首次初始化种子，UID 由新安装结果取得，不写死现机 UID。包含 H700 映射、独立整数 3 倍 LCD3x 配置、原配置覆盖包的 cheats/opts，无测试存档。
- 天马 G 主题、封面、logo、视频置于只读系统目录；可写配置在其标准 external files 目录。活动元数据显式写入媒体实际大小写路径，修正源元数据失效的旧媒体别名。游戏启动指向 ra32，不依赖 ARM64 包。
- 出厂数据分区确认仅 `lost+found`，ROMS 文件系统为空；两者及 GPT 原字节保留。不复制现机 userdata、账号、书架、壁纸偏好、ROM 或测试存档；系统壁纸用仓库中的原始 AT4K 默认图。
- MT 仍是补充候选，此轮未自动纳入；谷歌组件和其他试验 App 不纳入。

不含任何游戏 ROM、BIOS 或存档。用户可把自己持有的游戏 ZIP（保留合集子目录和文件名）复制到 ROMS 分区 `PegasusGBA/Roms/GBA`、`GBA hack`、`GBA vib`。活动元数据在前端配置目录，覆盖原 ROM 文件夹内的 metadata 不会改变本镜像的 ARM32 启动参数。未复制的游戏默认隐藏；复制完成后重启 Pegasus 重扫。

初次启动应完成七款安装、干净配置种子和 AT4K 默认 HOME 恢复后，`sys.h700.preinstall` 为 `complete`。源文件校验、安装、复制或 ROMS 挂载失败会中止，未完成时下次启动可重试；不会格式化分区，不安装可移动存储里的 APK，也不执行其脚本。

## 验证与限制

封装结果及精确大小/哈希在任务完成后写入本节与公开脱敏锁。五项主机边界测试、真实 Android PAX 中文长路径及不覆盖复制测试已通过。镜像封装会执行 ext4 检查、全部改动文件读回与 SELinux 标签检查、未修改的 native35 组件核对、硬件前缀/出厂尾部范围核对、整 IMG SHA 和 gzip 全解压 SHA 核验。

没有整卡刷写；新镜像的真实首刷、首次安装流程、断电冷启、实体合盖、耳机、亮度、蓝牙和深度挂起另行验收。旧软件/现机通过的测试不能替代新镜像首刷验收。现有 bringup wake lock 保持不变；轮询合盖不能唤醒已深度挂起的内核。GBA 性能是 2GB 样机上的短时结果，不外推为 1GB 或全部游戏通过。
