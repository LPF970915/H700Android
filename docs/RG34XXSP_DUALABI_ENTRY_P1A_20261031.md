# RG34XXSP 双 ABI 原型 P1a 启动入口修正

父检查点为 `baseline/rg34xxsp-dualabi-spare-p1-20261031`，提交 `869d430`；[P1记录](RG34XXSP_DUALABI_SPARE_P1_20261031.md)保留原图像的完整读回通过、首次厂商静态Logo及USB未枚举事实。P1a只针对启动入口，不把此前窗口通过当作ART64或模拟器共存通过。

## 修正内容

Android10 Bionic 的第一阶段 `get_executable_info()` 在proc尚未挂载时只对 `/init` 执行一次readlink。旧链 `/init -> /system/bin/init -> /system/bin/h700-bootstrap/init` 在选择链接命名空间时得到的是中间路径。P1a改为 `/init -> /system/bin/h700-bootstrap/init`，让第一跳就选中自有 bootstrap 库池；`/system/bin/init` 仍指向同一真实init，供后续重新exec使用。另增加只读标记 `/system/etc/h700-prototype/boot-entry-revision=p1a-one-hop-20261031`。

没有重新编译init、替换Mali、改framework/ART、内核或vendor。运行时家族标记仍是 `ro.h700.prototype=rg34xxsp-dualabi-gsi10-p1-20261031`；需同时读取入口修正标记，避免将两次尝试混淆。

由已校验P1的8GiB system派生，先校验父SHA，再修改入口并核对标签、文件系统、第一跳命名空间和完整组件解压。新system SHA为 `236a5233ad650c69ef03a3d5c10832ad70c92902af9ae8ecdbfa805ec1e85c94`；修正版分区gzip为859,662,928字节，SHA `98d53a09c98022143fef8cfbe565965fd5536212401ce8f6bc0440478512c9a1`。该组件是system分区，不能作为整卡映像使用。

用户将原64G卡放回TF1、128G卡放回TF2；重新核对USB、两张卡CID、profile、root及无挂载/holder后，完整读取原型system，确认失败首启并未改变P1的system SHA。因此采用6段、共32KiB的块差异修复：第一笔写入前逐段保存并验证旧块，校验新块SHA，再只写入备用卡p5。其他分区及原工作卡不在写入范围。写后同步并清除该分区缓存，完整读取8GiB，对比新system SHA及原系统关键状态。若父system已变化，工具会改用已校验的完整system组件，不猜测未知块差异。

## 复现与保留

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiBootEntry -Execute
py -3 -X utf8 .\tools\apply_h700_dualabi_boot_entry.py
# 默认只离线计划；--execute才核对当前原卡/备用卡并读取、写入。
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiEntryImage -Execute
```

保持既定低压力上限；组件准备耗时约2分56秒、CPU约2分18秒。完整镜像使用父P1的prefix/vendor/干净factory tail及新的system直接流式压缩，不产生整卡raw，不从设备复制userdata。原P1 gzip、P1a组件/整卡gzip、WSL两阶段及失败证据都保留，P1标签不回改。

本地材料在 `out/dualabi-entry-p1a-20261031/` 和 WSL `/home/lpf/h700-dualabi-entry-p1a-20261031/`。默认应用工具会先进行受保护的父system观察；`--reuse-parent-observation`只供同一受控会话15分钟内的已完成读回复用，仍逐块验证旧值并做完整写后读回。出现已开始记录时禁止盲目重放。

## 验收状态

| 项目 | 状态 |
| --- | --- |
| 入口组件、文件系统、第一跳及gzip | 通过 |
| 原型卡失败首启后的父system完整SHA | 与P1一致 |
| 32KiB差异写入 | 完成；清缓存后完整8GiB读回SHA匹配，原工作系统关键状态不变 |
| P1a整卡gzip | 通过完整解压、全量SHA及每段SHA校验，未生成整卡raw |
| 修正后的实体启动/USB | 第二次仍停厂商Logo且无USB；ramdisk日志确认切根前的init检查失败 |
| ART64 JNI、ARM64 MT、RA32/PPSSPP32共存 | 待测 |
| 整卡P1a重新刷卡后的全新首启 | 未执行；本次通过P1加入口修正验证 |

修正后的入口仍需实体启动验证，不能将源码定位写成唯一故障原因或成功启动证明。原工作卡和v6b候选保留回退；完整源码64位framework重建与原系统功能回归仍单独列为未完成。

## 第二次首启的实际阻塞证据

用户第二次换卡仍见静态Logo。换回原卡后，在私有挂载命名空间中以 `ro,noload` 读取原型system与data，主命名空间挂载表不变。`RGSP_SINGLE_CARD_BOOT.log` 两次明确记录 `ERROR: Android /system/bin/init is missing`。真实私有init文件存在，但在切根前对前缀路径检查绝对软链接会跳回ramdisk旧根，因此 `-x` 失败。此时尚未进入Android init，ART64与应用均未执行。

实际保留的ramdisk会先挂载proc，再执行 `switch_root ... /init selinux_setup`；因此先前P1a对“无proc第一阶段”的改良并不是当前首启阻塞的证据。下一轮需将 `/system/bin/init` 改成同目录相对链接，并对照ramdisk建立的旧兼容别名修正vendor fstab；真实GPT GUID继续保持独立。

另确认保留ramdisk会运行自动扩容。卡上容量记录为244277248扇区，未发现未完成扩容标记；不能再把“写卡时未扩容”等同于“首启不会扩容”。此前“未写userdata/vendor/GPT”只描述入口补丁工具的范围。早期日志及对应原boot ramdisk全部保留本地。

P1a整卡成品：`H700_RG34XXSP_2GB_DualABI_P1a_GSI10_20261031_NoROM.img.gz`，959,615,403字节，gzip SHA `b5996cbe4edc7c8f02b1209f2df3c4715b79d5ac10bf85e5ea5fba009767271b`；完整解压32,434,554,368字节，原始SHA `f76ea834212a5fcac3c2415bbcfb9c70adf5ee5172606f2baa3a419f823adb43`。封装约6分34秒、CPU约5分58秒，保持原资源上限。该成品使用干净factory tail，当前原型卡则来自P1加入口修正，两者的全新首刷验收不可混同。
