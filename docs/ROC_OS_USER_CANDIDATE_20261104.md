# ROC OS 独立 user 候选准备（2026-11-04—05）

2026-11-05 编译修正：首批002018在9518/95883任务处因平台MAC签名映射失败停止，用时35分43秒、峰值5GiB/swap0，images-result-v1与全部日志保留。旧keys.conf的@RELEASE USER固定请求testkey.x509.pem，与专用releasekey名称不符；不是超时，未原样重试。

独立产品新增私有keys.conf，仅将USER映射到现有正式releasekey证书。使用PRODUCT_PRIVATE_SEPOLICY_DIRS接入；板级入口被BSP覆盖的中间草案已被启动前守卫阻止（010812/images-v2），未进入重复编译。实际BSP insertkeys预检查通过平台XML及产品空XML两条路径，所有平台模板签名来自原正式身份，产品侧不增加签名权限规则。旧BSP、五组密钥及私有目录链接未修改；没有创建名为testkey的正式密钥别名。预检查使用保留的64位py2启动器，不安装全局Python；首个缺启动器PATH的prepare-v6预检查失败也保留。

修复前已核对repo和Native输入守卫；仅四个编译输入变化：候选mk、新keys.conf、prepare_candidate.py和低负载shell入口。11项发行工具测试通过（run-v8）。新批次011601/prepare-v9已启动，实际产品私有策略路径守卫通过，正在重生成构建图；复用旧输出，未清理已有产物。动态锁已按本次审查过的差异更新，旧锁与失败记录另存。源码修正和预检查通过尚不表示实际完整编译越过失败点，更不代表enforcing运行通过。

01:19实际编译已越过原失败点：真实plat_mac_permissions.xml为有效XML，SHA与正式证书预检查输出一致。新批次528/86878时正在编译libc++fs，内存约4.67GiB/swap0；计数域因增量图改变而重置，不与旧95883任务图逐项相加。见[修复证明](baselines/roc-os-user-mac-map-fix-20261105/acceptance.json)。完整分区、enforcing及正式发行仍未通过。

在发行收口基线 `1127cfd` 上继续。当前完成工程卡开合盖一轮及安装新初始化应用之后的真实重启：用户确认画面、中文桌面、A 解锁、Wi-Fi 和 Select 无异常；关键 SHA 保持，ROCProvisioning 在新 boot 下自动收到开机广播并保留设置，Thermal init 自启与框架 HAL Ready、Wi-Fi VALIDATED 再次通过。开盖采样晚于锁屏10秒自动息屏，保留这段样本；H700Lid/PowerManager事件与用户观察共同证明实际开盖亮屏，未把晚采样当成瞬间ON状态。均为当前 eng 工程卡验收，不是 user 镜像验收。

## 隔离准备

`H700UserPrepare` 将仓库内独立候选配置同步到 Native 新产品目录；核对最新成功构建及其对应分区审计、371项原输入、Source64独立产品及2项ABI5库，原工程产品、原AT4K和三分区产物均保留。用户正式密钥五组公钥/证书摘要与私钥公钥逐项对照，外置备份回读已通过。密钥实体在源码与Git之外；不复制其内容进入产品目录。

保留 BSP 的 AT4K 模块声明 PRESIGNED，会绕过新平台签名。因此仅在 user 候选中选中 `ROCReleaseLauncher` 私有重签模块，输入仍为已审计的同一AT4K APK；覆盖原模块选择，安装到独立目录以避免构建目标碰撞。组件包名和资源不因模块重命名改变。尚需检查真正签出的APK内容及证书，不能把模块定义当作签名已经完成。

`H700UserGraph` 使用独立输出 `/home/lpf/roc-os-user-20261104/out`，导出专用密钥目录，选择 `roc_os_release_candidate-user`，只执行 `m -j1 nothing`。编译的构建工具不等于完成Android分区。入口沿用单核、CPU0–1、nice19、RAM6GiB、swap512MiB、idleIO与3小时上限，全局锁阻止并发。

## 首轮错误及修正

`h700-low-pressure-20261104-232138` 构建图失败：旧Soong/APEX解析器拒绝绝对路径的默认签名目录，报 `Path is outside directory`。5分34秒、峰值3GiB/swap0；graph-result-v1保留。未编出Android镜像，原工程三分区SHA保持。

