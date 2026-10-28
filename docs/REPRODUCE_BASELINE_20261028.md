# 源码恢复与构建边界

标签：`baseline/h700-v5i-usb-network-20261028`。本仓库保存实测修改覆盖层，不是完整 AOSP 或可直接刷卡镜像。

## 验证 Git 快照

需要 Python 3.11+：

```sh
python3 tools/restore_h700_baseline.py
python3 -m unittest discover -s tools -p test_h700_baseline_restore.py -v
```

恢复锁覆盖 364 文件：原 native35 的 99 项证明、当前编辑过的文件、完整固定版 LeanbackIME 和本轮 USB/网络配置；额外保住不在原表中的 vold、StorageManagerService、healthd 等实际源码。日常产品入口是 `android/h700-android10/device/roc/`，冻结覆盖层是 `snapshots/v5i-native35-20261028/`。

冻结覆盖层保留实测文件的原始字节，包括 66 个带原有 CRLF 的文件；Git 属性对该目录关闭自动换行转换。不要格式化快照。新脚本与日常产品配置仍按各自 Git 属性处理，恢复精确源码时以冻结锁为准。

## 外部输入

基础输入详见 [来源记录](H616_ANDROID10_PROVENANCE_20260902.md)：

- H616 `android.tar.gz`：22,273,432,977 字节，MD5 `c5dd785ecd45ca9a2b9c53b1092ee6ec`。
- `longan.tar.gz`：1,405,505,469 字节，MD5 `11a2855d8b5c3430e3dd9dff6f40867e`。
- 硬件 boot/kernel/DTB 以 H700 实机为准，不能整体导入 Orange Pi 启动链。
- Mali/GLES、签名及 ARM grow runtime 见 [本地输入锁](baselines/h700-v5i-usb-network-20261028/local-inputs-lock.json)。私有保全目录含签名私钥，不可提交 GitHub。

厂商源包中的部分 `.git` 指向缺失 `.repo`；现有 WSL 树不能视为可完整 `git diff` 的标准 checkout。冻结点通过文件级 SHA 锁定修改层，基础树仍依赖源码包。

## 恢复到独立 AOSP 树

将基础树解到有空间的 Linux/ext4 路径，先只计划：

```sh
python3 tools/restore_h700_baseline.py --source /path/to/android
```

确认目标后，使用全新、位于源码树外的备份目录：

```sh
python3 tools/restore_h700_baseline.py --source /path/to/android \
  --backup /path/to/h700-before-restore --apply
```

工具核验全部冻结文件、拒绝越界/符号链接、先备份所有被覆盖文件，再写入和校验。它不构建、访问设备、写卡或删除输入。再次计划应显示零文件待恢复。

按输入锁恢复私有二进制和执行权限。不要恢复最终覆盖层后再盲目串行重放 `prepare_*`；它们针对不同旧版本，可能正确拒绝最终文件。

## 构建

当前 WSL 树为 `/home/lpf/h700-android10/android`。资源足够时才用：

```powershell
.\tools\build_h700_low_pressure.ps1 -Targets systemimage,vendorimage -Execute
```

保持 CPU 0-1 亲和性、合计一个 CPU、`-j1`、6GiB RAM、512MiB swap、nice 19 和空闲 I/O。本轮冻结未重新编译系统、重封装镜像或刷整卡。

第二轮空间清理已删除原生树 `out/`，保留完整源码和工具链。下次构建需重新生成中间文件，不能依赖旧增量缓存。整 IMG 与最终分区 raw 的无损压缩包和原文件现状见 [空间复核](SPACE_REVIEW_20261028.md)；需要 raw 输入时先解压并核验原始 SHA，不能把 gzip 直接当作 raw 文件传给历史封装器。

## 当前整镜像复现缺口

冻结之后的 APK/摇杆模块构建由 [RG34XXSP 开发记录](RG34XXSP_DEVELOPMENT_20261028.md) 单独描述。恢复冻结快照会回到旧基线，不能代替同步当前日常产品增量；原 364 文件锁不随新功能改变。

`tools/package_rgsp_v5g.py` 仍固定要求 SHA 为 `fed34834...` 的 v5f 整镜像 seed；此次盘点未找到该文件。保留的 v5i 包含当前硬件前缀和原厂空数据/ROMS，但历史脚本不会直接接受它作为替代。

不能宣称仅从 Git clone 就能一键重建相同 IMG，也不能把未来封装输入适配当成本次已验证内容。保留唯一 v5i IMG、最终 native35 阶段及私有保全目录；以后适配 seed/封装时仍需重新做文件系统、组件、范围读回和整镜像 SHA 校验。
