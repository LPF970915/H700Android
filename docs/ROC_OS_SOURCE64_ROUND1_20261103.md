# ROC OS ARM64 源码构建第一轮结果

2026-11-03 18:55（Asia/Shanghai），独立产品 `roc_os_source64-eng` 完成 `systemimage vendorimage ramdisk` 构建，退出状态为0。构建期间固定合计单核、CPU0–1、`-j1`、nice19、RAM6GiB、swap512MiB和idle IO，没有操作设备或存储卡。

## 已完成

- 完整依赖图及本轮三镜像构建通过；最终批次20716项全部完成。Ninja计数仅代表任务数量。
- 三产物的长度与SHA256再次核对通过；ramdisk gzip可解压为CPIO。
- 371项受保护原输入、57项独立产品文件和2项隔离ABI5主机库哈希复核通过。
- 实际检查应用进程、动态加载器、ART、JNI运行库、私有Gralloc共10项文件，分别为ARM64 ELF64/AArch64及ARM32 ELF32/ARM。构建属性主ABI为arm64-v8a，兼容armeabi-v7a/armeabi。
- 无活动构建，`roc-os`定时跟进已暂停。原失败、五次三小时超时批次、全部中间产物和审计材料保留。

首个整镜像批次因旧RenderScript主机Clang缺少ncurses/tinfo ABI5失败。后续仅使用保留工具链中的两个真实ABI5库建立隔离加载路径，未修改全局库或使用ABI6伪装链接。五次后续批次仅因设定的三小时上限结束，各次续编前均核对无活动构建、锁已释放和输入哈希匹配。

最终批次于17:30启动，运行1小时24分21.562秒，累计CPU时间1小时18分52.430秒，内存峰值约5.0GiB、swap峰值512MiB。此前最后采样19748项到完成新增968项。最终Ninja报告耗时1小时24分01秒；systemd耗时包含包装器审计。

## 本地产物

WSL目录：`/home/lpf/roc-os-source64-20261103/out/target/product/roc_os_source64/`。

| 文件 | 文件字节数 | 格式与逻辑容量 |
| --- | ---: | --- |
| system.img | 1,144,652,260 | Android sparse；逻辑8GiB |
| vendor.img | 65,843,420 | Android sparse；逻辑2GiB |
| ramdisk.img | 800,471 | gzip；解压CPIO为1,864,960字节 |

精确SHA、实际ELF检查及源输入守卫结果见[完成锁](baselines/roc-os-source64-round1-20261103/completion.json)。这些是分区/ramdisk构建产物，**不是可直接由Rufus写入的整卡镜像**。

本地回执位于 `D:\Works\H700Android\out\roc-os-source64-20261103\`：`images-result-v2.json`、`post-build-audit-v1.json`、`prepare-v8.json`及逐轮progress/timeout/preflight。最终日志为 `D:\Works\H700Android\out\logs\build\h700-low-pressure-20261103-173038.log`。镜像与原始日志不上传Git。

## 尚未完成的边界

本轮使用归档BSP QP1A.191105.004及受保护增量，没有完整`.repo`清单，不能视为完整锁定的上游检出，也不是当前GSI QJR1系统的同源重编。Mali等厂商二进制仍为预编译输入。

构建成功尚未证明新产物的文件系统离线验收、完整依赖闭包、实际启动和硬件运行正常；现行GSI/ARM32补丁的源码一致性也未完成验收。当前工作卡保持原状。纯净系统预装策略、TF1统一userdata/TF2外置卡布局、深度待机和发行安全仍是后续独立阶段，本轮不推进。

后续应先审计新产物与已验收系统的配置、导航/亮度/Hall等功能差异及启动依赖，再准备独立测试候选。不得将本轮结果直接标为正式发布版或自动刷入当前卡。
