# 天马 G / GBA 实测与预装增补

日期：2026-10-30。检查点：`baseline/rg34xxsp-pegasus-gba-20261030`。对象为 RG34XXSP / H700 / 2GB / Android 10 ARM32；没有重刷或改写旧 IMG。

用户提供整合包的 9 款定制前端和两款 RA 都只含 ARM64，不能安装到此镜像。使用官方 Pegasus `alpha16-112-g2a13b4f4` ARM32（versionCode 1975），配合原主题，保持已测 `com.retroarch.ra32` 1.22.2 不变。三合集共 604 条目；启动包名、核心路径和 CONFIGFILE 已适配。标准 gpSP 替代定制 gpsp_rumble，不宣称震动支持。

最初黑封面来自尚未完成的媒体复制与旧索引；完成复制并重扫后 604 条目都识别封面、logo、视频。六个仙剑条目仍有 missing 标志，虽然对应文件存在，未宣称整个合集均可启动。

预览另触发供体 AwMetadataRetriever 的 `libMemAdapter.so ion_alloc_open` 空指针崩溃。对照原生 MediaPlayerFactory 源码，加入仅在显式 rg34xxsp profile 下设置 `media.use_nuplayer=true` 的 init 配置。一次正常内核重启确认设置自动生效、预览实际连续运动、mediaserver 稳定、AT4K 默认 HOME 保持，system/vendor 只读。视频走 Android 软件解码路径，不表示通用硬解已修复。原设置及撤销脚本保存在本地。主题已有应用后台暂停视频逻辑，本轮未另改。

| 项目 | 结果与边界 |
| --- | --- |
| 马里奥赛车 / mGBA | 真正进入 50cc 比赛，A 加速、方向转向；短时约 59.1–59.2 FPS |
| 无滤镜 / LCD3x | 各约 24.5 秒；进程 CPU 约单核 59% / 56%，PSS 75 / 79 MiB，swap 0；场景不同，不据此判断滤镜降低 CPU |
| 存档 | 控制器快捷菜单保存成功；新进程自动加载自有测试存档，回到同一比赛；不代表手动载入菜单路径已单独测过 |
| 火红 / mGBA | 前端按 A 启动到实际标题动画 |
| 超级街霸 2X / gpSP | 前端按 A 启动、标题约 59 FPS；未做长时对战 |
| VBA-M | 马里奥赛车启动与标题约 59 FPS；未做比赛性能验收 |
| 火枪英雄 | 标题/演示启动；未完成实际游玩验收 |

GBA 使用独立配置，240×160 以 3 倍整数比例适配 720×480，单遍 LCD3x 自动预设实际加载；关闭 rewind、runahead、屏幕叠层和常驻 FPS/调试日志。原 RA 全局配置未覆盖。没有 1GB 实机或长时热稳验收，也未重新听音。

用户随后明确将天马 G 与配套配置加入下一镜像预装，排除 ROM。原六款选择仍保留，NOVA 用手机/平板模式。MT 仍是候选，未自动加入。此检查点只冻结现机测试与源配置；下一镜像应另有封装报告，不能把当前已装软件说成旧镜像已预装。

原始日志、截图、账号画面、ROM、APK、主题和备份留在忽略的本地目录。公开 [版本锁](baselines/rg34xxsp-pegasus-gba-20261030/component-lock.json) 与 [配置](../config/pegasus/README.md)。
