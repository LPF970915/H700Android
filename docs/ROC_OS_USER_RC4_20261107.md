# ROC OS User RC4：修复机型属性拆分造成的 HAL 启动回归

用户刷入 RC3 后，机器停在 Android 动画。认证 ADB 已确认真实 RC3、新 boot ID、user/Enforcing 和正常 Mali 设备。问题不是之前的图形驱动加载失败：SurfaceFlinger 存活，但 system_server 持续等待 `android.hardware.light@2.0::ILight/default`，`sys.boot_completed` 为空。

## 实际根因

RC3 将 `persist.vendor.rgsp.input_profile` 从通用 vendor 属性区划分为独立类型，只为签名应用和 shell 添加了读取规则，漏掉了原本也读取这个属性的亮度与温控 HAL。这是本轮修复引入的依赖遗漏。

真机日志明确显示：

- `hal_light_default` 和 `hal_thermal_default` 对 `roc_input_profile_prop` 的 read 被拒绝。
- H700Light 输出 `Refusing an unqualified device/profile` 并返回 1，温控服务同样在机型检查处返回 1，两者被 init 反复拉起。
- framework 反复等待 ILight/default，启动无法完成。崩溃缓冲区为空不能排除这种服务主动退出与注册失败。

证据保存在本地 `out/roc-os-user-rc3-firstboot-20261107/`。没有更改当前卡的策略、开启 root、切换 permissive 或自动刷写。

## RC4 修改与新增验证

候选产品只给公开的 `hal_light_server`、`hal_thermal_server` 属性增加同一机型属性的 `get_prop`。原硬件资格检查、属性值、应用读取、CPU 温度只读、Hall 只读和目录遍历规则全部保留；未授予写属性权限，也未开放应用对通用 vendor 属性区的读取。编译差异只有策略文件及 RC4 的两个版本标记文件。

新增 `audit_rc4_card.py` 扫描实际依赖闭合中的 ELF，以及全部实际 APK 的 classes DEX，枚举这个属性的二进制读取方，不只检查应用。预期四个组件：H700Light、H700Thermal、H700Lid、ROCReleaseProvisioning，逐一映射实际进程域并查询合并策略。对失败的 RC3 实际策略还执行 HAL 拒读负例，再对 RC4 执行 read/open/getattr/map 正例及禁止写属性检查，以确保本次审计能检出已知回归。

修改前完整输入守卫和旧 user 三镜像备份通过，记录在 `out/roc-os-user-rc4-repair-20261107-v1/`；备份 tar 不解引用私有签名目录。旧 RC3 审计脚本按原封装 SHA 保存后才扩展参数，旧镜像、旧失败日志和所有原输入均保留。

构建 `h700-low-pressure-20261107-002023.service` / prepare-v32 / images-result-v15 成功，555/555；耗时 337.253 秒、CPU 242.608 秒，峰值内存 5 GiB/swap 48.7 MiB，无 FAILED/OOM。合并策略、neverallow、Treble 26/27/28、VINTF 和三镜像记录已完成。整卡继续采用与已成功开机 RC2 一致的 boot，保持认证 USB ADB、user/Enforcing、root 拒绝和 TCP ADB 关闭。

最终镜像和独立校验结果将在完成后绑定到本轮 baseline。RC4 尚需真机重新验收 HAL 注册、boot_completed、首次自动导航/初始化、温度和 Hall，离线通过不代表正式发行验收。

最终封装与独立核验均通过：`out/roc-os-user-card-rc4-20261107/ROC_OS_ARM64_User_RC4_20261107.img.gz`，591,012,777 字节，SHA-256 `a7394633a4e8ebaf2d64c6af9eec6c2eab53cebe4c1154ba77232731d7e0c644`。解压后 32,434,554,368 字节，SHA-256 `c77f82a5d3ed22a8e09cca24da830ed3b11e13920f4ada42f373b5eb1ccef620`。证据见 `docs/baselines/roc-os-user-rc4-20261107/`。

封装耗时 541.785 秒/CPU 423.371 秒/峰值 5 GiB、swap75.8 MiB；独立核验13.433秒/CPU8.949秒，均退出0。Windows SHA 与 WSL 一致；实际卡内 boot 与成功 RC2 相同（`04e11bbdb1d14f8672439d948b6f5cbe95e3294634304cd510df10e3064ced49`），Enforcing、10个配对实际ELF、116APK签名、源 sparse/整卡范围/完整gzip、源输入和公钥种子均通过。没有活动作业，心跳保持 PAUSED，未自动刷卡或上传镜像；RC4 真机首次启动仍待验证。
