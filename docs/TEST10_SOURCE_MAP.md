# Test10 组件源码入口

更新于 2026-11-17。本页说明当前整卡的源码组成与复核入口；使用方法见[当前状态](CURRENT_STATUS.md)，镜像与离线检查见 [Test10 记录](ROC_OS_H700_STICK_RECOVERY_TEST10_20261117.md)。

## Android 用户空间

[公共构建指南](PUBLIC_BUILD.md)通过 [source-manifest.json](../build-support/public/source-manifest.json)解析覆盖层、基础源码复制关系和指定镜像输入。当前清单包括 Navigation18 与完整 ViewRoot 修复，保持其冻结 SHA256，不为本次说明调整旧收据。

| 内容 | 入口 |
| --- | --- |
| 导航状态、方向键连发与生命周期处理 | [Navigation 覆盖层](../build-support/public/overlay/device/roc/roc_os_source64/Navigation) |
| 框架摇杆转键、方向键交付保护 | [ViewRootImpl.java](../build-support/public/overlay/frameworks/base/core/java/android/view/ViewRootImpl.java) |
| 公共导航测试 | [run_source64.py](../tools/navigation_tests/run_source64.py)、[框架保护测试](../tools/navigation_tests/test_native_joystick_candidate.py) |
| 实际生产 framework／ART 集成与审计 | [build_navigation_test6.py](../tools/release/build_navigation_test6.py)、[audit_navigation_test6_art.py](../tools/release/audit_navigation_test6_art.py) |

## 通用启动、面板与翻盖

| 内容 | 入口 |
| --- | --- |
| 十二型号、分辨率、杆数及面板关系 | [models.py](../tools/boot_selector/twelve_model/models.py) |
| 机型菜单、三档音量试屏与加载显示 | [selector_rescue.c](../tools/boot_selector/twelve_model/selector_rescue.c)、[build_native_rescue.py](../tools/boot_selector/twelve_model/build_native_rescue.py) |
| 保存默认、单次启动与返回菜单 | [boot_state_preview.c](../tools/boot_selector/twelve_model/boot_state_preview.c)、[selector_init_rescue.sh](../tools/boot_selector/twelve_model/selector_init_rescue.sh) |
| 启动前面板配置与交接 | [h700_manual_selector_twelve.py](../tools/release/h700_manual_selector_twelve.py)、[early_profile_bridge_rescue.py](../tools/boot_selector/twelve_model/early_profile_bridge_rescue.py) |
| Lid4 翻盖适配 | [build_lid_twelve.py](../tools/boot_selector/build_lid_twelve.py)、[LidProfile.java](../tools/boot_selector/twelve_model/lid/LidProfile.java) |

Lid4 由构建工具在保留的基础 Lid 源码副本上生成；仅查看基础应用的旧 versionCode 不能代表当前整卡实际 Lid4。菜单试屏只循环三个代表，最终机型依然使用相应电气初始化。

## 摇杆与交换空间

| 内容 | 入口 |
| --- | --- |
| 当前恢复驱动 | [h700_stick_axes.c](../tools/input_profiles/stick_recovery_v3/h700_stick_axes.c)、[策略](../tools/input_profiles/stick_recovery_v3/h700_profile_policy.h) |
| 真实候选 C 与冻结旧 C 负面对照 | [run_host.py](../tools/input_profiles/stick_recovery_v3/run_host.py)、[test_recovery.c](../tools/input_profiles/stick_recovery_v3/test_recovery.c) |
| 新模块编译与两份加载脚本生成 | [build.py](../tools/input_profiles/stick_recovery_build_v1/build.py)、[prepare_loaders.py](../tools/input_profiles/stick_recovery_build_v1/prepare_loaders.py) |
| 默认 2GiB swap | [swap_prefix.sh](../tools/memory_swap_v1/swap_prefix.sh)、[test_swap.py](../tools/memory_swap_v1/test_swap.py) |
| Test10 定点封装与独立完整验证 | [package.py](../tools/input_profiles/stick_recovery_package_v1/package.py)、[verify.py](../tools/input_profiles/stick_recovery_package_v1/verify.py) |

驱动、早期 helper 和 Android loader 需要同批更新。L3／R3 不再依赖 ADC 放行；受限恢复不写 CCU、不强开时钟、不恢复 GPIO 复用，实际效果尚待硬件确认。swap 前缀相对 Test9 逐字保留，两份脚本仅替换固定的新模块 SHA256。

## 在公开源码上运行主机回归

Linux 中安装 GCC、Python 和 JDK 后，可通过资源限制包装器执行。各次 `--output`／`--work` 必须使用新的目录，保留旧结果。路径示例可替换；以下测试不访问掌机，不启用主机 swap。

```sh
python3 -B tools/public_build/validate_manifest.py

# 下列命令由普通用户运行；需要已可用的 sudo/systemd 环境。
sudo -v
bash tools/public_build/run-limited.sh \
  python3 -B tools/public_build/test_public_build.py

bash tools/public_build/run-limited.sh \
  python3 -B tools/navigation_tests/run_source64.py \
  --javac /path/to/jdk/bin/javac --java /path/to/jdk/bin/java \
  --work /path/to/fresh-navigation-tests

bash tools/public_build/run-limited.sh \
  python3 -B tools/input_profiles/stick_recovery_v3/run_host.py \
  --output /path/to/fresh-stick-tests
```

摇杆主机测试预期 26 个候选场景、5 个旧代码负面对照、802 项检查，硬件 API 采用模拟。导航主机测试也有虚拟 Android 边界，不能替代真机。

## 作者流程的边界

Test10 封装脚本绑定固定的 Test8 父镜像、既有 BSP 和历史审计产物，部分路径为作者缓存。面板机器码证明还依赖本地的探针与 FDT 审计缓存。公开这些源码使实现和变更可审阅，**不代表当前已提供从干净 clone 一步重建相同 Test10 整卡的便携流程**。

公共 Android 用户空间构建入口继续使用指定 0.0.1 启动资产；独立重编全部启动组件和移植 Test10 作者流程是另外的工作。完整整卡离线检查通过与实体机型验收分别记录，历史失败和冻结证明继续保留。
