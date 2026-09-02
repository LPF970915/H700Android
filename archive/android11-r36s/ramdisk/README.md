# Probe ramdisk

`init` 是 BusyBox 风格的早期探针模板，用于确认 kernel、devtmpfs、
`/proc`、`/sys` 和可选 `adbd` 是否能起来。它不是完整 Android `init`，
不能单独提供 SurfaceFlinger、zygote 或系统服务。

```powershell
py -3 .\tools\make_ramdisk.py .\ramdisk .\out\probe-ramdisk.gz
```

只有在确认目标 kernel 的 ramdisk 启动方式确实允许 shell `init` 时才替换
原厂 ramdisk；更稳妥的第一轮是保留原厂 ramdisk，仅替换兼容的 Android kernel。
