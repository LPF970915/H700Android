#!/usr/bin/env python3
"""One command: use UART to enable source-restricted temporary Wi-Fi debugging."""
from pathlib import Path
import argparse
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'settings_nav_probe'))
import audit


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    a=audit.Audit()
    try:
        output=a.command('if [ -f /system/bin/rgsp-wifi-adb-session.sh ]; then sh /system/bin/rgsp-wifi-adb-session.sh; else sh /data/local/tmp/rgsp-restore-debug.sh; fi')
        if 'DEBUG_GUARDS_RESTORED' not in output:raise RuntimeError('Debug guard restore not confirmed')
        network=a.command('ip -4 addr show wlan0 | grep "inet "')
        ips=re.findall(r'(?:^|\n)\s*inet (192\.168\.31\.\d+)/',network)
        if not ips:raise RuntimeError('No expected WLAN address; wait for Wi-Fi association and rerun')
        audit.TARGET=ips[-1]+':5555'
        if audit.adb('getprop ro.serialno').strip()!=audit.SERIAL:raise RuntimeError('ADB device identity mismatch')
        print('Wi-Fi ADB ready: '+audit.TARGET+'; allowed client: 192.168.31.211')
    finally:a.close()


if __name__=='__main__':main()
