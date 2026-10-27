# 工具入口与范围

先看 [当前基线](../docs/CURRENT_BASELINE_20261028.md) 与 [保留清单](../docs/STORAGE_RETENTION_20261028.md)。

| 类别 | 入口 | 边界 |
| --- | --- | --- |
| 快照核验/恢复 | `restore_h700_baseline.py` | 默认只读；`--apply --backup NEW_DIR` 才改源码，不访问设备 |
| 恢复回归 | `test_h700_baseline_restore.py` | 真实快照与临时目录 |
| 构建 | `build_h700_low_pressure.ps1` / `.sh` | 固定限额；默认 dry-run |
| 原生阶段 | `stage_rgsp_v5g.py` | 名称遗留，实际版本由输入决定；新输出目录，不覆盖最终阶段 |
| 历史封装 | `package_rgsp_v5g.py` | 仍依赖已缺失的 v5f seed；本轮未重封装 |
| Java 导航测试 | `runtime_nav_trial/tests/` | 离线几何/身份测试；build.ps1 另建试验 APK，不应直接替换原生包 |
| 历史原机审核 | `settings_nav_probe/`、`rgsp_debug_session.py`、`rgsp_adb.ps1` | 默认旧 COM4/IP/序列号，不能直接用于新机 |
| 本轮诊断 | `trial_34xxsp_usb_configfs.sh`、`NetworkEndpointProbe.java` | 保留过程；USB 试验仅对应特定旧启动状态，修复后不能盲目重跑 |
| 离线恢复 | `prepare_v5i_wifi_adb_recovery.py`、`apply_v5i_wifi_adb_recovery.ps1` | 精确匹配 v5i 分区；后续文件变化后旧块回退必须拒绝 |
| 旧烧录/修复/清理 | 根目录及 `write_*` / `recover_*` / `cleanup_*` | 历史布局和设备绑定，不是当前默认入口 |

操作前显式指定并核对设备序列号。两台机器可报告相同产品名。保持单控制者和单被动观察器，不并发打开串口，不盲目重放输入。

USB 试验脚本还要求显式设置 `H700_EXPECTED_SERIAL`，不会默认绑定公开报告之外的个人设备身份；已修复的系统不满足该试验的旧状态前置条件。
