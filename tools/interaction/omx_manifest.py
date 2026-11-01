"""Declare only the existing OMX interfaces; codec selection is unchanged."""
import xml.etree.ElementTree as ET

BLOCK = b'''    <hal format="hidl">
        <name>android.hardware.media.omx</name>
        <transport>hwbinder</transport>
        <version>1.0</version>
        <interface><name>IOmx</name><instance>default</instance></interface>
        <interface><name>IOmxStore</name><instance>default</instance></interface>
    </hal>
'''

def patch(data):
    root = ET.fromstring(data)
    assert root.attrib['type'] == 'device'
    assert not any(h.findtext('name') == 'android.hardware.media.omx' for h in root.findall('hal'))
    assert data.count(b'    <sepolicy>') == 1
    result = data.replace(b'    <sepolicy>', BLOCK + b'    <sepolicy>')
    ET.fromstring(result)
    return result
