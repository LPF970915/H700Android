# 0.0.1 重启日期回退与网络校时

2026-11-14，用户反馈重启后总回到11月7日，联网不能自动校时。本轮保留当前启动，完成只读分析、设备网络探测、单项持久配置及当前时间校正；没有重启或生成新系统镜像。

## 查到的事实

自动时间和自动时区均为1，时区为 Asia/Shanghai；不是设置未开启。`ntp_server` 与 `ntp_timeout` 没有用户覆盖。实际 Android10 的 `NtpTrustedTime` 默认请求 `time.android.com`，单次超时5秒。开机日志在单调时钟约55、129、315、405秒均出现 `SntpClient request time failed: SocketTimeoutException: Poll timed out`，NTP缓存年龄和精度为 Long.MAX_VALUE。系统默认网络已连通并通过验证。

`NewNetworkTimeUpdateService` 失败按60秒短周期重试3次，之后退回24小时周期。该机制解释了“联网后也长时间不自动同步”，不能从请求超时推断服务器全球故障或网络具体哪个环节阻断。

从同一台34XXSP的网络实测SNTP：默认服务器未返回，`ntp.aliyun.com` 两次取得48字节合法响应，版本4、server mode4、有效stratum、originate字段与本次请求一致，时间与主机接近。最终探测以设备端printf构造二进制请求、base64回传响应，避开Windows文本转换；早期exec-out不发送stdin及二进制输出不可靠的试验均保留，不能把其空响应当作网络失败。最终结果为 `out/time-sync-20261114/device-ntp-probes.json`。

日期回退有明确匹配项：实际 `ro.build.date.utc` 对应2026-11-05，实际 `/system` mtime为 **2026-11-07 23:10:30 +08:00**。`AlarmManagerService.onStart()` 会把过早时钟提升到构建日期、系统目录时间戳、Build.TIME三者最大值；Build.TIME本身来自构建日期。因此在RTC读到过早日期时，确实会落到11月7日。未抓到本次重启前后RTC值及该推进日志，故该机制与反馈吻合，但触发前提尚未实测。RTC sysfs和/proc读取受权限保护，未提权，不能据此判定RTC硬件损坏。

源码检查范围：Native Android10 `frameworks/base/core/java/android/util/NtpTrustedTime.java`、`NewNetworkTimeUpdateService.java`、`AlarmManagerService.java`及实际Source64对应副本；保留BSP的RTC代码仅作辅助，未证明与实机预编译内核逐字相同。

## 本机处理与边界

1. 将唯一持久设置 `global ntp_server` 从null改为 `ntp.aliyun.com`，读回一致。自动时间、时区均保持原值。
2. 使用标准 `cmd alarm set-time` 将当前系统时钟校正至主机时间；校正前设备约慢110秒，之后差值929ms，包含秒级读取舍入和USB传输延迟。此次是手动一次校正，不能称为自动NTP校时通过。
3. 同一boot、user/Enforcing和导航服务均保持；没有重启framework、系统或修改系统分区。

这个版本 `NtpTrustedTime` 的server字段为final，单例仅首次初始化读取设置；运行中改设置不能热切换，开关自动时间也仍请求旧服务器。它没有新版Android的force-refresh shell接口。因此 **下次正常开机才加载新服务器，重启后自动同步、RTC写入及断电保时尚未验收**。本机持久覆盖不等于所有已发布镜像都改变了默认值；正式镜像默认源/备用源策略仍需后续整合。

配置回退仅需 `settings delete global ntp_server`，下一次开机恢复Android默认源；不需改自动时间或时区。原配置、探测包、日志和变更收据保留在 `out/time-sync-20261114/`，总结为 `result.json`。

## 0.0.2 集成补充

本文件记录前述分析或原位更新阶段；后续0.0.2已完成本地整卡封装与独立核验，详见[版本说明](ROC_OS_0.0.2_20261114.md)。完整新卡首启、自动校时和低概率频闪仍保留各自验收边界。
