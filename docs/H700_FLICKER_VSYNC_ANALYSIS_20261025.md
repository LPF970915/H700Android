# H700 Android 10 屏幕闪烁专项分析与修复建议

日期：2026-10-25
对象：RGSP（`5c001089d750c872012`）/ RG34XXSP，Allwinner H700，Android 10
状态：**排查与实机取样完成；仅向设备推送过取证/实验工具，未改系统、未改源码、未重编内核**
更新：2026-10-25 14:30，新增 §2.7 实时取样、§2.8 GPU 合成失败证据、§4.5/§4.6 非内核方案与尝试记录；
修复顺序改为“先 S1（GPU 合成）后内核 VSYNC”。
用途：供 GPT 复核后，按本文决定“先修 GPU 合成还是先修内核 VSYNC”

---

## 0. 结论摘要

1. 闪烁不是应用画错：历史闪烁期间连续 12 张软件截图完全一致，问题发生在“合成之后”。
2. 2026-10-25 14:08 做了 69 秒实机同步取样（其中 29 秒用真实 HAT 连续操作）：
   DE 全程 `unblank`、`err` 恒为 1、亮度/PWM 不变、无电源键事件、无 `set mode` 切换 ——
   **背光瞬断和电源键熄屏基本可以排除**。
3. 本轮最强的新证据：**界面更新时 SurfaceFlinger 的 GPU 合成本身失败**。
   `libGLES_mali.so` 报 `Crop rectangle dimensions not equal to logical buffer dimensions`，
   `RenderEngine` 随后 `Failed to bind framebuffer! Aborting GPU composition`。
   该错误只在操作时出现（约 1 次/秒），空闲时为 0；本次开机累计 12,244 次。
4. 结构缺陷仍然存在：内核没有 `vsync proc N` 消费者线程，HWC 只能用 timerfd 软件 VSYNC。
   但它解释的是“提交没有帧同步”，不能单独解释“整帧黑”；**当前优先怀疑第 3 条**。
5. 因此修复顺序调整为：
   **先做非内核的 GPU 合成修复（S1/S2）**，验证闪烁是否消失；内核 VSYNC 作为第二阶段，
   避免一次改两个变量。
6. 两次纯运行时尝试都被阻断（详见 §4.6）：换壁纸因 `app_process` 拿不到 binder 被 KILL；
   强制 HWC 在 SF/HWC 里都没有任何运行时开关。
7. 另有一条独立线索：13:31 出现过 4 次 POWER 键睡眠/唤醒循环，需与显示问题分开判断（见 §2.6）。

---

## 1. 现象与验收定义

用户描述（RGSP 与 RG34XXSP 均出现）：

- 屏幕“频闪为黑色”，整屏黑一下再恢复；
- 静止一小会可以稳定显示；
- 一操作（按键、翻页、切换界面）就再次频闪。

验收定义（修复通过必须同时满足）：

- 连续操作 10 分钟，肉眼无黑闪（由用户确认，不能只凭日志）；
- `vsync` 计数按 ≈59/s 增长，`vsync_skip` 不再单调增长；
- 3 秒内能收到 `VSYNC0=` uevent；
- 60 次 `FBIO_WAITFORVSYNC` 总耗时 ≈ 1 秒（而不是现在的几百微秒）；
- HWC 日志不再打印 `RGSP software VSYNC enabled`；
- A 解锁、电源菜单、Wi-Fi、亮度调节无回归。

---

## 2. 已确认事实与证据

### 2.1 面板与显示时序（事实）

| 项 | 值 | 来源 |
|---|---|---|
| 分辨率 | 720×480 | `/sys/class/disp/disp/attr/sys` |
| 像素时钟 | 38461 ps | `rgsp_vsync_probe` framebuffer 参数 |
| ht / vt | 820 / 536 | 同上 |
| 帧周期 | **16,904,379 ns（59.156270 Hz）** | 由上述参数计算 |
| 背光 | PWM 20000 ns / 3906 ns，亮度 50 | `/sys/kernel/debug/pwm` |
| 面板驱动 | `rg34xxsp_v1`，RGB/HV | 设备树 `lcd_driver_name` |

