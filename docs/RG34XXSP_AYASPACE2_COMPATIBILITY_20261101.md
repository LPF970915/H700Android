# AYASpace 2 / Pocket Museum 本地兼容性验证

日期：2026-11-01。目标：当前 RG34XXSP / H700 / 2GB，原 64GB 卡上的 ARM64 Test2a，Android 10 / API 29。操作前按现卡 serial、CID、容量、profile 和 image marker 守卫核对，未使用旧 128GB 原型卡身份。

用户随后要求移植；独立签名兼容测试包及实际运行结果见 [Android10 适配记录](RG34XXSP_AYASPACE2_ANDROID10_20261101.md)。下文只记录未经修改的原始 APK，原始失败回执不回改。

## 结论

用户提供的 `pocketmuseum-0.3.3-release.apk` **不能正常安装到当前 Android 10 系统**。架构符合，但最低系统要求不符合；没有进入应用、ROM 或媒体的运行验收。

| 项目 | 结果 |
| --- | --- |
| 应用 | AYASpace 2 - Pocket Museum 0.3.3，versionCode 19 |
| 包名 | `com.pocketmuseum.app` |
| APK 大小 | 218,325,893 字节 |
| APK SHA-256 | `205cbf8b87d3b696b3c3873dbaa0ad47fbe0e57acce8ca208961a7aea476df38` |
| native ABI | 仅 `arm64-v8a`，符合当前主 ABI |
| minSdk / targetSdk | 31 / 36；最低需要 Android 12 |
| 图形声明 | OpenGL ES 3.0；未做实际 EGL/渲染验收 |
| 签名 | SDK apksigner 校验通过；这不单独证明 APK 来源可信或运行兼容 |
| 正常 ADB 安装 | 失败：`INSTALL_FAILED_OLDER_SDK`，要求 SDK 31，当前 SDK 29 |
| 安装后状态 | `pm path com.pocketmuseum.app` 无结果，无已安装包 |

没有修改 APK 的最低版本、重签名、伪造系统版本或替换系统库。单纯降低 manifest 的 minSdk 声明不能证明 Android 10 的 Java API、权限和 native 依赖兼容；若要继续，应取得支持 API 29 的版本，或另做源码兼容移植。

## 本地媒体与 ROM 输入

用户目录附带 Pocket Museum 自己的两个媒体包，使用 game_id / 区域 / manifest 索引。它们与天马 G 的按游戏目录及 metadata 配置不同，不能根据天马已存在封面就推断本应用能够自动识别。

| 媒体包 | 离线检查 |
| --- | --- |
| 图片 data25 | 20,002 条媒体记录，1,733 个 game_id；包含封面正背面、书脊、卡贴、标题图、截图和 logo；清单引用路径全部存在 |
| 视频 data24 | 1,522 条片段记录，1,515 个 game_id；清单引用路径全部存在；一个抽样片段成功读取并与清单 SHA-256 一致 |

图片样本读取通过 ZIP CRC；未对两个包逐文件解压或做全量内容 SHA 验证。图片与视频目录数据版本分别为 25、24，应用是否接受此组合尚未运行验证，不能标为兼容或不兼容。

天马 G ROM 压缩包可读取目录，内含嵌套 ZIP 和图片/视频。本轮未解压或复制整套 ROM，未改 Pegasus/RA 配置、存档和预装名单。因为安装已被系统拒绝，**封面实际显示、ROM 识别、视频播放、游戏启动、720×480 布局、性能及实体/受控十字键交互均未验收**。

原始安装回执、manifest、归档目录与媒体检查数据仅保存在忽略目录 `out/ayaspace2-20261101/`。APK、ROM、媒体和设备原始身份不提交 Git；没有修改 Test2a 镜像或设备系统分区。
