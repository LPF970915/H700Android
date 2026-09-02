# RGSP H700 Android fix44

日期：2026-08-31

## 实机依据

fix43 已在 RGSP 实机完成一次性启动验证：

- `StartLightsService` 每轮均在 0 ms 完成；
- 不再出现 `Starting com.android.server.lights.LightsService`；
- Watchdog 首错前移到 `DisplayManagerService` 构造函数：

```text
SurfaceControl.nativeGetCompositionDataspaces
  -> SurfaceControl.getCompositionColorSpaces
  -> DisplayManagerService.<init>
  -> SystemServer.startBootstrapServices
```

这是 headless 模式下同步等待未启动 SurfaceFlinger 的同类阻塞。

## 候选改动

fix44 保留 fix42 Watchdog 诊断修改和 fix43 LightsService bypass，并在 headless framework 验证期间：

- 跳过 `DisplayManagerService` 创建；
- 跳过 `setupSchedulerPolicies()`；
- 跳过 `windowManagerAndInputReady()`；
- 跳过 `systemReady()`。

这不是最终显示实现。恢复 SurfaceFlinger 前必须撤销这些 headless bypass，并接入经过验证的 Gralloc/HWC/EGL 组合。

候选文件：

`work/fix44-tools/services-display-bypass.jar`

SHA-256：

`f158b6d77c1ee2b977561939bc6a84088f19ea59119798075dcb2f68128aab27`

本地验证：smali assemble 成功；重新反汇编后不再存在 `DisplayManagerService` 的启动和三处生命周期调用，LightsService bypass 仍保留。

尚未写入 TF2，也未改写 TF1 boot。
