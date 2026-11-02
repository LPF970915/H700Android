# 快捷设置亮度条的十字键修复

2026-11-02，RG34XXSP / H700 / 2GB，当前卡为 Test2a + 四项 Light vendor 文件。用户报告长按Menu打开快捷设置后，亮度条不能用左右键调整。

## 原因与修复

现场导航服务已经选中 `com.android.systemui:id/slider`，控件也公布了 RangeInfo 和 SET_PROGRESS 动作，但 `adjustRange()` 仅接受 `settings` scope，排除了 `shade`。左右键被导航代理消费，却没有执行亮度调整。

Navigation13（诊断版本37）仅对 shade 中这个确切ID开放 Range 动作。该控件范围为0…1023，左右每次调整约5%的**滑条进度**，而非只动一档；亮度数值由Android曲线转换，不承诺每次物理亮度恰好变化5%。设置页原有整数/浮点步长保持，一次按键只执行一个已声明动作，不因返回失败重复递增；上下仍离开滑条，端点不越界。

保留Navigation12的原生SystemUI A/电源菜单委派、Menu和Select鼠标逻辑。只修改导航应用，没有修改SystemUI、框架或背光服务。

## 现场验证

先按现卡身份及四项vendor SHA守卫核对，备份原system Navigation12 APK和16KiB应用数据。新旧APK的签名证书一致，正常覆盖安装Navigation13至data；system APK原件未改，不刷卡、不清数据。

按当前ANBERNIC-keys handler注入实际Menu/方向HAT/B事件，每一步观察结果后继续：

| 操作 | 结果 |
| --- | --- |
| B关闭原下拉栏，再单独长按Menu | 重新打开快捷设置，未走短按Home路径 |
| 从首个磁贴向上 | 选中亮度条 |
| 左、右 | 836→785→836，系统亮度102→81→102；BRIGHT策略下驱动读回81、102 |
| 继续向右 | 887/130、938/166、989/214，最终进度1023、系统设置255 |
| 最大进度再按右 | 保持1023，焦点不跳走、不越界 |
| 从端点向左 | 进度972、设置197，驱动读回197 |
| 下、上 | 可离开到磁贴，再返回亮度条 |
| B | 下拉栏关闭，导航mode回inactive |

测试临时延长系统亮屏超时以区分DIM策略，结束后恢复原亮度102和超时60000；未修改USB常亮、trace或待机锁。上述为受控注入，不是用户实体手感验收，没有重做重启或全部应用回归。

上端点时两次观察到系统设置255而驱动读回200，样本完整保留，尚未定位该上限/临时亮度差异。不能据此宣称快捷设置到物理背光的全范围已验收；本轮确认的是左右动作、进度、设置写入，以及多档设置到驱动的对应。没有通过写原始背光绕过该差异。

## 后续封装与保全

低压力构建入口：`tools/build_h700_low_pressure.ps1 -Targets H700QsBrightness -Execute`，保持单核、CPU0–1、-j1、nice19、6GiB RAM与512MiB swap。APK及签名验证、确切SHA见[结果锁](baselines/rg34xxsp-qs-brightness-20261102/result-lock.json)。

`H700ReadinessStage`现在生成独立r3阶段，将同一个Navigation13 APK装入system，先验证其API29签名与父system APK一致，再执行分区/关键文件检查。r2、Test2a及所有冻结镜像不回改。本轮没有生成新的整卡IMG，也没有把整个r3写入当前卡；现机仍是Test2a加Light四文件及data Navigation13更新。

当前会话守卫为 `out/rg34xxsp-qs-brightness-20261102/device-guard.private.json` 和同目录session.py：在Light守卫之上增加已安装导航APK的SHA检查。

保护 `out/rg34xxsp-qs-brightness-20261102/` 的备份、私有界面树/截图/注入记录/失败断言及守卫，`out/dualabi-interaction-20261101/qs-brightness/` 和新WSL交互构建目录、readiness stage-v3。只提交源码与脱敏锁，不上传APK、应用数据、身份或原始日志。AYASpace试验及七款预装没有改动。
