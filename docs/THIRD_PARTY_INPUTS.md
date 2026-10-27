# 来源与第三方输入

本次冻结没有给整个仓库新增统一授权。第三方文件保留原文件或上游提供的通知和来源。

- AOSP 修改源码/资源快照保留原通知；基础树来自 H616 Android 10 厂商包，见 `H616_ANDROID10_PROVENANCE_20260902.md`。
- LeanbackIME 固定在 AOSP 提交 `1667592ee5924122e43b611fa813c8f894087cd6`，快照包含其 `NOTICE`。适配 Android 10 不表示导入 Android 11 框架。
- Allwinner HWC、healthd 源码保留通知，完整 Longan/BSP 不在 Git 中。
- 产品 AT4K APK、RTL8821CS 模块/固件和壁纸保留原有来源，未描述为项目原创源码。重复的旧 APK 与 apktool 缓存已从当前树移除，原版本仍能从历史标签取回。
- Mali/GLES 私有输入、完整上游镜像与签名私钥只在本地保存；公开哈希不等于已上传文件。

快照是修改层恢复资料，不替代上游完整源码、二进制来源或各自的许可说明。
