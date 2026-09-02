# R36S Android 11 封存说明

日期：2026-09-02  
最终状态：fix58 已部署，等待一次冷启动验证；不再作为产品主线

## 档案价值

Android 11 分支成功证明了 H700 可以运行 Android init、Binder、zygote64、
system_server、SurfaceFlinger 和 H616 图形候选，并建立了可靠的串口、日志、写入保护与
Linux 自动回退工具。这些成果全部服务于 Android 10 主线。

## 封存原因

原始 system/vendor 来自 R36S LineageOS 18.1，包含 `r36s`、`rk3326`、
`rk30board` 和 Android 11 HAL 假设。fix40 以后为了诊断先后修改或旁路了
SurfaceFlinger、Watchdog、LightsService、DisplayManagerService、BatteryService、
LMKD 和 AudioService。fix58 又把 H616 Android 10 Audio HAL 5.0 接入 Android 11
framework，进一步证明该树已经是跨平台诊断组合，不适合作为可维护产品。

## 后续规则

- fix58 只再执行一次冷启动和日志回收；
- 不再制作 fix59 类型的 Android 11 framework patch；
- 新问题先在 Android 10 原生 framework 上复现；
- Android 11 文件只能用于比较调用顺序、日志格式和硬件事实；
- 任何复制动作都必须证明文件不含 Rockchip/R36S ABI 或属性依赖。
