# ARM64 隔离运行库、Mali 与 EGL 离屏验证

日期：2026-10-30；检查点 `baseline/rg34xxsp-arm64-isolated-egl-20261030`。前置 [静态 ARM64 验证](RG34XXSP_ARM64_FEASIBILITY_20261030.md)。用户明确授权本轮补齐隔离运行环境并测试加载与离屏渲染；没有把早期静态通过当作驱动替换或刷卡授权。

**最终结果通过：真正的 ARM64 共享库程序运行、libm dlopen 对照、Mali dlopen、EGL 1.4 初始化、16×16 GLES2 pbuffer 红色清屏及像素读回。** 原系统、驱动和 v6b 镜像没有改写；这不是 ARM64 Android APK、双 ABI 整机或窗口显示通过。

## 输入与准备

本地 H616 Android10 v1.2 官方包经原 SHA 校验后，在副本解析 IMAGEWTY / sparse super / logical partitions。确认它也是纯 ARM32，没有 linker64/lib64，不能作为本轮的 64 位运行库来源；这些提取物保留，不回填 H700。

最终采用 [Google 官方 AOSP Android10 ARM64 GSI](https://dl.google.com/developers/android/qt/images/gsi/aosp_arm64-exp-QJR1.191112.001-6004257.zip)，597,613,423 字节，SHA-256 `0bbbf53e1164b032eace999cbd6bf0877ab636819a2e929f63079ccfe71095c7`，镜像 build.prop 的 API=29 已确认。仅提取开源运行库和加载器，不安装或启动该 GSI。Mali 来自已保留 BSP 的 `mali-g31/arm64/lib64/libGLES_mali.so`，固定 SHA 与上一轮一致；保持原厂二进制，不修改签名或内容。

准备了 bootstrap 版 linker64/Bionic 和递归依赖。来源清单中有 31 个依赖项，包括供链接用的 ld-android.so 桩；最终 chroot 不部署该桩，由运行中的 linker 提供对应接口，system/lib64 有 Mali 加 30 项依赖。全部实体库为 ELF64，逐项 SHA 固定。目录形式的依赖齐全不等于 ABI 通过，本轮实际加载与初始化证据才是通过依据。

## 已通过项目

| 项目 | 结果 |
| --- | --- |
| 真正动态可执行文件 | ELF64 AArch64；DT_NEEDED 明确包含 libc.so 和 libdl.so，打印 pointer_bits=64，退出 0 |
| 动态加载对照 | 同一隔离环境加载 libm.so 成功 |
| Mali 加载 | 使用标准 dlopen(RTLD_NOW) 成功；不依赖直接链接变体来冒称 dlopen 通过 |
| EGL | eglGetDisplay、eglInitialize 成功，EGL 1.4 / ARM |
| 上下文与离屏面 | GLES2 context + 16×16 pbuffer；没有创建 window surface、调用交换前台窗口或更改屏幕模式 |
| GPU 与读回 | GL_RENDERER=Mali-G31；glClear 红色，glFinish 后 glReadPixels(8,8) 得 RGBA=255/0/0/255；GL_NO_ERROR，完整 EGL surface/context/terminate 清理后退出 0 |
| 基线保护 | 对比首轮前到全部结束：boot ID、SurfaceFlinger/system_server PID、services.jar/Navigation/现用 32 位 Mali SHA、父进程挂载表均一致；根与 vendor 没有改成可写；未遗留测试 linker/probe/strace/crash_dump 进程 |

公开 [结果与运行库锁](baselines/rg34xxsp-arm64-isolated-egl-20261030/result-lock.json)、[自有源码锁](baselines/rg34xxsp-arm64-isolated-egl-20261030/source-lock.json)。原始输出含指针、PID 和设备身份，仅留本地，不上传。

## 隔离方法及保护

设备端所有文件位于自有 `/data/local/tmp/h700-arm64-isolated-20261030/`。外层保持系统原有 32 位工具环境，不把 64 位 LD_LIBRARY_PATH 提前传给 32 位 timeout/env 等辅助命令。由 unshare 创建新的 mount namespace，核对不同于调用者原 namespace，然后设置 MS_PRIVATE|MS_REC；进入最小 chroot，提供标准 /system、/apex 路径与只读 proc/sys/属性目录。仅绑定白名单设备节点，包括 Mali、ION、随机源和 Binder 等；不绑定块设备或整张卡。节点仍对应原内核，因此这是文件系统/挂载隔离，不是独立虚拟 GPU；不能承诺隔离内核驱动缺陷。

平台自带 mount 工具在此系统上对递归私有和 bind-remount 标志的处理不符合本次所需，字符节点还曾误走 loop 设置并失败。保留这些失败记录，最终不用它执行挂载，改用约束过的 syscall-only ARM64 helper。helper 拒绝原 namespace、限定所有目标在上述 rootfs 下、拒绝 ..、只允许固定源白名单；四项负向用例在设备通过。只有全套隔离建立成功才运行 probe；测试有超时与强杀后备。测试结束子 namespace 消失，父挂载表复核一致。

代码只供本检查点固定路径实验。不得直接对原 namespace 调用 helper，也不应把这个最小 rootfs 当作完整 Android 系统或生产安全容器。准备工具不自动控制设备，部署/执行要沿用当前 USB 身份及 profile 守卫，不使用旧设备默认值。

## 排错记录与不能计为通过的结果

1. 最初尝试 APEX 运行库和私有目录，出现空 dlerror、超时或启动崩溃；其中不能直接归因为 Mali 不兼容。
2. 后续发现预编译 SDK 平台目录缺共享版 libc/libdl，`-lc -ldl` 静默选择静态归档，产生带解释器却实际链接了静态 libc/libdl 桩的错误探针。早期 C 输出不是动态链路通过，空 dlopen 和直接链接崩溃不能计作驱动失败。
3. 最终改为显式链接从 GSI 提取的真实共享 libc.so/libdl.so，并加入 DT_NEEDED 断言，保留静态误链接探针和失败运行库副本。使用 bootstrap 配套运行库后，按普通动态程序→libm 对照→Mali→EGL 顺序重新执行，全部退出 0。没有单独重新验证修正后的 APEX 变体，不能断言 APEX 版自身不兼容。
4. 最后整理可重复准备脚本并再构建，产物探针 SHA 与实测成功的 probe 一致；未为这次代码整理额外重复 GPU 测试。

## 重复准备与存储

`tools/build_h700_low_pressure.ps1 -Targets H700Arm64Isolated -Execute`。需要保留的本地官方 GSI ZIP；脚本先核验精确 SHA，再解压到独立 WSL 工作目录、提取 ELF64 递归依赖、编译 probe/mount helper、生成 prepared-rootfs。目标 rootfs 已存在会拒绝覆盖。没有修改原生 AOSP 产品架构或构建整套 framework。CPU 0–1、合计单核、nice19、单任务、6GiB RAM、512MiB swap、空闲 I/O 的限制全程保留。最后准备构建约 20.5 秒，CPU 4.4 秒、内存峰值约 1.7MiB、swap0；它不是前面提取/下载/排错全过程计时。

`out/arm64-isolated-20261030/` 保存 GSI、库/探针/rootfs、来源锁、失败原型、私有运行证据；WSL `/home/lpf/h700-arm64-isolated-20261030/` 保存供体及 GSI 提取阶段，均保留，不因 Git 已上传而删除。GSI、Mali 或运行库二进制不上传 Git，亦不加入现有 v6b。

## 结论与下一道门槛

现在已排除“当前内核不能执行 ARM64”以及“候选 64 位 Mali 在当前内核上连最小 EGL 离屏都跑不起来”这两项疑虑，具备继续独立双 ABI 原型的实际依据。尚未验证 shader 编译、纹理/复杂绘制、跨进程缓冲区传递、64 位 Gralloc/mapper 与现有 HWC 的窗口显示、SurfaceFlinger/system_server/ART64、ARM32/64 APK 共存、游戏/长时内存和休眠恢复。这个 16×16 clear/readback 结果不意味着完整驱动或系统兼容、性能提升或 1GB 机型可用。

下一步应建立独立双 ABI 产品和可回退镜像，先关闭 64 位窗口/Gralloc/HWC 链路，再验证一款 ARM64 应用与现有 ARM32 RA/PPSSPP 共存；v6b 继续作为当前工作和回退基线。
