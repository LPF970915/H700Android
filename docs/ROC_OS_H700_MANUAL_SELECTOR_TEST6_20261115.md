# H700 共用机型选择镜像 Test6：导航恢复修复

日期：2026-11-15。离线封装、独立验收及 Windows 哈希核对通过。2026-11-16 的 RG35XX H 首次实测未见机型菜单，当前故障取证中；离线通过不代表实体启动通过。

用户要求将导航恢复修复合入共用机型选择镜像，提供 RG35XX H 刷机测试包。
父卡为 Test5；本轮保留其整个启动前缀，只合入系统 Java 运行闭包。
首次启动直接进入机型选择菜单，默认 RG35XX H / 640×480，不需要按音量减。

这是同一套共用镜像的下一测试版。菜单列出 12 个机型，当前只有 RG34XX SP、RG SP、
RG35XX H 接入两套电气显示配置；其余机型尚未接入，不能将它描述为全系兼容已完成。
Test5 尚未通过实物显示测试，Test6 同样需要 RG35XX H 重新验证。

## 本轮内容

- 原 Test5 启动菜单、bootloader、内核、DTB、vendor、userdata 和 GPT 保持逐字节身份。
- 保留 Test5 的机型感知 Lid3、USB 配置、0.0.2 版本和时间默认值。
- 合入 Navigation18 / 2.4-resume-guard 与 ViewRoot joystick、physical DPAD 两条保护。
- 短按立即响应，400ms 开始长按重复，160ms 间隔；单次连续动作绝对上限 10 秒。
  熄屏、失焦、停止、detach 清理队列和代次；超限后需要实际松开或对应轴回中才能重新触发。
- 使用真实生产框架、arm/arm64 boot ART 和全部依赖预编译文件。
  原编译器输出中的 Lid2 不覆盖父卡 Lid3，Lid3 继续不携带不匹配的预编译文件。

导航源码与回归验证见 [导航恢复修复记录](ROC_OS_NAVIGATION_RESUME_FIX_20261115.md)。
原 Test5 启动修正见 [Test5 记录](ROC_OS_H700_MANUAL_SELECTOR_TEST5_20261114.md)。

## 构建与验证

生产构建在私有 mount namespace 内，以原绝对路径只读覆盖冻结源码；实际编译用户为 lpf。
保留原 Native/BSP/Source64 文件与签名密钥，复用 user 缓存。
任务执行单核总额、CPU0–1、nice19、6GiB 内存、512MiB swap、idle IO、全局互斥锁和 3 小时上限。
旧安装树和内外两层系统镜像先归档，然后执行真实 `m -j1 systemimage`。
该 OUT 在构建后属于新修复源码版本，旧 prepare38/images21 仅能作为历史缓存来源。

真实生产构建通过，编译约 82 分钟；最终安装树和实际 system.img 分别冻结并核对。
生产 ART 审计通过 55 个启动文件、136 个依赖 OAT；合并后再次审计通过 55 个启动文件、
135 个有效依赖 OAT，差一项为特意保留父卡 Lid3、排除旧 Lid2 的预编译。
最终 271 个依赖预编译文件、4 个 profile 的完整集合、SHA 和大小逐项匹配生产构建。
22 条共享 VDEX 软链保留，两个无对应 APK 的历史 ROCProvisioning 缓存明确移除。

整卡封装通过，完整 gzip 读回通过；独立工具重新从 gzip 提取并核对所有分区范围、
整个 Test5 启动前缀、3,657 个实际文件系统节点的权限/属主/SELinux、只读 fsck、
Navigation18 的 Android 10 生产签名及实际 DEX 类定义、framework 内两种导航保护类。
Windows 再次读取完整 gzip，大小和 SHA 与 Linux 封包结果一致。
封包耗时 452.023 秒，独立验收耗时 209.636 秒；无设备或实体卡访问。

