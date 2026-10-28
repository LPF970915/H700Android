import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;
import java.lang.reflect.Method;

/** Bounded joystick-only fixture; never injects a click or edits settings. */
public final class StickMotion {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("axis value: X/Y/Z/RZ, -1..1");
        int axis;
        switch (args[0]) {
            case "X": axis = MotionEvent.AXIS_X; break;
            case "Y": axis = MotionEvent.AXIS_Y; break;
            case "Z": axis = MotionEvent.AXIS_Z; break;
            case "RZ": axis = MotionEvent.AXIS_RZ; break;
            default: throw new IllegalArgumentException("Unknown axis");
        }
        float value = Float.parseFloat(args[1]);
        if (!Float.isFinite(value) || Math.abs(value) > 1) throw new IllegalArgumentException("Value range");
        InputDevice controller = null;
        for (int id : InputDevice.getDeviceIds()) {
            InputDevice candidate = InputDevice.getDevice(id);
            if (candidate != null && "ANBERNIC-keys".equals(candidate.getName())) {
                if (controller != null) throw new IllegalStateException("Ambiguous controller");
                controller = candidate;
            }
        }
        if (controller == null || controller.getMotionRange(axis, InputDevice.SOURCE_JOYSTICK) == null)
            throw new IllegalStateException("Controller/axis unavailable");
        Class<?> type = Class.forName("android.hardware.input.InputManager");
        Object manager = type.getMethod("getInstance").invoke(null);
        Method inject = type.getMethod("injectInputEvent", InputEvent.class, int.class);
        MotionEvent.PointerProperties properties = new MotionEvent.PointerProperties();
        properties.id = 0;
        properties.toolType = MotionEvent.TOOL_TYPE_UNKNOWN;
        long start = SystemClock.uptimeMillis();
        // Always finish by sending an explicit neutral frame, even on failure.
        try {
            for (int i = 0; i < 25; i++) {
                send(manager, inject, controller.getId(), properties, axis, value, start);
                SystemClock.sleep(20);
            }
        } finally {
            send(manager, inject, controller.getId(), properties, axis, 0, start);
        }
        System.out.println("STICK_FIXTURE_FINISHED " + args[0] + "=" + value);
    }

    private static void send(Object manager, Method inject, int device,
            MotionEvent.PointerProperties properties, int axis, float value, long start) throws Exception {
        MotionEvent.PointerCoords coordinates = new MotionEvent.PointerCoords();
        coordinates.setAxisValue(axis, value);
        MotionEvent event = MotionEvent.obtain(start, SystemClock.uptimeMillis(), MotionEvent.ACTION_MOVE,
                1, new MotionEvent.PointerProperties[]{properties},
                new MotionEvent.PointerCoords[]{coordinates}, 0, 0, 1, 1, device, 0,
                InputDevice.SOURCE_JOYSTICK, 0);
        try {
            if (!Boolean.TRUE.equals(inject.invoke(manager, event, 2)))
                throw new IllegalStateException("Motion injection rejected");
        } finally { event.recycle(); }
    }
}
