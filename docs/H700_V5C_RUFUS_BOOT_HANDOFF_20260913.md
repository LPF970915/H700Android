# v5c Rufus 手动烧录后的实机测试交接

日期：2026-09-13
目标会话：`01a09914-7f6d-7070-acc0-08e173a51405`
项目：`D:\Works\H700Android`

## 当前任务

用户已明确报告：Rufus 手动烧录完成，即将开机测试。
下一步是捕获串口并验证此次启动，不是再次烧录、格式化或重建镜像。
本交接没有启动串口、ADB、写卡或物理盘诊断进程。

## 本次镜像

- 文件：`D:\Works\H700Android\out\H700_Android_SingleCard_v5c_SettingsDpad.img`
- 清单：`D:\Works\H700Android\out\H700_Android_SingleCard_v5c_SettingsDpad.json`
- 大小：`32434554368` 字节。
- SHA-256：`cf481773dd2658a0a7307222f2a19679fd74c88a53923a0d72a13bfe7ef711cb`
- 清单状态：`OFFLINE_VERIFIED_READY_FOR_FLASH`。
- 清单的 `physical_boot_verified` 仍为 `false`。
- 用户报告 Rufus 已完成，不等于本窗口已经取得完整回读哈希或实机启动证据。

上述清单在此次交接时已重新读取，但没有重新计算大镜像哈希，也没有读取卡。

## 版本内容与待验收项

清单记录已包含以下修改，运行效果仍需本次实测：

1. AT4K 小屏布局适配、预置及出厂默认桌面。
2. TV UI mode type 为 4，D-pad 声明开启，触摸屏声明关闭。
3. Settings 焦点修复：主页 `afterDescendants`，偏好列表的
   `focusableInTouchMode` 为 false。
4. Settings APK SHA-256：
   `f1756b7dca7b92e4b3946c9b66701aa289363b8646e2b1b5b8cae25be03bfc83`。
5. 剩余空间扩展方案：GPT 第 8 分区及 FAT32 扩容，不通过格式化实现。
   128G 实卡上的执行结果仍需检查。

不能把“TV 模式已设置”当作所有菜单焦点已经修好。重点实测系统设置、
文件管理器及 AT4K 右上角菜单，特别是向下移动和滚动。

## 卡与成功历史

此前电脑识别目标为 Disk 3，USB，读卡器报告序列号 `000000001539`，
容量 `125069950976` 字节。重新插拔后磁盘编号可能变化。
相同的读卡器序列号与容量不能证明是同一张物理卡，用户明确说换过卡。

历史完整写入和回读成功证据：

- `D:\Works\H700Android\out\rgsp-v5-direct-flash-20260912-224130\result.json`
- `D:\Works\H700Android\out\rgsp-v5b-direct-flash-20260913-002430\result.json`

这些记录的状态为 `DIRECT_WRITE_AND_READBACK_VERIFIED`，但记录自身
不证明相应版本所有功能均通过实机验收。

## 本轮自动烧录失败与结论纠正

以下三次尝试没有完整写入和回读成功凭据：

- `D:\Works\H700Android\out\rgsp-v5c-direct-flash-20260913-114825`
- `D:\Works\H700Android\out\rgsp-v5c-direct-flash-20260913-121231-offline`
- `D:\Works\H700Android\out\rgsp-v5c-direct-flash-20260913-121335-skip-tail`

日志均报告 Write 调用“对路径的访问被拒绝”。最后一次跳过卡尾清理，
仍然失败。之后 Windows 报告的第 8 分区大小发生变化，故没有 WRITE
进度日志不能证明卡完全未修改。

以下旧结论证据不足，不得继续当作已确诊原因：

- 不能由访问拒绝直接认定卡或读卡器损坏。
- WPD 设备存在不能证明有进程持有冲突句柄。
- 只读诊断没有输出文件不能证明底层读取挂起，也可能是脚本异常退出。
- 128G 容量本身不是已证实的根因，也不能据此排除容量相关软件缺陷。

有一个明确的软件审计线索：后续重试启动的是 Windows PowerShell
`powershell.exe`，而非此前尝试使用的 PowerShell 7 `pwsh.exe`。
烧录及诊断脚本使用 `[Convert]::ToHexString`，需要复核运行时兼容性和
异常日志。不要继续混用运行时，也不要把未生成结果解释为硬件故障。
`SkipPhysicalTailClear` 是失败排查中新加的选项，未验证成功，不是稳定路径。

## 接手后的顺序

1. 先查项目已有串口成功配置并重新枚举端口。用户换过 USB 接口，
   不要直接认定旧 COM 号仍有效；只启用一个串口读取进程。
2. 从上电前开始保存完整日志，记录厂商图、Android logo、桌面的阶段。
3. 用户使用安卓独立卡在 TF1 单卡启动；不依赖旧 Linux TF1 加安卓 TF2。
4. 进入桌面后检查当前 HOME、Settings/文件/AT4K 菜单焦点与小屏裁切。
5. 检查实际分区容量、挂载状态和首次启动扩容结果，之后再做冷启动复验。
6. 失败时先保存 UART/ADB 日志，确定首个失败阶段，不自动重新烧录。

## 保护范围

用户明确要求保留安卓源码、WSL 工具链、增量构建产物及修复系统所需文件。
旧轮次已经删除过 v3b 输出目录及部分废弃烧录产物；此次交接未继续清理。
工作区有未提交变更，不要回退或覆盖。不要在没有新授权的情况下再次写卡。
