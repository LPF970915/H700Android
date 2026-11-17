"""Exercise the exact retained Android10 SyntheticJoystickHandler on a host JVM.

Run only through tools/public_build/run-limited.sh (or the parent capped scope).
This extracts the complete unchanged inner class; Android input delivery,
Handler scheduling, clock, MotionEvent and KeyEvent are explicit test doubles.
It neither builds framework/APK/images nor contacts a device. A passing probe
demonstrates source mechanisms, not the cause of a recorded hardware failure.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

from test_navigation_service_fix import block_end


SOURCE_SHA256 = "0eadf38bc8ceb599dcf57eb2d6a8b9e818a19ecedca1143b3a361682c0e64639"


def sha(data):
    return hashlib.sha256(data).hexdigest()


HARNESS = r'''
import java.util.*;

public final class NativeJoystickSourceProbe {
    static int checks;
    static final List<String> scenarios = new ArrayList<>();
    static void check(boolean condition, String reason) {
        checks++;
        if (!condition) throw new AssertionError(reason);
    }
    final AttachInfo mAttachInfo = new AttachInfo();
    final String mTag = "HostSourceProbe";
    final List<KeyEvent> delivered = new ArrayList<>();
    void enqueueInputEvent(KeyEvent event) { delivered.add(event); }
    static class AttachInfo { boolean mHasWindowFocus = true; }
    static class SystemClock {
        static long now;
        static long uptimeMillis() { return now; }
    }
    static class ViewConfiguration {
        // Deliberate virtual boundary constants; no device timing claim.
        static int getKeyRepeatTimeout() { return 500; }
        static int getKeyRepeatDelay() { return 50; }
    }
    static class Log {
        static void e(String tag, String text) { throw new AssertionError(text); }
        static void w(String tag, String text) { throw new AssertionError(text); }
    }
    static class SparseArray<T> {
        final TreeMap<Integer,T> values = new TreeMap<>();
        int size() { return values.size(); }
        T valueAt(int index) { return new ArrayList<T>(values.values()).get(index); }
        void put(int key, T value) { values.put(key, value); }
        void clear() { values.clear(); }
    }
    static class Message {
        int what;
        Object obj;
        long when, serial;
        boolean asynchronous;
        void setAsynchronous(boolean value) { asynchronous = value; }
    }
    static class Handler {
        final List<Message> messages = new ArrayList<>();
        long serial;
        Handler(boolean asynchronous) {}
        public void handleMessage(Message message) {}
        Message obtainMessage(int what, Object obj) {
            Message message = new Message(); message.what = what; message.obj = obj;
            return message;
        }
        boolean sendMessageDelayed(Message message, long delay) {
            message.when = SystemClock.now + delay; message.serial = ++serial;
            messages.add(message); return true;
        }
        void removeMessages(int what) {
            for (Iterator<Message> it = messages.iterator(); it.hasNext();)
                if (it.next().what == what) it.remove();
        }
        void advance(long milliseconds) {
            final long until = SystemClock.now + milliseconds;
            int executed = 0;
            while (true) {
                Message next = null;
                for (Message message : messages) {
                    if (message.when <= until && (next == null || message.when < next.when
                            || (message.when == next.when && message.serial < next.serial)))
                        next = message;
                }
                if (next == null) break;
                if (++executed > 10000) throw new AssertionError("Unbounded virtual execution");
                messages.remove(next); SystemClock.now = next.when; handleMessage(next);
            }
            SystemClock.now = until;
        }
    }
    static class KeyEvent {
        static final int ACTION_DOWN=0, ACTION_UP=1;
        static final int KEYCODE_UNKNOWN=0, KEYCODE_DPAD_UP=19, KEYCODE_DPAD_DOWN=20;
        static final int KEYCODE_DPAD_LEFT=21, KEYCODE_DPAD_RIGHT=22;
        static final int FLAG_FALLBACK=0x400, FLAG_CANCELED=0x20;
        final long downTime, eventTime;
        final int action, keyCode, repeat, metaState, deviceId, scanCode, flags, source;
        KeyEvent(long downTime, long eventTime, int action, int keyCode, int repeat,
                int metaState, int deviceId, int scanCode, int flags, int source) {
            this.downTime=downTime;this.eventTime=eventTime;this.action=action;
            this.keyCode=keyCode;this.repeat=repeat;this.metaState=metaState;
            this.deviceId=deviceId;this.scanCode=scanCode;this.flags=flags;this.source=source;
        }
        int getRepeatCount() { return repeat; }
        static KeyEvent changeTimeRepeat(KeyEvent old, long time, int repeat) {
            return new KeyEvent(old.downTime,time,old.action,old.keyCode,repeat,
                    old.metaState,old.deviceId,old.scanCode,old.flags,old.source);
        }
    }
    static class MotionEvent {
        static final int ACTION_MOVE=2, ACTION_CANCEL=3;
        static final int AXIS_X=0, AXIS_Y=1, AXIS_Z=11, AXIS_RZ=14;
        static final int AXIS_HAT_X=15, AXIS_HAT_Y=16;
        final int action, deviceId;
        final float[] axes = new float[17];
        MotionEvent(int action, int deviceId, float x, float y, float hatX, float hatY) {
            this.action=action;this.deviceId=deviceId;
            axes[AXIS_X]=x;axes[AXIS_Y]=y;axes[AXIS_HAT_X]=hatX;axes[AXIS_HAT_Y]=hatY;
        }
        int getActionMasked() { return action; }
        int getHistorySize() { return 0; }
        long getEventTime() { return SystemClock.now; }
        long getHistoricalEventTime(int history) { throw new AssertionError("No history fixture"); }
        float getHistoricalAxisValue(int axis, int pointer, int history) {
            throw new AssertionError("No history fixture");
        }
        float getAxisValue(int axis) { return axes[axis]; }
        int getMetaState() { return 0; }
        int getDeviceId() { return deviceId; }
        int getSource() { return 0x1000010; }
    }

/* EXACT_COMPLETE_SOURCE_CLASS */

    static NativeJoystickSourceProbe fresh() {
        SystemClock.now=0;return new NativeJoystickSourceProbe();
    }
    static MotionEvent move(int device, float x, float y, float hx, float hy) {
        return new MotionEvent(MotionEvent.ACTION_MOVE,device,x,y,hx,hy);
    }
    int count(int action, int key) {
        int count=0;
        for (KeyEvent event : delivered)
            if (event.action==action && event.keyCode==key) count++;
        return count;
    }
    static void testSingleAxisWithoutNewMove() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        handler.process(move(7,1,0,0,0));
        check(root.delivered.size()==1,"one X immediate DOWN");
        check(handler.messages.size()==1,"one X repeat queued");
        handler.advance(60000);
        check(root.delivered.size()==1192,"one X sample produces 1192 DOWNs in virtual 60 seconds");
        check(handler.messages.size()==1,"X repeat remains queued beyond ten seconds");
        check(root.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==0,"no fabricated release");
        scenarios.add("single-X-without-further-MOVE:1192-DOWNs/virtual-60s");
    }
    static void testOpposedHatAndStick() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        handler.process(move(7,1,0,-1,0));
        check(root.delivered.size()==2,"conflicting X/HAT emit two immediate DOWNs");
        check(root.delivered.get(0).keyCode==KeyEvent.KEYCODE_DPAD_RIGHT,"X update precedes HAT");
        check(root.delivered.get(1).keyCode==KeyEvent.KEYCODE_DPAD_LEFT,"HAT emits opposite DOWN");
        check(handler.messages.size()==2,"two messages with shared horizontal what coexist");
        check(handler.messages.get(0).what==handler.messages.get(1).what,"both use same what");
        handler.advance(750);
        check(root.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==7,"right immediate plus six repeats");
        check(root.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT)==7,"left immediate plus six repeats");
        check(handler.messages.size()==2,"both repeat loops persist");
        scenarios.add("opposed-X-HAT:two-concurrent-opposite-repeat-loops");
    }
    static void testHatNeutralCancelsBoth() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        handler.process(move(7,1,0,-1,0));handler.advance(750);
        handler.process(move(7,1,0,0,0));
        check(handler.messages.isEmpty(),"HAT neutral removes ALL horizontal repeat messages");
        check(root.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_LEFT)==1,"HAT receives UP");
        check(root.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==0,"other X has no UP");
        int count=root.delivered.size();handler.advance(2000);
        check(root.delivered.size()==count,"canceled X repeat does not reappear");
        handler.process(move(7,1,0,0,0));
        check(root.delivered.size()==count,"unchanged held X cannot rearm after shared removal");
        check(handler.messages.isEmpty(),"unchanged X remains without repeat");
        scenarios.add("HAT-neutral:cancels-both-horizontal-loops");
    }
    static void testCancelAndRecoveryNonzero() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        handler.process(move(7,1,0,-1,0));handler.advance(550);
        handler.process(new MotionEvent(MotionEvent.ACTION_CANCEL,7,0,0,0,0));
        check(handler.messages.isEmpty(),"CANCEL removes both axis message classes");
        check(handler.mDeviceKeyEvents.size()==0,"CANCEL clears stored per-device UP");
        check(handler.mJoystickAxesState.mAxisStatesStick[0]==0,"CANCEL resets X state");
        check(handler.mJoystickAxesState.mAxisStatesHat[0]==0,"CANCEL resets HAT state");
        check(root.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_LEFT)==1,"CANCEL emits last stored UP");
        check(root.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==0,"same-device storage kept only last axis UP");
        KeyEvent canceled=root.delivered.get(root.delivered.size()-1);
        check((canceled.flags&KeyEvent.FLAG_CANCELED)!=0,"cancel UP carries CANCELED");
        int count=root.delivered.size();handler.advance(2000);
        check(root.delivered.size()==count,"CANCEL has no delayed resurrection");
        handler.process(move(7,1,0,0,0));
        check(root.delivered.size()==count+1,"fresh nonzero MOVE after reset starts immediately");
        check(handler.messages.size()==1,"fresh nonzero MOVE can rearm after recovery");
        scenarios.add("CANCEL-clears;new-post-reset-nonzero-rearms-without-neutral");
    }
    static void testFocusBoundaryAndExplicitCancel() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        handler.process(move(7,1,0,0,0));root.mAttachInfo.mHasWindowFocus=false;
        handler.advance(500);
        check(root.delivered.size()==1,"repeat callback suppresses delivery without focus");
        check(handler.messages.isEmpty(),"unfocused callback does not requeue");
        // Model the verified SyntheticInputStage focus-loss call to cancel().
        handler.cancel();root.mAttachInfo.mHasWindowFocus=true;
        handler.process(move(7,1,0,0,0));
        check(root.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==2,"post-cancel sample can start again");
        scenarios.add("focus-guard-and-modeled-explicit-focus-cancel");
    }
    static void testDeviceStateIsShared() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        handler.process(move(7,1,0,0,0));
        handler.process(move(8,1,0,0,0));
        check(root.delivered.size()==1,"same-valued axis from second device does not get own DOWN");
        check(((KeyEvent)handler.messages.get(0).obj).deviceId==7,"repeat still attributed to first device");
        handler.process(move(8,0,0,0,0));
        check(handler.messages.isEmpty(),"second device neutral cancels first device repeat");
        KeyEvent release=root.delivered.get(root.delivered.size()-1);
        check(release.action==KeyEvent.ACTION_UP && release.deviceId==8,"UP attributed to neutral device");
        check(handler.mDeviceKeyEvents.size()==2,"per-device UP table does not isolate shared axis states");
        scenarios.add("shared-axis-state-across-devices");
    }
    static void testRightStickIsNotSynthesized() {
        NativeJoystickSourceProbe root=fresh();
        SyntheticJoystickHandler handler=root.new SyntheticJoystickHandler();
        MotionEvent event=move(7,0,0,0,0);
        event.axes[MotionEvent.AXIS_Z]=1;event.axes[MotionEvent.AXIS_RZ]=-1;
        handler.process(event);
        check(root.delivered.isEmpty(),"right-stick Z/RZ produce no DPAD in this handler");
        check(handler.messages.isEmpty(),"right-stick Z/RZ start no repeat");
        scenarios.add("right-stick-Z-RZ-ignored-by-this-handler");
    }
    public static void main(String[] args) {
        testSingleAxisWithoutNewMove();testOpposedHatAndStick();testHatNeutralCancelsBoth();
        testCancelAndRecoveryNonzero();testFocusBoundaryAndExplicitCancel();
        testDeviceStateIsShared();testRightStickIsNotSynthesized();
        for(String scenario:scenarios) System.out.println("SCENARIO "+scenario);
        System.out.println("PASS: "+checks+" actual SyntheticJoystickHandler source checks");
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--javac", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    report = {
        "passed": False,
        "scope": "exact source class; virtual Android input/scheduling; host only",
        "hardware_reproduction": False,
        "production_source_modified": False,
        "Android_framework_built": False,
        "virtual_repeat_timeout_ms": 500,
        "virtual_repeat_delay_ms": 50,
        "source": str(args.source),
        "expected_source_sha256": SOURCE_SHA256,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "extractor_sha256": sha(Path(__file__).with_name("test_navigation_service_fix.py").read_bytes()),
    }
    try:
        original = args.source.read_bytes()
        report["source_sha256"] = sha(original)
        if report["source_sha256"] != SOURCE_SHA256:
            raise ValueError("Retained ViewRootImpl source SHA differs")
        source = original.decode("utf-8")
        marker = "    final class SyntheticJoystickHandler extends Handler {"
        if source.count(marker) != 1:
            raise ValueError("Expected one complete SyntheticJoystickHandler class")
        start = source.index(marker)
        end = block_end(source, source.index("{", start))
        fragment = source[start:end]
        report["source_first_line"] = source[:start].count("\n") + 1
        report["source_last_line"] = source[:end].count("\n") + 1
        report["fragment_sha256"] = sha(fragment.encode())
        report["fragment_bytes"] = len(fragment.encode())
        (args.work / "SyntheticJoystickHandler.exact.java.txt").write_text(
            fragment, encoding="utf-8", newline="\n")
        java_source = HARNESS.replace("/* EXACT_COMPLETE_SOURCE_CLASS */", fragment)
        java_file = args.work / "NativeJoystickSourceProbe.java"
        java_file.write_text(java_source, encoding="utf-8", newline="\n")
        report["generated_harness_sha256"] = sha(java_file.read_bytes())
        classes = args.work / "classes"
        classes.mkdir()
        commands = [
            [str(args.javac), "-encoding", "UTF-8", "-source", "8", "-target", "8",
             "-d", str(classes), str(java_file)],
            [str(args.java), "-cp", str(classes), "NativeJoystickSourceProbe"],
        ]
        report["commands"] = []
        for index, command in enumerate(commands):
            run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=90)
            (args.work / ("compile.log" if index == 0 else "run.log")).write_text(
                run.stdout, encoding="utf-8", newline="\n")
            report["commands"].append({"argv": command, "returncode": run.returncode,
                                       "output": run.stdout})
            if run.returncode:
                raise RuntimeError("Host source probe command failed: " + str(run.returncode))
        match = re.search(r"PASS: (\d+) actual SyntheticJoystickHandler source checks", run.stdout)
        if match is None:
            raise AssertionError("Missing explicit source probe PASS")
        report["checks"] = int(match.group(1))
        report["scenarios"] = re.findall(r"^SCENARIO (.+)$", run.stdout, re.MULTILINE)
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        (args.work / "result.json").write_text(json.dumps(report, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    print(json.dumps({"passed": True, "checks": report["checks"],
                      "result": str(args.work / "result.json")}))


if __name__ == "__main__":
    main()
