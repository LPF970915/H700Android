# RC4 真机启动、操作与 Wi-Fi 保留性记录

当前卡由用户烧录 RC4 整卡，SHA-256 为 `a7394633a4e8ebaf2d64c6af9eec6c2eab53cebe4c1154ba77232731d7e0c644`。首次报告停 Logo 后，电脑端 USB 重新插拔恢复认证连接；读到实际 RC4、user、Enforcing 和 `boot_completed=1`，系统截图已为 Android 页面。此轮没有修改源码、system/vendor、策略或镜像来让系统进入桌面。

已确认的结果：

- 首次初始化记录 `Defaults complete; mode=fresh`，导航与合盖服务自动启动，无需手动启用导航。用户实物确认 Home 下拉、Select 鼠标、菜单十字键正常。
- 用户实物确认亮度逐档变暗/变亮、B 返回正常。
- 正常重启后，初始化记录 `mode=preserve-existing`，导航、合盖和温控自动运行；用户确认开盖亮屏、A 解锁和操作正常。真实 Hall 计数 sleep/wake 各 1，读取与电源调用错误均为 0。这不计作深睡验收。
- Mali-G31 GLES 正常，Thermal HAL Ready，CPU/GPU/VE/DDR/电池五项温度均有有限读数；各次采样崩溃缓冲区为空。
- 九个 shell 可读的关键静态文件与实际交付分区提取文件哈希一致，并在第一次正常重启前后保持。两项 HAL 执行文件的设备端哈希读取被策略拒绝，未为验证而放宽权限；其主机分区字节链、实际进程运行与 HAL 注册另有记录。

## Wi-Fi：当前卡保留性通过，首次干净写入原因仍开放

第一次联网通过 VALIDATED，但其后缓冲写出现 `WifiConfigStore` / `AtomicFile` 的 IOException，提示无法创建 `/data/misc/wifi/WifiConfigStore.xml`。第一次正常重启后已保存网络为 0，未自动重连。该异常文本会掩盖最初的 FileNotFoundException 原因，目前不能据此断言是目录、DAC、标签或文件系统的哪一种问题。

检查确认 system_server 包含 wifi 组，实际策略允许所需的 wifi_data_file 目录和文件操作；userdata 为 rw ext4，没有独立 Wi-Fi 临时挂载。没有因此加入宽泛 allow、修改目录权限或提取密码。

用户重新连接相同网络后，配置多次写入完成（约 17～27 毫秒），网络再次 VALIDATED。随后进行第二次正常重启：新的 boot ID、`boot_completed=1`，已保存网络数 1，自动连接并再次 VALIDATED。当前卡上的重新保存和重启保留性通过；**首次干净启动时那次写入失败的机制尚未定位，也没有通过重新连接或第二次重启来消除这条失败记录**。正式发行前仍需重复干净首次连接的保存测试。

公开结果在 `docs/baselines/roc-os-user-rc4-runtime-20261107/acceptance.json`。含网络名称/IP、boot ID、截图和完整日志的证据仅保存在本地忽略目录 `out/roc-os-user-rc4-firstboot-20261107/`；没有读取或导出 WLAN 密码。

本轮没有新编译、封装、刷卡、上传镜像或改变设备安全状态。源输入和旧失败证据均保留。完整电源/深睡、音频及外设、恢复、许可、首次 Wi-Fi 写入原因与最终同镜像发行验收仍未收口。