合并中发现并保留了两项工程检查记录：第一次分类正则漏掉带连字符的启动文件名；
随后发现 Camera2 重建仅因 HAS_BUILD_NUMBER 构建类型位导致版本码变化。
代码和资源完全相同，因此保留 Test5 原 Camera2 APK，再用实际 DEX 校验和重新验证其新缓存。
封包前置检查对合法零字节占位文件的误拒绝也已修正；使用最终 v4 合并记录和 v8 工具封包。
旧失败目录、收据和日志全部保留。未重新执行完整源码重编，未推送 Git 或上传镜像。

## 文件与证据

镜像：[ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test6_Navigation_20261115.img.gz](../out/roc-os-h700-manual-selector-test6-20261115/ROC_OS_ARM64_ver0.0.2_H700_ManualModel_Test6_Navigation_20261115.img.gz)

| 项目 | 值 |
| --- | --- |
| 压缩大小 | 591,790,317 字节 |
| 压缩 SHA-256 | `44d82f7779e68ff0c8dad12e2b6d9211c37fe6271ca40af34103fbfe4bff5798` |
| 展开大小 | 32,434,554,368 字节 |
| 展开 SHA-256 | `74eba8376145f09f79fe8b45b5f720400fbe539eb8670ceda7f8af35c71c044d` |
| system SHA-256 | `6ab9b9423f2cf21f365d9e028d37f7311a678f220645cadbd7f1ba491a9ca59a` |
| 同图 Navigation18 APK SHA-256 | `8b3227dc5db5d3fa79a6d99d26647f4c2746f4ecd864609f0d23a29ff61c55d8` |
| framework.jar SHA-256 | `60ab589c7f638dd03954dc379d614ee5ca3242bf0708aec7cd88c578c0f4c8e0` |

最终收据：[acceptance.json](../out/roc-os-h700-manual-selector-test6-20261115/acceptance.json)。
详细证据位于 `out/nav-test6-production-20261115/`、`out/nav-test6-integration-20261115-v4/`
与 `out/roc-os-h700-manual-selector-test6-20261115/`。显示候选指针指向本包，正式 0.0.2 和已接受基线不升级。

## 实物测试范围

手动将本次 `.img.gz` 刷入至少 64GB 测试 TF1，TF2 留空。
装回 RG35XX H，连接 USB 并正常冷启动；先看机型菜单，再确认 RG35XX H 并启动，首次等待约 5 分钟。
若出现黑屏，保留开机及 USB 现场；若能进入 Android，再观察熄屏、亮屏、解锁后的导航。
2026-11-16 用户反馈仅按电源、TF2 留空，从未出现机型菜单，随后显示无文字的躺倒绿色安卓机器人。
主机连续三次检测到在线 `USB Developer`，VID/PID `1F3A:1010`、接口 `FF/42/03`；
这些描述符及本镜像中的 `fastbootlogo.bmp` 与原 U-Boot Fastboot 实现相符。
Windows 缺对应驱动（ProblemCode 28），ADB / Fastboot 工具均没有可访问设备；
没有安装驱动或发送重启、刷写、退出 Fastboot 命令。

当前状态为 U-Boot Fastboot，不能仅凭图标判为 Android Recovery；是否曾短暂进入 Linux 后重启仍待实体卡证据。
原镜像离线验收收据保持原样，本次实体失败另作补充。
用户已关机并将本次 TF1 接入读卡器，接下来按新动态磁盘身份守卫只读核对实际引导内容与启动日志。
35XX H 菜单、Android 显示、导航恢复及全机型兼容均未取得实体通过。

