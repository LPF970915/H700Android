# ROC OS ARM64 User RC2 启动修复与复验

本轮目标：依据 BootDiag1 真机日志修复已确认的启动和硬件服务问题，重新编译、核验并封装带认证 USB ADB 的整卡测试镜像。离线编译、封装通过不等于真机或正式发行验收通过。

## 真机证据

电脑端重新插拔同一 USB 数据线后，BootDiag1 已建立公钥认证 ADB。设备为 `roc_os_release_candidate` / `rgsp`，shell UID 2000、SELinux Enforcing、user 构建。先前“APEX 阻止 ADB 启动”的推测没有成立证据；没有应用 ELF、链接器或 bootstrap 修改。

原始日志、崩溃栈、属性、进程、模块、HAL 与 22 组 AVC 分类保存在本地 `out/roc-os-user-bootdiag1-20261106-v2/live-20261106/`，不随公开文档上传。关键结论：

| 问题 | 证据与影响 | RC2 修复 |
| --- | --- | --- |
| Mali 驱动加载被拒绝 | init 对 `/system/lib/modules/mali_kbase.ko` 的 `module_load` 被 `system_lib_file` 标签拒绝；模块和 `/dev/mali0` 均不存在。EGL 初始化失败，SurfaceFlinger 在处理空 EGL 字符串时崩溃，继而每约 5 秒重启 zygote。 | 同一原始模块 SHA 不变，候选产品另装入 `/vendor/modules/`，由候选 graphics RC 加载。实际既有 policy 允许 init 加载 `vendor_file`，没有扩大模块加载权限。 |
| userdata 根标签无效 | Native `checkfc` 明确拒绝 `system_data_root_file`：该类型未定义；真机启动早期 `/data` 显示 unlabeled，引发 logd/init 拒绝。 | 新 userdata 使用实际 Native 类型 `system_data_file`；保持 UID/GID 1000、模式 0771，并增加 early-init 根目录 restorecon。旧 GSI 类型作为负例保留。 |
| Thermal HAL 无法枚举传感器 | `hal_thermal_default` 反复被拒读 generic sysfs 的 thermal 目录。 | 仅为 class/virtual thermal 子树建立 `sysfs_roc_thermal`，通过公开 `hal_thermal_server` 属性授予只读权限；禁止写、创建、setattr。 |
| Health HAL 无法读电池 | 实际 AXP2202 battery/type 被 generic sysfs 标签拒绝。 | 精确标记 H700 battery、USB 供电和 class/power_supply 为已有 `sysfs_batteryinfo`；保留更具体的 Hall 子节点标签。 |
| 旧启动动作与标准 Android /dev 冲突 | vendor 递归 restorecon `/dev`、重复 devpts/functionfs mount、硬编码 Mali mknod 均有 AVC。 | 保留经验证的 fresh tmpfs `/dev` 与真实 ueventd coldboot；退休候选中的旧动作；FunctionFS 仅初始化一次。 |
| 串口与 bringup 动作不适合 enforcing handoff | init 继承旧 devtmpfs tty FD，旧 graphics RC 尝试启动 root 串口服务、写 wake_lock。 | 删除候选 root 串口服务；切根前将标准 FD 接到新 `/dev/null`；在 policy 加载前申请固定 bringup wake lock，继续禁止把本轮当作深睡验收。 |
| 音频 init 声明不一致 | 实际服务注册 audio/effect 5.0，旧 RC 声明 2.0/4.0。主音频模块和输出实际已加载，可选 msd 等探测失败不是独立启动阻塞。 | 新唯一文件名 RC 使用 `override`，保持同一二进制、UID、组和 capabilities，声明实际 5.0 接口；不放宽 audioserver 对 vendor_file 的访问。 |

缺少 soundtrigger、camera、蓝牙音频卸载、部分 tracefs/BPF 等日志另行保留。未据此制造 HAL 占位或加入宽泛 allow。新的 framework/桌面稳定运行后，需要重新判断是否仍有独立功能故障。

