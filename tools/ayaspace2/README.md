# Pocket Museum 的 H700 / Android 10 测试适配

只处理用户提供且 SHA-256 固定为 `205cbf8b87d3b696b3c3873dbaa0ad47fbe0e57acce8ca208961a7aea476df38` 的 0.3.3 APK。源文件留在本地下载目录；本目录不包含原 APK、第三方反编译源码、模型、媒体、游戏或签名私钥。

构建依赖现有受保护的 AOSP JDK/SDK、固定 apktool、GSI API 检查输入和本地原 APK。不能仅从 Git clone 独立重建。先读工作区基线/保留政策，然后通过低压力入口运行：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets H700AyaspaceInspect -Execute
.\tools\build_h700_low_pressure.ps1 -Targets H700AyaspaceCompat -Execute
py -3 tools/ayaspace2/test_sql_compat.py
```

审计目标创建新的 `inspect-v1`，已有目录会拒绝覆盖。构建使用该只读反编译输入，每轮创建新的 `build-vN`；`REVISION` 标识输出版本，已有同名 APK 不应覆盖。保留失败轮次。入口保持 CPU 0–1、合计 1 CPU、RAM 6GiB、swap 512MiB、nice19、idle I/O；没有完整 AOSP/Godot 源码重编。

修改范围：

- 直接调整二进制 manifest：API29、legacy 文件权限、去除 `android.uid.system`，保留无关资源索引。
- 将实际调用的新版文件权限、卷目录、启动/全屏/系统栏、键盘布局、窗口尺寸、震动接口换成 API29 实现。
- 在应用内识别 H700，系统机型属性和 SELinux 不变；当前试验不代表 enforcing SELinux 下的全部厂商功能通过。
- 对两条固定的 identification_history UPSERT 做事务内等价改写，保留 promoted 标记；其他 SQL 原样执行。测试直接读取 Java 中的 SQL，与原 UPSERT 比较 243 组三步序列及回滚结果。
- 仅对 ANBERNIC-keys 的物理 A / scan304，在前端和游戏 Activity 内改为 BUTTON_A；其他按键保持原语义。
- 游戏 Activity 内短按 Select+Start 转为返回键以打开暂停；1.5秒组合窗口，避免将单独长按 Select 呼出的系统鼠标误作此组合。

签名为独立普通应用测试签名，私钥/口令仅在受保护本地目录；不是系统平台签名。所有原 native 库、assets、资源逐条 SHA 对照保持不变。APK 本身不含本轮游戏样本和外置媒体包。运行验收及限制见 `docs/RG34XXSP_AYASPACE2_ANDROID10_20261101.md`。
