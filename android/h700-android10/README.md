# H700 Android 10 产品与源码覆盖层

这是当前 Android 10/API29、32 位用户空间产品配置与实测修改覆盖层，完整 AOSP 在 WSL。

- `device/roc/rgsp/`：产品、输入、键盘、系统/应用资源与 USB/网络配置。
- `device/roc/h700-common/`：共用构建配置。
- `snapshots/v5i-native35-20261028/`：364 个冻结源文件，保留原字节和上游通知。
- 源码锁：`docs/baselines/h700-v5i-usb-network-20261028/source-lock.json`。

源自 H616 Android 10 的芯片级 HAL/BSP，与当前 H700 实机 boot/kernel/DTB 配套使用。不能整体导入 Orange Pi 启动链、设备树或电视产品配置。

原 Settings-v5c 重复快照、Android 11 scaffold 与历史 prepare 链已经移出当前分支。LeanbackIME 完整固定版输入已包含在当前覆盖层，不需重放旧的拉取/补丁脚本。

恢复与输入缺口见根目录 `docs/REPRODUCE_BASELINE_20261028.md`。新原生改动须纳入新的 Git 覆盖层和证明，避免只保存在无法完整 git diff 的 WSL 树中。
