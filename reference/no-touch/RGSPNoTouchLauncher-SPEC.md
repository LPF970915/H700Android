# RGSPNoTouchLauncher 最小规格

## 目标

为 720x480、无触摸、约 1 GB RAM 的 H700 Android 提供一个可完全用 DPAD 操作的常驻启动器。

## 页面

1. 首页：应用、设置、文件、关机四个主入口。
2. 应用页：纵向列表，支持 L1/R1 翻页。
3. 设置页：显示、声音、输入、网络、电源、关于。
4. 错误页：启动失败时显示原因和 `BACK` 返回。

## 按键契约

```text
DPAD_*     移动焦点
DPAD_CENTER/ENTER  打开
BACK       返回
HOME       回到首页
MENU       打开当前项目菜单
PAGEUP/DOWN 快速滚动
```

## 实现约束

- 原生 Activity + RecyclerView/Leanback 风格控件。
- 不使用触摸事件作为必经路径；`onTouch` 只能作为可选调试便利。
- 焦点项目必须有可见边框、状态色和无障碍描述。
- 不预加载大图；图标采用小尺寸缓存，列表按需加载。
- 启动器退出/应用切换走显式 supervisor IPC，不直接依赖 SDL 前端抢占设备节点。

## 验收用例

- 冷启动 10 秒内落到首个入口。
- 仅使用 D-pad、A、B、Start 完成打开设置、修改音量、返回首页。
- USB 键盘方向键、Enter、Esc、Home 分别对应 DPAD、确认、返回、主页。
- 失去焦点、应用崩溃、输入设备断开时仍可回到首页。