注意：GPT 已把 HWC 的软件 VSYNC 周期从写死的 16949152 ns 改为 16904379 ns（`eac4cb95…`），
这是正确的校准，但没有改变“没有硬件同步”这一事实。

### 2.2 硬件 VSYNC 链路：消费者线程不存在（关键事实）

设备上逐个读取 186 个 `/proc/*/comm`，**没有任何名字包含 `vsync` 的线程**；
`ps -A` 中也只有 `[kthreadd]`，没有代码里应创建的 `[vsync proc 0]`。

`/sys/class/disp/disp/attr/sys` 实测（2026-10-25 13:40 左右）：

```text
screen 0:
de_rate 696000000 hz, ref_fps:59
mgr0: 720x480 fmt[rgb] cs[0x204] ... err[0] force_sync[0] unblank direct_show[false] iommu[1]
	lcd output	backlight( 50)	fps:59.8	 720x 480
	err:1	skip:0	irq:1875566	vsync:3	vsync_skip:41486
```

- `vsync:3` 从开机到现在没有变化；
- `vsync_skip:41486` 持续增长；
- `err:1` 说明本次开机累计 1 次显示错误（不是每次闪烁都有）。

`rgsp_vsync_probe` 实测：

```text
120 次 FBIO_WAITFORVSYNC 总计 274,625 ns   （本应约 2 秒）
3 秒 uevent: 1 条消息，其中 VSYNC 消息 0 条
```

### 2.3 代码路径（事实，源码位置）

内核（`/home/lpf/h700-android10/longan/kernel/linux-4.9`）：

| 位置 | 内容 |
|---|---|
| `.../disp2/disp/dev_fb.c:22` | `#define VSYNC_NUM 4`，环形队列只有 4 格 |
| `.../disp2/disp/dev_fb.c:854` | `drv_disp_vsync_event()`：写队列、`wake_up_process(vsync_task)`，队列满返回 -1 |
| `.../disp2/disp/dev_fb.c:985` | `vsync_thread()`：唯一消费者，调用 `vsync_proc()` 发 `VSYNC%d=` uevent |
| `.../disp2/disp/dev_fb.c:2100` | `kthread_create(vsync_thread, i, "vsync proc %ld")`，仅在 probe 时创建 |
| `.../disp2/disp/de/disp_display.c:768` | `sync_event_proc()` 中断侧：`vsync_event_en && vsync_event` 时统计 vsync/skip |
| `.../disp2/disp/de/disp_display.c:695` | `bsp_disp_vsync_event_enable()` 只置标志位，不创建线程 |
| `.../disp2/disp/dev_disp.c:3283` | `DISP_VSYNC_EVENT_EN` ioctl 入口 |

结论链：**probe 时线程没建成功（或建后退出）→ 队列 4 格写满 → 之后每次中断都走 -1 → `vsync_skip` 增长、`vsync_cnt` 停在 3 → uevent 永远不发。**

HWC（`work/h700-source-analysis/h616/android/hardware/aw/hwc2`）：

| 位置 | 内容 |
|---|---|
| `de2family/DisplayOpr.cpp:1831` | `diplayToScreen()`：`DISP_SHADOW_PROTECT` → `DISP_LAYER_SET_CONFIG2` → `DISP_HWC_COMMIT` → 解除 protect |
| `tools/h616-hwc-rgsp-software-vsync.patch` | timerfd 软件 VSYNC，`period = displayConfigList[...]->vsyncPeriod` |
| 运行属性 | `persist.vendor.hwc.software_vsync=true` |

`DISP_SHADOW_PROTECT` 只保证寄存器写入的原子性，**不提供帧边界**；提交发生在任意扫描位置。

### 2.4 背光与显示增强（排除项）

