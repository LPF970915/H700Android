"""Disable optional Settings illustration videos on the H700 codec BSP."""
import argparse
import hashlib
import json
from pathlib import Path

REL='packages/apps/Settings/src/com/android/settings/widget/VideoPreference.java'
BEFORE='76c7981e72c2d4dd60f95f8710aa74148a5e53d4dcf2f75a6fcc7833dcf7eb29'
DEFAULT='packages/apps/Settings/res/values/config_video_previews.xml'
OVERLAY='device/roc/rgsp/overlay/packages/apps/Settings/res/values/bools.xml'
RESOURCE='config_enable_settings_video_previews'
XML='<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <bool name="'+RESOURCE+'">true</bool>\n</resources>\n'
GUARD='''        // Illustration playback is optional. This BSP's video decoder can
        // kill mediaserver during prepare, including from onViewVisible().
        if (!mContext.getResources().getBoolean(R.bool.config_enable_settings_video_previews)) {
            setVisible(false);
            return;
        }
'''
EDITS=[('    private void initialize(Context context, AttributeSet attrs) {\n',
        '    private void initialize(Context context, AttributeSet attrs) {\n'+GUARD),
       ('    private void initMediaPlayer() {\n','    private void initMediaPlayer() {\n'+GUARD)]


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    target=a.source/REL;original=target.read_text()
    if hashlib.sha256(original.encode()).hexdigest()!=BEFORE:
        for old,new in reversed(EDITS):original=original.replace(new,old,1)
    if hashlib.sha256(original.encode()).hexdigest()!=BEFORE:raise SystemExit('Unrecognized VideoPreference edits; preserved')
    patched=original
    for old,new in EDITS:
        if patched.count(old)!=1:raise SystemExit('Ambiguous video lifecycle guard anchor')
        patched=patched.replace(old,new,1)
    default=a.source/DEFAULT
    if default.exists() and default.read_text()!=XML:raise SystemExit('Unrecognized video capability resource; preserved')
    overlay=a.source/OVERLAY;text=overlay.read_text()
    line='    <bool name="'+RESOURCE+'">false</bool>\n'
    if RESOURCE in text:
        if text.count(line)!=1:raise SystemExit('Unrecognized product video capability; preserved')
    else:
        if text.count('</resources>')!=1:raise SystemExit('Ambiguous Settings overlay')
        text=text.replace('</resources>',line+'</resources>')
    target.write_bytes(patched.encode());default.write_bytes(XML.encode());overlay.write_bytes(text.encode())
    receipt={'status':'PASS_ONLY_OPTIONAL_VIDEO_CAPABILITY_GUARDS_AND_PRODUCT_FALSE',
        'source':REL,'before_sha256':BEFORE,'after_sha256':hashlib.sha256(patched.encode()).hexdigest(),
        'default_resource':DEFAULT,'product_overlay':OVERLAY,
        'scope':'No notification preference, input route, media framework, decoder, or unrelated Settings code changed. Both constructor and resume entry points stop before MediaPlayer creation.'}
    (a.source/'out/rgsp-settings-video-policy-inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('SETTINGS_VIDEO_POLICY_PREPARED',receipt['after_sha256'])


if __name__=='__main__':main()
