# 0.0.3 组件源码入口

更新于 2026-11-17。本页从 Test10 源码地图继续维护，列出正式 0.0.3 的实现与依赖入口。使用方法见[当前状态](CURRENT_STATUS.md)，发行身份与封装范围见 [0.0.3 说明](ROC_OS_0.0.3_20261117.md)。旧 Test10／Test11 源码和证明保留各自目录。

## Android 用户空间

[公共构建指南](PUBLIC_BUILD.md)通过 [source-manifest.json](../build-support/public/source-manifest.json)解析覆盖层、基础源码复制关系和指定镜像输入。当前覆盖层版本为 0.0.3，已包含 Navigation18 和 ViewRoot 修复；更新后的输入检查单独记录，不修改冻结历史收据。

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

Lid4 由构建工具在保留的基础 Lid 源码副本上生成；基础应用的旧 versionCode 不代表整卡实际 Lid4。菜单试屏只循环三个代表配置，最终型号使用自己的面板初始化。

## 摇杆与交换空间

| 内容 | 当前入口 |
| --- | --- |
| ADC 控制位修复驱动 | [h700_stick_axes.c](../tools/input_profiles/stick_recovery_v4/h700_stick_axes.c)、[策略](../tools/input_profiles/stick_recovery_v4/h700_profile_policy.h) |
| 实际候选 C 与冻结旧 C 负控 | [run_host.py](../tools/input_profiles/stick_recovery_v4/run_host.py)、[test_recovery.c](../tools/input_profiles/stick_recovery_v4/test_recovery.c) |
| 模块编译与两份加载脚本生成 | [build.py](../tools/input_profiles/stick_recovery_build_v2/build.py)、[prepare_loaders.py](../tools/input_profiles/stick_recovery_build_v2/prepare_loaders.py) |
| 默认 2GiB swap | [swap_prefix.sh](../tools/memory_swap_v1/swap_prefix.sh)、[test_swap.py](../tools/memory_swap_v1/test_swap.py) |
| Test11 集成封装与独立验证 | [package.py](../tools/input_profiles/stick_recovery_package_v2/package.py)、[verify.py](../tools/input_profiles/stick_recovery_package_v2/verify.py) |

方向 ADC 检查使用实际 H700 模式位 18～19 与启用位 16，保留其他控制位。L3／R3 与方向采样独立；有界恢复不写 CCU、不强开时钟、不恢复 GPIO 复用。用户已确认该 Test11 修复在 RG35XX H 有效。驱动、早期 helper 和 Android loader 须配套更新；默认 2GiB swap 前缀按字节继承。

## 正式 0.0.3 封装

| 内容 | 入口 |
| --- | --- |
| 版本属性定点封装 | [package_003.py](../tools/release/package_003.py) |
| 独立整卡验证 | [verify_003.py](../tools/release/verify_003.py) |
| 资源限制包装器 | [package_003.ps1](../tools/release/package_003.ps1) |
| 源码版本一致性检查 | [check_003_source.py](../tools/release/check_003_source.py) |
| 正式收据生成 | [record_003.py](../tools/release/record_003.py) |
| 机器可读发行身份与验收 | [0.0.3.json](../build-support/releases/0.0.3.json)、[acceptance.json](baselines/roc-os-003-20261117/acceptance.json) |

正式包以精确 Test11 为父，仅修改 `/system/build.prop` 两处等长版本字符，其余 raw 字节保留。公共源码覆盖版本同步为 0.0.3，源清单与公开验证另行更新；Test11 冻结收据不回写。

## 主机回归入口

Linux 中安装 GCC、Python 和 JDK 后，可通过资源限制包装器运行。每次输出与工作目录使用新路径，保留旧结果。测试不访问掌机，不启用主机 swap。

```sh
python3 -B tools/public_build/validate_manifest.py

sudo -v
bash tools/public_build/run-limited.sh \
  python3 -B tools/public_build/test_public_build.py

bash tools/public_build/run-limited.sh \
  python3 -B tools/navigation_tests/run_source64.py \
  --javac /path/to/jdk/bin/javac --java /path/to/jdk/bin/java \
  --work /path/to/fresh-navigation-tests

bash tools/public_build/run-limited.sh \
  python3 -B tools/input_profiles/stick_recovery_v4/run_host.py \
  --output /path/to/fresh-stick-tests
```

当前摇杆回归预期 38 个候选场景、6 个冻结旧代码负控、1846 项检查，并模拟真实保留位读回行为。硬件 API、导航时钟和部分 Android 边界采用测试替身，主机检查不能替代实体机型覆盖。

## 作者流程的边界

Test11 封装仍绑定固定 Test8 父镜像、BSP 和历史审计产物，部分路径为作者缓存；面板机器码证明也依赖既有探针与 FDT 审计。0.0.3 再绑定精确 Test11 做版本定点更新。公开源码供实现和变更审阅，不代表干净克隆能一步重建同字节正式整卡。

公共 Android 用户空间入口继续使用指定 0.0.1 启动资产。完整整卡离线检查、用户实测反馈与独立公开重编分别记录，历史失败及冻结证明继续保留。
