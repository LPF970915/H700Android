"""Exercise exact NavigationService fragments with a virtual Android boundary.

Run only inside the caller's capped build scope. This script does not build an
APK or contact a device. Framework stubs model action delivery and scheduling;
they do not prove Android framework or hardware behaviour.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def block_end(text, opening):
    """Match Java braces while ignoring strings, chars and comments."""
    depth, state, escaped, i = 0, "code", False, opening
    while i < len(text):
        char = text[i]
        after = text[i + 1] if i + 1 < len(text) else ""
        if state == "line":
            if char == "\n":
                state = "code"
        elif state == "comment":
            if char == "*" and after == "/":
                state, i = "code", i + 1
        elif state in ("string", "char"):
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif (state == "string" and char == '"') or (state == "char" and char == "'"):
                state = "code"
        elif char == "/" and after == "/":
            state, i = "line", i + 1
        elif char == "/" and after == "*":
            state, i = "comment", i + 1
        elif char == '"':
            state = "string"
        elif char == "'":
            state = "char"
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("Unterminated Java block")


def extract(text, pattern, field=False):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError("Expected one source fragment: " + pattern)
    start = matches[0].start()
    opening = text.index("{", matches[0].end() - 1)
    end = block_end(text, opening)
    if field:
        if text[end:].lstrip()[:1] != ";":
            raise ValueError("Runnable field lacks terminator")
        end = text.index(";", end) + 1
    return text[start:end]


HARNESS = r'''
package com.roc.rgsp.navtrial;
import java.util.*;

public final class ServiceFragmentTest {
    static int checks;
    static void check(boolean ok, String message) {
        checks++;
        if (!ok) throw new AssertionError(message);
    }
    static final class SystemClock {
        static long now;
        static long uptimeMillis() { return now; }
    }
    static final class Direction {
        static final int UP=19, DOWN=20, LEFT=21, RIGHT=22;
    }
    static final class Rect {
        int left, top, right, bottom;
        Rect(int l,int t,int r,int b) {left=l;top=t;right=r;bottom=b;}
        Rect(Rect r) {this(r.left,r.top,r.right,r.bottom);}
        public boolean equals(Object other) {
            if (!(other instanceof Rect)) return false;
            Rect r=(Rect)other;
            return left==r.left && top==r.top && right==r.right && bottom==r.bottom;
        }
        public int hashCode() {return Objects.hash(left,top,right,bottom);}
        String toShortString() {return left+","+top+","+right+","+bottom;}
    }
    static final class AccessibilityNodeInfo {
        static final int ACTION_FOCUS=1;
        static final class AccessibilityAction {
            static final AccessibilityAction ACTION_SHOW_ON_SCREEN=new AccessibilityAction();
            int getId() {return 16908342;}
        }
        final int id;
        int focuses, shows;
        boolean editable, focusSupport=true, showSupport=true, inList=true, range;
        String pkg="test.files";
        Rect rect=new Rect(0,0,100,40);
        AccessibilityNodeInfo(int id) {this.id=id;}
        static AccessibilityNodeInfo obtain(AccessibilityNodeInfo n) {return n;}
        void recycle() {}
        public boolean equals(Object o) {return o instanceof AccessibilityNodeInfo && ((AccessibilityNodeInfo)o).id==id;}
        public int hashCode() {return id;}
        boolean performAction(int action) {
            if(action==ACTION_FOCUS) focuses++;
            else if(action==AccessibilityAction.ACTION_SHOW_ON_SCREEN.getId()) shows++;
            else throw new AssertionError("Unexpected action "+action);
            return true;
        }
        boolean isEditable() {return editable;}
        Object getRangeInfo() {return range ? this : null;}
        String getPackageName() {return pkg;}
        int getWindowId() {return 7;}
    }
    static final class VirtualHandler {
        final Map<Runnable,Long> tasks=new IdentityHashMap<>();
        void removeCallbacks(Runnable task) {tasks.remove(task);}
        boolean postDelayed(Runnable task,long delay) {
            if(delay<0) throw new AssertionError("Negative delay");
            tasks.put(task,SystemClock.now+delay);return true;
        }
        void advance(long target) {
            int guard=0;
            while(true) {
                Runnable next=null; long at=Long.MAX_VALUE;
                for(Map.Entry<Runnable,Long> entry:tasks.entrySet())
                    if(entry.getValue()<at) {next=entry.getKey();at=entry.getValue();}
                if(next==null || at>target) break;
                if(++guard>1000) throw new AssertionError("Unbounded scheduler");
                tasks.remove(next);SystemClock.now=at;next.run();
            }
            SystemClock.now=target;
        }
    }
    static final class Mouse {boolean isActive(){return false;}}
    final VirtualHandler handler=new VirtualHandler();
    final Runnable refreshTask=()->refresh();
    AccessibilityNodeInfo selected, fixture=new AccessibilityNodeInfo(1);
    String selectedIdentity, mode="files", inputOrigin="external-key";
    static final String AT4K="com.overdevs.at4k";
    int selectionActions, ringRedraws;
    long releaseUntil;
    int pendingScroll;
    Mouse mouse;
    FocusRing ring=new FocusRing();
    final List<String> traces=new ArrayList<>();
    void trace(String text) {traces.add(text);}
    String identity(AccessibilityNodeInfo n) {return "semantic-"+n.id;}
    Rect focusBounds(AccessibilityNodeInfo n) {return new Rect(n.rect);}
    boolean supportsAction(AccessibilityNodeInfo n,int action) {
        return action==AccessibilityNodeInfo.ACTION_FOCUS ? n.focusSupport : n.showSupport;
    }
    boolean insideSettingsList(AccessibilityNodeInfo n) {return n.inList;}
    AccessibilityNodeInfo applicationRoot() {return fixture;}
    String scope(AccessibilityNodeInfo n) {return mode;}
    boolean managed() {return true;}
    void clearSelection() {selected=null;ring.show(null);}
    void collectItems(AccessibilityNodeInfo root,List<AccessibilityNodeInfo> items) {items.add(fixture);}
    int current(List<AccessibilityNodeInfo> items) {return 0;}
    boolean awaitingScroll(AccessibilityNodeInfo root) {return false;}
    int afterScroll(List<AccessibilityNodeInfo> items) {return 0;}
    int initial(List<AccessibilityNodeInfo> items) {return 0;}
    void recycle(List<AccessibilityNodeInfo> items) {}
    void overlayFocus(boolean value) {}

    __SELECT_DEFAULT__
    __SELECT__
    __REFRESH__

    final class FocusRing {
        Rect bounds;
        int invalidations, navigations;
        boolean allowed=true, present=true, synchronousStop, synchronousReplace;
        final AxisNavigation axis=new AxisNavigation();
        boolean repeatQueued;
        void invalidate() {invalidations++;}
        boolean axisAllowed() {return allowed;}
        boolean ownerPresent() {return present;}
        void navigate(int key,String origin) {
            navigations++;
            if(synchronousStop) stopRepeat("synchronous-navigation-stop");
            if(synchronousReplace) {
                stopRepeat("synchronous-owner-replaced");
                axis.update(SystemClock.now,99,0x1000010,Direction.DOWN,0);
            }
        }
        __SHOW__
        __RANGE__
        __REPEAT__
        __SCHEDULE__
        __STOP__
        void start(int direction) {
            int step=axis.update(SystemClock.now,7,0x1000010,direction,0);
            check(step==direction,"fixture starts owner");
            scheduleRepeat(AxisNavigation.FIRST_REPEAT_MS);
        }
    }

    static ServiceFragmentTest fresh() {SystemClock.now=0;return new ServiceFragmentTest();}
    static void selectionTests() {
        ServiceFragmentTest s=fresh();
        s.refresh();
        check(s.fixture.focuses==0 && s.fixture.shows==0 && s.selectionActions==0,
                "actual refresh performs no native actions on initial selection");
        s.fixture=new AccessibilityNodeInfo(2);s.refresh();
        check(s.fixture.focuses==0 && s.fixture.shows==0 && s.selectionActions==0,
                "actual refresh performs no native actions on replacement node");
        AccessibilityNodeInfo n=new AccessibilityNodeInfo(3);s.select(n);
        check(n.focuses==1 && n.shows==1 && s.selectionActions==2,
                "default user selection preserves focus and reveal");
        s.select(n);
        check(n.focuses==1 && n.shows==1,"unchanged explicit node is not re-actioned");
        AccessibilityNodeInfo passive=new AccessibilityNodeInfo(4);s.select(passive,false);
        check(passive.focuses==0 && passive.shows==0,"explicit passive selection is side-effect free");
        s.mode="settings";
        AccessibilityNodeInfo unsupported=new AccessibilityNodeInfo(5);unsupported.focusSupport=false;
        s.select(unsupported,true);
        check(unsupported.focuses==0 && unsupported.shows==1,"settings action support is retained");
        AccessibilityNodeInfo editable=new AccessibilityNodeInfo(6);editable.editable=true;
        s.select(editable,true);
        check(editable.focuses==1 && editable.shows==0,"editable controls are not revealed");
    }
    static void paintTests() {
        ServiceFragmentTest s=fresh();
        s.ring.show(null);
        check(s.ring.invalidations==0,"initial null bounds skip redraw");
        Rect first=new Rect(1,2,30,40);s.ring.show(first);
        check(s.ring.invalidations==1 && s.ringRedraws==1,"new bounds redraw once");
        s.ring.show(new Rect(first));
        check(s.ring.invalidations==1,"equal bounds skip invalidate");
        first.left=9;
        check(s.ring.bounds.left==1,"stored bounds are copied");
        s.ring.show(first);
        check(s.ring.invalidations==2,"changed bounds redraw");
        s.ring.show(null);s.ring.show(null);
        check(s.ring.invalidations==3,"clearing redraws only once");
    }
    static void repeatTests() {
        ServiceFragmentTest s=fresh();s.ring.start(Direction.DOWN);
        s.handler.advance(399);check(s.ring.navigations==0,"no early repeat");
        s.handler.advance(400);check(s.ring.navigations==1 && s.ring.repeatQueued,"first repeat schedules successor");
        s.handler.advance(10000);
        check(!s.ring.axis.active() && !s.ring.repeatQueued && s.handler.tasks.isEmpty(),"ten-second deadline drains actual wrapper");
        check(s.ring.navigations==60,"bounded 400ms then 160ms cadence");
        s.handler.advance(60000);check(s.ring.navigations==60,"no later task resurrection");

        s=fresh();s.ring.synchronousStop=true;s.ring.start(Direction.UP);s.handler.advance(400);
        check(s.ring.navigations==1 && !s.ring.axis.active() && !s.ring.repeatQueued && s.handler.tasks.isEmpty(),
                "navigate synchronously stops owner without requeue");
        s=fresh();s.ring.synchronousReplace=true;s.ring.start(Direction.DOWN);s.handler.advance(400);
        check(s.ring.axis.active() && !s.ring.repeatQueued && s.handler.tasks.isEmpty(),
                "generation change cannot inherit old runnable");
        s=fresh();s.selected=new AccessibilityNodeInfo(1);s.selected.range=true;
        s.ring.start(Direction.LEFT);s.handler.advance(400);
        check(s.ring.navigations==0 && !s.ring.axis.active() && s.handler.tasks.isEmpty(),
                "horizontal range remains a single initial step");
        s=fresh();s.ring.start(Direction.DOWN);s.ring.allowed=false;s.handler.advance(400);
        check(s.ring.navigations==0 && !s.ring.axis.active() && s.handler.tasks.isEmpty(),"lost context stops wrapper");
        s=fresh();s.ring.start(Direction.DOWN);s.ring.present=false;s.handler.advance(400);
        check(s.ring.navigations==0 && !s.ring.axis.active() && s.handler.tasks.isEmpty(),"removed owner stops wrapper");
        s=fresh();s.ring.start(Direction.UP);SystemClock.now=9950;s.ring.scheduleRepeat(160);
        check(s.handler.tasks.get(s.ring.repeat)==10000L,"last schedule clamps to deadline");
        s.handler.advance(10000);
        check(!s.ring.axis.active() && s.handler.tasks.isEmpty(),"clamped deadline expires without action");
    }
    public static void main(String[] args) {
        selectionTests();paintTests();repeatTests();
        System.out.println("PASS: "+checks+" actual Service fragment checks");
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "axis", "javac", "java", "work", "result"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    # A fresh output is intentional: old generated classes must never count.
    args.work.mkdir(parents=True, exist_ok=False)
    args.result.parent.mkdir(parents=True, exist_ok=True)
    report = {"schema": 1, "passed": False, "test_type": "actual_service_fragments_virtual_framework",
              "source_sha256": sha(args.source), "axis_sha256": sha(args.axis),
              "test_script_sha256": sha(__file__), "device_accessed": False,
              "APK_built": False, "hardware_reproduction": False}
    try:
        source = args.source.read_text(encoding="utf-8")
        patterns = {
            "SELECT_DEFAULT": r"private void select\(AccessibilityNodeInfo node\)\s*\{",
            "SELECT": r"private void select\(AccessibilityNodeInfo node, boolean requestActions\)\s*\{",
            "REFRESH": r"private void refresh\(\)\s*\{",
            "SHOW": r"void show\(Rect rect\)\s*\{",
            "RANGE": r"private boolean rangeDirection\(int key\)\s*\{",
            "REPEAT": r"private final Runnable repeat = new Runnable\(\)\s*\{",
            "SCHEDULE": r"private void scheduleRepeat\(long delay\)\s*\{",
            "STOP": r"void stopRepeat\(String reason\)\s*\{",
        }
        fragments = {name: extract(source, pattern, field=name == "REPEAT")
                     for name, pattern in patterns.items()}
        harness = HARNESS
        for name, fragment in fragments.items():
            harness = harness.replace("__" + name + "__", fragment)
        if re.search(r"__[A-Z_]+__", harness):
            raise ValueError("Unexpanded harness fragment")
        # MOVE boundary checks supplement, rather than substitute for, the
        # executed state machine and actual repeat wrapper above.
        motion = extract(source, r"@Override public boolean onGenericMotionEvent\(MotionEvent event\)\s*\{")
        static_checks = {
            "motion_source_matches_device": "(device.getSources() & event.getSource()) != event.getSource()" in motion,
            "raw_nonfinite_rejected": "Float.isNaN(raw) || Float.isInfinite(raw)" in motion,
            "normalized_nonfinite_rejected": "Float.isNaN(stick[0])" in motion and "Float.isInfinite(stick[1])" in motion,
            "motion_generation_rechecked": "axis.generation() == token" in motion,
            "motion_range_single_step": 'if (rangeDirection(key)) stopRepeat("range-single-step")' in motion,
        }
        report["static_boundary_checks"] = static_checks
        if not all(static_checks.values()):
            raise AssertionError("MOVE boundary check failed: " + str(static_checks))
        report["fragments_sha256"] = {name: hashlib.sha256(value.encode()).hexdigest()
                                      for name, value in fragments.items()}
        java_file = args.work / "ServiceFragmentTest.java"
        java_file.write_text(harness, encoding="utf-8", newline="\n")
        axis_file = args.work / "AxisNavigation.java"
        axis_file.write_bytes(args.axis.read_bytes())
        classes = args.work / "classes"
        classes.mkdir()
        commands = [
            [str(args.javac), "-encoding", "UTF-8", "-source", "8", "-target", "8", "-d", str(classes), str(axis_file), str(java_file)],
            [str(args.java), "-cp", str(classes), "com.roc.rgsp.navtrial.ServiceFragmentTest"],
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
                raise RuntimeError("Service fragment command failed: " + str(run.returncode))
        if not re.search(r"PASS: \d+ actual Service fragment checks", run.stdout):
            raise AssertionError("Missing explicit Service fragment PASS")
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        args.result.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": True, "result": str(args.result)}))


if __name__ == "__main__":
    main()
