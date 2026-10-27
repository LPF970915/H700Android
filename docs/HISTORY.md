# 历史内容查询

旧版本、旧文档、早期试验和一次性部署工具已从当前分支移除。它们仍完整保存在公开冻结标签 [`baseline/h700-v5i-usb-network-20261028`](https://github.com/LPF970915/H700Android/tree/baseline/h700-v5i-usb-network-20261028)，不再复制成当前目录内的另一份备份。

查询历史文件不会改工作区：

```sh
git fetch origin tag baseline/h700-v5i-usb-network-20261028
git show baseline/h700-v5i-usb-network-20261028:docs/H700_DPAD_WIFI_AUDIT_20261023.md
git show baseline/h700-v5i-usb-network-20261028:docs/RG34XXSP_H700_SYSTEM_HARDWARE_BASELINE.md
git log --all --oneline
```

该标签包含旧的 Android 11/R36S、H618 参考、v5c/v5e/v5f 说明、原始输入标定和导航修复历史、失败/恢复工具、旧测试及 APK 工具。历史脚本中的串口、设备身份、分区布局和前置状态不一定适用于当前机器，不能因能取回就直接执行。

当前 v5i/native35 源码快照、组件哈希、验收摘要和恢复工具继续保留在当前分支。大型旧阶段只保留小型证明，已删除的分区镜像不在 Git 中，详见本轮清理记录。
