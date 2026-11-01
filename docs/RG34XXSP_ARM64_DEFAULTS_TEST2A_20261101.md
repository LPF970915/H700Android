# ARM64 Test2a：固化简体中文和 AT4K 默认桌面

日期：2026-11-01。承接[Parity Test2](RG34XXSP_ARM64_PARITY_20261101.md)，只修改六个系统文件；七款ARM64预装、核心、主题/媒体、vendor、硬件前缀及干净userdata/ROMS/GPT保持原字节。原Test2及所有标签/产物不变。本轮不刷卡、不重置设备数据。

## 修改原因和实现

原ARM64候选虽然在`prop.default`设置了中文，但`/system/build.prop`仍是`ro.product.locale=en-US`。本地Android10 init源码证明：启动时先收集各文件属性，后读文件会覆盖前读文件，包括`ro.*`；不能用“ro属性不可写”推断前一份设置优先。

Test2a同时统一`/system/etc/prop.default`与`/system/build.prop`的`ro.product.locale=zh-CN`、`ro.product.locale.language=zh`和`ro.product.locale.region=CN`，保留工厂`persist.sys.locale=zh-CN`。封装器按属性加载顺序检查system、vendor及product中的有效语言值，拒绝后续英文覆盖。默认值用于干净首启；日后用户主动选择的语言仍由data持久化，不在每次开机强改回中文。

原AT4K工厂默认配置已存在于产品源码，但未进入GSI派生ARM64镜像，原先要等`sys.boot_completed`后的脚本调用`pm set-home-activity`。这晚于第一次HOME解析，因此会出现首次桌面选择框。

本轮把已锁定的`configs/at4k-home.xml`安装到`/system/etc/preferred-apps/at4k-home.xml`。PackageManager在首次HOME前加载，目标为`com.overdevs.at4k/.MainActivity`，过滤MAIN、HOME和DEFAULT；候选集合由系统扫描结果生成，没有固写其他桌面名单。其他桌面保留，后续仍可更改默认桌面。首次安装天马G后原脚本重新确认AT4K的逻辑也保留，用于处理新HOME候选造成的偏好失效。

没有修改APK、框架DEX或图形库。镜像标记改为`dualabi-parity-test2a-20261101`，release及初始化版本标记同步区分Test2a；本轮不重建整套AOSP。

## 封装与验证

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiDefaultsStage -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700DualAbiDefaultsImage -Execute
```

继续使用CPU0-1、合计单核、nice19、RAM6GiB、swap512MiB与idle I/O，不调整电压、不提高负载。Stage从精确SHA匹配的已验收Test2离线system复制到新目录，写入六项增量并逐项核对SHA、mode、root属主、SELinux标签，e2fsck必须退出0；关键GSI/ART/bootstrap文件再次比对。工厂HOME XML结构和目标已检查，未删除其他桌面或预填设备私有package-restrictions数据。

整卡直接按四段输入流压缩，不生成32GB raw副本。最终完整gzip解压、逐范围及整体SHA结果和文件身份见[镜像锁](baselines/rg34xxsp-arm64-defaults-test2a-20261101/image-lock.json)，只有镜像锁通过后才视为交付。输出目录为`out/dualabi-defaults-test2a-20261101/image/`。

**本轮未进行实卡干净首启。** 需要刷备用卡后确认首次画面直接进入中文AT4K且无桌面选择框，七应用安装后Home仍解析为AT4K，再做一次正常重启确认。Test2原有全部系统/硬件验收边界继续有效，不能把本轮离线通过说成新镜像首启或恢复出厂通过。

## 最终交付

检查点：`baseline/rg34xxsp-arm64-defaults-test2a-20261101`。离线镜像已全部通过。

- 文件：`out/dualabi-defaults-test2a-20261101/image/H700_RG34XXSP_2GB_ARM64_Parity_Test2a_20261101_NoROM.img.gz`
- gzip：3,625,312,231字节；SHA256：`ed2aee0bd712c0fc74f86c8d120d6abbee76a8f4ae02a8e2153dcb147d811a80`
- 解压后：32,434,554,368字节；SHA256：`ff6e8fb89afc20b13dfdac3d086fecbd7460b42d9122fd70f9e984e9c3f290ad`
- 六项写入回读、fsck、有效中文属性顺序、关键库保护及完整gzip分段/整体SHA检查均通过；新实卡首启仍未验收。

## 保全

保护`out/dualabi-defaults-test2a-20261101/`及WSL`/home/lpf/h700-dualabi-parity-20261101/defaults-stage-v1/`，包括最终gzip、分区、属性输入审计、差异和完整镜像锁。旧Test2、v6b、Test1及原工作卡继续保留。只上传源码/配置/脱敏锁，不上传镜像、APK、私钥、原始日志或设备数据；现机未作控制。