修正为 Native 候选目录内专用 `.private-signing` 目录符号链接，指向外部私有目录。Make仍检查绝对私有目录中的五组密钥；Soong收到词法上位于源码树内的路径。链接只在本地Native准备时创建，Git不含链接、私钥或APK。准备与结果守卫记录链接目标；备份旧候选源目录时不解引用链接。此设计不等于所有APEX/应用已完成发行签名。

修正版构建图 `h700-low-pressure-20261104-232920` / graph-result-v2通过，9分17秒，峰值5GiB/512MiB swap；原工程源码及三分区保持。Soong实际识别 Eng=false、Debuggable=false 和新的默认签名目录。它只证明规则生成成功，不证明最终签名和安装路径正确。

随后离线签名探针在Ninja目标查询阶段发现私有启动器模块手动设置的安装目录被Make再次追加模块名，形成两层重复目录；当时尚未执行签名。已移除多余目录设置，使用 privileged 模块的默认安装根。最终 `h700-low-pressure-20261104-235142` / graph-result-v3、prepare-v4通过：9分55秒、峰值5GiB/446.5MiB swap；实际系统镜像依赖只选新启动器路径，旧PRESIGNED安装路径未选中。失败日志与首轮探针工作目录保留。

`H700UserSigningProbe` 核对实际Ninja签名计划选择专用platform密钥，再用Android SDK官方apksigner离线签署同一APK。最终 `h700-low-pressure-20261105-000222` / signing-probe-v1通过，约16秒：Android10签名、zipalign、966个非签名ZIP成员内容一致；新证书SHA与专用platform身份一致。原APK未变，新APK未安装。这与实际Make编出APK、在user系统安装运行及全系统签名审计是不同步骤。

发行工具回归 `h700-low-pressure-20261105-000912` / run-v7的11项检查通过；工程镜像继续被正式发行门禁拒绝。Native候选源备份检查确认未解引用密钥目录链接，归档不含pk8/pem/pass文件实体。最新脱敏证明见[结果锁](baselines/roc-os-user-candidate-graph-r1-20261105/acceptance.json)。

## 供电切换

用户拔USB后操作并插回，报告无明显异常。最初150样本没有捕获拔出，原样保留；延长的600样本捕获USB online从1变0、电池状态Full变Discharging，kernel boot ID保持。记录结束时仍离线，连续的插回边沿未捕获；稍后读回USB online=1与框架USB powered=true，确认重新供电。未把读数拼接成精确连续的拔插时长。只通过一次基本供电切换，不代表容量准确性、完整充电、续航、低电或深睡通过。两段观察均已达到边界退出，没有修改唤醒锁或电源设置。

## 后续工作

仍有四组 su 域启动功能待处理：双杆模块加载、输入节点准备/工程诊断、网络验证默认值、壁纸原图发布。不能仅删除它们导致摇杆、输入权限、联网或壁纸行为回退。正式签名全量检查、SELinux/ADB/root/console和boot审计，以及同一最终镜像的干净首启与实体回归仍未完成，不是仅剩压缩封装。

为先发现 user 变体专属的编译问题，已启动一版隔离的**未收口中间构建**，四组功能迁移后还须再增量编译；该中间产物不作为刷卡或发行候选。`H700UserBuild` 首批 `h700-low-pressure-20261105-002018`，prepare-v5，沿用独立输出与全部原限额。原工程版单核完整编译以十几小时计，不能以本轮构建图/签名探针的分钟级耗时推算整机发行完成时间。

已按用户此前持续报告编译的要求，将原 `roc-os` 跟进更新为此 user 作业，每15分钟采样；只有明确因3小时上限超时、无编译错误/OOM、无活动构建/锁占用，且repo脚本/候选源文件集合、Native受保护输入、候选文件/私有链接和密钥公开摘要都匹配，才允许续编。守卫不匹配或非超时失败需报告定位，不能原样无限重试。动态作业及输入锁留本地 out/source64-user-candidate-20261104/result-lock.json。编译成功只报告三分区/实际ELF核对并暂停跟进，不自动封装或刷写。当前没有新整卡镜像或刷卡操作。
