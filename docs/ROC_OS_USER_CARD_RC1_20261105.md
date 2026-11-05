# ROC OS ARM64 User RC1 整卡候选镜像（2026-11-05）

完整整卡已封装并独立复核，适用 RG34XXSP / H700 / 2GB。仍待新user镜像真机验收；本轮没有接触、刷写或切换当前设备安全模式。

## 文件与烧录

- 文件：`out/roc-os-user-card-20261105/ROC_OS_ARM64_User_RC1_20261105.img.gz`，585,700,498字节。
- gzip SHA-256：`c549d011a1a332e92a1b317601f6128e2b849813ec40bdac988eaa05913e4ee5`。
- 解压IMG：32,434,554,368字节，SHA-256：`44dfc8e35744f92260c64005e2fc4ca0410c6205bcbd8d92f62bea13fc99c8ed`。
- 使用至少64GB备用卡。先解压为`.img`再整卡烧录，目标卡内容会替换；保留当前工作卡。首次仅放TF1，TF2留空，保持供电等待扩容及可能的自动重启。

包括硬件引导前段、boot、system、vendor、全新userdata和主备GPT。Boot0、内核、DTB、启动地址保持；新boot沿用统一存储增长逻辑，准备精确身份匹配的摇杆，移除失败匿名shell并请求SELinux enforcing。TF1余量首启扩展给内部存储，TF2独立作为外置卡。不含旧账号、网络密码、存档、ROM或旧userdata。本版换用ROC签名身份，应按完整镜像干净首启，不把旧eng userdata混入新系统。

## 修复与验证

四组su启动功能在候选中实现迁移：摇杆/节点权限在硬件启动阶段准备，Android早期恢复设备标签；网络默认值和壁纸原图由独立UID的平台签名应用处理。壁纸使用MediaStore待提交记录及SHA回读，不替换已有文件；壁纸失败不触发下次开机重置系统默认配置。键盘校验绑定实际换签APK。Hall仅对历史AVC中的单一节点增加只读标签规则，没有扩大为任意sysfs访问。

11项发行工具回归通过。实际镜像116个APK全部通过Android10签名校验，证书均来自固定ROC production-v1五组身份；桌面、导航、SystemUI、设置、Hall、旋转和初始化应用采用ROC平台身份。签名不完整的CTS测试占位包及其配对模块仅从候选排除，原件与中间镜像、所有失败记录均归档保留。

36个启动根、548个ELF、631个命名空间状态、41个早期对象无依赖缺项；10个实际ARM64/ARM32 ELF核对通过。实际user属性secure=1、adb.secure=1、debuggable=0、USB默认none、TCP ADB关闭，编译策略无permissive域。旧产品MAC文件不在镜像中；合法空产品策略摘要与vendor配对一致，不含人工空CIL/映射。

主机和Android ARM64 fsck通过，userdata根1000:1000、0771、system_data_root_file标签正确。整卡连续区段回读、完整gzip解压SHA，以及独立解析编译sparse得到的system/vendor展开SHA均一致。原ramdisk的BusyBox及自带库完成QEMU预执行和哈希工具验证。所有重任务保持单核、CPU0–1、nice19、RAM6GiB、swap512MiB、idle IO、单次3小时上限。

## 验收边界

这是完整可刷的**测试候选版**，并非正式发行验收通过。新user镜像尚未真机启动；历史eng通过不能替代本镜像的首启、扩容、导航/Hall/亮度/Wi-Fi/TF2、充电/温控/深睡、认证ADB和恢复验收。保持bringup电源策略，不宣称续航/深睡通过。

源码直接构建的标签仍是`dev-keys`；这并非使用公开AOSP测试私钥，116个APK实际证书已核对ROC专用身份。正式signed-target-files元数据、运行时安全、双构建对照、许可和同镜像最终验收仍开放。私钥及口令没有写入源码、Git或镜像，镜像不上传Git。

详细输入、分区和整卡SHA见[镜像锁](baselines/roc-os-user-card-rc1-20261105/image-lock.json)。原始审计、失败目录与SPACE_REVIEW用户修改保留。

## 工具

编译使用`tools/build_h700_low_pressure.ps1 -Targets H700UserBuild -Execute`；封装为`tools/release/package_candidate.ps1 -Execute`，独立复查为`tools/release/package_candidate.ps1 -VerifyOnly -Execute`。工具只操作固定普通文件并持有全局锁，已有交付不会覆盖。不要自动重启已完成作业；新版本需先审查输入与版本名。
