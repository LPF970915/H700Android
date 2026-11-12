// SPDX-License-Identifier: Apache-2.0
#define LOG_TAG "H700Light"

#include "Backlight.h"

#include <android-base/properties.h>
#include <android-base/unique_fd.h>
#include <android/hardware/light/2.0/ILight.h>
#include <hidl/HidlTransportSupport.h>
#include <log/log.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <cerrno>

using android::hardware::Return;
using android::hardware::Void;
using android::hardware::hidl_vec;
using namespace android::hardware::light::V2_0;

class DispIo final : public h700::DisplayIo {
public:
    int set(int fd, unsigned long command, unsigned long* args) override {
        int result;
        do {
            result = ioctl(fd, command, args);
        } while (result < 0 && errno == EINTR);
        return result < 0 ? -errno : 0;
    }
};

class Light final : public ILight {
public:
    explicit Light(int fd) : backlight_(fd, io_) {}

    Return<Status> setLight(Type type, const LightState& state) override {
        if (type != Type::BACKLIGHT) return Status::LIGHT_NOT_SUPPORTED;
        if (state.brightnessMode == Brightness::LOW_PERSISTENCE)
            return Status::BRIGHTNESS_NOT_SUPPORTED;
        int result = backlight_.setColor(state.color);
        if (result != 0) {
            ALOGE("Backlight ioctl failed: %d", result);
            return Status::UNKNOWN;
        }
        return Status::SUCCESS;
    }

    Return<void> getSupportedTypes(getSupportedTypes_cb callback) override {
        hidl_vec<Type> types;
        types.resize(1);
        types[0] = Type::BACKLIGHT;
        callback(types);
        return Void();
    }

private:
    DispIo io_;
    h700::Backlight backlight_;
};

int main() {
    // Product labels alone are shared across several physical H700 devices.
    if (android::base::GetProperty("ro.product.device", "") != "rgsp"
            || android::base::GetProperty("persist.vendor.rgsp.input_profile", "")
                != "rg34xxsp") {
        ALOGE("Refusing an unqualified device/profile");
        return 1;
    }
    // The vendor driver accepts the brightness ioctl on a read-only handle;
    // this also matches its existing hal_light_default SELinux permissions.
    android::base::unique_fd fd(open("/dev/disp", O_RDONLY | O_CLOEXEC));
    if (fd.get() < 0) {
        ALOGE("Cannot open /dev/disp: %d", errno);
        return 1;
    }
    android::hardware::configureRpcThreadpool(1, true);
    android::sp<ILight> service = new Light(fd.get());
    if (service->registerAsService("default") != android::OK) {
        ALOGE("Cannot register ILight/default");
        return 1;
    }
    android::hardware::joinRpcThreadpool();
    return 1;
}
