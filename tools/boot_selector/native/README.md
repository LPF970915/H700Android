# 原生 initramfs 机型选择器

这是可独立运行的静态 AArch64 Linux 程序，不使用 Android 图形或输入服务。调用前必须由外部引导逻辑正确初始化物理面板；写入 framebuffer 并不证明屏幕已经点亮。

已构建候选：`out/boot-selector-integration-20261114/native/build-v4/roc-boot-selector`。其 ELF 无 PT_INTERP，1,008,968 字节；SHA-256 为 `1f685652b248c1b3869dbb2ae9613da6a18175d15d404a11974a4c5fb35ed7ea`。v3 保留原产物；不能使用 v2：其新增提示字库尚未同步，已保留作历史记录。

调用接口：

```sh
/grow/roc-boot-selector \
  --fb /dev/fb0 \
  --input-directory /dev/input \
  --output /run/roc-selector-result.json \
  --initial-model rg35xxh \
  --available-models rg34xxsp,rgsp,rg35xxh \
  --timeout 300
```

旧别名 `--inputs '/dev/input/event*'`、`--result`、`--initial` 也可用。结果只在用户明确选择“启动系统”后输出；保存框默认关。结果文件要求不存在，以 O_EXCL、O_NOFOLLOW、0600 创建普通单链接文件，不覆盖既有文件。

```json
{"schema":2,"model_id":"rg35xxh","save_default":true}
```

这是一次选择的输出，`save_default` 交给外部处理；它不是 reference_model.py 的持久化偏好 schema，外部持久化应只保存已解析并允许的机型记录。程序没有默认配置读写、物理磁盘、FDT、环境区写入、重启或点屏代码。

退出码 0 表示已确认并写出结果，3 表示期限内没有经过输入防护接受的有效按下且无结果，2 表示参数、设备、格式或文件错误。默认无操作期限300秒，可用 `--timeout 5..3600` 调整。首次有效按下之后不再因该期限退出，必须明确选择“启动系统”。启动时已按住、内核重复、仅释放和丢同步期间的事件不算首次有效操作；本轮 poll 输入先于超时判断处理。收到有效按键不能证明用户看到了实体画面。无输入设备或 framebuffer 不符合界限时失败，不能冒充已显示。外层负责超时与错误的启动策略；本程序没有换屏、可见倒计时或自动启动。

12款型号始终显示，顺序和属性由 `reference_model.py` 的 `MODEL_CATALOG` 导出。`--available-models` 仅限制本测试包有代码路径的型号，不代表这些型号已通过实机验收。选中未接入型号后启动，会提示“该机型尚未接入，请重新选择”并回到机型焦点，不产生启动结果。真实集成必须显式传入本包支持的列表；省略此参数仅适合组件模拟，不应据此宣称12款已支持。

输入支持 Linux `KEY_UP/DOWN/LEFT/RIGHT`、`BTN_DPAD_*`、`ABS_HAT0X/Y`（-1/0/+1）以及 `BTN_SOUTH=304`、`KEY_ENTER`、`KEY_A`。左右切机型，上下切焦点，A确认／勾选。忽略内核 value2 自动重复；方向键使用450ms初延时、140ms间隔，10秒后必须松开才能继续。打开时已按住的键需先释放；SYN_DROPPED 后清除动作，重新见到释放才接受。实际 H700 保存输入资料的 HAT 范围为 -1..1；不将摇杆 ABS_X/Y 当十字键。

framebuffer 仅支持 packed truecolor 16/24/32bpp，检查 RGB／alpha bitfield、实际 stride、可见区偏移、虚拟宽高与 smem_len。640×480内容在当前可见屏幕中心绘制；只写可见页，不翻页、不改屏幕时序。双缓冲虚拟高不会当成物理屏高。仅清当前可见区为黑色，其他虚拟页、行padding和偏移外字节不写。

字库为项目 AOSP `external/noto-fonts/cjk/NotoSansCJK-Regular.ttc` 的 SC Regular/index2、30px、40行单色80字子集。源字体SHA与机型表、字库SHA在 `generated-v2/assets.json`；OFL许可完整保存在同目录 `FONT-NOTICE.txt`。不得用Windows字体替代这个交付子集。

验证：v4受控单元170539，8.230秒、CPU3.077秒、swap0。host及实际静态A64经QEMU各165项通过，包含原102项及新增63项无操作超时检查。新增检查覆盖期限边界、有效操作后长时间停留、启动时按住、重复、释放、丢同步、HAT回中及跨输入源明确确认。它们调用生产使用的输入锁存与超时函数，没有模拟真实 poll/设备 IO。原检查覆盖12机型、方向环绕、保存确认、RGB565/24/32bpp、三种尺寸、非零x/y偏移、双缓冲与stride padding保护、10秒上限及缺字。三个比例的PPM由原生渲染器输出；v3的640预览已人工检视。没有读取或修改任何实机、系统卡或启动镜像。

在准备好的字体子集基础上受控重建：

```powershell
tools/boot_selector/native/build.ps1 -Execute `
  -Work /home/lpf/roc-boot-selector-native-20261114-v5 `
  -Output /mnt/d/Works/H700Android/out/boot-selector-integration-20261114/native/build-v5 `
  -Generated /mnt/d/Works/H700Android/out/boot-selector-integration-20261114/native/generated-v2
```

脚本使用全局flock及既有CPU、RAM、swap、nice、IO限制；新工作目录和新输出名，保留历史结果。构建同时可编译旁边的 `boot_state.c`，只产出ELF不执行其环境写入逻辑；boot-state本身的验证由外层负责。