实体卡只读核对现已完成：整个 U-Boot TOC、环境分区及 boot 分区与交付 Test6 完全一致；
两个实际系统文件 Navigation18 与 framework.jar 的完整内容 SHA 也一致。
前缀总计只有 90 字节变化，位于主 GPT 备份位置/CRC 与两份 boot0 的 DRAM 参数及校验字段；
两份 boot0 相同、校验正确，实际原厂代码包含正常启动时的参数回写路径。
userdata 仍为 seed 20GiB，superblock mount_count/mount_time 均为零，无 needs_recovery 和文件系统错误，
当前磁盘视图未见 `/rgsp-persist`。用户回忆机器人约开机几秒后出现。
这些证据不支持已完成 Android handoff，也不能恢复在 U-Boot 分流时已清除的 RTC 标志。

所有只读句柄已关闭，未挂载、修复或写卡。
Stage1 外层进程未取得 child ExitCode，原 FAILED 收据保留；实际完整采集与关闭状态另有核对收据，未伪造退出码。
Stage2 修正进程句柄保留后，实际内外层退出零、文件身份和读取守卫均通过。
本次补充：[runtime-supplement-20261116.json](baselines/roc-os-h700-manual-selector-test6-20261115/runtime-supplement-20261116.json)。
下一步为从电源启动前开始录制的 UART 串口日志；录制工具仅接收数据，不发送控制字符。

2026-11-16 首轮 UART 采集已覆盖用户关机后重新开机，115200 / 8N1 / 无流控，
仅得到 137 字节零散二进制值，其中 99 字节为 NUL，没有可读的启动文本。
原始字节和完成收据保留，接收句柄已正常关闭；不能将本次采集视为有效启动日志。
实际 boot0 与 U-Boot 的串口参数有独立核对，boot0 指定 UART0 的 PH0/PH1 mux2，
本地芯片 pinctrl 源码将其分别标为 TX/RX；这不能替代 RG35XX H 实体焊盘映射。
用户表示可能接反，已先开启第二轮接收再重新开机，目前尚未取得有效文本。
仍需确认焊盘、共地和信号电平，不能从乱码或零字节直接定位 Fastboot 原因。

### 2026-11-16 22:05 UART 有效启动记录

用户重新接线后，COM4 以 115200 / 8N1 仅接收采集成功，300 秒录制正常结束并关闭句柄。
原始记录为 11,689 字节，SHA-256 为
`684282f7936fb6a4366e79dd7cd601dd387347984f0c1ac6c63f2bf76ec3737c`。
部分区间仍有乱码，但首次启动的下列链路清晰，足以修正此前“是否进入 Linux 未知”的结论：

1. DRAM 在初始校准错误后恢复，DST 和 simple test 成功，识别为 1GiB LPDDR4。
2. U-Boot 已建立 640×480 framebuffer，拒绝显示原 720×480 bootlogo。
3. U-Boot 报 `fdt_initrd: FDT_ERR_NOSPACE`，仍继续 `Starting kernel ...`。
4. Linux 运行约 3.306 秒时，Android init 找不到 `/vendor/etc/selinux/plat_sepolicy_vers.txt`。
5. 约 3.317 秒 SELinux 策略加载失败，调用栈包含 `SetupSelinux`、`InitAborter`、`InitFatalReboot`。
6. 约 4.284 秒明确记录 `Restarting system with command 'bootloader'`，随后再次出现 BOOT0。

因此本次已经证明 Linux → init 致命错误 → 请求 bootloader 重启，不能继续把它描述为
从未进入内核或单凭按键误触直接进入 Fastboot。ramdisk 未正确传递是当前首要假设：
它与 `fdt_initrd` 空间不足、未出现自定义 ramdisk 初始化及机型菜单、vendor 未挂载相吻合；
仍需对实际 U-Boot/FDT 路径进一步验证，不能仅凭一条错误宣布完整根因或修复通过。
没有修改 SELinux 强制策略、启动文件、设备或卡；日志还明确证明了引导程序自身的两份 SPL 参数回写。

追加收据：[uart-runtime-followup-20261116.json](baselines/roc-os-h700-manual-selector-test6-20261115/uart-runtime-followup-20261116.json)。
原离线验收和较早的 runtime supplement 保持原样。
