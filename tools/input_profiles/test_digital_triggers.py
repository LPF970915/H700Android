#!/usr/bin/env python3
"""Compile the production joystick mapper with a fake event hub on Linux."""

import argparse
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
INPUT_READER = 'frameworks/native/services/inputflinger/InputReader'
OVERLAY = REPO / 'build-support/public/overlay' / (INPUT_READER + '.cpp')

FIXTURE = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iterator>
#include <linux/input.h>
#include <map>
#include <string>
#include <vector>
#include <android/input.h>

using nsecs_t = int64_t;
using std::fabs;
#define ALOGI(...) do {} while (0)
constexpr int INPUT_DEVICE_CLASS_JOYSTICK = 1;
int getAbsAxisUsage(int, int) { return INPUT_DEVICE_CLASS_JOYSTICK; }
float avg(float a, float b) { return (a + b) / 2; }

struct RawAbsoluteAxisInfo {
    bool valid = false;
    int32_t minValue = 0, maxValue = 0, flat = 0, fuzz = 0, resolution = 0;
};
struct AxisInfo {
    enum { MODE_NORMAL, MODE_INVERT, MODE_SPLIT } mode = MODE_NORMAL;
    int32_t axis = -1, highAxis = -1, splitValue = 0, flatOverride = -1;
};
struct RawEvent { nsecs_t when; int type, code, value; };
struct InputDeviceIdentifier {
    std::string name = "ANBERNIC-keys";
    uint16_t bus = BUS_HOST, vendor = 1, product = 1, version = 0x0100;
};
struct InputReaderConfiguration {};
struct PointerCoords {
    static constexpr size_t MAX_AXES = 30;
    std::array<float, 64> axes{};
    void setAxisValue(int axis, float value) { axes.at(axis) = value; }
};
struct InputDeviceInfo {
    std::map<int32_t, std::array<float, 2>> ranges;
    void addMotionRange(int32_t axis, uint32_t src, float min, float max, float, float, float) {
        assert(src == AINPUT_SOURCE_JOYSTICK);
        assert(ranges.emplace(axis, std::array<float, 2>{min, max}).second);
    }
};
template<typename K, typename V>
class KeyedVector {
    std::map<K, V> data;
    auto at(size_t i) { return std::next(data.begin(), i); }
    auto at(size_t i) const { return std::next(data.begin(), i); }
public:
    size_t size() const { return data.size(); }
    K keyAt(size_t i) const { return at(i)->first; }
    V& editValueAt(size_t i) { return at(i)->second; }
    const V& valueAt(size_t i) const { return at(i)->second; }
    ssize_t indexOfKey(K key) const {
        auto found = data.find(key);
        return found == data.end() ? -1 : std::distance(data.begin(), found);
    }
    void add(K key, V value) { assert(data.emplace(key, value).second); }
    void removeItemsAt(size_t i) { data.erase(at(i)); }
};
struct InputDevice {
    InputDeviceIdentifier id;
    bool external = false;
    std::map<int, bool> keys{{314, false}, {315, false}};
    std::map<int, int> mapped{{ABS_Z, AMOTION_EVENT_AXIS_Z}, {ABS_RUDDER, AMOTION_EVENT_AXIS_RZ}};
    std::vector<PointerCoords> events;
    bool hasKey(int code) const { return keys.count(code); }
    bool isKeyPressed(int code) const { return keys.count(code) && keys.at(code); }
    bool isExternal() const { return external; }
    int getClasses() const { return INPUT_DEVICE_CLASS_JOYSTICK; }
    InputDeviceIdentifier getDeviceIdentifier(int) const { return id; }
    int mapAxis(int, int code, AxisInfo* axis) const {
        if (!mapped.count(code)) return -1;
        axis->axis = mapped.at(code);
        return 0;
    }
};
class InputMapper {
    InputDevice* device;
public:
    explicit InputMapper(InputDevice* device) : device(device) {}
    virtual ~InputMapper() = default;
    void populateDeviceInfo(InputDeviceInfo*) {}
    void configure(nsecs_t, const InputReaderConfiguration*, uint32_t) {}
    void reset(nsecs_t) {}
    InputDevice* getEventHub() const { return device; }
    InputDevice* getDevice() const { return device; }
    int getDeviceId() const { return 2; }
    void getAbsoluteAxisInfo(int code, RawAbsoluteAxisInfo* raw) const {
        if (device->mapped.count(code)) {
            *raw = {true, -100, 100, 0, 0, 0};
        }
    }
};
'''

CASES = r'''
void JoystickInputMapper::dump(std::string&) {}

// Replace only the input dispatch plumbing. The mapper filters and emits its
// values with production code, including the compatibility aliases.
void JoystickInputMapper::sync(nsecs_t, bool force) {
    if (!filterAxes(force)) return;
    PointerCoords report;
    for (size_t i = 0; i < mAxes.size(); ++i) {
        const auto& axis = mAxes.valueAt(i);
        setPointerCoordsAxisValue(&report, axis.axisInfo.axis, axis.currentValue);
    }
    getDevice()->events.push_back(report);
}

