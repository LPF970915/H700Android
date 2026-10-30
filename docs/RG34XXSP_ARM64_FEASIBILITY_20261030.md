# RG34XXSP ARM64 小范围可行性验证

日期：2026-10-30。检查点 `baseline/rg34xxsp-arm64-feasibility-20261030`。这次没有构建/刷写新系统，没有替换现机驱动、改变 ABI 属性或重启。v6b 候选保持不变。

**结论：已实证当前内核可执行 AArch64 用户程序，源码中有双 ABI 图形路线的候选输入；尚未证明 ARM64 Android 应用、64 位 EGL 或双 ABI 整机能工作。** 值得继续做隔离运行库/图形探针，不应据此直接改写现有主线。

## 已完成的验证

| 项目 | 实际结果 |
| --- | --- |
| 内核基础 | 固定内核配置为 CONFIG_ARM64/CONFIG_64BIT/CONFIG_COMPAT；当前 shell 的 uname 为 armv8l，不能据此误判内核仅有 32 位能力 |
| 原生 ARM64 执行 | 新编译的 ELF64 AArch64、无 PT_INTERP/无 libc 程序实际在当前 USB 样机退出 0，输出 ARM64_STATIC_OK；mmap 一页、64 位存取、munmap 通过 |
| 现机 Android 运行环境 | abilist 只有 armeabi-v7a/armeabi，zygote32；所查 system/APEX linker64、64 位 libc 与 vendor 64 位 EGL 标准路径均不存在 |
| Mali 候选 | 已核验 arm/lib 的现用源输入、arm64/lib 的配对 ARM32 库以及 arm64/lib64 的 AArch64 库；三者均标 r20p0-01rel0；候选配对 32/64 库构建标识一致，与现用独立 ARM32 库标识不同，不可宣称可直接互换 |
| Gralloc 源码 | mali-bifrost/gralloc/src/Android.mk 包含 LOCAL_MULTILIB := both、分别的 lib/lib64 路径和 arm/arm64 编译标志，存在双位数构建设计；没有在本轮真正构建该 HAL |
| 平台配置 | AOSP 树含 core_64_bit.mk、init.zygote64_32.rc；当前产品仍是 TARGET_ARCH=arm，未修改主/副架构或现机 Zygote |
| 安全边界 | 仅在固定自有 /data/local/tmp 目录放置一个小探针；不打开 Mali/ION/disp，不做 GPU ioctl、画面切换或应用安装；执行前后 boot ID、services.jar/Navigation/Mali 哈希、挂载清单一致，根与 vendor 均只读 |

探针只覆盖这些 Linux syscall 与本进程内存，不是 Android ART、Bionic、JNI、Binder 或图形驱动测试，也不能代表任意 ARM64 程序均兼容。原始身份、设备状态和日志仅保留 `out/arm64-feasibility-20261030/`；公开 [脱敏结果/组件锁](baselines/rg34xxsp-arm64-feasibility-20261030/result-lock.json) 和 [源码锁](baselines/rg34xxsp-arm64-feasibility-20261030/source-lock.json)。

## 明确的剩余依赖

AArch64 Mali 的 DT_NEEDED 有九项：`libcutils.so`、`android.hardware.graphics.common@1.0.so`、`libnativewindow.so`、`liblog.so`、`libm.so`、`libc.so`、`libdl.so`、`libz.so`、`libc++.so`。还需追踪它们的传递依赖、版本化符号与 linker namespace/VNDK 约束。本轮没有把源码、SDK/NDK 链接桩或预编译目录里的同名文件当作已验证运行库。

因此不能只复制 libGLES_mali.so 或修改 abilist：现机缺少所查标准路径中的 64 位加载环境。下一步应在独立工作目录准备与 Android 10 相符的 linker64/Bionic 及必要依赖，先验证普通动态 ELF 的加载/符号解析，再验证 Mali dlopen、EGL 初始化、离屏 pbuffer 渲染和像素读回。Gralloc/mapper/ION/HWC 的缓冲区布局、跨位数传递及驱动握手必须另外验证；r20p0 标签相同不足以证明这些 ABI 相同。

本次不为了完成 EGL 测试而临时替换唯一现机图形栈。若需要设备级图形测试或完整双 ABI 产品，先形成隔离方案/回退输入，之后优先备用镜像和备用卡，保留当前 ARM32 工作系统。

## 构建与失败边界

唯一构建入口：`tools/build_h700_low_pressure.ps1 -Targets H700Arm64Feasibility -Execute`。继续合计单核、CPU 0–1、nice 19、RAM 6GiB、swap 512MiB、单任务、空闲 I/O。成功小探针构建约 1.5 秒，内存峰值约 1.7MiB、swap 0；没有全量 AOSP 构建。

首次构建碰到旧 clang 包装器依赖未安装的 python 命令，改为直接使用同一工具链的 clang.real，没有安装全局 Python 别名或修改原工具链。第二次修正旧汇编器不接受的长度立即数表达式，最终低负载编译和真实设备执行均通过；失败日志保留，不计入成功证明。此工具只生成本地探针和离线清单，不自动控制设备。

下一道准入门槛是**隔离的 64 位动态加载与 EGL/Gralloc 实测**；在此之前，64 位迁移总体风险仍为中高，不能对外宣称支持 ARM64 APK、性能提升或 1GB 可用。