- 250 次采样（51.48 秒）：`brightness=50`、PWM `20000/3906 ns` 全程不变；
- `enhance_mode=0`、`enhance_bright/contrast/saturation` 均为 0，`displayservice` 未启用内容增强；
- 因此“内容自适应背光/CABC”不是本次闪烁的已证实原因，但不能排除低亮度下的 PWM 瞬断（见 §4.3）。

### 2.5 合成器输出正常（事实）

历史闪烁期间连续 12 张软件截图 SHA-256 完全相同（`4d3d2f67…`），内容正常。
SurfaceFlinger 侧没有画黑，黑发生在 DE/面板/背光之后，或发生在扫描输出的某一帧。

### 2.6 电源键事件（独立线索，待区分）

`/proc/interrupts`：`axp20x-pek-dbf = 7`、`axp20x-pek-dbr = 7`。

日志在 13:31:52–13:31:59 出现 4 个完整循环：

```text
Waking up from Asleep (reason=WAKE_REASON_POWER_BUTTON)
Brightness [128] reason changing to: 'manual', previous reason: 'screen_off'
1.2 秒后
Going to sleep due to power_button
Brightness [0] reason changing to: 'screen_off'
```

如果当时没有人按电源键，那么“黑闪”可能就是 PEK 误触发导致的熄屏/亮屏，而不是显示链路；
两者必须分开验证，不能混为一谈。判定方法：让 `getevent -lt /dev/input/event0` 与肉眼观察同时进行，
若黑闪时没有 event0 事件，则是显示问题；若有，则先修输入/PMIC。

### 2.7 69 秒实机同步取样（2026-10-25 14:08）

工具：`tools/flicker/capture_live.sh`（已推送到 `/data/local/tmp/capture_live.sh`，只读采样）。
同时采集：`/sys/class/disp/disp/attr/sys`、背光节点、`logcat -b all`、`getevent`。
取样期间用 `/data/local/tmp/nav-hat.sh` 注入 18 轮方向键（约 29 秒），模拟真实操作。

结果（310 个样本 / 69.0 秒，约 4.4 Hz）：

| 通道 | 结果 |
|---|---|
| `unblank` | **310/310 全部为真**，没有一次 blank |
| `err` | 恒为 1（开机累计，不随操作变化） |
| `vsync` / `vsync_skip` | 恒为 3 / 仅 +299 |
| `fps` | 恒为 59 |
| LCD IRQ | +4109，约 59.55 Hz |
| 背光 | 节点为空；`attr/sys` 中 `backlight( 50)` 不变 |
| 电源事件 | **0 次** sleep/wake，0 次 `set mode` |

结论：在这 29 秒真实操作期间，**背光、电源键、DE blank 三条通道都没有异常**。
如果用户此时确实看到黑闪，它发生在软件计数器看不到的层面。

证据：`out/flicker-live/samples.txt`、`logcat.txt`、`input.txt`、`sf.txt`。

### 2.8 GPU 合成失败：与操作严格同步的新证据

取样期间出现成对错误：

```text
E/        (1513): Crop rectangle dimensions not equal to logical buffer dimensions
E/RenderEngine(1513): Failed to bind framebuffer! Aborting GPU composition for buffer (0xea52cb00)
```

用 `strings` 核对厂商库，确认第一句来自 **`libGLES_mali.so`**（不是 SF、不是内核）：

```text
Crop rectangle dimensions not equal to logical buffer dimensions
Crop rectangle exceeds physical buffer dimensions
```

按分钟统计出现次数：

- 只在注入按键的 **14:08:34–14:09:12** 出现，约 **1 次/秒**；空闲时段为 0；
- 本次 `logcat` 缓冲区内累计 **12,244 次**（从 05:11 开机起就有）；
- `dumpsys SurfaceFlinger` 的 `hwc:` 段列出 5 个层，合成类型均为 `CLIENT (1)`（GPU 路径），
  同时 `HWC missed frame count: 4428`、`GPU missed frame count: 5259`；
  另一处 `compositionengine::Layer` 段显示壁纸层为 DEVICE，两段属于不同快照，需在实施前再取一次同刻对照。