## 构建与输入保持

`h700-low-pressure-20261106-035203.service` / prepare-v30 / images-result-v13 成功，567/567。耗时 331.945 秒、CPU 239.659 秒，峰值 RAM 5 GiB、swap 960 KiB；无 FAILED/OOM。实际 policy、neverallow、Treble 26/27/28 兼容及 VINTF 检查均经 Ninja 完成。

候选源文件集合、repo 编译输入、Native 371 个保护输入、Source64 1237 文件、两项真实 ABI5 库、五套生产密钥公开身份和原 eng 三镜像均受守卫保护。修改前的候选、旧 user 三镜像、旧锁与全部失败尝试保留在 `out/roc-os-user-repair-20261106-v2/` 及其记录的 Native 备份目录。`SPACE_REVIEW` 用户修改保留。

## 镜像与验收状态

封装使用新 `package_rc2.py`，复用已验证的 Boot0、kernel、DTB、GPT 布局和静态扩容工具；新 system/vendor 来自 images-result-v13。原 RC1、Bootfix1、BootDiag1 镜像全部保留。第一次封装前审计在旧版 `chown` 检查处停止，未输出镜像；改为核验已通过真实 ARM64/私有挂载测试的 fresh-dev 脚本与 SHA，失败目录保留。

ADB：stock user adbd、`ro.secure=1`、`ro.adb.secure=1`、`ro.debuggable=0`、Enforcing、TCP ADB 关闭。fresh userdata 仅预置本工作站的公钥，不含私钥、口令或原用户数据。USB 在 post-fs-data 启用，并在 boot 保持；Android AdbService 源码会从 `persist.sys.usb.config` 继承状态并同步 ADB_ENABLED。此设置用于本轮刷机查错，正式发行仍需单独决定调试入口策略。

整卡、独立范围核验和最终完成记录已写入 `docs/baselines/roc-os-user-rc2-20261106/`。最终包为 `out/roc-os-user-card-rc2-20261106/ROC_OS_ARM64_User_RC2_20261106.img.gz`，591,012,706 字节，SHA-256 `13eb405d04fa4fb73450e6c651832b6e033067b89ceef49d6de539974f86abab`。解压后 32,434,554,368 字节，SHA-256 `3c9a6423af7f7757b0ee69beeb4d48ddcfeb5866ca15983e08367549f9464674`。

最终封装作业 `roc-user-rc2-card-20261106-041625.service` 成功，耗时 545.898 秒、CPU 422.422 秒、峰值 5 GiB/swap 20.3 MiB。独立核验 `042620` 成功，耗时 16.069 秒：源 sparse 展开范围一致，实际整卡 boot 为 Enforcing，RC2 init/helper 字节一致，公钥目录/文件的 UID/GID/mode/context 正确，Mali 为 ARM64/4.9.170，10 个配对 ARM64/ARM32 ELF 正确。116 APK 签名、36 启动根/548 ELF/631 namespace states/41 early objects 闭合无未解析项；没有 permissive 域。Windows 独立读取 gzip 的 SHA 与 WSL 记录一致。

三次未产出整卡的审计尝试全部保留：旧入口 `chown` 预期、注释中的 `mknod` 字样、debugfs 八进制模式前导 0；均修正了检查器，未为通过检查改变候选系统或放宽权限。最终成功目录为 `/home/lpf/roc-os-user-card-rc2-20261106-v4`，所有失败目录、旧镜像及日志仍在。

当前没有活动构建或封装作业，心跳保持 PAUSED。没有自动刷卡、上传镜像或将 RC2 标为已通过真机/正式发行验收；旧 RC1 完成记录仅作为历史保留。

下一次手动刷机后，首先核对 RC2 标记、boot ID、Mali 模块及设备、SurfaceFlinger/system_server 持续存活、boot_completed、Thermal/Health 读数、Wi-Fi、音频、Select/亮度/Hall 与 ADB 重连。深睡、电源完整性、恢复/许可和同镜像正式发行验收仍独立开放。
