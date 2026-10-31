# RG34XXSP 双 ABI 原型 P1c 运行记录（2026-10-31）

本检查点承接 [P1b 切根修复](RG34XXSP_DUALABI_HANDOFF_P1B_20261031.md)，仅针对 H700 / RG34XXSP / 2GB 的独立 128GB 备用卡。原约 64GB 工作卡已取下保存，v6b 正式候选及全部既有 gzip 保持不变。P1c 是 P1b 卡上的受控文件修正，没有另行交付一份 P1c 整卡镜像。

## 从 Logo 到 Android 的阻塞

P1b 此次物理启动已经进入 Android，USB ADB 可读，实际主、次 Zygote 为 ELF64 和 ELF32。厂商 Logo 长时间保留的直接运行障碍是显示服务反复重启，不能再沿用先前“USB 未枚举、尚未切根”的判断。

进一步定位了三个原型集成遗漏：

1. 系统和 vendor 的 API 均为 29，但没有声明 `ro.vndk.version`。GSI 的 `init.legacy-gsi.rc` 因而导入 `init.vndk-27.rc`，在 early-init 设置 27。其严格加载配置找不到 H700 Android 10 所需的 mapper 2.1、composer 2.2、audio 4.0 等接口。旧 BSP 没有同名 27 配置、走了另一套回退路径，不能直接照搬这个隐含行为。
2. GSI 没有带入原 BSP 的 Java 堆参数。MT 初次启动出现 16MB growth limit 的 OOM；保留系统的 `heapgrowthlimit=128m`、`heapsize=256m` 恢复后可显示协议页面。这是原型配置缺失，不能作为 ARM64 应用不兼容的证据。
3. 旧 BSP 的 HWC 已实现软件 VSYNC，但原型缺少启用属性。源码 `h700_rgsp.mk` 明确设置该属性，`hwc_event_thread.cpp` 说明这块屏幕没有可用的 VSYNC uevent。遗漏时出现 `Faking VSYNC due to driver stall`，前台任务和截图画面可能不一致；不能据此接受画面切换或短按输入。

## 保存的修正与回退

先用可撤销 bind 将已存在的 API 29 linker 配置覆盖到当次选中的 27 路径，验证显示服务及 Android 首启。私有 bootstrap 配置前缀保持一致，原文件未被该试验覆盖。一次 bind 的附加只读 remount 命令失败，但 bind 本身已成功；随后通过 init 视角的 SHA、mountinfo 和运行状态核实，没有盲目重放。

随后以正常文件系统操作原子替换 `/system/etc/prop.default`，补入：

```properties
ro.vndk.version=29
dalvik.vm.heapgrowthlimit=128m
dalvik.vm.heapsize=256m
ro.h700.prototype.runtime=p1c-vndk29-heap-20261031
persist.vendor.hwc.software_vsync=true
```

最初四属性阶段与补齐 VSYNC 的阶段分别保存原文件、候选、完整 SHA、应用回执和带设备/卡身份守卫的回退脚本。每次短暂 remount 根文件系统为 rw，写入同目录临时文件、校验内容和属主/权限/标签后 rename，并恢复根文件系统 ro。没有直接写裸块，也没有写 Boot0、GPT、kernel、ramdisk 或 vendor。

工具默认只显示计划，不访问设备：

```powershell
py -3 -X utf8 .\tools\test_h700_dualabi_vndk29.py
py -3 -X utf8 .\tools\apply_h700_dualabi_runtime.py
```

新建同样的 P1b 实验卡时，先在精确 USB、CID、profile、版本、root 和命名空间守卫通过后执行第一条的 `--execute`，等待 `sys.boot_completed=1` 与一次性 APK 安装完成，再执行第二条的 `--execute`。文件修正后需独立重启检查版本、堆参数、VSYNC、根只读状态及无临时 bind。`--complete-vsync` 只允许补齐本次保留的精确四属性中间态；不是重复应用入口。已完成的本地尝试均拒绝重放，发生失败应先读回执。

回退脚本只恢复对应阶段的属性文件，不承诺已损坏系统仍有 USB 可用；原 64GB 工作卡继续作为物理回退。不要在正式卡上运行这些工具，也不要对已运行系统裸写离线分区差异。

## 应用测试范围

四个测试 APK 仍来自 P1 的已锁定 payload：ARM64-only ABI probe、强制 arm64-v8a 的 MT 2.26.10、强制 armeabi-v7a 的 RA32 1.22.2_GIT 与 PPSSPP 1.20.4。实际进程 ELF class 和已加载原生库均读取核对；安装包支持 ABI 或 `primaryCpuAbi` 属性不能单独作为运行证明。

