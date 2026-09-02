# H700 投影仪首次连接电脑与系统信息采集

日期：2026-08-31  
目标板：照片所示 `H21S-700-V3.0`，Allwinner H700，三星 eMCP，板上标有 `DC12V`。

## 0. 先区分两种连接

- **USB-TTL 串口**：读取 BOOT0、U-Boot、Linux/Android 启动日志，必要时进入串口 shell。
- **网络 SSH/ADB**：设备成功启动并联网后读取完整文件和软件信息。

USB-TTL 不是供电器，不能给投影仪主板供电。投影仪只使用原装 `DC12V` 输入或原装电源模块；USB-TTL 的 `VCC` 永远悬空。

## 1. 主板 UART 焊盘

第一张照片中央可见三个金色测试焊盘，丝印直接标出 `RX / TX / GND`。以照片当前方向观察，从左到右是：

```text
RX   TX   GND
```

实际接线前仍以焊盘旁边的丝印为准，不要按杜邦线颜色判断信号。

## 2. 断电接线前的安全状态

1. 投影仪关机，拔掉 `DC12V` 适配器。
2. 拔掉所有 USB、HDMI、TF 卡和网线。
3. 不要触碰投影光源、电源板或任何标有高压的区域。
4. USB-TTL 从电脑拔出。
5. 不要把 USB-TTL `VCC` 接到投影仪任何焊盘。

## 3. 先测 UART 电平

投影仪主板不能直接假定与 RGSP 一样是 3.3 V。先用万用表确认：

1. 黑表笔插 `COM`，红表笔插 `VΩHz`。
2. 投影仪完全断电时，用蜂鸣档确认 UART `GND` 与 USB/HDMI 金属外壳或大面积地之间导通。
3. 切换到白色 `V⎓ 20` 直流电压档。
4. 黑笔固定在 UART `GND`。
5. 接通原装 `DC12V`，正常开机。
6. 红笔只碰 UART `TX`，记录待机、开机 Logo、稳定运行时电压。

初筛：

| TX 空闲电平 | USB-TTL 电平档 |
|---|---|
| 约 `3.3 V` | 选择 `3.3 V` |
| 约 `1.8 V` | 选择 `1.8 V`，不能使用 3.3 V 直连 |
| 约 `5 V` | 立即停止，不能连接普通 TTL |
| 约 `0 V` | 可能接错点、接到 RX 或串口未上电，先不要连接 |

电压测完后，先拔掉 `DC12V` 和 USB-TTL，再进行信号接线。

## 4. 推荐的第一次只读接线

假设实测 TX 为 3.3 V；若实测为 1.8 V，必须改用 1.8 V 档或电平转换器。

```text
投影仪 GND  -------- USB-TTL GND
投影仪 TX   -------- USB-TTL RX
投影仪 RX   -------- 暂时不接
USB-TTL TX  -------- 暂时不接
USB-TTL VCC -------- 不接
```

信号必须交叉：板端 `TX` 接转换器 `RX`。第一次只读不接板端 `RX`，避免电脑向未知 bootloader 发送字符。

### 没有焊接工具时的选择

这块投影仪的 `RX/TX/GND` 是平面测试焊盘，不是通孔，不能把裸线“插进去”。按推荐顺序选择：

1. **迷你测试钩/抓钩线**：购买两根带尖钩的 `mini grabber test hook` 或 `pogo pin test lead`，直接夹住 `TX` 和 `GND` 焊盘，不需焊接。
2. **请手机/电脑维修店代焊**：让店家在 `GND/TX/RX` 焊盘各焊一根细线或 2.54 mm 排针，通常几分钟即可完成。明确要求只焊这三个低压 UART 点，不改动电源和存储芯片。
3. **临时探针法**：只能用于断电测量或非常短的观察，不建议用手扶着探针通电启动。若不得不临时测试，使用弹簧探针垂直压住焊盘，并用绝缘胶带固定探针主体；不能使用铝箔、散开的铜丝或会滑动的裸线。

不要把杜邦母头硬压在平面焊盘上，也不要用导电胶、锡纸或金属夹子同时跨接相邻焊盘。通电采集日志时，接触一旦抖动就会产生乱码，滑动则可能短路 `TX/RX` 或电源。

### 临时购买焊接设备是否值得

值得。对持续开发 H700 来说，给 `GND/TX/RX` 焊三根线比反复购买临时夹具更可靠。建议购买：

- 60 W 以上、可调温的恒温电烙铁或 USB-C PD 恒温焊台；
- 细尖烙铁头（约 0.8-1.2 mm）；
- 0.5-0.8 mm 焊锡丝、助焊剂、吸锡带；
- 烙铁架、黄铜棉、镊子、放大镜或手机微距镜头；
- 绝缘耐热垫和小夹具。

先在废旧 PCB 上练习：上锡、焊一根细线、拆线、清理连锡、用万用表测通断。练习成功后再焊投影仪；主板完全断电，先只焊 `GND` 和 `TX`，并在线身处用胶带做应力释放。禁止给通电主板焊接，禁止触碰 `DC12V`、电源板和 eMMC 周围焊盘。

