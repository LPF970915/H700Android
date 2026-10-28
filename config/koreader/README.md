# H700 的 KOReader 可选配置

仅在 **KOReader GitHub Android ARM 2026.07.1** 上验证，配套 APK 的哈希、证书和机型条件见 [测试记录](../../docs/RG34XXSP_SMALL_SCREEN_APPS_20261028.md)。这是应用的官方用户补丁机制，不是 APK 重签名；不要假设其他版本、F-Droid 构建或其他机型支持同样接口。

`2-h700-dpad.lua` 放在应用数据目录 `koreader/patches/`，本机为 `/sdcard/koreader/patches/2-h700-dpad.lua`。启用前退出/停止 KOReader，备份已有同名补丁和 `settings.reader.lua`，再复制文件并重启应用。已有旧试验补丁必须停用，避免重复包装输入函数；本机的 `1-h700-dpad.lua.disabled` 不会执行。

补丁在晚期初始化启用 HAT 十字键、A 确认、B 返回、Select 菜单、Start 文件浏览器、单列文件列表左右分页，以及 EPUB 的 L1/R1 字号减/增。按住 HAT 的计划重复延迟为 450ms，后续间隔 180ms，实体长按手感尚待复核。它不使用摇杆移动、不改变系统按键映射或屏幕密度，也不会给其他应用补遥控器功能。

首轮安装将原返回策略保存到 `h700_dpad_original_back_in_reader`，再把 `back_in_reader` 设为 `filebrowser`。后续显式用户设置保留；L1/R1 调整的是当前可重排书籍字号，未验证 PDF/CBZ 任意缩放。A 可打开阅读调整面板，但其全部控件尚未实现按键可达。

撤回：停止 KOReader，将该补丁改名为 `2-h700-dpad.lua.disabled`，重新启动。撤回补丁不会自动恢复应用偏好；需要恢复原返回策略时，在 KOReader 设置中修改，或在应用停止且已另备份现状后恢复安装前的 `settings.reader.lua`。本机原值是 `previous_location`，最终试验设置与安装前备份均只在本地保留。

升级 KOReader 后应重新测试。补丁依赖 `ffi/input_android`、FocusManager、Menu、ReaderUI 的当前接口；若上游接口改变或出现补丁错误提示，先停用此文件，保留错误记录，不要重签名替换 APK 或清除阅读数据。

上游：[KOReader](https://github.com/koreader/koreader)、[用户手册](https://koreader.rocks/user_guide/)、[用户补丁 API](https://koreader.rocks/doc/modules/userpatch.html)。本配置仅调用其现有接口，原应用许可证和分发来源不变。