RA 使用官方无内容 2048 核心，PPSSPP 使用官方 cube.elf。二者均由已有本地夹具另行推入测试卡，没有商业 ROM/BIOS，不写入现有镜像。首次存储权限单独授予测试应用。RA 测试另复制仓库已有的 `H700_ANBERNIC_keys.cfg`，将配置中的自动映射目录改为绝对路径 `/data/user/0/com.retroarch.ra32/autoconfig`，并设 `menu_swap_ok_cancel_buttons=false`。原配置与修改后配置均留本地；早期 `~/data/user/...` 目录未正确读到映射的失败证据保留。

MT 只验证 64 位原生库加载与协议页面绘制，没有据此认定文件操作、完整十字键导航或所有第三方 ARM64 APK 通过。四应用同时驻留、任务前台切换、实际画面更新和性能是不同门槛，结果以本检查点的脱敏 `result-lock.json` 为准。

## 最终受控结果

补齐五属性后再次重启，`sys.boot_completed=1`、VNDK29、堆参数和软件 VSYNC 均由卡内配置生效；旧临时 linker bind 消失，根文件系统为只读。HWC 进程的 timerfd 间隔为 16,904,379ns，证明软件 VSYNC 定时器已创建。

| 门槛 | 结果 |
| --- | --- |
| ART64 + ARM64-only JNI | 实际进程 ELF64，日志 `ART64_JNI=true pointer_bits=64` |
| Mali64 / EGL / GLES 窗口 | Mali-G31，绿色区域 255,600 像素；用户确认实体屏幕能看到绿色测试页 |
| MT64 | 实际 ELF64，加载 arm64 原生库，协议页可绘制；未继续协议后的工作流 |
| RA32 + 官方 2048 | 实际 ELF32，32 位核心已加载；通过受控 evdev 路径启动，方向下输入移动棋盘并新增方块 |
| PPSSPP32 + 官方 cube | 实际 ELF32 与原生库，Mali32 绘制；相隔 3 秒的中央 480×380 区域有 103,490 像素变化 |
| 四应用共存与往返 | 同次启动同时驻留；PPSSPP→MT→RA→ARM64 probe，前台和截图各自核对，核心及四应用 PID 不变 |
| 此轮应用崩溃 | 最终带 VSYNC 的重启后 crash buffer 为空；不延伸为长期稳定性结论 |

同次轻量内存样本：probe 22,943KiB、MT 85,370KiB、RA 60,261KiB、PPSSPP 140,880KiB PSS，四者 swap 样本均为 0。前后台状态不同，不能把这些相加当作整机需求或据此承诺 1GB 设备表现；没有做游戏性能或长时间负载测试。

测试中临时启用 USB 常亮，收尾已恢复原值 0 并请求回到 Home；蓝牙保持关闭以避开已记录的 HCI 崩溃，没有把禁用当作修复。用户的实体确认仅涵盖绿色测试页，未覆盖所有模拟器输入和开关机/合盖验收。

## 保留与验收边界

保护 `out/dualabi-runtime-p1c-20261031/` 及卡内 `/data/local/tmp/h700-p1c-*`，包括中间四属性阶段、VSYNC 阶段、失败日志、所有属性原件/回退、实际进程与映射、截图、RA 配置原件和测试夹具。P1/P1a/P1b 的 gzip、WSL stage、差异和原始启动证据继续保护。Git 只发布自有工具、文档与脱敏 SHA/结果，不上传 APK、镜像、原始日志、身份或截图。

以下仍不由本次原型证明：

- 从新封装镜像重新刷卡的干净首启、完全断电冷启动及首启中断恢复。
- 完整 BSP 源码的 64 位 framework/ART 重建；本原型使用锁定的官方 GSI 配套运行时。
- v6b 八应用、横屏、锁屏、合盖、Wi-Fi、音频、亮度、蓝牙的功能等价回归。曾见蓝牙服务因 HCI 不可用崩溃循环，测试中关闭了蓝牙，没有修复或验收蓝牙。
- 商业游戏、帧率基准、长时间负载、1GB 设备内存与散热表现。
- 用户实体按键、应用切换画面与供电/背光的完整验收。绿色测试页已获实体确认，其他远程 evdev 注入和截图只能支持其各自的受控检查。

本轮无源码编译或离线镜像封装；后续如需执行，仍必须走既定低压力入口，CPU0–1、合计单核、`-j1`、nice19、6GiB RAM、512MiB swap 不变。
