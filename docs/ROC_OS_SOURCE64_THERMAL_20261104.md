# Source64 Thermal HAL 2.0 接入

2026-11-04。用户授权“补齐 Thermal HAL”。只在独立 Source64 产品新增实现，不替换旧 BSP 模块、kernel/DTB，不刷卡、不重封整卡镜像。当前工程系统仍为 Permissive；本轮不是 enforcing 或全部温控保护验收。

## 实现

`device/roc/roc_os_source64/Thermal/` 提供真正的 HIDL 2.0 服务，包含旧1.0查询、温度/阈值/冷却状态查询、过滤、变化回调及回调断连处理。CPU使用量由 /proc/stat 换算为毫秒，未制造假数据。

按 type 动态发现CPU、GPU、电池、VE和DDR温区，不固定 thermal_zone 编号；毫摄氏度转换为摄氏度，缺失/异常值为NaN。读取内核已有 passive/critical trip：前两档映射LIGHT/MODERATE，critical映射SHUTDOWN；其他阈值和VR阈值留NaN。此映射是初始产品策略，持续负载下的热等级、迟滞与UX仍待校准。

CPU cpufreq冷却设备报告CPU类型；devfreq不能仅凭名字判定GPU，因此报告COMPONENT。没有假造机身温度，也没有臆设电池充电或关机阈值。服务每2秒采样，读数变化至少0.1°C或热等级变化时通知回调；RPC在锁外调用，清除失效回调。温区和冷却设备只读，不操作频率、充电或唤醒锁。启动限定rgsp/rg34xxsp，进程降为system UID/GID并清空补充组。

## 构建与审计

最终构建 `h700-low-pressure-20261104-182059`、`images-result-v17.json`、`prepare-v20.json` 成功；22项主机用例通过，包含模拟文件下的温度单位、60/70/115°C边界、NaN、非法值、设备编号变化及冷却状态越界。

`h700-low-pressure-20261104-183100` / `round2-audit-v12.json` 通过123项检查；36启动根、548 ELF、631命名空间状态及41个早期对象无依赖缺项，Thermal服务22个依赖状态无未解析强符号。真实分区含唯一Thermal2.0声明、服务/RC及正确exec标签。资源限额保持单核、CPU0–1、-j1、nice19、6GiB/512MiB、idle IO；最终构建9分34秒，峰值5GiB/416MiB swap，审计1分29秒、峰值4.3GiB/swap0。首轮构建及所有中间产物保留。

## 当前卡运行验证

在精确卡身份、容量、软件标记和关键SHA守卫下备份原文件后，仅新增Thermal ELF/RC，并补vendor VINTF与文件上下文。运行守卫已加入这4项，vendor恢复只读。

Android10框架首次HAL连接失败后不主动重试，HIDL管理器也缓存清单。因此本轮受控重启HIDL管理器及Android框架；不是整机重启，kernel boot ID和vold PID保持。先将临时 no_physical_media 限制写入并确认落盘，阻止StorageManager重建时自动挂载TF2；验证后撤回，TF2全程保持卸载，原用户状态恢复。

当前服务通过受控后台方式在 hal_thermal_default 域以UID/GID1000运行；init RC已写卡并纳入源码，但当前init未重新解析该新增RC，**冷启动由init自动拉起仍待验**。没有以当前后台启动冒充冷启动持久化通过。

框架从 HAL Ready:false 变为 true，并显示 ThermalHAL 2.0 connected:yes。5温区、2冷却设备可查询；四次独立dump的缓存CPU读数由57.086→55.466→53.846→51.254°C变化，与直接查询读数有正常采样时差，说明缓存由回调更新，而非仅dump时同步查询。该段是框架启动后的自然降温，未加热或注入高温。

另外受控终止并重新启动一次HAL，框架成功重连，后续温度继续更新；这一段system_server、vold和kernel均保持，崩溃缓冲区为空。它验证死亡重连，**不是init自动重启验收**。原亮度100/手动0/超时60000/Asleep、AT4K和bringup锁保持。未请求任何人工操作。

## 尚未验收

- 冷启动自动拉起、断电/救援及最终同镜像回归。
- 实际过热限频、降温恢复、临界关机；仅主机模拟文件验证边界，没有改真实 emul_temp 或覆盖系统热等级。
- 电池温度准确性、完整充电保护、机身温度与持续负载下的热策略/迟滞。
- 深睡/待机耗电、SELinux enforcing及完整Thermal VTS。

当前是前一修正Test1再加本轮4项vendor增量。源码和新分区产物已同步；旧gzip不含这些修正，镜像未上传。证据见[脱敏结果锁](baselines/roc-os-source64-thermal-r1-20261104/acceptance.json)，原始身份、备份、临时启动/回退及诊断记录仅留忽略的out/source64-thermal-20261104。
