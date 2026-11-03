# ROC OS 源码产物与已验收系统的离线差异审计

2026-11-03。结论：**源码三镜像构建成功，基础离线检查通过，但功能和存储布局尚未对齐，当前不应直接制作整卡交付镜像。** 本轮只审计，没有修改构建输入、重新编译、制作整卡镜像或访问设备/存储卡。

新产物为 `roc_os_source64-eng`，准确镜像SHA见[首轮完成锁](baselines/roc-os-source64-round1-20261103/completion.json)。比较基准为已物理验收的Test2a加四项Light文件及data Navigation13；离线文件来自锁定的readiness r4 stage-v5。r4中的完整品牌迁移只通过离线检查，未装入当前卡，不能视为已物理验收系统。

## 已通过和已保留的部分

| 项目 | 本轮证据与边界 |
| --- | --- |
| 分区文件系统 | 从原始sparse产物生成独立审计raw文件；system、vendor均执行只读`e2fsck -fn`，退出0。原sparse文件未修改 |
| 启动依赖 | 34个入口，包含init、adbd、服务管理、SurfaceFlinger、vold、双ABI应用进程、HAL及Mali/Gralloc/HWC插件。543项不同ELF、626项命名空间状态的DT_NEEDED路径/ELF位数检查无缺失；init早期bootstrap另查41项，无缺失 |
| 中文与桌面 | 镜像中默认zh-CN、AT4K工厂HOME XML存在；AT4K APK、HOME XML、樱花壁纸及Leanback APK均与比较基准逐字节一致 |
| 物理A解锁 | 检查实际SystemUI DEX，存在`rgsp`、`ANBERNIC-keys`、scan304、ENTER及锁屏/非密码框限定。新产物使用源码原生实现，不能因缺少GSI的`SystemUiKeys`类就判为补丁丢失 |
| 电源菜单焦点 | 实际DEX存在方向键、HAT方向及初始焦点方法。与GSI辅助类实现不同，需要新系统首启后物理回归，不能直接沿用现卡的通过结论 |
| Hall | H700Lid APK和启动接收器、明确设备profile、hallkey路径、调用电源键语义的sleep/wake链路均存在。签名与新平台角色一致；APK/DEX与GSI包装不完全相同，不声称整包一致或新运行已验收 |
| 输入与GPU输入件 | 按键表、双摇杆模块、8821cs模块及Mali32/64库SHA与基准一致；私有Gralloc及成对ART/JNI仍为本轮已构建产物 |
| 签名 | 选择的23个新/参考APK通过API29签名验证；新Hall、旋转、Navigation、SystemUI等平台角色证书匹配。不是全系统共享UID或旧userdata迁移验收 |
| 待机保护 | bringup唤醒锁仍存在，未解除。Hall代码存在不等于内核深睡可用 |

依赖检查未执行ARM二进制，未证明运行时符号版本、全部dlopen分支、内核ioctl ABI、APEX运行挂载及实际启动。上述检查不代替真机验收。

## 必须先处理的差异

| 编号 | 当前新产物 | 封装前的处理 |
| --- | --- | --- |
| NAV | 实际Navigation APK为8，现机为13。源码`adjustRange()`仍仅接受Settings，SystemUI下拉栏被排除，缺少已验收的亮度滑条修复 | 在独立产品中同步确切的滑条修复；如采用Nav13委派逻辑，必须与源码SystemUI已有原生补丁及委派标记配对，不能只复制APK |
| LIGHT | 新vendor没有`android.hardware.light@2.0-service.h700`、h700-light.rc及Light VINTF声明 | 集成已验证BACKLIGHT-only服务、RC、contexts和接口依赖，确保只有一个`ILight/default`，复核标签及闭包 |
| AUDIO | 新混音XML为12,162字节，使用`Speaker Switch`、AIF1等厂商旧控制；基准为888字节H700映射，使用`SPK Switch`、LINEOUT和输出混音控制，内容有实质差异 | 在独立产品中固定已验收H700映射，核对HAL所需路径和音频配置后重建vendor。原生库能链接不证明声音正常 |
| MEDIA | OMX服务可执行文件与RC存在，但新vendor VINTF没有基准已有的`IOmx`/`IOmxStore`声明 | 补齐已有软件编解码目录的接口声明，检查合并VINTF和目录文件；本轮不宣称硬件解码通过 |
| STORAGE/BOOT | fstab、ROMS交接仍为旧p8布局；保留boot ramdisk明确依赖p8，并调用旧扩容器 | 为TF1剩余空间归userdata、TF2外置卡设计独立GPT/启动/扩容/fstab/vold及恢复流程，测试几何和中断分支。旧写卡器不能直接套用 |
| DEFAULTS | 型号属性已有ROC OS，但USB产品串仍为`H700 Android USB`，没有r4保存名称迁移；旧v6b安装服务/脚本仍在，首启服务尚未统一nice19/idle0 | 收口品牌及纯净系统初始化，只保留AT4K和系统帮助服务，移出候选中的历史第三方安装入口并保留本地历史输入；重新验证首启守卫、输入法和低优先级流程 |

