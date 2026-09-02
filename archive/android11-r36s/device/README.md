# 设备只读采集

`read-only-inventory.sh` 只读取设备信息、boot 分区哈希和内核配置。它不
停止前端、不修改环境变量、不写块设备，也不读取密码。

在设备上执行前先确认目标地址和权限：

```sh
scp device/read-only-inventory.sh root@DEVICE:/tmp/
ssh root@DEVICE 'sh /tmp/read-only-inventory.sh | tee /mnt/data/rgsp-android-inventory.txt'
```

若需要导出原始镜像，使用管理员确认过的维护窗口和足够空间，优先导出到
网络主机或备用介质；不要把大镜像写入只剩约 233 MiB 的 `/mnt/mmc`。
