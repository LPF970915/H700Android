"""Preserve fractional LCD timing and isolate secondary-display power on RGSP."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REL='hardware/aw/hwc2/de2family/DisplayOpr.cpp'
BEFORE='fae8d02be89eb9b1ee26a7997ee73e592a8282b9a92746fd79ab45831776966a'
OLD_RATE='''\trefreshRate = 1000000000000LLU /
\t\t(uint64_t(info.upper_margin + info.lower_margin + info.vsync_len + info.yres)
\t\t * ( info.left_margin  + info.right_margin + info.hsync_len + info.xres)
\t\t * info.pixclock);
\tif (refreshRate == 0) {
\t\tALOGW("invalid refresh rate, assuming 60 Hz");
\t\trefreshRate = 60;
\t}'''
NEW_RATE='''\t// Avoid truncating fractional LCD refresh to an integer number of Hz.
\tconst int32_t framePeriod = rgspFramePeriodNs(
\t\t(uint64_t)info.xres + info.left_margin + info.right_margin + info.hsync_len,
\t\t(uint64_t)info.yres + info.upper_margin + info.lower_margin + info.vsync_len,
\t\tinfo.pixclock);
\tALOGI("LCD timing pixel_ps=%u frame_period_ns=%d", info.pixclock, framePeriod);'''
EDITS=[
 ('#include "../hwc.h"','#include "../hwc.h"\n#include "RgspFramePeriod.h"'),
 ('\tint refreshRate;\n\tint fbfd = -1;','\tint fbfd = -1;'),
 (OLD_RATE,NEW_RATE),
 ('\tconfig->vsyncPeriod = 1000000000 / refreshRate;','\tconfig->vsyncPeriod = framePeriod;'),
 ('\tALOGD("set mode %d %ld",mode, vsyncEn);\n\tif (ioctl(dispFd, DISP_BLANK, arg)) {',
  '''\tALOGD("set mode %d %ld",mode, vsyncEn);
\tchar productDevice[PROPERTY_VALUE_MAX] = {0};
\tproperty_get("ro.product.device", productDevice, "");
\tconst bool lcdPrimary = !strcmp(productDevice, "rgsp");
\t// DISP_BLANK is a global runtime suspend on this kernel. Secondary HDMI
\t// power changes must not blank the built-in LCD or disable its VSYNC.
\tif ((!lcdPrimary || display->displayId == 0)
\t\t\t&& ioctl(dispFd, DISP_BLANK, arg)) {'''),
 ('\targ[1] = vsyncEn;\n\tif (ioctl(dispFd, DISP_VSYNC_EVENT_EN, arg)) {',
  '\tif (lcdPrimary) arg[0] = display->displayId;\n\targ[1] = vsyncEn;\n\tif (ioctl(dispFd, DISP_VSYNC_EVENT_EN, arg)) {'),
]

def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    target=a.source/REL;text=target.read_text();base=text
    if sha(text.encode())!=BEFORE:
        for old,new in reversed(EDITS):base=base.replace(new,old,1)
    if sha(base.encode())!=BEFORE:raise SystemExit('Unrecognized HWC edits; preserved')
    patched=base
    for old,new in EDITS:
        if patched.count(old)!=1:raise SystemExit('Ambiguous HWC anchor')
        patched=patched.replace(old,new,1)
    header=(ROOT/'android/h700-android10/device/roc/rgsp/graphics/RgspFramePeriod.h').read_bytes().replace(b'\r\n',b'\n')
    dest=target.with_name('RgspFramePeriod.h')
    if dest.exists() and dest.read_bytes()!=header:raise SystemExit('Unrecognized timing header; preserved')
    target.write_bytes(patched.encode());dest.write_bytes(header)
    (a.source/'out/rgsp-hwc-timing-inputs.json').write_text(json.dumps({REL:sha(patched.encode()),str(dest.relative_to(a.source)):sha(header)},indent=2)+'\n')
    print('RGSP_HWC_FRACTIONAL_TIMING_AND_SECONDARY_POWER_PREPARED')
if __name__=='__main__':main()
