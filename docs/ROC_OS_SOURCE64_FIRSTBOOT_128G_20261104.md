# Source64 Clean Test1：128GB 首启与运行修正

用户将新整卡镜像刷入 128GB TF 卡并明确授权连接查询、发现问题自行修复。本轮通过 USB/ADB 在精确 CID、软件标记、容量和关键文件哈希守卫下进行；未重刷、重新格式化或迁移工作卡。私有身份、网络、日志、截图、原始文件与失败采样均留在 `out/source64-firstboot-128g-20261104/`，不入 Git。

## 已确认状态

- 新源码系统完成启动，两个 ABI 的 zygote 均运行；实际 system_server 为 ELF64 `app_process64`。
- 128GB 卡的 p7 已自动增长，文件系统总量 113,592,975,360 字节；内部共享存储与 `/data` 使用同一文件系统，无 p8 ROMS。
- SurfaceFlinger 报告 ARM / Mali-G31 / OpenGL ES 3.2，远程画面为 AT4K 与樱花壁纸。
- 用户确认初次下拉栏、鼠标可用；随后报告 Wi-Fi 开关回弹、Select 在 Wi-Fi 页面失败并影响后续桌面呼出。该回归单独保留，不能沿用早先通过结论。

## 已修复

| 问题 | 实际原因与修正 | 验证 |
| --- | --- | --- |
| Wi-Fi 开启即关闭 | 驱动和 wlan0 已存在，但 VINTF 缺失 supplicant 声明，框架按 1.0 接口查询空列表；补入实际运行的 1.2 ISupplicant | 重启后保持开启；用户连接成功；HTTP/HTTPS 204；关闭重开后自动重连并 VALIDATED |
| 默认 HOME 未保持 | 工厂初始化后 HOME 角色为空，解析回 ResolverActivity；明确绑定 HOME 角色，并同步工厂源码 | 多次重启后解析到 AT4K，无需重新选择 |
| Select 鼠标失效 | Settings 叠加层存在焦点释放、重复投递和遗留按键状态；实际日志还确认 MENU 回退事件保留扫描码 310，却没有 FLAG_FALLBACK，旧热键逻辑因此取消长按 | Navigation16 按扫描码归一回退；修正焦点/事件处理，加入无回退标志及组合键保留测试；Wi-Fi→桌面反复长按/B 退出通过受控事件测试，重启后复测通过；HAT 移动及松手停止通过 |
| 重启后权限控制器崩溃 | BSP 后续启动快捷路径跳过父 zygote 字体初始化，出现 `gDefaultTypeface` 断言 | 在持久属性加载后、zygote-start 前选择完整预加载；从后续启动状态连续重启，权限管理界面能打开，相关启动崩溃缓冲区为空 |
| 部分 ADB 命令失败 | ramdisk 对 `/dev` 的普通 bind 不携带子 devpts 挂载；`exec-out` 报 fork ENODEV | 在 post-fs-data 挂载 devpts，普通 exec-out 恢复，两次重启后挂载保留 |

当前卡是 **Clean Test1 + vendor supplicant 清单修正 + system 启动 RC + data Navigation16 + HOME 角色设置**，不能称为未修改 Test1。vendor/system 文件修改前后保存证据并回读，挂载恢复只读；旧系统 Navigation14 APK 和中间 Navigation15、失败跟踪均保留。

Navigation16 在包更新后仍为启用的无障碍服务，原 system APK 不替换。只修正独立产品的派生导航源码，原 BSP/原产品保持。长按仍为 Select 单独按住约两秒后松开，不引入摇杆快捷键；组合键取消规则保留。

## 编译与复审

最终增量构建 `h700-low-pressure-20261104-030629` / `images-result-v14.json` / `prepare-v17.json` 通过。最终复审 `h700-low-pressure-20261104-031118` / `round2-audit-v10.json` 通过 120 项检查及 21 项主机用例；35 个根、545 个 ELF 的启动依赖无缺项。资源限制保持单核、CPU0–1、nice19、6GiB/512MiB、idle IO。

早期无 USB 枚举后，设备自然出现 ADB，并非通过改电脑驱动恢复。诊断中原始 exec-out 捕获失败、睡眠状态下的无效注入、切桌面尚未稳定时被正确取消的长按，以及实际失败的 Navigation15 Wi-Fi 测试均保留；不将无效测试计为产品回归通过。

## 边界与后续

- 2026-11-04 后续：用户回应本轮 WLAN/桌面长按、移动/B 复测请求“select有效”，已补实体确认；原 acceptance.json 是此前冻结结果，新证据见 [TF2 增量](ROC_OS_SOURCE64_TF2_20261104.md)。
- 本轮未重新封装整卡 gzip；此前交付的 Test1 压缩镜像保持不可变，重新刷旧文件不会自动包含这些修正。源码及新分区产物已同步修正。
- 未完成 TF2 实卡、深度休眠、断电恢复、充电温控、长期稳定性或发布安全验收。
- 原始与修正后的镜像、失败构建/审计、备份及 SPACE_REVIEW 用户改动全部保留。