补充排查：

- 失败 buffer 指针 `0xea52cb00` 长时间不变，更像 SF 复用的 **client target**，而不是某个应用层；
- `ImageWallpaper` 层是 1243×1024、缩放 0.58，但在设置页 `VisibleRegion count=0`，
  说明它不是本场景的触发者，换壁纸的收益很低（见 §4.6）。

推断：每次界面更新 → SF 走 GPU 合成 → Mali 在导入 client target 时拒绝 → `drawLayers` 返回
`BAD_VALUE` → 该帧没有正常合成/呈现 → 用户看到黑闪；空闲时不更新，所以稳定。
这与“一操作就闪、静止就稳、截图正常”三条现象同时吻合。

---

## 3. 根因判断

| 编号 | 判断 | 置信度 | 依据 |
|---|---|---|---|
| **R0** | **GPU 合成失败导致整帧丢失**：Mali 拒绝 client target 的 crop/几何，`drawLayers` 返回 BAD_VALUE | **高（当前首选）** | §2.8：错误与操作同步、约 1 次/秒、空闲为 0；错误串来自 `libGLES_mali.so` |
| R1 | 内核 VSYNC 消费者缺失，HWC 只能软件定时，提交与面板不同步 | 高（结构性缺陷） | §2.2、§2.3 直接证据；但单独不能解释“整帧黑” |
| R2 | 不同步导致提交落在扫描中途，DE 换帧时出现整帧黑 | 中 | R1 + 截图正常；缺少同步观测 |
| R3 | DE 带宽不足/欠载（AFBC 关、双显示、`BandwidthLimited=338800`） | 低中 | 操作时内存压力增大，但无欠载计数可证 |
| R4 | PEK 误触发熄屏 | 待定 | §2.6；本次 69 秒取样中为 0，需专项复现 |
| R5 | 低亮度 PWM 瞬断 | 低 | 采样期间亮度/PWM 恒定 |

**当前最可信的修复目标是 R0（非内核）**：先让 GPU 合成失败不再丢帧，或让这些层改走 HWC/DEVICE。
R1 是真实存在的结构缺陷，但应作为第二阶段单独验证，避免一次改两个变量；
R3/R4/R5 在 R0 修复后若仍复现，再分别处理。

---

## 4. 修复方案

### 4.1 方案 A（第二阶段）：内核补齐 VSYNC 消费者

改动只在 disp 驱动，不动面板时序、PWM、DTB、boot 参数。

**A1. 懒创建线程（最小改动）**

在 `dev_fb.c` 增加：

```c
s32 drv_disp_vsync_task_ensure(u32 sel)
{
    if (g_fbi.vsync_task[sel] && !IS_ERR(g_fbi.vsync_task[sel]))
        return 0;
    char name[24];
    snprintf(name, sizeof(name), "vsync proc %u", sel);
    g_fbi.vsync_task[sel] = kthread_create(vsync_thread,
                                           (void *)(unsigned long)sel, name);
    if (IS_ERR(g_fbi.vsync_task[sel])) {
        s32 err = PTR_ERR(g_fbi.vsync_task[sel]);
        g_fbi.vsync_task[sel] = NULL;
        pr_err("vsync proc %u create failed: %d\n", sel, err);
        return err;
    }
    wake_up_process(g_fbi.vsync_task[sel]);
    pr_info("vsync proc %u created lazily\n", sel);
    return 0;
}
EXPORT_SYMBOL(drv_disp_vsync_task_ensure);
```

在 `disp_display.c` 的 `bsp_disp_vsync_event_enable()`（line 693）里，`enable=true` 时调用：

```c
if (enable && gdisp.init_para.vsync_task_ensure)
    gdisp.init_para.vsync_task_ensure(disp);
```

