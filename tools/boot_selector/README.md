# H700 启动机型选择器参考

状态（2026-11-14晚）：Test3与Test4均撤回推荐。Test4在35XX H实体测试为背光黑屏；最终交付U-Boot的simple parser不支持该包的`&&`／`if`脚本，且内层1712字节超长，已由实际机器码重现。Test5仅把环境区改成短命令嵌套`run`；实际解析器296项、真实FDT18项、完整封装与gzip读回、独立全包和Windows SHA均通过，可供35XX H重刷测试，实体菜单／输入／Android仍待验收。最新文件与收据见`docs/ROC_OS_H700_MANUAL_SELECTOR_TEST5_20261114.md`。后文Test4流程仅保留设计参考，不证明原包实际走到菜单。

Test4仍为一个共用镜像。当前有3个允许启动的型号、2套底层显示配置：原34XX SP与用户原RGSP共用legacy720，35XX H使用完整35H640；其余9个型号可浏览，启动时提示尚未接入，不产生启动结果。不能把相同分辨率的机型自动映射为同一面板。

首次无保存记录时，直接用完整35H640配置进入菜单，初选35XX H、保存关闭，无需组合键；不自动试屏。U-Boot已在环境读取后、首次显示前应用所选配置，并同步Android boot中的内核DTB；独立机型／翻盖属性已传给Lid3。以上已完成离线接入，仍需实体显示、按键和启动验收。

勾选保存并确认启动后，下一次使用保存型号的面板配置并跳过菜单。开机时按住音量减只强制重新打开菜单，保留当前已解析型号的面板。未勾保存不会删除已有默认：切换型号时通过一次性请求重启初始化，进入Android前清除临时请求，之后仍按原保存默认启动；原先没有保存默认时，下次恢复首次菜单。同型号、不保存的确认会清除临时请求并直接继续。

640×480只规定内容布局，首次35H640不保证720面板、35XX SP或其余机型能看到菜单。音量减也不切换面板；若选错配置导致黑屏，重选界面仍可能不可见，按用户接受的重刷方式恢复。本轮首先验证35XX H，详见 `docs/ROC_OS_H700_MANUAL_SELECTOR_TEST4_20261114.md`。

28XX的逻辑界面为640×480，用户已确认物理屏幕为480×640并横用；对应面板档需要独立时序与旋转，不能直接套用35XX H。

`reference_model.py` 的 `MODEL_CATALOG` 是机型信息的单一来源。顺序与用户清单一致，首行用左右箭头循环选择，分辨率、翻盖、摇杆从目录只读派生。该纯参考状态模型与浏览器预览保留早期34XX SP、保存关闭的默认；它们不决定Test4启动包的首次35XX H默认。完整机型表与启动接入边界见 [SPEC.md](SPEC.md)。

35XX Plus 与35XX+（2025）分列；原RGSP保留720×480。只有35XX+（2025）与28XX登记用户明确的无Wi-Fi，其余为未知，不据此更改驱动。目录元数据不证明12款均有可用完整面板配置。

`PanelResolution` 是纯参考模型中外部解析器的结果，必须绑定当前具体机型。即使分辨率、翻盖相同，换机型也拒绝复用旧解析结果。目录自身的 `preview()` 全部返回 `unvalidated`、不提供完整面板ID。Test4的3个允许型号另由启动接入代码绑定完整显示配置；其余9款仍需各自的初始化命令、扫描时序、修订分支及U-Boot／内核接入。

以下接口与JSON仅描述纯参考模型：只有明确调用 `confirm_start()` 且勾选保存，才产生 `ConfigIntent` 保存请求。模型不执行启动或写入；加载和切换不会保存。schema2偏好严格只有 `schema` 和稳定 `model_id`：

```json
{"schema":2,"model_id":"rg35xxh"}
```

不保存可由目录推导的geometry/lid，也不把UI勾选状态或外部硬件验证状态写成配置权威。schema1仅有几何和翻盖，存在多个对应机型，拒绝猜测迁移。未知schema、机型、额外字段或错误类型均拒绝。Test4原生菜单的单次输出另外包含 `save_default`，由状态助手处理；真正持久记录位于TF1环境区，并非这里的JSON文件。

`StartupDecision.from_saved_config()` 将有效机型偏好分流为跳过菜单；无记录、损坏记录或旧schema回默认菜单。跳页不等同于已经解析或点亮面板。`SelectorState.from_config()` 用于主动打开编辑页，加载后保存开关为关。

```python
from tools.boot_selector.reference_model import BootRoute, SelectorState, StartupDecision

state = SelectorState().choose_model("rg35xxh").choose_save_default(True)
assert state.selection.geometry.value == "640x480"
assert state.selection.lid is False
payload = state.confirm_start().save_request.to_mapping()
# 这里只做纯参考状态分流，不执行Test4的环境区读写。
decision = StartupDecision.from_saved_config(payload)
assert decision.route is BootRoute.SKIP_SELECTOR
```

`test_reference_model.py` 的12项测试涵盖清单、只读派生、左右环绕、同几何机型区分、确认后保存、默认跳页、坏输入与过期解析结果；已通过主机测试。无硬件I/O。

生成预览时由同一个目录导出，不维护另一份机型表：

```text
python tools/boot_selector/build_preview.py out/h700-startup-selector-20261114/h700-model-selector.html
```

`preview-template.html`是浏览器交互稿；纯黑640×480内容在三种实际屏幕比例中居中。预览屏幕尺寸选择器属于外部演示工具。此预览与12项状态测试不证明首次菜单能够在未知物理面板上显示。