新镜像未带既有`h700-preinstall`载荷目录；残留v6b脚本要求旧release marker，在新产物上不满足。不能把它描述为正在安装七款应用，也不能仅凭载荷缺失宣称纯净预装策略已经正式完成。

默认中文、AT4K和A解锁并非全部丢失。需要补的是明确缺少的功能和配置，再在新系统上统一回归；不应整体覆盖GSI框架或回放历史打补丁脚本。

## 启动入口的具体结论

保留boot中的shell init会检查`/android-root/system/bin/init`可执行，再以`/init selinux_setup`切换根。新system中`/system/bin/init`是普通可执行ELF，根`/init`直接指向它，解释器`/system/bin/bootstrap/linker64`及早期依赖可找到；此前“绝对嵌套符号链接导致外部-x检查失败”的条件在新产物上未复现。

新编译的`ramdisk.img`包含Android原生ELF init，与目前保留的掌机shell ramdisk不是同一套启动流程。它尚未被证明能直接替换既有boot中的ramdisk。制作新卡布局时需要明确选择并审计启动方案，同时保留验证过的Boot0、boot-resource、env、内核及DTB输入。

## 距离可刷整卡测试镜像的剩余步骤

1. 在独立源码产品中修正NAV、LIGHT、AUDIO、MEDIA及品牌/纯净首启差异，保留旧产品和本轮完整产物。
2. 按原负载限制增量编译受影响模块和分区，再做差异、APK/API/签名、VINTF、依赖、权限标签和fsck检查。当前编译已成功，后续是修正后的增量验证，不需要无条件从零重编。
3. 完成TF1统一userdata/TF2外置布局与启动扩容方案的离线测试。该项涉及启动流程和存储恢复，是独立工作，不是只改分区名称。
4. **收到用户确认后**，才组装独立整卡测试镜像；核对Boot0/GPT保护、全部段范围、默认空userdata及完整压缩解压哈希。此步骤尚未开始。
5. 另行确认刷卡后，进行干净首启、容量、A/电源/Menu/鼠标、亮度、Hall、声音、Wi-Fi及重启验收。

“能刷的测试镜像”和“正式发布版”仍有不同验收范围。深度待机、充电/温控、长时间稳定性、蓝牙和扩展硬件支持范围、发行签名/ADB/root/SELinux/恢复策略仍需继续收口；本轮没有推进这些阶段。

## 证据与保全

脱敏结论见[审计锁](baselines/roc-os-source64-audit-20261103/audit-lock.json)。原始离线证据及脚本保存在 `D:\Works\H700Android\out\roc-os-source64-audit-20261103\`，独立文件系统副本/提取物在WSL `/home/lpf/roc-os-source64-audit-20261103/audit-v1/`，均不是整卡镜像。

保留了两项审计工具草稿问题：第一次DEX工具因要求单CPU可见而拒绝运行，改为更严格的CPU0后通过；早期boot文本检查被随后解析的ELF覆盖了快照，已明确拒绝该节并以`boot-contract-v3.json`替代。它们是审计工具问题，不是系统启动失败；SystemUI DEX证据独立有效。

审计结束再次核对371项原输入、57项独立产品、2项ABI5库及原三镜像哈希保持。没有修改SPACE_REVIEW用户内容，没有设备会话或写卡操作，定时编译跟进仍暂停。