焊完后再通电前必须确认：

```text
TX 与 GND 不短路
GND 线牢固
TX 线牢固
USB-TTL VCC 悬空
```

## 5. Windows 串口捕获

先把 USB-TTL 插入电脑，确认设备管理器出现新的 COM 号。RGSP 之前使用的是 CH343 `COM4`，投影仪连接时必须重新确认，不能盲认 COM4。

在 PowerShell 中运行：

```powershell
Set-Location D:\Works\H700Android
.\tools\capture_rgsp_uart.ps1 -List
```

将 `COMx` 换成投影仪 USB-TTL 实际端口：

```powershell
.\tools\capture_rgsp_uart.ps1 -Port COMx
```

脚本固定使用：

```text
115200 baud, 8 data bits, no parity, 1 stop bit, no hardware flow control
```

先启动捕获，再接通投影仪 `DC12V` 或按电源键。让捕获持续到出现 Linux 登录提示、Android 卡 Logo，或至少等待 3 分钟；按 `Ctrl+C` 停止。日志保存到：

```text
D:\Works\H700Android\out\logs\uart\rgsp\
```

文件名虽然带 `rgsp`，内容可以是投影仪；后续应按设备名重命名或复制归档。

## 6. 先从串口日志读取什么

日志中优先搜索：

```text
H700 / sun50iw9 / allwinner
U-Boot / boot0 / boot package
Linux version
Android / init / system_server / zygote
root= / mmcblk / GPT / eMMC
DRAM SIZE / panel / disp / mali / audio
```

PowerShell 快速筛选：

```powershell
Select-String -Path .\out\logs\uart\rgsp\*.log `
  -Pattern 'H700|sun50iw9|U-Boot|Linux version|Android|system_server|zygote|root=|mmcblk|DRAM SIZE|mali|disp|audio' `
  -CaseSensitive:$false
```

串口日志本身通常已经能判断：是否 Android、内核版本、根分区、eMMC/TF 启动来源、是否存在厂商 HAL 或 Mali 初始化错误。

## 7. 如果串口出现登录提示

先只读记录提示内容，不要猜密码。若卖家或固件资料提供了账号，再登录；成功进入 shell 后执行以下命令，并把输出保存到文本：

### Linux 系统

```sh
date
uname -a
cat /etc/os-release 2>/dev/null || true
cat /proc/cpuinfo
free -h
df -hT
mount
cat /proc/cmdline
cat /proc/partitions
ls -l /dev/mmcblk* 2>/dev/null
```

### Android 系统

```sh
getprop 2>/dev/null || true
cat /system/build.prop 2>/dev/null || true
cat /vendor/build.prop 2>/dev/null || true
ls -l /system /vendor /product /odm 2>/dev/null
ls -l /vendor/lib64/hw /vendor/bin/hw 2>/dev/null
```

### H700 图形/硬件线索

```sh
ls -l /dev/fb* /dev/disp /dev/ion /dev/mali* /dev/dri/* 2>/dev/null
cat /proc/version
dmesg | grep -Ei 'mali|disp|fb|ion|drm|audio|codec|lcd|hdmi|mmc|wifi|bluetooth'
```

## 8. 网络方式读取

如果投影仪进入系统并连接局域网：

```sh
ip addr
ip route
```

在电脑上测试设备 IP 的 SSH 端口：

```powershell
Test-NetConnection <设备IP> -Port 22
ssh root@<设备IP>
```

Android 若启用了 ADB 网络调试，可测试：

```powershell
Test-NetConnection <设备IP> -Port 5555
adb connect <设备IP>:5555
adb shell
```

不要因为端口开放就立刻刷写。先完成文件清单和哈希记录。

## 9. 只读分区盘点与备份

进入 root shell 后，先执行只读盘点：

```sh
blkid 2>/dev/null || true
fdisk -l /dev/mmcblk0 2>/dev/null || true
cat /proc/dumchar_info 2>/dev/null || true
cat /proc/mtd 2>/dev/null || true
```

如需导出分区，优先通过网络传回电脑，并先确认磁盘空间。示例（设备端）：

```sh
mkdir -p /tmp/h700-info
sha256sum /dev/mmcblk0p1 /dev/mmcblk0p2 2>/dev/null > /tmp/h700-info/partition-hashes.txt
```

完整 eMMC 原始镜像可能很大，不能在未确认空间和传输方式前执行 `dd if=/dev/mmcblk0`。禁止写入 `boot0`、`boot1`、GPT、U-Boot 或任何分区。

## 10. 需要回传给协作窗口的材料

```text
投影仪型号/外壳标签：
主板丝印：H21S-700-V3.0
UART 焊盘顺序与照片：RX / TX / GND
实测 TX 电平：
USB-TTL 芯片与 COM 号：
串口参数：115200 8N1
完整 UART 日志文件及 SHA-256：
是否出现登录提示：
uname -a / getprop / 分区表输出：
是否联网、设备 IP、SSH/ADB 端口：
```
