"""Read-only power/audio/input inventory for one explicitly identified H700.

Raw output is private. A software snapshot never certifies physical behavior.
No setting writes, suspend, reboot, audio playback, ioctl or file deletion.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

READS = {
    'power': 'dumpsys power', 'battery': 'dumpsys battery',
    'audio': 'dumpsys audio', 'audio_flinger': 'dumpsys media.audio_flinger',
    'input': 'dumpsys input', 'input_caps': 'getevent -lp',
    'hal': 'lshal', 'thermal': 'dumpsys thermalservice',
    'meminfo': 'cat /proc/meminfo', 'swaps': 'cat /proc/swaps',
    'settings': 'settings get system screen_off_timeout; settings get system screen_brightness; '
                'settings get system screen_brightness_mode; settings get global stay_on_while_plugged_in',
    'backlight': 'for d in /sys/class/backlight/*; do [ -d "$d" ] || continue; '
                 'printf "%s\\n" "$d"; for f in brightness actual_brightness max_brightness; do '
                 '[ ! -r "$d/$f" ] || { printf "%s=" "$f"; cat "$d/$f"; }; done; done',
    'power_supplies': 'for d in /sys/class/power_supply/*; do [ -d "$d" ] || continue; '
                 'printf "%s\\n" "$d"; for f in type present online status capacity voltage_now current_now temp; do '
                 '[ ! -r "$d/$f" ] || { printf "%s=" "$f"; cat "$d/$f"; }; done; done',
    'wake_sources': 'cat /sys/kernel/debug/wakeup_sources',
    'lights': 'dumpsys lights',
    'backend_files': 'ls /vendor/bin/hw/*light* /vendor/bin/hw/*power* '
                     '/vendor/lib/hw/*light* /vendor/lib/hw/*power* 2>/dev/null; '
                     'cat /vendor/etc/vintf/manifest.xml; '
                     'grep -n -E "light|power|thermal" /vendor/etc/init/*.rc',
    'kernel_thermal': 'for d in /sys/class/thermal/thermal_zone*; do [ -d "$d" ] || continue; '
                      'printf "%s\\n" "$d"; for f in type temp trip_point_*_temp trip_point_*_type; do '
                      '[ ! -r "$d/$f" ] || { printf "%s=" "$f"; cat "$d/$f"; }; done; done',
    'properties': 'getprop ro.build.version.sdk; getprop ro.product.cpu.abilist; '
                  'getprop ro.config.low_ram; getprop persist.vendor.rgsp.input_profile',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    session = json.loads(args.session.read_text(encoding='utf-8'))
    serial = session['serial']
    assert re.fullmatch(r'[A-Za-z0-9]+', serial), 'Use the saved USB serial, not a network address'
    def read(command):
        result = subprocess.run([args.adb, '-s', serial, 'shell', command],
            capture_output=True, timeout=45)
        return {'return_code': result.returncode,
                'stdout': result.stdout.decode('utf-8', 'replace').replace('\r',''),
                'stderr': result.stderr.decode('utf-8', 'replace').replace('\r','')}
    assert read('getprop ro.serialno')['stdout'].strip() == serial, 'Device identity mismatch'
    assert read('getprop ro.product.device')['stdout'].strip() == 'rgsp', 'Unexpected product'
    model = read('getprop ro.product.model')['stdout'].strip()
    assert model in ('RGSP H700', 'RGSP_H700'), 'Unexpected model'
    args.out.mkdir(parents=True, exist_ok=True)
    raw = {}
    for name, command in READS.items():
        raw[name] = read(command)
        (args.out / (name + '.private.txt')).write_text(raw[name]['stdout'], encoding='utf-8')
        print('READ', name, 'exit=' + str(raw[name]['return_code']), flush=True)
    (args.out / 'raw-read-results.private.json').write_text(json.dumps(raw, indent=2) + '\n')
    def match(name, pattern):
        value = re.search(pattern, raw[name]['stdout'], re.MULTILINE)
        return value.group(1) if value else None
    settings = raw['settings']['stdout'].strip().splitlines()
    properties = raw['properties']['stdout'].strip().splitlines()
    summary = {
        'read_only': True, 'physical_acceptance_performed': False,
        'read_exit_codes': {name: value['return_code'] for name, value in raw.items()},
        'hal_inventory_complete': raw['hal']['return_code'] == 0,
        'sdk': properties[0] if len(properties)>0 else None,
        'abi': properties[1] if len(properties)>1 else None,
        'low_ram': properties[2] if len(properties)>2 else None,
        'input_profile': properties[3] if len(properties)>3 else None,
        'memory_kib': match('meminfo', r'^MemTotal:\s+(\d+)'),
        'screen_off_timeout_ms': settings[0] if len(settings)>0 else None,
        'brightness_setting': settings[1] if len(settings)>1 else None,
        'brightness_mode': settings[2] if len(settings)>2 else None,
        'stay_on_while_plugged_in': settings[3] if len(settings)>3 else None,
        'wakefulness': match('power', r'mWakefulness=(\w+)'),
        'battery_level': match('battery', r'^\s*level:\s*(\d+)'),
        'battery_temperature_tenths_c': match('battery', r'^\s*temperature:\s*(-?\d+)'),
        'backlight_class_nodes': re.findall(r'^/sys/class/backlight/([^\n]+)',raw['backlight']['stdout'],re.M),
        'lid_switch_capability_listed': 'SW_LID' in raw['input_caps']['stdout'],
        'input_names': re.findall(r'name:\s+"([^"\n]+)"', raw['input_caps']['stdout']),
        'registered_audio_hal': 'android.hardware.audio@' in raw['hal']['stdout'],
        'registered_power_hal': 'android.hardware.power@' in raw['hal']['stdout'],
        'registered_light_hal': 'android.hardware.light@' in raw['hal']['stdout'],
        'registered_health_hal': 'android.hardware.health@' in raw['hal']['stdout'],
        'thermal_hal_ready': match('thermal', r'^HAL Ready:\s*(\w+)'),
        'swap_devices_listed': max(0,len(raw['swaps']['stdout'].strip().splitlines())-1),
        'open_physical_checks': ['five actual brightness levels', 'speaker/headphone listening',
            'charging transitions', 'lid/power key sleep and wake', 'normal shutdown and cold start'],
        'notes': ['Missing HIDL registration is a backend lead; legacy HAL paths may still exist.',
                  'A nonzero lshal exit means partial inventory; absence is not definitive.',
                  'No SW_LID declaration alone does not prove that lid hardware is absent.'],
    }
    (args.out / 'runtime-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
