# RGSP UART 首次连接流程

日期：2026-08-29

目标：以只读方式将 RGSP 的 H700 调试串口接到 Windows，保存从 U-Boot、Linux kernel 到 Android early-init 的完整冷启动日志。

## 1. 设备与端子

照片中的 USB-TTL 正面端子从左至右标为：

```text
GND  RX  TX  VCC
```

设备还标有 `1.8V / 3.3V / 5.0V` 电平选择。RGSP 接线前必须先用万用表测量板端 UART 空闲电平，不能仅凭 H700 型号假设。若实测空闲高电平约 `3.3V`，转换器只选择 `3.3V`；确保不会同时打开两个电平档。`VCC` 全程悬空。

杜邦线颜色没有固定意义。接完后用标签或纸条记录每根线对应的信号。

## 2. USB-TTL 单独检测

先不要连接 RGSP：

1. 将 USB-TTL 插入电脑。
2. PowerShell 进入项目目录：

```powershell
Set-Location D:\Works\H700Android
.\tools\capture_rgsp_uart.ps1 -List
```

3. 插入前后对比列表，新出现的 `COMx` 才是 USB-TTL。电脑固有的 `COM1` 不应直接认作它。
4. 如果没有新端口，在设备管理器中查看“端口（COM 和 LPT）”及带黄色感叹号的设备，按转换器实际 USB 芯片安装驱动。

### 可选回环验证

转换器不连主板、不接 `VCC`：

```text
USB-TTL TX ---- USB-TTL RX
```

运行自动回环测试，其中 `COMx` 替换为新出现的端口：

```powershell
.\tools\test_usb_ttl_loopback.ps1 -Port COMx
```

看到 `PASS` 即为通过。回环结束后拔掉 USB，并拆除 TX-RX 短接线。

## 3. 拆机前准备

1. 正常关机，拔掉充电线和 USB。
2. 取出 TF 卡，记录 TF1/TF2 位置；首次测量不需要插 Android 测试卡。
3. 在不拉扯排线的前提下打开后壳。
4. 电池能安全拔下时先拔下；不能安全拔下时，不做蜂鸣/电阻扫描。
5. 拍摄主板正反面高清照片，尤其是成排焊盘、`TX/RX/GND/UART` 丝印、USB 和 microSD 附近。

在没有主板照片和实测值之前，不按网上其他 RG35XX/RGSP 修订版图片盲接测试点。

## 4. 确认 GND

### RG SP V2.0 已确认焊盘

2026-08-29 实机照片确认，主板丝印为 `RG SP V2.0`。以主板元件面朝上、HDMI/USB-C 位于上边、耳机孔位于下边观察，左下角靠近振动马达的三枚竖排通孔从上到下为：

```text
GND
TX
RX
```

实机测量结果：

- 断电时，最上方 `GND` 与 Type-C 金属外壳持续蜂鸣，读数约 `0.6 ohm`；
- 中间 `TX` 未开机约 `-0.01 V`；
- 开机 Logo 阶段约 `3.26 V`；
- Linux 完全启动后约 `3.27 V`。

因此该 `RG SP V2.0` 实机的调试串口按 **3.3 V TTL** 连接。

主板必须完全断电：

1. 万用表黑笔保持 `COM`，红笔保持最右侧 `VΩHz`。
2. 旋钮置蜂鸣/通断档。
3. 一支表笔接 USB、HDMI 或 microSD 金属外壳。
4. 另一支表笔确认其他接口外壳持续蜂鸣、读数接近表笔短接值。
5. 测量 UART 候选焊盘；与多个接口外壳都持续近零欧的点可标记为 GND。

不能在主板接着电池、充电器或 USB 时使用蜂鸣/电阻档。

## 5. 确认 TX 电平

1. 万用表转到白色 `V⎓ 20` 直流电压档。
2. 黑笔固定到已经确认的 GND。
3. 恢复电池或原厂供电并正常开机。
4. 红笔每次只接触一个候选焊盘，记录关机、开机瞬间、Logo 阶段和稳定后的电压。

判断原则：

- 空闲约 `3.3V`，开机期间平均读数有变化：可能是 3.3V UART TX；
- 空闲约 `1.8V`，开机期间有变化：可能是 1.8V UART TX；
- 稳定 `5V`：视为电源点，避开；
- 稳定 `0V`：可能是 GND、RX 或其他信号，不能凭电压单独判定。

万用表只能初筛 TX，最终以串口是否输出可读日志为准。

## 6. 第一次只读连接

全部设备先断电，USB-TTL 也从电脑拔下：

```text
RGSP GND  -------- USB-TTL GND
RGSP TX   -------- USB-TTL RX
RGSP RX   -------- 不接
RGSP VCC  -------- 不接
USB-TTL TX -------- 不接
```

检查没有松散线头碰到相邻焊盘后：

1. USB-TTL 插入电脑。
2. 先启动捕获脚本，其中 `COMx` 替换为实际端口：

```powershell
Set-Location D:\Works\H700Android
.\tools\capture_rgsp_uart.ps1 -Port COMx
```

3. 串口参数已经固定为 `115200 8N1`、无奇偶校验、无硬件流控。
4. 再给 RGSP 完全断电冷启动。
5. 等待进入 Linux 或卡在 Android 启动点后，按 `Ctrl+C` 停止抓取。
6. 日志保存在 `out/logs/uart/rgsp/`。

## 7. 结果判断

| 表现 | 下一步 |
|---|---|
| 从上电即出现可读 U-Boot 文本 | TX、GND、波特率基本正确，保存完整日志 |
| 完全无字符 | 复核公共 GND、交换另一个候选 TX、确认冷启动和 COM 口 |
| 持续乱码 | 优先复核电平与 GND，再测试常见波特率，不向主板发送字符 |
| Linux 中途才开始输出 | 可能接到其他 UART，或 U-Boot 未启用该控制台 |
| 一接线设备就异常 | 立即断电，检查是否误接 VCC、电平档或短接相邻焊盘 |

首次抓日志不需要连接板端 RX。只有在确认电平匹配并确实需要中断 U-Boot 后，才考虑 `RGSP RX <- USB-TTL TX`；这属于下一阶段。

## 8. 本轮需要留档的信息

```text
RGSP 主板版本丝印：
USB-TTL 新增 COM 号：
USB-TTL 选择电平：
GND 测试点及断电通断读数：
TX 测试点：
TX 关机/启动/稳定电压：
串口参数：115200 8N1，无流控
日志文件：
测试所用 TF 卡和 boot 镜像 SHA-256：
```

## 9. 2026-08-29 首次成功记录

- USB-TTL：CH343，Windows `COM4`；
- 回环：`115200 8N1` 通过；
- 接线：只读 `RGSP GND -> USB-TTL GND`、`RGSP TX -> USB-TTL RX`；
- 捕获范围：BOOT0、BL31、U-Boot 2018.05、Linux 4.9.170、BusyBox `/init`、systemd、`ANBERNIC login:`；
- 原厂 root：`/dev/mmcblk0p5`；
- 日志：`out/logs/uart/rgsp/rgsp_uart_20260829_190418_115200.log`；
- 日志大小：10394 bytes；
- SHA-256：`5FC2A3CA3846CB3CB8689FEF00A8A39766D6A9BFD3A3FE7F769DBA4AFC643BEC`。
