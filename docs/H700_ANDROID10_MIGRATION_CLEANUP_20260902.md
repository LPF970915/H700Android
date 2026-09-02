# H700 Android 10 迁移与清理记录

日期：2026-09-02

## 结果

- 清理对象：98 个文件或目录；
- 实际回收：82.71 GiB；
- D 盘清理后可用空间：约 318.21 GiB；
- `work/` 从约 53.45 GiB 降至约 9.75 GiB；
- `out/` 从约 9.14 GiB 降至约 1.97 GiB；
- `H700_Android_Example/` 从约 55.23 GiB 降至约 23.48 GiB。

清理完成并解压主线源码后的最终存储复核：

- Ubuntu WSL2 已迁至 `D:/Works/H700Android/.wsl/Ubuntu/`；
- D 盘 `ext4.vhdx` 约 119.81 GiB，其中 Android+Longan 工作树约 52 GiB；
- C 盘未发现本项目的大包、失败解压残片或旧 Ubuntu VHDX；
- 2026-09-02 实测 C 盘可用约 117.86 GiB，D 盘可用约 230.53 GiB。

## 已删除

H618：

- 18 个完整源码分卷；
- 工作区中重复的 31.75 GiB 合并源码包；
- raw Android 镜像副本；
- `super.raw`、`super.fex`、`system_a.img`、`vendor_a.img` 中间产物。

Android 11/R36S：

- 原始 3 GiB R36S 整卡镜像；
- 重复的 2.2 GiB raw system 镜像；
- 旧 fix11 raw/gzip system；
- fix2-fix31 重复 64 MiB handoff boot；
- 对应的旧 ramdisk 和解包验证目录。

## 已保留

H616 主资料：

- 完整 `android.tar.gz`；
- 完整 `longan.tar.gz`；
- Android 10 官方压缩镜像和已提取的 vendor/HAL 分析树；
- H700 Longan kernel、DTS、U-Boot 和芯片级配置。

H618 对照资料：

- 约 133 MiB 精选源码/vendor/system 元数据；
- 1267 项常规文件 SHA-256 清单；
- 182 项符号链接清单；
- 原厂源码分卷 MD5 清单；
- 0.54 GiB 官方 Android 12 压缩镜像及 MD5。

Android 11 档案：

- 一个完整的压缩 system 参考镜像；
- 最终 fix32 handoff boot/ramdisk；
- 所有源码脚本、分析文档和关键日志；
- fix51-fix58 H616 图形/音频 payload 与 provenance。

## 可重复执行

清理脚本：`tools/cleanup_android10_migration.ps1`

默认只显示候选项；只有传入 `-Execute` 才删除。脚本验证每个目标的绝对路径都位于
当前工作区内，并始终保留 fix32、H616 主资料、H618 精选集和 Android 11 压缩参考。
