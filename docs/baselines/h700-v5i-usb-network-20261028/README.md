# h700-v5i-usb-network-20261028

标签：`baseline/h700-v5i-usb-network-20261028`。状态入口：[CURRENT_BASELINE](../../CURRENT_BASELINE_20261028.md)。

| 文件 | 内容 |
| --- | --- |
| `source-lock.json` | 364 个冻结源码的路径、大小、权限、SHA |
| `v5i-stage-source-proof.json` | 原 native35 的 99 项源码证明 |
| `components-v5i.json` | 原 v5i 的 42 项组件 SHA |
| `image-manifest.json` | 未上传镜像的身份、范围哈希、版本边界 |
| `software-validation-summary.json` | 旧 RGSP 的软件可达性覆盖摘要 |
| `device-validation-summary.json` | 新机 USB/网络/重启与原组件复核摘要 |
| `evidence-index.json` | 本地证据路径、大小、SHA；原日志不公开 |
| `local-inputs-lock.json` | Git 不含的恢复输入、封装缺口 |
| `host-test-results.json` | 本轮离线恢复及既有主机测试结果 |

原 v5i IMG：32,434,554,368 字节，SHA `3fd34fef4d5a2275f14023dba5dc488330ab0669a50889e8b748e30c9f3e68cd`，未包含本轮 USB/网络配置。当前卡已验证正常内核重启，未做本轮断电冷启动或完整 MTP 传输验收。

历史报告的中间失败字段不能覆盖最终结论，摘要通过也不能扩张为所有硬件与应用业务均通过。
