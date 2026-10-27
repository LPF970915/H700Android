#!/system/bin/sh
# Reversible runtime trial on the identified new device. No system writes.
set -eu
export PATH=/system/bin:/vendor/bin
expected_serial=${H700_EXPECTED_SERIAL:?Set H700_EXPECTED_SERIAL to the verified target serial}
[ "$(id -u)" = 0 ]
[ "$(getprop ro.serialno)" = "$expected_serial" ]
[ "$(getprop service.adb.tcp.port)" = 5555 ]
[ "$(settings get global adb_enabled)" = 1 ]
[ "$(getprop sys.usb.config)" = adb ]
[ "$(getprop sys.usb.configfs)" = 0 ]
[ -d /sys/class/udc/5100000.udc-controller ]
[ ! -e /config/usb_gadget/g1 ]
[ ! -e /dev/usb-ffs/adb/ep0 ]

g=/config/usb_gadget/g1
mkdir "$g"
echo 0x18d1 > "$g/idVendor"
echo 0x4ee7 > "$g/idProduct"
echo 0x0200 > "$g/bcdUSB"
echo 0x0100 > "$g/bcdDevice"
mkdir "$g/strings/0x409"
getprop ro.serialno > "$g/strings/0x409/serialnumber"
echo ANBERNIC > "$g/strings/0x409/manufacturer"
echo 'H700 Android ADB' > "$g/strings/0x409/product"
mkdir "$g/configs/b.1"
mkdir "$g/configs/b.1/strings/0x409"
echo adb > "$g/configs/b.1/strings/0x409/configuration"
echo 500 > "$g/configs/b.1/MaxPower"
mkdir "$g/functions/ffs.adb"
mkdir -p /dev/usb-ffs/adb
mount -t functionfs -o uid=2000,gid=2000 adb /dev/usb-ffs/adb
chmod 0770 /dev/usb-ffs/adb
echo CONFIGFS_AND_FUNCTIONFS_PREPARED
ls -l /dev/usb-ffs/adb
setprop sys.usb.configfs 1
echo RESTART_ADBD_EXPECT_BOTH_TCP_AND_USB
# Last operation: init may kill this shell along with the old adbd.
# Existing init.usb.configfs.rc binds g1 when the new adbd sets ffs.ready=1.
setprop ctl.restart adbd