`init_para.vsync_task_ensure` 在 `dev_fb.c` probe 时赋值（与 `vsync_event` 同一处，line 2167 附近）。
`DISP_VSYNC_EVENT_EN` 来自 ioctl，属于进程上下文，`kthread_create` 安全。

**A2. 兜底：中断侧不依赖线程**

若 A1 仍失败（例如 kthread 创建受限），在 `sync_event_proc()` 里改为 `schedule_work()`，
由 workqueue 调用 `vsync_proc(disp)` 发 uevent。注意 `kobject_uevent_env()` 不能在中断/tasklet 里调用，
必须走 workqueue。同时把“队列满就丢弃”改成“满时覆盖最旧一格并唤醒消费者”，避免再次永久停摆。

**A3. 可选：新增 `DISP_GET_CUR_LINE` ioctl**

给 HWC 一个可轮询的扫描行接口，作为 A1/A2 之外的独立兜底；
不是必须，若 A1 通过就不做，避免扩大内核改动面。

### 4.2 修复后的 HWC 切换

内核生效后：

1. 把 `persist.vendor.hwc.software_vsync` 置 `false`（产品或 build.prop），
2. 重启 `android.hardware.graphics.composer@2.2-service` / SurfaceFlinger 使 HWC 重新 init，
3. 确认日志不再出现 `RGSP software VSYNC enabled`，且 `vsync` 计数增长。

回退：属性改回 `true` 并重启 HWC 即可恢复旧行为，不需要回刷 boot。

### 4.3 方案 B（不推荐单独使用）：HWC 侧对齐

当前内核没有暴露扫描行，`FBIOGET_VBLANK` 被 `#if 0` 关闭，
所以 HWC 无法获得真实帧边界。只有先做 A3 才谈得上 B。
**不建议在没有 A1/A2 的情况下单独改 HWC**，那只是换一种猜。

### 4.4 方案 C（临时缓解，不解决根因）

- 打开 `debug.hwui.use_buffer_age=true`、`use_partial_updates=true`，减少每帧全屏重绘；
- 操作期间降低动画/减少全屏刷新；
- 这些只能降低黑闪概率，不能作为验收依据。

### 4.5 非内核修复 S1/S2（当前优先，待复核后实施）

**S1（推荐，改动最小）：GPU 合成失败时不要丢帧**

在 SurfaceFlinger 的合成路径上，`RenderEngine::drawLayers()` 返回 `BAD_VALUE` 时：
保留上一次成功的 frame，或改用 HWC/DEVICE 合成该帧，而不是把空/旧 buffer present 出去；
同时把失败次数打到 `dumpsys SurfaceFlinger` 便于回归。
只改 framework（system 分区），不改 boot、不改面板。

**S2：让这些层在 HWC 里走 DEVICE**

修改 `hwcomposer.cupid.so` 的 `validateDisplay`，对当前被标为 CLIENT 的常规 UI 层返回 DEVICE，
避免进入 Mali 的 client target 路径。改动在 vendor 分区，影响面比 S1 大。

两者都以“错误计数不再增长 + 用户连续操作 10 分钟无黑闪”为通过标准；
S1 优先，因为不动 vendor、可一条命令回退。

### 4.6 本轮已做的运行时尝试与阻断原因（均未改变设备）

| 尝试 | 做法 | 结果 |
|---|---|---|
| 换壁纸（去掉 1243×1024 缩放层） | 编译 `tools/flicker/WallpaperSwap.java`（app_process + 反射 `ActivityThread.systemMain`），先备份再设 720×480 | **失败**：`systemMain` 触发 `Bad file descriptor`，进程被 SIGKILL；未修改壁纸。且该层在设置页 `VisibleRegion=0`，本来就不是本场景触发者 |
| 强制只走 HWC 合成 | 查 SF 全部 33 个 `debug.sf.*` 属性、HWC 二进制字符串 | **不可行**：没有任何“禁用 GPU 合成/强制 HWC”的运行时开关；合成策略在 SF 内部 |

