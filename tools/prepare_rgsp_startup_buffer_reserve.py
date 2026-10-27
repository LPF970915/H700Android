"""Keep the H700 allocator's malformed first framebuffer allocation off screen."""
import argparse
import hashlib
from pathlib import Path

REL = 'frameworks/native/services/surfaceflinger/DisplayHardware/FramebufferSurface.cpp'
BEFORE = '01dcc1e7367857a6054cfc3207d6417665538e7e1451b6a9c1ef2cfe3a2a0e60'
ANCHOR = '''    mConsumer->setMaxAcquiredBufferCount(
            SurfaceFlinger::maxFrameBufferAcquiredBuffers - 1);'''
RESERVE = '''    // On this H700 BSP the first allocator buffer can acquire an all-zero
    // crop attribute after boot; Mali rejects it and SF periodically presents
    // its unrendered contents. Keep that startup allocation outside the BQ.
    // This is a process-lifetime reserve, not an extra queued/displayed frame.
    char productDevice[PROPERTY_VALUE_MAX] = {};
    char boardPlatform[PROPERTY_VALUE_MAX] = {};
    property_get("ro.product.device", productDevice, "");
    property_get("ro.board.platform", boardPlatform, "");
    const auto internalId = mHwc.getInternalHwcDisplayId();
    const auto physicalId = mHwc.fromPhysicalDisplayId(displayId);
    if (!strcmp(productDevice, "rgsp") && !strcmp(boardPlatform, "cupid")
            && internalId && physicalId && *internalId == *physicalId
            && activeConfig->getWidth() == 720 && activeConfig->getHeight() == 480) {
        static Mutex reserveLock;
        static sp<GraphicBuffer> startupReserve;
        Mutex::Autolock lock(reserveLock);
        if (startupReserve == nullptr) {
            sp<GraphicBuffer> buffer = new GraphicBuffer(
                    activeConfig->getWidth(), activeConfig->getHeight(),
                    HAL_PIXEL_FORMAT_RGBA_8888, 1,
                    GRALLOC_USAGE_HW_FB | GRALLOC_USAGE_HW_RENDER | GRALLOC_USAGE_HW_COMPOSER,
                    "RGSP startup allocator reserve");
            if (buffer->initCheck() == NO_ERROR) {
                startupReserve = buffer;
                ALOGI("Retaining startup allocator buffer for RGSP LCD (%ux%u)",
                      activeConfig->getWidth(), activeConfig->getHeight());
            } else {
                ALOGW("Unable to retain startup allocator buffer: %d", buffer->initCheck());
            }
        }
    }
'''
EDITS = [('#include <utils/String8.h>', '#include <utils/String8.h>\n#include <cutils/properties.h>'),
         (ANCHOR, RESERVE + ANCHOR)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    target = args.source / REL
    source = target.read_text()
    original = source
    if hashlib.sha256(original.encode()).hexdigest() != BEFORE:
        for old, new in reversed(EDITS):
            original = original.replace(new, old, 1)
    if hashlib.sha256(original.encode()).hexdigest() != BEFORE:
        raise SystemExit('Unexpected FramebufferSurface edits; preserved')
    patched = original
    for old, new in EDITS:
        if patched.count(old) != 1:
            raise SystemExit('Ambiguous startup-buffer reserve anchor')
        patched = patched.replace(old, new, 1)
    target.write_bytes(patched.encode())
    print('RGSP_STARTUP_BUFFER_RESERVE_PREPARED', hashlib.sha256(patched.encode()).hexdigest())


if __name__ == '__main__':
    main()
