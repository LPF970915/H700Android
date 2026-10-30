# 天马 G / H700 ARM32 配置

2026-10-30 用户明确加入预装。采用官方 Pegasus ARM32 加用户整合包主题；包内定制 APK 与 RA 仅支持 ARM64，未安装。保留实测 RA ra32 1.22.2，使用官方 ARM32 mGBA、gpSP、VBA-M。

`retroarch-gba.cfg` 是新镜像的干净 GBA 配置，不含游戏、账号或历史路径。配合已有 H700 autoconfig。`global.glslp` 通过当前配置目录自动加载单遍 LCD3x，GBA 240×160 在本机 720×480 整数放大三倍。旧 `video_shader` 键不参与 RA 1.22.2 的自动预设查找。

整合包、主题、图片/视频、APK 和原始测试记录仅保留本地。封装工具按允许的资源类型选取，拒绝将 ROM/存档加入输出；活动元数据的 ARM32 启动参数与 ROM 路径由工具生成。详细结果见 [测试记录](../../docs/RG34XXSP_PEGASUS_GBA_20261030.md)。
