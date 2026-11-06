# ROC OS User RC3：首次启动导航初始化修复

2026-11-07 真机复验失败：RC3 的独立属性权限遗漏 Light/Thermal HAL 读取，导致两服务反复退出、framework 等待 ILight，停在 Android 动画。详见 `ROC_OS_USER_RC4_20261107.md`。下述离线记录和旧镜像保留，不能作为 RC3 真机启动通过的依据。

RC2 已经由用户刷入并进入 Android/AT4K。真实 user、Enforcing 和认证 shell ADB 下，Mali 模块及 `/dev/mali0` 正常，SurfaceFlinger/system_server 稳定，`sys.boot_completed=1`，崩溃缓冲区为空。电池与四项温度读数已恢复；CPU 温度和自动初始化仍有遗漏。本轮保持已经成功的 RC2 boot、kernel、DTB 与 ADB 路径。

## 导航回归与当前机器修复

用户报告长按 Home/菜单下拉、Select 鼠标和菜单十字键全部失效。检查发现导航 APK 已安装，`enabled_accessibility_services=null`、`accessibility_enabled=0`。签名初始化应用 `ROCReleaseProvisioning` 与 H700Lid 都被 SELinux 拒读 `persist.vendor.rgsp.input_profile`：该属性被归入通用 `vendor_default_prop`。初始化程序的机型保护因此返回不支持，没有进入设置键盘、HOME、导航、网络默认值等流程。

修改前的 secure settings 和服务状态保存在本地 `out/roc-os-user-rc2-firstboot-20261106/accessibility-before.private.txt`。仅通过 shell 支持的 Settings API 启用已有 `com.roc.rgsp.navtrial/.NavigationService`，服务成功绑定；用户明确反馈“三项均恢复”。没有换导航 APK、放宽 SELinux、提权或改 system/vendor 分区。

随后正常重启，新的 boot ID、`sys.boot_completed=1`、secure 配置和导航自动绑定均已读取确认；崩溃缓冲区仍为空。用户物理确认属于重启前恢复后的那次测试；重启后的保留性由系统状态确认，没有虚记第二次物理验收。当前机器是修改了导航设置、启用 Wi-Fi 的 RC2，并非 RC3。

## 固化进 RC3 的最小修复

- 在候选产品的 platform-private `property_contexts` 中，为这一条机型属性设置独立 `roc_input_profile_prop`；仅授予 platform_app 和 shell 读取。未开放通用 vendor 属性区，未授予应用写属性权限，未绕过机型保护。
- Thermal 的目录标签已经修好，但 BSP 对 CPU `temp` 的更具体条目仍使用 `sysfs_thermal`，导致 CPU 为 NaN。仅补 thermal server 对该文件类型的读权限，不授予温控写权限。
- 合盖程序还需要穿过已精确标记的 battery 目录、跟随 class 符号链接才能读取 Hall 端点。仅补目录 search 与链接 read/getattr；端点保持只读，不允许读取其他 battery 文件或写 sysfs。

修改前全量守卫和备份通过，证据在 `out/roc-os-user-rc3-repair-20261106-v1/`；旧 user 三镜像复制并核对哈希，Native 备份不解引用私有密钥目录链接。审查的七文件差异包含上述策略、RC3 标记和精确文件集合守卫；旧 BSP、Source64、ABI5、生产密钥、旧镜像及 SPACE_REVIEW 均保留。

## 编译、封装与后续验收

构建 `h700-low-pressure-20261106-232812.service` / prepare-v31 / images-result-v14 通过，562/562；耗时 335.213 秒、CPU 244.611 秒、峰值内存 5 GiB/swap 73.3 MiB，无 FAILED/OOM。实际 property_contexts、合并策略、neverallow、Treble 26/27/28 和 VINTF 检查完成。

新审计直接检查实际分区中的属性映射与 compiled policy：精确属性读取与 init 设置为正例；应用写、未授权应用读取、通用 vendor 属性读取为负例；CPU 温度只读与 Hall 父目录/链接/端点访问逐项检查。继续执行 RC2 的图形、标签、签名、依赖及文件系统审计。整卡仅由普通文件组装，保留认证 ADB 公钥种子、user/Enforcing、root 拒绝和 TCP ADB 关闭。

最终封装和独立核验均通过，记录在 `docs/baselines/roc-os-user-rc3-20261106/`。新包 `out/roc-os-user-card-rc3-20261106/ROC_OS_ARM64_User_RC3_20261106.img.gz` 为 591,013,035 字节，SHA-256 `a6c81241980d8805a4b44012cd5517b1e6e1478931a4c0881a3d98f9233696ad`。解压后 32,434,554,368 字节，SHA-256 `2b36ec2bf09e2101245406d0055cb82e141a8359951a01073702b4fd11e65ce3`。

封装 `roc-user-rc3-card-20261106-233455.service` 耗时 565.970 秒、CPU 420.977 秒，峰值 5 GiB、swap 0；独立核验 `234432` 耗时 13.326 秒、CPU 8.894 秒，均退出 0。116 个 APK 签名、10 个配对实际 ELF、36 roots/548 ELF/631 states/41 early 依赖闭合、两组各 24 条实际策略查询、普通文件镜像 fsck、全部范围和完整 gzip 解压哈希通过；Windows SHA 与 WSL 一致。实际整卡 boot SHA 为 `04e11bbdb1d14f8672439d948b6f5cbe95e3294634304cd510df10e3064ced49`，与已经开机成功的 RC2 boot 字节一致，命令行为 Enforcing。

没有活动构建或封装作业，心跳仍 PAUSED，未自动刷卡、上传镜像或清理旧产物。RC3 的真正干净首次启动自动初始化、CPU 实际读数及 Hall 功能仍需用户刷入新整卡复验。RTC hctosys 标签告警、完整电源/深睡、恢复与许可等后续验收仍单独开放，不因本轮导航恢复而宣称正式发行通过。
