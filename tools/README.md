# 当前工具入口

当前状态见 [基线](../docs/CURRENT_BASELINE_20261028.md)，历史删除项从 [旧标签](../docs/HISTORY.md) 查询。

| 用途 | 入口 | 范围 |
| --- | --- | --- |
| 冻结源码核验/恢复 | `restore_h700_baseline.py` | 默认只读；显式 `--apply --backup NEW_DIR` 才恢复源码，不访问设备 |
| 恢复回归 | `test_h700_baseline_restore.py` | 真实快照、临时目录、备份和篡改拒绝 |
| Java 按键几何 | `test_navigation_geometry.ps1` / `navigation_tests/` | 方向、指针与控件身份，只编译主机 class |
| 被动观察器 | `settings_nav_probe/Dump.java`、`build.ps1` | 不注入触摸或按键；保留 29 项主机安全测试 |
| 历史控制辅助核心 | `settings_nav_probe/audit.py`、`files.py`、`graph.py` | 控制后端仍绑定旧 RGSP/COM4，先适配身份与 transport，不能直接用于新机 |
| 资源受限构建 | `build_h700_low_pressure.ps1` / `.sh` | 默认 dry-run，固定一个 CPU、6GiB、512MiB swap、-j1 |
| 基础源码解包 | `prepare_h616_android10_source.ps1` / `.sh` | 先核验包与空目标目录；不在当前树重放 |
| 新阶段生成 | `stage_rgsp_v5g.py` | 名称遗留，版本由输入决定；不能覆盖最终阶段 |
| 历史封装 | `package_rgsp_v5g.py` | 仍依赖缺失的 v5f seed，未作为当前可执行打包流程 |
| 存储保护/增长 | `test_rgsp_roms.py`、`test_rgsp_auto_grow.py`、`test_rgsp_dirty_fat.py` | 保留启动卡保护、增长及脏 FAT 回归；测试使用自有临时夹具 |
| 增长 runtime | `build_rgsp_grow_helpers.sh`、`prepare_rgsp_grow_runtime.sh`、`rgsp_grow_*` | 源码与 runtime 构建，不自动写卡 |
| 格式只读检查 | `android_bootimg.py`、`android_sparse_to_raw.py`、`android_lp_extract.py`、`fdt_dump_props.py`、`inspect_rgsp_apk.py` | 文件格式/分区/设备树/APK 检查工具，各自 CLI 决定本地输出 |
| 显示排查 | `flicker/`、`analyze_rgsp_flicker_video.py` | 后者使用保留的 `out/video-analysis-tools/` 依赖 |
| 网络端点排查 | `NetworkEndpointProbe.java` | 正常证书校验的 HTTP/HTTPS 只读探测，不改变检测设置 |
| AT4K 补丁源 | `at4k/` | 当前产品 APK 的来源/重建记录；apktool 为外部依赖 |
| RG34XXSP 增量 | `build_h700_apps.py`、`build_h700_kernel_input.py` | 仅从低压力入口调用；构建 APK、输入模块和观察夹具，不自动安装 |
| 内核 ABI 核验 | `h700_kernel_abi.py` | 固定 kernel SHA；比较真实导出、参考模块、本地 genksyms 和全部模块导入，拒绝不匹配 |
| 控制器鼠标验收 | `input_probe/verify_controller_mouse.py` / `PointerProbe.java` | 显式 USB 身份；默认只核对，加 `--execute` 后只对自有夹具注入并核对触点结束 |
| 电源/音频盘点 | `audit_h700_runtime.py` | 只读；原始输出私有，保留退出码，软件清单不能代替实体验收 |
| 导航小更新/回退 | `update_h700_navigation.py` | 默认只计划；显式执行时核对本机及前/后 APK SHA，再保留数据安装，拒绝未知版本 |

`build_rgsp_compact_image.py`、`audit_rgsp_single_card_boot.py`、`patch_ramdisk.py` 和 `rgsp_single_card_init.sh` 因存储策略测试和只读格式解析的依赖而保留；它们的历史整镜像 CLI 不代表当前 seed 已齐备。

旧烧录、整卡写入、UART 上传、热更新、失败恢复和一次性回归脚本已移出当前工作树。不要为取一个参考而把整套历史脚本还原回 main。

设备操作始终显式指定并核对序列号，保持单控制者和单被动观察器。清理之后的设备增量及专用构建输入见 [开发记录](../docs/RG34XXSP_DEVELOPMENT_20261028.md)。

## 保留测试的运行方式

Windows 的基础恢复与观察器检查：

```powershell
py -X utf8 tools/restore_h700_baseline.py
py -X utf8 -m unittest discover -s tools -p test_h700_baseline_restore.py -v
py -X utf8 -m unittest discover -s tools/settings_nav_probe -p 'test_*.py' -v
.\tools\test_navigation_geometry.ps1
```

存储与 shell 夹具测试需在安装了 g++、dosfstools 的 Linux/WSL 中，从仓库根目录运行：

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

本轮本地主机共通过 37 项根级与 29 项观察器 Python 测试；其中两个真实 FAT 捕获夹具只在本地保存，公开克隆没有这些捕获时相应测试可跳过。上述测试不访问实体存储卡；Java 入口不依赖 Android SDK，也不构建 APK。
