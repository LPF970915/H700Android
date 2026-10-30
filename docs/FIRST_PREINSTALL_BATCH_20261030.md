# 首批预装软件确认名单

日期：2026-10-30。依据：用户在当前 RG34XXSP / H700 / 2GB / Android 10 样机上的实测反馈，明确只有以下六款作为首批预装软件。

| 用途 | 软件 | 当前测试版本 | 后续预装要求 |
| --- | --- | --- | --- |
| 音乐 | QQ 音乐 TV | 9.0.0.39 / ARM32 | 使用已测 TV 版 |
| 动画流媒体 | Animeko TV | 6.4.0 / armeabi-v7a | 使用已测独立 TV 包 `me.him188.ani.tv` |
| PSP 游戏 | PPSSPP | 1.20.4 | 保留当前按键配置 |
| 多平台游戏 | RetroArch（RA 全能模拟器） | 1.22.2_GIT / ra32 | 配套 H700 控制器映射和菜单配置 |
| 本地视频 | NOVA Video Player | 6.6.2-20261027.1847 / armeabi-v7a | **设置为手机/平板模式；TV 模式显示不全，不作为预装默认值** |
| 电子书、漫画 | KOReader | 2026.07.1 / ARM | 配套本仓库 H700 按键用户补丁 |

这是一份已确认的首批名单，供后续镜像集成使用。本次只登记选择与配置要求，没有修改设备设置、安装/卸载应用或重新封装 IMG；当前卡上的安装状态不等于已集成出厂预装。后续打包需要将 NOVA 手机/平板模式纳入默认配置和首次启动验收，不能沿用旧测试的 TV/mdpi 预配置。

用户确认的是这些应用当前实测可用，不推导为所有菜单、媒体格式、游戏性能或其他内存机型全部通过。其他应用均不在首批名单：Bilibili 已取消；红果短剧仍未通过播放验证；微信读书不纳入；谷歌组件仅离线准备，登录另测。后续增补需单独确认。

同日按用户要求[安装 MT 管理器并清理试验应用](RG34XXSP_MT_CLEANUP_20261030.md)。MT 的复制、重命名、ZIP、解压、回收站及全选常用路径可按键操作，但底栏和侧栏顶部有焦点断点，仍需鼠标辅助，先列为补充候选。未入选的 10 款试验应用及按键采样测试 App 已备份后卸载，六款名单与配置要求保持不变。

## 版本与配置依据

- QQ 音乐：[安装锁](baselines/rg34xxsp-hardware-20261029/qqmusic-tv-lock.json)。
- PPSSPP、RetroArch：[组件锁](baselines/rg34xxsp-controller-mouse-20261028/component-lock.json)；[RA 控制器映射](../config/retroarch/android/H700_ANBERNIC_keys.cfg)及[菜单配置片段](../config/retroarch/h700-menu-overrides.cfg)。
- NOVA、KOReader：[APK 锁](app-tests/rg34xxsp-20261028/apk-lock.json)；[KOReader 配置](../config/koreader/README.md)。旧锁描述当时的测试条件，不覆盖本次 NOVA 模式要求。
- Animeko：发布页 `https://github.com/open-ani/animeko/releases/tag/v6.4.0`；文件 `ani-tv-6.4.0-armeabi-v7a.apk`，32,209,143 字节，SHA-256 `ee3126653e5554906f99eb7eda7bb254f69e7246258e55f19e1aaf997bde23da`。本地 APK 已验证 API 29 签名、最低 API 26 和 ARM32 ABI；原始证据与 APK 位于 `out/video-gapps-20261029/`，不上传。

既有 [小屏首轮记录](RG34XXSP_SMALL_SCREEN_APPS_20261028.md)保留原始测试结果；当前预装选择和 NOVA 模式要求以本文为准。应用 APK、账号、书架/播放截图及原始日志继续仅保留本地。

## 同日明确增补：天马 G

用户要求将天马 G 与相关配置加入下一镜像，**不含游戏 ROM**。采用官方 ARM32 Pegasus、用户整合包主题及本机 RA ra32，详见 [GBA 记录](RG34XXSP_PEGASUS_GBA_20261030.md)。上文“只有六款”描述最初确认时点，当前选择为这六款加天马 G；MT 仍候选。封装另有报告前，不代表已生成新 IMG。