static void emit(JoystickInputMapper& mapper, int type, int code, int value) {
    RawEvent event{0, type, code, value};
    mapper.process(&event);
}
static void report(JoystickInputMapper& mapper) { emit(mapper, EV_SYN, SYN_REPORT, 0); }
static InputDeviceInfo configure(JoystickInputMapper& mapper) {
    mapper.configure(0, nullptr, 0);
    InputDeviceInfo info;
    mapper.populateDeviceInfo(&info);
    return info;
}
static void expect(const InputDevice& device, float left, float right, float z, float rz) {
    auto axes = device.events.back().axes;
    assert(axes[AMOTION_EVENT_AXIS_LTRIGGER] == left && axes[AMOTION_EVENT_AXIS_BRAKE] == left);
    assert(axes[AMOTION_EVENT_AXIS_RTRIGGER] == right && axes[AMOTION_EVENT_AXIS_GAS] == right);
    assert(axes[AMOTION_EVENT_AXIS_Z] == z && axes[AMOTION_EVENT_AXIS_RZ] == rz);
}

int main() {
    InputDevice h700;
    JoystickInputMapper mapper(&h700);
    auto info = configure(mapper);
    assert(info.ranges.size() == 6);
    for (int axis : {AMOTION_EVENT_AXIS_LTRIGGER, AMOTION_EVENT_AXIS_RTRIGGER,
                     AMOTION_EVENT_AXIS_BRAKE, AMOTION_EVENT_AXIS_GAS}) {
        assert((info.ranges.at(axis) == std::array<float, 2>{0, 1}));
    }
    emit(mapper, EV_ABS, ABS_Z, 100);
    emit(mapper, EV_ABS, ABS_RUDDER, -100);
    report(mapper);
    expect(h700, 0, 0, 1, -1);
    emit(mapper, EV_KEY, 314, 1);
    assert(h700.events.size() == 1);
    report(mapper);
    expect(h700, 1, 0, 1, -1);
    emit(mapper, EV_KEY, 314, 2);
    emit(mapper, EV_KEY, 304, 1);
    report(mapper);
    assert(h700.events.size() == 2);
    emit(mapper, EV_KEY, 315, 1);
    report(mapper);
    expect(h700, 1, 1, 1, -1);
    emit(mapper, EV_KEY, 314, 0);
    report(mapper);
    expect(h700, 0, 1, 1, -1);
    emit(mapper, EV_KEY, 315, 0);
    report(mapper);
    expect(h700, 0, 0, 1, -1);
    emit(mapper, EV_KEY, 315, 1);
    report(mapper);
    mapper.reset(1); // Kernel state is released and the original edge was dropped.
    expect(h700, 0, 0, 0, 0);
    h700.keys[315] = true;
    mapper.reset(2);
    expect(h700, 0, 1, 0, 0);

    InputDevice external;
    external.id.bus = BUS_USB;
    external.external = true;
    JoystickInputMapper externalMapper(&external);
    assert(configure(externalMapper).ranges.size() == 2);
    emit(externalMapper, EV_KEY, 314, 1);
    report(externalMapper);
    assert(external.events.empty());

    InputDevice oneTrigger;
    oneTrigger.keys.erase(315);
    JoystickInputMapper oneTriggerMapper(&oneTrigger);
    auto oneInfo = configure(oneTriggerMapper);
    assert(oneInfo.ranges.count(AMOTION_EVENT_AXIS_LTRIGGER));
    assert(!oneInfo.ranges.count(AMOTION_EVENT_AXIS_RTRIGGER));

    InputDevice realTrigger;
    realTrigger.mapped[ABS_BRAKE] = AMOTION_EVENT_AXIS_BRAKE;
    JoystickInputMapper realTriggerMapper(&realTrigger);
    auto realInfo = configure(realTriggerMapper);
    assert(realInfo.ranges.count(AMOTION_EVENT_AXIS_BRAKE));
    assert(!realInfo.ranges.count(AMOTION_EVENT_AXIS_LTRIGGER));
    assert(realInfo.ranges.count(AMOTION_EVENT_AXIS_RTRIGGER));
}
'''


def test(native):
    header = (native / (INPUT_READER + '.h')).read_text()
    start = header.index('class JoystickInputMapper : public InputMapper')
    end = header.index('\n};', start) + len('\n};')
    mapper = header[start:end]
    impl = OVERLAY.read_text()
    start = impl.index('JoystickInputMapper::JoystickInputMapper(')
    stop = impl.index('void JoystickInputMapper::dump(', start)
    configuration = impl.index('void JoystickInputMapper::configure(', stop)
    sync = impl.index('void JoystickInputMapper::sync(', configuration)
    coords = impl.index('void JoystickInputMapper::setPointerCoordsAxisValue(', sync)
    end = impl.index('} // namespace android', coords)
    source = '\n'.join((FIXTURE, mapper, impl[start:stop], impl[configuration:sync], impl[coords:end], CASES))
    with tempfile.TemporaryDirectory(prefix='h700-trigger-test-') as directory:
        path = Path(directory)
        (path / 'test.cpp').write_text(source)
        subprocess.run(['c++', '-std=c++17', '-O2', '-I', native / 'frameworks/native/include',
                        path / 'test.cpp', '-o', path / 'test'], check=True)
        subprocess.run([path / 'test'], check=True)
    print('PASS: trigger ranges, aliases, independent edges, both held, reset, right stick, and scoping')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', required=True, type=Path)
    test(parser.parse_args().native)