结论：这两个方向都不是“改个属性”能完成的，必须改代码（S1/S2）。

---

## 5. 验证方案（必须按序）

### 5.1 修复前基线（已具备，可直接复用）

- `out/flicker-investigation-20261025/after-native-hwc-reboot/`：250 次采样、`vsync:3`、uevent 0；
- `out/flicker-investigation-20261024/`：历史基线；
- `out/flicker-live/`：2026-10-25 14:08 的 69 秒同步取样（310 样本、29 秒真实按键、GPU 合成失败 12,244 次）；
- 本次补充：`err:1`、186 个线程无 vsync、13:31 PEK 循环、Mali 拒绝 client target 的错误串。

### 5.2 内核修复后的判据

```sh
# 1) 线程存在
cat /proc/[0-9]*/comm | grep -i vsync

# 2) 计数增长（两次采样间隔 5 秒，差值应约 295）
cat /sys/class/disp/disp/attr/sys | grep 'vsync:'

# 3) uevent 真实产生
#    rgsp_vsync_probe 观察 3 秒，vsync_messages 应约 177

# 4) 等待真实生效
#    60 次 FBIO_WAITFORVSYNC 总耗时应约 1 秒（当前约 0.27 ms）

# 5) HWC 不再软件定时
logcat -d | grep -i 'software VSYNC'
```

### 5.3 回归项

- 连续操作 10 分钟无黑闪（用户确认）；
- A 解锁、电源菜单关机/重启、Wi-Fi 开关与重连、亮度调节、休眠/唤醒；
- 30 分钟浸泡无 `err` 增长、无 SurfaceFlinger 重启；
- 34XXSP 同镜像复测（同一内核，应同步生效）。

### 5.4 S1/S2 的验证判据

```sh
# 1) GPU 合成失败计数（修复后 10 分钟操作内应保持 0 或不增长）
logcat -d -b all | grep -c 'Aborting GPU composition'

# 2) SF 的 composition type（期望不再全部 CLIENT，或失败时不再丢帧）
dumpsys SurfaceFlinger | grep -E 'composition type=|missed frame'

# 3) 与 2.7 相同方式的 69 秒同步取样，确认 unblank/err/亮度无异常
sh /data/local/tmp/capture_live.sh /data/local/tmp/flicker-after-s1 70
```

通过标准：错误计数为 0 或不随操作增长 + 用户连续操作 10 分钟无黑闪 + 上述 5.3 回归全部通过。
若错误计数仍增长但闪烁消失，说明 SF 已正确回退，记录为“S1 生效但 Mali 缺陷仍在”。

---

## 6. 风险与回退

| 风险 | 说明 | 缓解 |
|---|---|---|
| 内核源码与实际运行内核不一致 | 运行内核为 `4.9.170 #2 SMP PREEMPT Wed Jun 24 19:15:50 CST 2026`，gcc 5.3.1；源码树为 `/home/lpf/h700-android10/longan` | 先原样编译一次，确认能启动且 `uname`/版本字符串一致，再打补丁 |
| 线程创建时机 | probe 过早可能失败 | A1 改为 ioctl 时懒创建；保留 A2 兜底 |
| uevent 风暴 | 60Hz uevent 对 CPU 影响 | 只发给订阅者；观察 30 分钟 CPU 占用 |
| 休眠/唤醒 | vsync 线程在 suspend 时的行为 | 回归休眠/唤醒 20 次 |
| 刷 boot 失败 | 设备无法启动 | 保留原 boot.img；走已有多卡/UART 恢复流程 |
| 与 GPT 构建冲突 | 共用构建机 | 内核构建用独立输出目录，错开 system/vendor 构建时段 |

**不改变**：面板时序、PWM 频率/极性、DTB、boot 参数、分区布局。

---

## 7. 对 34XXSP 的影响

