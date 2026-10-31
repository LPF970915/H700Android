# RG34XXSP 双 ABI 原型 P1b：ramdisk 切根兼容

父检查点 [P1a](RG34XXSP_DUALABI_ENTRY_P1A_20261031.md) 为 `baseline/rg34xxsp-dualabi-entry-p1a-20261031`、提交 `2315936`。前两次原型首启均未进入Android；两轮完整分区校验不等同启动通过。生产候选v6b和原64G工作卡继续保留。

## 已证实的阻塞点

保留boot ramdisk的 `/init` 是单卡切根脚本。它先运行容量准备、挂载system/vendor/data，再在ramdisk根目录中检查 `[ -x /android-root/system/bin/init ]`，最后绑定proc/sys并 `switch_root ... /init selinux_setup`。

P1/P1a把 `/system/bin/init` 改成绝对链接 `/system/bin/h700-bootstrap/init`。在切根前，绝对目标从ramdisk旧根解析，实际私有init存在也无法通过检查。对原型卡只读、禁止journal回放的私有命名空间取证复现了检查失败；卡上boot log两次明确记录 `ERROR: Android /system/bin/init is missing`。这比此前“无proc时只读一层链接”的源码推断更直接；当前ramdisk实际已在Android init前挂好proc。

容量证书显示244277248扇区，未发现FAT扩容pending标记；不能把静态Logo归为仍在扩容。保留ramdisk确实会自动扩容，写卡工具本身没有扩容不代表首启不会改变GPT/ROMS。

## 修正与不变量

- `/system/bin/init` 改为相对链接 `h700-bootstrap/init`，在切根前后都能解析；`/init` 仍直接指向私有init。
- vendor fstab的system/vendor/data设备路径改回ramdisk实际创建的三处旧兼容别名。它们是 `/dev/block/by-partuuid/...` 路径，由ramdisk显式指向当前启动卡的p5/6/7；真实GPT磁盘/分区GUID继续保持P1的独立值，没有改回原工作卡GUID。
- 入口标记为 `p1b-ramdisk-handoff-20261031`，运行时家族仍为 `rg34xxsp-dualabi-gsi10-p1-20261031`。没有重新编译或替换native init、Mali、framework/ART、内核、Boot0或boot ramdisk。

原型system/vendor均由已锁定父镜像派生，文件系统和组件完整解压通过。使用真实ELF文件但不执行init的前缀目录夹具，验证旧绝对链接失败、新相对链接可执行访问成功；三处别名逐项与已固定ramdisk源码核对。4KiB块差异另由父分区加差异流重建SHA，避免遗漏块。

## 卡写入与隔离检查

总修改28KiB。先核对精确USB、原卡/备用卡CID、root/profile、分区起止、无挂载/holder；全部旧块匹配后才写入备用卡system/vendor。当前内核的MMC次设备号曾与上次相反，守卫因此改为从目标sysfs实时派生，再与实际块节点rdev及mountinfo逐一核对，不再假设固定minor范围。

写后同步并清除两个目标分区缓存，完整读取8GiB system及2GiB vendor，两个SHA匹配；原工作系统的boot、核心PID、挂载及关键文件SHA保持一致。没有由本次补丁写入userdata/GPT/内核/Boot0。

随后在隔离挂载及网络命名空间中只读挂载真实原型system：切根前可执行检查通过，真实ELF64 bootstrap linker加载私有adbd并执行 `--version` 正常返回1.0.41。源码确认这个选项在守护程序main前返回；未执行init、未启动另一adbd，未绑定宿主USB/属性/Binder，父系统状态不变。这是加载检查，不代表已启动原型系统。

## 复现、产物与边界

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiHandoff -Execute
py -3 -X utf8 .\tools\apply_h700_dualabi_handoff.py
# 默认仅计划；--execute才在精确身份守卫后应用差异。
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiHandoffImage -Execute
```

固定单核、CPU0–1、nice19、6GiB RAM、512MiB swap。准备组件约3分41秒；整卡流式封装约6分32秒。整卡gzip使用干净factory tail，不从设备复制userdata，完整解压长度、整段SHA、每分区SHA都通过；不生成整卡raw。

保护 `out/dualabi-bootchain-p1b-20261031/`、WSL `/home/lpf/h700-dualabi-handoff-p1b-20261031/`、两组旧/新块和设备回读、早期boot log、隔离探针与全部父镜像/失败材料。Git只保存自有工具和脱敏锁，不上传二进制、卡身份或原始日志。

| 门槛 | 状态 |
| --- | --- |
| ramdisk真实前缀检查、别名及文件系统 | 通过 |
| 28KiB补丁、10GiB完整物理读回、原工作系统不变量 | 通过 |
| 隔离ELF64 adbd版本检查、未启动守护 | 通过 |
| P1b整卡gzip及完整分段解压校验 | 通过 |
| P1b物理首启、ART64、MT64、RA32/PPSSPP32共存 | 等待再次换卡，不宣称通过 |
| 从P1b整卡重新刷写后的全新首启 | 未执行；目前是P1/P1a加受控修正 |
| 完整源码64位framework重建、正式系统功能回归 | 未完成 |