- 34XXSP 当前运行的是同一套 H700 内核与 `rg34xxsp_v1` 面板配置，因此内核修复对它同样生效；
- 但摇杆映射仍缺失（`NavigationService` 在非 `rgsp` 设备上 `disableSelf()`，`ANBERNIC-keys.kl` 无摇杆轴），
  属于另一项工作，不与闪烁修复混合；
- 若 34XXSP 的闪烁表现与 RGSP 不同（例如更轻），修复后仍需分别确认。

---

## 8. 待确认问题

1. probe 阶段 `kthread_create` 到底返回了什么？需要在原内核上加一行 `pr_info` 验证，不能靠猜。
2. 13:31 的 4 次 POWER 循环是否有人为按键？需要一次 `getevent -l /dev/input/event0` 与肉眼同步的复现。
3. `err:1` 对应哪一次提交？可在修复前用 `dmesg`/`logcat` 对照时间点。
4. 修复后若仍有轻微闪烁，再评估 R3（DE 带宽），不要一次改多个变量。
5. **需要一次“用户看到黑闪”与 `logcat` 的同步记录**：当前只有“错误与操作同步”的统计相关性，
   还没有“某一次黑闪 = 某一次 GPU 合成失败”的逐帧对应；这是 S1 实施前最好的补充证据。
6. S1 由谁实施、何时有可用的构建窗口（不能与 GPT 的 system/vendor 构建并发）。

---

## 9. 复现命令（只读）

```sh
# 显示状态与计数
cat /sys/class/disp/disp/attr/sys

# VSYNC 线程是否存在
cat /proc/[0-9]*/comm | grep -i vsync

# 电源键中断计数
grep -i 'axp20x-pek' /proc/interrupts

# 原始电源键事件（需要人眼同步观察）
getevent -lt /dev/input/event0

# HWC 是否仍在软件定时
logcat -d -b all | grep -i 'software VSYNC\|sunxihwc'

# 69 秒同步取样（背光/显示计数/logcat/input）；脚本在 tools/flicker/capture_live.sh
adb push tools/flicker/capture_live.sh /data/local/tmp/capture_live.sh
adb shell sh /data/local/tmp/capture_live.sh /data/local/tmp/flicker-live 70
```

---

## 10. 交接执行顺序

**第一阶段（非内核，优先）：GPU 合成失败**

1. 复核 §2.8 的日志与 `out/flicker-live/` 证据，确认“错误只在操作时出现”这一结论。
2. 实施 S1：`RenderEngine::drawLayers()` 返回 `BAD_VALUE` 时不丢帧（保留上一帧或改走 HWC），
   并在 `dumpsys SurfaceFlinger` 暴露失败计数；只重编 framework，只替换 system 分区。
3. 用 §5.4 的判据验证；若闪烁消失但错误计数仍增长，记录为“S1 生效、Mali 缺陷仍在”，再决定是否做 S2。
4. S2（HWC 走 DEVICE）只在 S1 无效时做，改 vendor `.so`，单独回退。

**第二阶段（内核，确认第一阶段无效后再做）**

5. 先原样编译 `/home/lpf/h700-android10/longan`（入口 `build.sh`），确认产物能启动、`uname` 与版本串一致；
   这一步不改任何代码，只验证源码树与运行内核匹配。
6. 在 `sunxi_fb_probe()` 的 `kthread_create` 后加一行 `pr_info`，启动一次读 dmesg，确认返回的是 ERR 还是成功；
   **不要在不知道原因的情况下直接改逻辑**。
7. 按 A1 打最小补丁（懒创建），编译内核，只替换 boot 分区；system/vendor 不动。
8. 开机后按 §5.2 的四项判据验证；全部通过再关 HWC 软件 VSYNC。
9. 若 A1 无效，回退 boot，改用 A2（workqueue 投递）；A3/B 只在 A1/A2 都无效时再做。
10. 修复确认后，把 `persist.vendor.hwc.software_vsync` 的默认值改为 false 并纳入最终镜像；
   旧镜像与旧 boot 保留可回退。

**不要**在同一个版本里同时改内核、HWC 和显示配置，否则无法归因。
