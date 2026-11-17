"""Exercise isolated Navigation resume fragments with explicit Android doubles.

Run with the existing run-limited.sh wrapper. No APK, framework, image, signing,
device or card operation is performed. The exact AxisNavigation candidate and
extracted service/mouse lifecycle code execute on a host JVM. These checks do
not establish the cause of the remote HOME failure or test Android scheduling.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from test_navigation_service_fix import extract, HARNESS as LEGACY_HARNESS

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "com.roc.rgsp.navtrial."


def sha(data):
    return hashlib.sha256(data).hexdigest()


HARNESS = r'''
package com.roc.rgsp.navtrial;
import java.util.*;

public final class Source64ResumeFragmentTest {
    static int checks;
    static final List<String> scenarios = new ArrayList<>();
    static void check(boolean condition, String reason) {
        checks++; if (!condition) throw new AssertionError(reason);
    }
    static final class SystemClock { static long now; static long uptimeMillis(){return now;} }
    static final class Handler {
        final Map<Runnable,Long> tasks=new IdentityHashMap<>();
        boolean post(Runnable task){return postDelayed(task,0);}
        boolean postDelayed(Runnable task,long delay){tasks.put(task,SystemClock.now+delay);return true;}
        void removeCallbacks(Runnable task){tasks.remove(task);}
        void advance(long target){
            int guard=0;
            while(true){
                Runnable next=null;long when=Long.MAX_VALUE;
                for(Map.Entry<Runnable,Long> e:tasks.entrySet())
                    if(e.getValue()<when){next=e.getKey();when=e.getValue();}
                if(next==null||when>target)break;
                if(++guard>10000)throw new AssertionError("Unbounded virtual scheduler");
                tasks.remove(next);SystemClock.now=when;next.run();
            }
            SystemClock.now=target;
        }
    }
    static final class PowerManager {boolean interactive=true;boolean isInteractive(){return interactive;}}
    static final class KeyguardManager {boolean locked;boolean isKeyguardLocked(){return locked;}}
    static final class AccessibilityService {static final String POWER_SERVICE="power",KEYGUARD_SERVICE="keyguard";}
    static final class Context {}
    static final class Intent {
        final String action;Intent(String action){this.action=action;}String getAction(){return action;}
    }
    static abstract class BroadcastReceiver {public abstract void onReceive(Context c,Intent i);}
    static final class SparseBooleanArray {final Set<Integer> keys=new HashSet<>();void clear(){keys.clear();}}
    static final class SparseIntArray {final Map<Integer,Integer> data=new HashMap<>();int get(int id){return data.getOrDefault(id,0);}}
    static final class SparseLongArray {
        final Map<Integer,Long> data=new HashMap<>();
        long get(int id,long fallback){return data.getOrDefault(id,fallback);}
        void put(int id,long value){data.put(id,value);}
    }
    static class View {public boolean onGenericMotionEvent(MotionEvent e){return false;}}
    static final class InputDevice {
        static final int SOURCE_JOYSTICK=0x1000010;
        static final Map<Integer,InputDevice> devices=new HashMap<>();
        final int id,source;InputDevice(int id,int source){this.id=id;this.source=source;}
        static InputDevice getDevice(int id){return devices.get(id);}
        int getId(){return id;}int getSources(){return source;}
    }
    static final class MotionEvent {
        static final int ACTION_MOVE=2,ACTION_CANCEL=3;
        static final int AXIS_X=0,AXIS_Y=1,AXIS_Z=11,AXIS_RX=12,AXIS_RY=13,AXIS_RZ=14,AXIS_HAT_X=15,AXIS_HAT_Y=16;
        final int id,source,action;final long time;final float[] axes=new float[17];
        MotionEvent(int id,int source,int action,long time){this.id=id;this.source=source;this.action=action;this.time=time;}
        boolean isFromSource(int expected){return(source&expected)==expected;}
        int getActionMasked(){return action;}int getDeviceId(){return id;}int getSource(){return source;}
        InputDevice getDevice(){return InputDevice.getDevice(id);}long getEventTime(){return time;}
        float getAxisValue(int axis){return axes[axis];}
    }
    // Explicit normalization stand-in: hardware MotionRange/ADC behavior is not tested.
    static final class MouseController {
        static float[] sticks(MotionEvent e){return new float[]{e.getAxisValue(0),e.getAxisValue(1)};}
    }
    static final class KeyEvent {
        static final int ACTION_DOWN=0,ACTION_UP=1,FLAG_FALLBACK=0x400;
        static final int KEYCODE_DPAD_UP=19,KEYCODE_DPAD_DOWN=20,KEYCODE_DPAD_LEFT=21,KEYCODE_DPAD_RIGHT=22;
        static final int KEYCODE_BUTTON_A=96,KEYCODE_BUTTON_B=97,KEYCODE_BUTTON_X=99,KEYCODE_BUTTON_Y=100;
        static final int KEYCODE_DPAD_CENTER=23,KEYCODE_ENTER=66;
        static final int KEYCODE_BACK=4,KEYCODE_ESCAPE=111,KEYCODE_BUTTON_L1=102,KEYCODE_BUTTON_R1=103;
        final int device,key,action,scan;final long time;
        KeyEvent(int device,int key,int action,int scan){this.device=device;this.key=key;this.action=action;this.scan=scan;time=SystemClock.now;}
        int getDeviceId(){return device;}int getKeyCode(){return key;}int getAction(){return action;}
        int getScanCode(){return scan;}int getFlags(){return 0;}long getEventTime(){return time;}
        boolean isCanceled(){return false;}
    }
    static final class android {static final class util {static final class Log {static void i(String tag,String value){}}}}
    static final class Toast {
        static final int LENGTH_SHORT=0;static Toast makeText(Object service,String text,int duration){return new Toast();}
        void show(){}
    }
    static final class AccessibilityNodeInfo {int getWindowId(){return 1;}void recycle(){}}
    static final String POWER_SERVICE="power",KEYGUARD_SERVICE="keyguard";
    static final int GLOBAL_ACTION_HOME=2,GLOBAL_ACTION_QUICK_SETTINGS=5;
    final PowerManager power=new PowerManager();final KeyguardManager keyguard=new KeyguardManager();
    Object getSystemService(String type){return POWER_SERVICE.equals(type)?power:keyguard;}
    final Handler handler=new Handler();final MenuHotkey menu=new MenuHotkey();
    final SparseBooleanArray held=new SparseBooleanArray();
    final SparseIntArray deviceGenerations=new SparseIntArray();
    final List<String> traces=new ArrayList<>();
    final Runnable refreshTask=()->{};final Runnable documentLongPress=()->{};
    Runnable menuHold;long menuGeneration,releaseUntil;String armedIdentity,mode="files";int armedKey;
    boolean shadeBack;int menuHomeCount,menuShadeCount,globalActions,clears;
    final FocusRing ring=new FocusRing();final MouseProbe mouse=new MouseProbe();
    void trace(String detail){traces.add(detail);}
    void releaseForAction(){}void clearSelection(){clears++;}
    void stopPhysicalKeys(String reason){}
    boolean performGlobalAction(int action){globalActions++;return true;}
    AccessibilityNodeInfo applicationRoot(){return interactionAllowed()?new AccessibilityNodeInfo():null;}
    String scope(AccessibilityNodeInfo root){return mode;}

    __INTERACTION_ALLOWED__
    __CANCEL_MENU__
    __STOP_SESSION__
    __GUARD_INTERACTION__
    __SCHEDULE_MENU__
    __MENU_ACTION__
    __SCREEN_RECEIVER__
    __MOUSE_DIRECTION__
    __MOUSE_CONFIRM__

    final class FocusRing extends View {
        final AxisNavigation axis=new AxisNavigation();final SparseLongArray lastMotionTimes=new SparseLongArray();
        boolean repeatQueued,focused=true;int axisDeviceGeneration,axisWindow=-1,navigations;
        long axisAcceptedAt;String rawAxes="none";
        boolean hasWindowFocus(){return focused;}boolean isFocused(){return focused;}
        boolean ownerPresent(){return true;}boolean rangeDirection(int key){return false;}
        void navigate(int key,String origin){navigations++;}
        __AXIS_DIRECTION__
        __AXIS_ALLOWED__
        __AXIS_REPEAT__
        __AXIS_SCHEDULE__
        __AXIS_STOP__
        __MOTION__
    }

    final class MouseProbe {
        final Source64ResumeFragmentTest service=Source64ResumeFragmentTest.this;
        final MouseHotkey hotkey=new MouseHotkey();final Map<Long,Integer> consumed=new HashMap<>();
        boolean active,busy,destroyed,aLong,dragRunning,dragEndRequested,scrollAxisArmed=true;
        Long aKey,dragKey,scrollKey;int generation,selectToggleDevice=Integer.MIN_VALUE;
        long selectToggleGeneration,movementStart;float hatX,hatY,stickX,stickY;
        int enters,touches,ended;Runnable selectToggle;final Runnable frame=()->{};
        final Surface surface=new Surface();
        final class Surface{void show(float x,float y,boolean pressed){}void ended(){ended++;}}
        boolean isActive(){return active;}
        void enter(){if(allowed()&&!busy){active=true;enters++;}}
        void stopDrag(){dragEndRequested=true;}
        void startDrag(){}void swipe(int key){}void touch(boolean longPress){if(active&&allowed())touches++;}
        // Gesture delivery itself is outside this lifecycle probe.
        boolean onMotion(MotionEvent event){return active;}
        __MOUSE_ALLOWED__
        __MOUSE_CLEAR_MOVEMENT__
        __MOUSE_EXIT__
        __MOUSE_SUSPEND__
        __MOUSE_CANCEL_SELECT__
        __MOUSE_QUEUE_SELECT__
        __MOUSE_WINDOW_FOCUS__
        __MOUSE_A_TIMER__
        __MOUSE_ON_KEY__
    }

    static Source64ResumeFragmentTest fresh(){
        SystemClock.now=0;InputDevice.devices.clear();
        for(int id:new int[]{7,8,9})InputDevice.devices.put(id,new InputDevice(id,InputDevice.SOURCE_JOYSTICK));
        return new Source64ResumeFragmentTest();
    }
    static MotionEvent move(int device,int source,float hx,float hy,float x,float y){
        MotionEvent event=new MotionEvent(device,source,MotionEvent.ACTION_MOVE,SystemClock.now);
        event.axes[15]=hx;event.axes[16]=hy;event.axes[0]=x;event.axes[1]=y;return event;
    }
    static MotionEvent move(int device,float hx,float x){return move(device,InputDevice.SOURCE_JOYSTICK,hx,0,x,0);}
    static KeyEvent key(int code,int action){return new KeyEvent(7,code,action,code==109?310:0);}
    void pressMenu(){menu.update(7,110,312,false,true,false,SystemClock.now);scheduleMenu();}

    static void blockedSampleAndChannelIsolation(){
        Source64ResumeFragmentTest root=fresh();
        root.ring.axis.update(0,7,InputDevice.SOURCE_JOYSTICK,0,0);
        root.power.interactive=false;SystemClock.now=1;
        root.ring.onGenericMotionEvent(move(7,0,1));
        check(!root.ring.axis.active()&&root.ring.navigations==0,"blocked MOVE is observation only");
        check(root.ring.axis.describe(1).contains("axisBlockedObservations=1"),"blocked sample is retained");
        root.power.interactive=true;SystemClock.now=2;
        root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==0,"same nonzero sample cannot arm after resume");
        SystemClock.now=3;root.ring.onGenericMotionEvent(move(7,0,-1));
        check(root.ring.navigations==0,"polarity reversal cannot bypass blocked stick");
        SystemClock.now=4;root.ring.onGenericMotionEvent(move(8,0,0));
        SystemClock.now=5;root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==0,"foreign neutral cannot unlock original stream");
        SystemClock.now=6;root.ring.onGenericMotionEvent(move(7,-1,1));
        check(root.ring.navigations==1&&root.ring.axis.direction()==AxisNavigation.LEFT,"independent neutral HAT keeps first legal press");
        SystemClock.now=7;root.ring.onGenericMotionEvent(move(7,0,1));
        check(!root.ring.axis.active(),"HAT release does not hand off to blocked stick");
        SystemClock.now=8;root.ring.onGenericMotionEvent(move(7,0,0));
        SystemClock.now=9;root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==2&&root.ring.axis.direction()==AxisNavigation.RIGHT,"own neutral and repress recovers stick");
        scenarios.add("validated-blocked-MOVE-retained;channel-specific-neutral");
    }
    static void preserveFreshInputsAndSourceGates(){
        AxisNavigation axis=new AxisNavigation();int source=InputDevice.SOURCE_JOYSTICK,other=0x2000010;
        axis.update(0,7,source,0,0);axis.stop("screen-off",true);
        check(axis.update(1,7,source,AxisNavigation.DOWN,0)==AxisNavigation.DOWN,"known-neutral first press retained");
        axis.stop("screen-off",true);
        check(axis.update(2,9,source,AxisNavigation.RIGHT,0)==AxisNavigation.RIGHT,"unknown device first press retained");
        axis=new AxisNavigation();axis.observeBlocked(0,7,source,0,AxisNavigation.LEFT);
        check(axis.update(1,7,other,0,AxisNavigation.RIGHT)==0,"new source cannot bypass residual device gate");
        axis.update(2,7,other,0,0);
        check(axis.update(3,7,source,0,AxisNavigation.LEFT)==0,"other source neutral does not unlock original source");
        check(axis.update(4,7,other,0,AxisNavigation.RIGHT)==AxisNavigation.RIGHT,"that source can recover after its own neutral");
        axis=new AxisNavigation();axis.observeBlocked(0,7,source,0,0);
        check(axis.update(1,7,source,AxisNavigation.UP,0)==AxisNavigation.UP,"observed blocked neutral preserves first press");
        scenarios.add("known-neutral-and-new-device-first-press;source-isolation");
    }
    static void screenCancelsAndRetiresCallbacks(){
        for(String action:new String[]{"SCREEN_OFF","SCREEN_ON","USER_PRESENT"}){
            Source64ResumeFragmentTest cycle=fresh();cycle.pressMenu();Runnable staleMenu=cycle.menuHold;
            cycle.mouse.queueSelectToggle(7);Runnable staleSelect=cycle.mouse.selectToggle;
            cycle.screenReceiver.onReceive(new Context(),new Intent(action));
            check(cycle.menuHold==null&&cycle.mouse.selectToggle==null,"each screen broadcast retires both pending hotkeys: "+action);
            SystemClock.now=3000;staleMenu.run();staleSelect.run();
            check(cycle.globalActions==0&&cycle.mouse.enters==0,"each screen broadcast invalidates removed callbacks: "+action);
        }
        Source64ResumeFragmentTest root=fresh();root.pressMenu();Runnable oldMenu=root.menuHold;
        root.mouse.queueSelectToggle(7);Runnable oldSelect=root.mouse.selectToggle;
        root.armedIdentity="document";root.armedKey=96;root.held.keys.add(96);
        root.handler.postDelayed(root.documentLongPress,600);
        root.screenReceiver.onReceive(new Context(),new Intent("SCREEN_OFF"));
        check(root.menuHold==null&&root.menu.nextDelay(0)<0,"screen boundary clears menu press and runnable");
        check(root.mouse.selectToggle==null&&!root.mouse.active,"screen boundary clears Select toggle");
        check(root.armedIdentity==null&&root.held.keys.isEmpty()&&!root.handler.tasks.containsKey(root.documentLongPress),"screen boundary retires document hold");
        SystemClock.now=3000;oldMenu.run();oldSelect.run();
        check(root.globalActions==0&&root.mouse.enters==0,"already-removed old callbacks cannot revive on resume");
        check(root.menu.update(7,110,312,false,false,false,3000)==MenuHotkey.CONSUME,"late old Menu UP is consumed without short action");
        root.pressMenu();root.handler.advance(3700);
        check(root.menuShadeCount==1,"new standalone Menu hold works after boundary");
        root.mouse.queueSelectToggle(7);root.handler.advance(3800);
        check(root.mouse.enters==1,"new standalone Select request works after boundary");
        scenarios.add("screen-broadcast-retires-menu-select-document;fresh-hotkeys-recover");
    }
    static void liveStateBeforeBroadcast(){
        Source64ResumeFragmentTest root=fresh();root.pressMenu();root.mouse.queueSelectToggle(7);
        Runnable pendingMenu=root.menuHold,pendingSelect=root.mouse.selectToggle;
        root.power.interactive=false;SystemClock.now=800;pendingMenu.run();
        check(root.globalActions==0&&root.mouse.selectToggle==null,"live screen-off blocks Menu before broadcast and cancels Select");
        root.power.interactive=true;pendingSelect.run();
        check(root.mouse.enters==0,"off-retired Select does not enter after wake");
        root=fresh();root.pressMenu();root.keyguard.locked=true;root.handler.advance(700);
        check(root.globalActions==0&&root.menu.nextDelay(700)<0,"live keyguard blocks delayed Menu before broadcast");
        root=fresh();root.mouse.queueSelectToggle(7);root.power.interactive=false;root.handler.advance(100);
        check(root.mouse.enters==0&&root.mouse.selectToggle==null,"Select callback independently rejects live screen-off");
        root.power.interactive=true;root.handler.advance(3000);
        check(root.mouse.enters==0,"rejected Select has no periodic resurrection");
        scenarios.add("live-interactive-keyguard-block-before-broadcast");
    }
    static void retiredCallbacksDoNotEraseNewCallbacks(){
        Source64ResumeFragmentTest root=fresh();root.pressMenu();Runnable oldMenu=root.menuHold;
        root.cancelMenu();SystemClock.now=1;root.pressMenu();Runnable newMenu=root.menuHold;
        oldMenu.run();
        check(root.menuHold==newMenu&&root.handler.tasks.containsKey(newMenu),"retired Menu cannot erase new pending callback");
        root.mouse.queueSelectToggle(7);Runnable oldSelect=root.mouse.selectToggle;
        root.mouse.suspendInput();root.mouse.queueSelectToggle(8);Runnable newSelect=root.mouse.selectToggle;
        oldSelect.run();
        check(root.mouse.selectToggle==newSelect&&root.mouse.selectToggleDevice==8,"retired Select cannot erase newer pending request");
        root.handler.advance(101);
        check(root.mouse.enters==1,"new Select callback retains ownership");
        scenarios.add("generation-guards-preserve-newer-menu-select-requests");
    }
    static void mouseReleaseOwnershipAndHotkeyReset(){
        Source64ResumeFragmentTest root=fresh();root.mouse.active=true;
        check(root.mouse.onKey(key(22,KeyEvent.ACTION_DOWN)),"active mouse owns direction DOWN");
        root.mouse.onKey(key(109,KeyEvent.ACTION_DOWN));
        long identity=((long)7<<32)|22;
        root.mouse.suspendInput();
        check(root.mouse.consumed.containsKey(identity),"suspend retains previously consumed DOWN identity");
        check(root.mouse.consumed.get(identity)==0,"suspend removes held movement but retains release ownership");
        root.power.interactive=false;
        check(root.mouse.onKey(key(22,KeyEvent.ACTION_DOWN)),"owned repeated DOWN remains consumed while screen is off");
        root.power.interactive=true;
        check(root.mouse.onKey(key(22,KeyEvent.ACTION_DOWN)),"owned repeated DOWN remains consumed after resume");
        check(root.mouse.touches==0&&root.mouse.selectToggle==null,"owned repeats cannot touch or requeue Select");
        check(root.mouse.onKey(key(22,KeyEvent.ACTION_UP)),"eventual owned UP remains consumed after mode exit");
        check(!root.mouse.consumed.containsKey(identity),"owned UP retires ownership");
        SystemClock.now=3000;root.mouse.onKey(key(109,KeyEvent.ACTION_UP));
        check(root.mouse.selectToggle==null,"pre-sleep Select DOWN cannot trigger on post-resume UP");
        SystemClock.now=4000;root.mouse.onKey(key(109,KeyEvent.ACTION_DOWN));
        SystemClock.now=6000;root.mouse.onKey(key(109,KeyEvent.ACTION_UP));
        check(root.mouse.selectToggle!=null,"new full Select hold can queue normally");
        root.handler.advance(6100);check(root.mouse.active,"new full Select hold activates normally");
        root.power.interactive=false;root.mouse.onKey(key(22,KeyEvent.ACTION_DOWN));
        check(!root.mouse.active&&root.mouse.selectToggle==null,"live blocked key exits active mouse and retires pending hotkeys");
        Source64ResumeFragmentTest plain=fresh();
        check(!plain.mouse.onKey(key(109,KeyEvent.ACTION_DOWN)),"plain Select DOWN remains forwarded outside mouse mode");
        plain.power.interactive=false;plain.screenReceiver.onReceive(new Context(),new Intent("SCREEN_OFF"));
        SystemClock.now=3000;plain.power.interactive=true;
        check(!plain.mouse.onKey(key(109,KeyEvent.ACTION_UP)),"plain Select old UP remains forwarded after screen boundary");
        plain.handler.advance(3100);
        check(plain.mouse.selectToggle==null&&plain.mouse.enters==0,"plain Select pre-sleep DOWN cannot create post-resume toggle");
        scenarios.add("mouse-consumed-UP-balanced;old-Select-UP-does-not-toggle");
    }
    static void mouseAButtonTimerUsesLiveState(){
        Source64ResumeFragmentTest root=fresh();root.mouse.active=true;
        root.mouse.onKey(key(96,KeyEvent.ACTION_DOWN));root.keyguard.locked=true;
        root.handler.advance(600);
        check(root.mouse.touches==0&&!root.mouse.active&&root.mouse.aKey==null,"A hold timer observes live lock and retires session");
        scenarios.add("mouse-A-hold-live-lock-guard");
    }
    static void mouseContextStillRecordsBlockedAxis(){
        Source64ResumeFragmentTest root=fresh();root.mouse.active=true;
        root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==0&&!root.ring.axis.active(),"mouse-consumed MOVE cannot navigate service");
        check(root.ring.axis.describe(0).contains("axisBlockedObservations=1"),"mouse capture also observes blocked axis sample");
        root.mouse.suspendInput();SystemClock.now=1;root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==0,"held mouse axis cannot become navigation after mouse exit");
        SystemClock.now=2;root.ring.onGenericMotionEvent(move(7,0,0));
        SystemClock.now=3;root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==1,"mouse-exit navigation recovers after own neutral");
        scenarios.add("mouse-capture-records-blocked-axis-before-return");
    }
    static void rejectedSamplesDoNotEstablishNeutral(){
        Source64ResumeFragmentTest root=fresh();
        root.ring.axis.observeBlocked(0,7,InputDevice.SOURCE_JOYSTICK,0,AxisNavigation.RIGHT);
        SystemClock.now=2000;
        MotionEvent stale=new MotionEvent(7,InputDevice.SOURCE_JOYSTICK,MotionEvent.ACTION_MOVE,0);
        root.ring.onGenericMotionEvent(stale);
        root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==0,"rejected stale neutral cannot unlock gated stick");
        SystemClock.now=2001;MotionEvent invalid=move(7,0,0);invalid.axes[0]=Float.NaN;
        root.ring.onGenericMotionEvent(invalid);
        SystemClock.now=2002;root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==0,"nonfinite sample cannot unlock gated stick");
        SystemClock.now=2003;root.ring.onGenericMotionEvent(move(7,0,0));
        SystemClock.now=2004;root.ring.onGenericMotionEvent(move(7,0,1));
        check(root.ring.navigations==1,"validated neutral still recovers after rejected samples");
        scenarios.add("stale-and-nonfinite-samples-do-not-unlock");
    }
    public static void main(String[] args){
        blockedSampleAndChannelIsolation();preserveFreshInputsAndSourceGates();
        screenCancelsAndRetiresCallbacks();liveStateBeforeBroadcast();
        retiredCallbacksDoNotEraseNewCallbacks();mouseReleaseOwnershipAndHotkeyReset();
        mouseAButtonTimerUsesLiveState();mouseContextStillRecordsBlockedAxis();
        rejectedSamplesDoNotEstablishNeutral();
        for(String scenario:scenarios)System.out.println("SCENARIO "+scenario);
        System.out.println("PASS: "+checks+" actual candidate resume fragment checks");
    }
}
'''


KEY_HARNESS = r'''
package com.roc.rgsp.navtrial;
import java.util.*;

public final class Source64KeyWrapperTest {
    static int checks; static final List<String> scenarios=new ArrayList<>();
    static void check(boolean value,String reason){checks++;if(!value)throw new AssertionError(reason);}
    static final class SystemClock{static long now;static long uptimeMillis(){return now;}}
    static final class Handler {
        final Map<Runnable,Long> tasks=new IdentityHashMap<>();
        void removeCallbacks(Runnable task){tasks.remove(task);}
        boolean postDelayed(Runnable task,long delay){tasks.put(task,SystemClock.now+delay);return true;}
        void advance(long target){int guard=0;while(true){Runnable next=null;long when=Long.MAX_VALUE;
            for(Map.Entry<Runnable,Long> e:tasks.entrySet())if(e.getValue()<when){next=e.getKey();when=e.getValue();}
            if(next==null||when>target)break;if(++guard>1000)throw new AssertionError("unbounded key scheduler");
            tasks.remove(next);SystemClock.now=when;next.run();}SystemClock.now=target;}
    }
    static final class SparseBooleanArray{final Set<Integer> data=new HashSet<>();void delete(int key){data.remove(key);}}
    static final class AccessibilityNodeInfo{
        final int window;final String mode;AccessibilityNodeInfo(int window,String mode){this.window=window;this.mode=mode;}
        int getWindowId(){return window;}void recycle(){}
    }
    static final class MouseProbe{boolean active;boolean isActive(){return active;}boolean onKey(KeyEvent event){return active;}}
    static class View{public boolean dispatchKeyEvent(KeyEvent event){return false;}}
    static final class KeyEvent{
        static final int ACTION_DOWN=0,ACTION_UP=1;
        static final int KEYCODE_BUTTON_B=97,KEYCODE_BACK=4,KEYCODE_ESCAPE=111;
        final int action,key,device,source,scan,repeat;final long time;final boolean canceled;
        KeyEvent(int action,int key){this(action,key,-1,0,0,0,SystemClock.now,false);}
        KeyEvent(int action,int key,int device,int source,int scan,int repeat,long time,boolean canceled){
            this.action=action;this.key=key;this.device=device;this.source=source;this.scan=scan;
            this.repeat=repeat;this.time=time;this.canceled=canceled;}
        int getAction(){return action;}int getKeyCode(){return key;}int getDeviceId(){return device;}
        int getSource(){return source;}int getScanCode(){return scan;}int getRepeatCount(){return repeat;}
        long getEventTime(){return time;}boolean isCanceled(){return canceled;}
    }
    final Handler handler=new Handler();final SparseBooleanArray held=new SparseBooleanArray();
    final KeyNavigation physicalKeys=new KeyNavigation();final MouseProbe mouse=new MouseProbe();
    Runnable physicalRepeat;long physicalTaskGeneration,releaseUntil;int physicalWindow=-1;
    String physicalScope="inactive",currentMode="settings",inputOrigin="external-key";
    boolean axisSynthetic,keySynthetic,interactive=true,locked,reentrantStop;int window=1,navigations,mouseKeys;
    boolean interactionAllowed(){return interactive&&!locked;}
    AccessibilityNodeInfo applicationRoot(){return interactionAllowed()?new AccessibilityNodeInfo(window,currentMode):null;}
    String scope(AccessibilityNodeInfo root){return root==null?"inactive":root.mode;}
    void stopInputSession(String reason){stopPhysicalKeys(reason);}void back(){}

    __KEY_GUARD_INTERACTION__
    __MANAGED_SCOPE__
    __CANCEL_PHYSICAL__
    __STOP_PHYSICAL__
    __OBSERVE_UNAVAILABLE__
    __PHYSICAL_CONTEXT__
    __EMIT_PHYSICAL__
    __SCHEDULE_PHYSICAL__
    __PHYSICAL_DIRECTION__
    final class FocusRing extends View { __RING_KEY_DISPATCH__ }

    // Explicit dispatch boundary: menu/mouse/key delivery and the navigation
    // body are doubled; every controller, gate, timer and cancellation method
    // above is extracted from the exact service source.
    boolean onKeyEvent(KeyEvent event){
        if(!interactionAllowed()){stopPhysicalKeys("live-unavailable");observeUnavailableDirection(event);return false;}
        if(mouse.active){mouseKeys++;if(event.getAction()==KeyEvent.ACTION_UP)observeUnavailableDirection(event);return true;}
        if(physicalDirection(event))return true;
        if(KeyNavigation.direction(event.getKeyCode())&&event.getAction()==KeyEvent.ACTION_DOWN
                &&managedScope(currentMode)){
            navigations++;if(reentrantStop){reentrantStop=false;stopPhysicalKeys("synchronous-window-change");}
            return true;
        }
        return false;
    }
    static Source64KeyWrapperTest fresh(){SystemClock.now=0;return new Source64KeyWrapperTest();}
    KeyEvent raw(int action,int key,int repeat,boolean canceled){return new KeyEvent(action,key,7,0x101,key+100,repeat,SystemClock.now,canceled);}
    boolean down(int key){return onKeyEvent(raw(0,key,0,false));}
    boolean up(int key,boolean canceled){return onKeyEvent(raw(1,key,0,canceled));}

    static void localRepeatOwnsRawDowns(){
        Source64KeyWrapperTest t=fresh();check(t.down(21)&&t.navigations==1,"first press acts immediately");
        for(int time=10;time<400;time+=10){SystemClock.now=time;check(t.down(21),"raw zero-count repeats consumed");}
        check(t.navigations==1,"raw repeats do not navigate");
        t.handler.advance(400);check(t.navigations==2,"local first repeat at 400ms");
        t.handler.advance(559);check(t.navigations==2,"local repeat waits 160ms");
        t.handler.advance(560);check(t.navigations==3,"local repeat at 160ms");
        check(t.up(21,false)&&!t.physicalKeys.active(),"real UP retires owner");
        t.handler.advance(1000);check(t.navigations==3&&t.handler.tasks.isEmpty(),"release leaves no key callback");
        scenarios.add("managed-raw-DOWNs-use-local-400-160-timer");
    }
    static void absoluteCapAndCanceledRelease(){
        Source64KeyWrapperTest t=fresh();t.down(21);t.handler.advance(10000);int count=t.navigations;
        check(!t.physicalKeys.active()&&t.handler.tasks.isEmpty(),"absolute cap cancels repeat");
        SystemClock.now=10001;check(t.down(21)&&t.navigations==count,"zero count after cap cannot renew");
        t.up(21,true);SystemClock.now=10002;t.down(21);check(t.navigations==count,"canceled UP cannot rearm");
        t.up(21,false);SystemClock.now=10003;t.down(21);check(t.navigations==count+1,"real release permits fresh press");
        scenarios.add("absolute-10s-cap-requires-real-UP");
    }
    static void scopeAndWindowNeverReceiveOldRepeats(){
        Source64KeyWrapperTest t=fresh();t.down(21);t.currentMode="inactive";
        SystemClock.now=10;check(!t.down(22),"unmanaged game DOWN passes through");
        check(!t.physicalKeys.active()&&t.handler.tasks.isEmpty(),"game entry stops service timer");
        check(!t.up(21,false),"game UP passes through");
        t.currentMode="settings";SystemClock.now=20;
        check(t.onKeyEvent(t.raw(0,21,1,false))&&t.navigations==1,"orphan native repeat cannot own new page");
        t.up(21,false);SystemClock.now=21;t.down(21);int count=t.navigations;
        t.window=2;t.handler.advance(421);
        check(t.navigations==count&&!t.physicalKeys.active(),"window changed without broadcast still blocks old timer");
        scenarios.add("unmanaged-game-passthrough-and-window-owner");
    }
    static void axesMouseAndOtherButtonsRemainSeparate(){
        Source64KeyWrapperTest t=fresh();t.axisSynthetic=true;t.down(21);
        check(t.navigations==1&&!t.physicalKeys.active(),"axis-owned synthetic input bypasses physical timing");
        t.axisSynthetic=false;
        check(!t.physicalDirection(new KeyEvent(0,96)),"A is outside physical DPAD controller");
        check(!t.physicalDirection(new KeyEvent(0,97)),"B is outside physical DPAD controller");
        check(!t.physicalDirection(new KeyEvent(0,109)),"Select is outside physical DPAD controller");
        check(!t.physicalDirection(new KeyEvent(0,82)),"Menu is outside physical DPAD controller");
        t.mouse.active=true;t.down(21);check(t.mouseKeys==1&&!t.physicalKeys.active(),"mouse retains direction ownership");
        Source64KeyWrapperTest u=fresh();u.down(21);u.handler.advance(10000);int count=u.navigations;
        u.mouse.active=true;SystemClock.now=10001;u.up(21,true);u.mouse.active=false;
        SystemClock.now=10002;u.down(21);check(u.navigations==count,"mouse-owned canceled UP preserves timeout debt");
        u.mouse.active=true;SystemClock.now=10003;u.up(21,false);u.mouse.active=false;
        SystemClock.now=10004;u.down(21);check(u.navigations==count+1,"mouse-owned real UP clears timeout debt");
        scenarios.add("axis-mouse-and-non-DPAD-buttons-preserved");
    }
    static void generationsAndSynchronousStop(){
        Source64KeyWrapperTest t=fresh();t.down(21);Runnable old=t.physicalRepeat;
        SystemClock.now=1;t.stopPhysicalKeys("screen-off");SystemClock.now=2;t.down(22);Runnable current=t.physicalRepeat;
        int count=t.navigations;old.run();
        check(t.physicalRepeat==current&&t.navigations==count,"retired callback cannot erase newer task");
        t.reentrantStop=true;t.handler.advance(402);
        check(t.navigations==count+1&&!t.physicalKeys.active()&&t.handler.tasks.isEmpty(),"synchronous lifecycle stop cannot requeue");
        scenarios.add("retired-and-reentrant-key-callbacks-cannot-resurrect");
    }
    static void unavailableAndEventBoundaries(){
        Source64KeyWrapperTest t=fresh();SystemClock.now=100;t.stopPhysicalKeys("window-change");
        KeyEvent stale=new KeyEvent(0,21,7,0x101,121,0,99,false);
        check(t.onKeyEvent(stale)&&t.navigations==0&&!t.physicalKeys.active(),"pre-boundary DOWN is rejected");
        KeyEvent future=new KeyEvent(0,21,7,0x101,121,0,101,false);
        check(t.onKeyEvent(future)&&t.navigations==0,"future DOWN is rejected");
        t.interactive=false;check(!t.down(21)&&!t.physicalKeys.active(),"live screen state blocks before broadcast");
        SystemClock.now=101;t.interactive=true;t.stopPhysicalKeys("screen-on");t.down(21);
        check(t.navigations==1,"ordinary wake does not create permanent release debt");
        t.locked=true;t.handler.advance(501);check(t.navigations==1&&!t.physicalKeys.active(),"live keyguard stops queued repeat");
        scenarios.add("live-power-keyguard-and-event-time-boundaries");
    }
    static void ringUnavailableStillObservesRealRelease(){
        Source64KeyWrapperTest t=fresh();FocusRing ring=t.new FocusRing();t.down(21);t.handler.advance(10000);
        int count=t.navigations;t.interactive=false;SystemClock.now=10001;
        check(!ring.dispatchKeyEvent(t.raw(1,21,0,true)),"unavailable Ring keeps ordinary dispatch result");
        t.interactive=true;SystemClock.now=10002;t.down(21);
        check(t.navigations==count,"unavailable Ring canceled UP does not clear timeout debt");
        t.interactive=false;SystemClock.now=10003;ring.dispatchKeyEvent(t.raw(1,21,0,false));
        t.interactive=true;SystemClock.now=10004;t.down(21);
        check(t.navigations==count+1,"unavailable Ring real UP clears timeout debt");
        scenarios.add("unavailable-Ring-observes-real-UP-and-preserves-canceled-debt");
    }
    public static void main(String[] args){
        localRepeatOwnsRawDowns();absoluteCapAndCanceledRelease();scopeAndWindowNeverReceiveOldRepeats();
        axesMouseAndOtherButtonsRemainSeparate();generationsAndSynchronousStop();unavailableAndEventBoundaries();
        ringUnavailableStillObservesRealRelease();
        for(String scenario:scenarios)System.out.println("KEY_SCENARIO "+scenario);
        System.out.println("PASS: "+checks+" actual candidate key wrapper checks");
    }
}
'''

KEY_PATTERNS = {
    "KEY_GUARD_INTERACTION": r"private boolean guardInteraction\(String reason\)\s*\{",
    "MANAGED_SCOPE": r"private static boolean managedScope\(String currentMode\)\s*\{",
    "CANCEL_PHYSICAL": r"private void cancelPhysicalRepeat\(\)\s*\{",
    "STOP_PHYSICAL": r"private void stopPhysicalKeys\(String reason\)\s*\{",
    "OBSERVE_UNAVAILABLE": r"private void observeUnavailableDirection\(KeyEvent event\)\s*\{",
    "PHYSICAL_CONTEXT": r"private boolean physicalContextAllowed\(\)\s*\{",
    "EMIT_PHYSICAL": r"private void emitPhysicalDirection\(int key\)\s*\{",
    "SCHEDULE_PHYSICAL": r"private void schedulePhysicalRepeat\(\)\s*\{",
    "PHYSICAL_DIRECTION": r"private boolean physicalDirection\(KeyEvent event\)\s*\{",
    "RING_KEY_DISPATCH": r"@Override public boolean dispatchKeyEvent\(KeyEvent event\)\s*\{",
}


SERVICE_PATTERNS = {
    "INTERACTION_ALLOWED": r"private boolean interactionAllowed\(\)\s*\{",
    "CANCEL_MENU": r"private void cancelMenu\(\)\s*\{",
    "STOP_SESSION": r"private void stopInputSession\(String reason\)\s*\{",
    "GUARD_INTERACTION": r"private boolean guardInteraction\(String reason\)\s*\{",
    "SCHEDULE_MENU": r"private void scheduleMenu\(\)\s*\{",
    "MENU_ACTION": r"private void menuAction\(int action\)\s*\{",
    "SCREEN_RECEIVER": r"private final BroadcastReceiver screenReceiver = new BroadcastReceiver\(\)\s*\{",
    "AXIS_DIRECTION": r"private int axisDirection\(float x, float y\)\s*\{",
    "AXIS_ALLOWED": r"private boolean axisAllowed\(\)\s*\{",
    "AXIS_REPEAT": r"private final Runnable repeat = new Runnable\(\)\s*\{",
    "AXIS_SCHEDULE": r"private void scheduleRepeat\(long delay\)\s*\{",
    "AXIS_STOP": r"void stopRepeat\(String reason\)\s*\{",
    "MOTION": r"@Override public boolean onGenericMotionEvent\(MotionEvent event\)\s*\{",
}
MOUSE_PATTERNS = {
    "MOUSE_ALLOWED": r"private boolean allowed\(\)\s*\{",
    "MOUSE_DIRECTION": r"private static boolean direction\(int key\)\s*\{",
    "MOUSE_CONFIRM": r"private static boolean confirm\(KeyEvent event\)\s*\{",
    "MOUSE_CLEAR_MOVEMENT": r"private void clearMovement\(\)\s*\{",
    "MOUSE_EXIT": r"void exit\(\)\s*\{",
    "MOUSE_SUSPEND": r"void suspendInput\(\)\s*\{",
    "MOUSE_CANCEL_SELECT": r"private void cancelSelectToggle\(\)\s*\{",
    "MOUSE_QUEUE_SELECT": r"private void queueSelectToggle\(int device\)\s*\{",
    "MOUSE_WINDOW_FOCUS": r"void windowFocusLost\(\)\s*\{",
    "MOUSE_A_TIMER": r"private final Runnable aTimer = \(\) ->\s*\{",
    "MOUSE_ON_KEY": r"boolean onKey\(KeyEvent event\)\s*\{",
}


def generate(candidate, work):
    package = candidate / "src/com/roc/rgsp/navtrial"
    service = (package / "NavigationService.java").read_text(encoding="utf-8")
    mouse = (package / "MouseController.java").read_text(encoding="utf-8")
    manifest = ET.parse(candidate / "AndroidManifest.xml").getroot()
    android = "{http://schemas.android.com/apk/res/android}"
    if (manifest.get("package") != "com.roc.rgsp.navtrial"
            or manifest.get(android + "versionCode") != "18"
            or manifest.get(android + "versionName") != "2.4-resume-guard"):
        raise AssertionError("Expected isolated Navigation18 resume candidate manifest")
    fields = {"SCREEN_RECEIVER", "AXIS_REPEAT", "MOUSE_A_TIMER"}
    fragments = {name: extract(service, pattern, field=name in fields)
                 for name, pattern in SERVICE_PATTERNS.items()}
    fragments.update({name: extract(mouse, pattern, field=name in fields)
                      for name, pattern in MOUSE_PATTERNS.items()})
    key_fragments = {name: extract(service, pattern) for name, pattern in KEY_PATTERNS.items()}
    key_harness = KEY_HARNESS
    for name, fragment in key_fragments.items():
        # Only the lexical outer-class name changes for this standalone host.
        key_harness = key_harness.replace("__" + name + "__", fragment.replace(
                "NavigationService.this", "Source64KeyWrapperTest.this"))
    if re.search(r"__[A-Z_]+__", key_harness):
        raise ValueError("Unexpanded physical-key wrapper fragment")
    (work / "Source64KeyWrapperTest.java").write_text(key_harness, encoding="utf-8", newline="\n")
    harness = HARNESS
    for name, fragment in fragments.items():
        harness = harness.replace("__" + name + "__", fragment)
    if re.search(r"__[A-Z_]+__", harness):
        raise ValueError("Unexpanded candidate fragment")
    (work / "Source64ResumeFragmentTest.java").write_text(harness, encoding="utf-8", newline="\n")
    # Preserve the original 32 service-fragment assertions for allowed-state
    # regressions. Only the new live boundary is deliberately stubbed as allowed;
    # the separate harness above exercises the exact guard implementation.
    legacy = LEGACY_HARNESS.replace("    boolean managed() {return true;}",
            "    boolean managed() {return true;}\n"
            "    boolean guardInteraction(String reason) {return true;}\n"
            "    void stopPhysicalKeys(String reason) {}")
    legacy_patterns = {
        "SELECT_DEFAULT": r"private void select\(AccessibilityNodeInfo node\)\s*\{",
        "SELECT": r"private void select\(AccessibilityNodeInfo node, boolean requestActions\)\s*\{",
        "REFRESH": r"private void refresh\(\)\s*\{",
        "SHOW": r"void show\(Rect rect\)\s*\{",
        "RANGE": r"private boolean rangeDirection\(int key\)\s*\{",
        "REPEAT": r"private final Runnable repeat = new Runnable\(\)\s*\{",
        "SCHEDULE": r"private void scheduleRepeat\(long delay\)\s*\{",
        "STOP": r"void stopRepeat\(String reason\)\s*\{",
    }
    for name, pattern in legacy_patterns.items():
        legacy = legacy.replace("__" + name + "__", extract(service, pattern, field=name == "REPEAT"))
    if re.search(r"__[A-Z_]+__", legacy):
        raise ValueError("Unexpanded legacy fragment")
    (work / "ServiceFragmentTest.java").write_text(legacy, encoding="utf-8", newline="\n")
    static_checks = {
        "onKey_live_guard_before_menu": service.index('guardInteraction("key-unavailable")') < service.index("int menuResult = menu.update"),
        "dispatch_back_has_live_guard": 'guardInteraction("dispatch-key-unavailable")' in service,
        "refresh_before_mouse_has_live_guard": extract(service,r"private void refresh\(\)\s*\{").index("guardInteraction") < extract(service,r"private void refresh\(\)\s*\{").index("mouse.isActive()"),
        "blocked_observation_after_finite_validation": fragments["MOTION"].index("axis.observeBlocked") > fragments["MOTION"].index("Float.isNaN(stick[0])"),
        "mouse_capture_after_validated_axes": fragments["MOTION"].index("boolean mouseHandled") > fragments["MOTION"].index("Float.isNaN(stick[0])"),
        "mouse_motion_live_guard": 'if (!allowed())' in extract(mouse,r"boolean onMotion\(MotionEvent event\)\s*\{"),
        "diagnostic_candidate39": "navigationVersion=39" in service,
        "physical_gate_after_mouse_and_before_held": service.index("if (physicalDirection(event))")
                > service.index("if (mouse != null && mouse.onKey(event))")
                and service.index("if (physicalDirection(event))") < service.index("event.getAction() == KeyEvent.ACTION_UP && held.get(key)"),
        "unavailable_service_and_Ring_observe_directions": service.count("observeUnavailableDirection(event);") >= 3,
    }
    if not all(static_checks.values()):
        raise AssertionError("Candidate boundary guard missing: " + str(static_checks))
    copied = []
    tests = Path(__file__).resolve().parent / "com/roc/rgsp/navtrial"
    for name in ("AxisNavigation", "Direction", "MenuHotkey", "MouseHotkey", "KeyNavigation"):
        target = work / (name + ".java")
        shutil.copyfile(package / target.name, target)
        copied.append(target)
    target = work / "AxisNavigationTest.java"
    shutil.copyfile(tests / target.name, target)
    copied.append(target)
    target = work / "KeyNavigationTest.java"
    shutil.copyfile(tests / target.name, target)
    copied.append(target)
    return {"fragments_sha256": {name: sha(value.encode()) for name, value in fragments.items()},
            "static_checks": static_checks,
            "legacy_allowed_guard_stub": True,
            "key_wrapper_fragments_sha256": {name: sha(value.encode()) for name, value in key_fragments.items()},
            "candidate_version": {"versionCode": 18, "versionName": "2.4-resume-guard", "diagnostics": 39},
            "test_doubles": ["clock", "Handler", "power", "keyguard", "input device", "motion/key events",
                             "raw-to-stick normalization", "gesture delivery", "accessibility roots", "global actions"],
            "generated_files": {p.name: sha(p.read_bytes()) for p in sorted(work.glob("*.java"))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--javac", type=Path)
    parser.add_argument("--java", type=Path)
    parser.add_argument("--emit-only", action="store_true", help="Generate and inspect only; do not compile or run")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    inputs = {str(p): sha(p.read_bytes()) for p in sorted(args.candidate.rglob("*")) if p.is_file()}
    control_paths = [Path(__file__).resolve(), Path(__file__).with_name("test_navigation_service_fix.py"),
                     Path(__file__).parent / "com/roc/rgsp/navtrial/AxisNavigationTest.java",
                     Path(__file__).parent / "com/roc/rgsp/navtrial/KeyNavigationTest.java"]
    controls = {str(path): sha(path.read_bytes()) for path in control_paths}
    report = {"passed": False, "hardware_reproduction": False, "device_accessed": False,
              "production_modified": False, "APK_built": False, "HOME_fix_proven": False,
              "emit_only": args.emit_only, "candidate_inputs_sha256": inputs,
              "test_controls_sha256": controls, "commands": []}
    try:
        report.update(generate(args.candidate, args.work))
        if not args.emit_only:
            if args.javac is None or args.java is None:
                raise ValueError("--javac and --java are required for execution")
            classes = args.work / "classes"
            classes.mkdir()
            commands = [[str(args.javac), "-J-Xmx512m", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                         "-d", str(classes), *[str(p) for p in sorted(args.work.glob("*.java"))]]]
            commands.extend([[str(args.java), "-Xmx256m", "-cp", str(classes), PACKAGE + name]
                             for name in ("AxisNavigationTest", "ServiceFragmentTest", "Source64ResumeFragmentTest",
                                          "KeyNavigationTest", "Source64KeyWrapperTest")])
            for index, command in enumerate(commands):
                process = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, timeout=120)
                (args.work / ("command-" + str(index) + ".log")).write_text(process.stdout, encoding="utf-8", newline="\n")
                report["commands"].append({"argv": command, "returncode": process.returncode, "output": process.stdout})
                if process.returncode:
                    raise RuntimeError("Candidate host command failed: " + str(index))
            expected = [(1, r"PASS: 79 production AxisNavigation state-machine checks"),
                        (2, r"PASS: 32 actual Service fragment checks"),
                        (3, r"PASS: (\d+) actual candidate resume fragment checks")]
            for index, pattern in expected:
                if re.search(pattern, report["commands"][index]["output"]) is None:
                    raise AssertionError("Missing explicit PASS: " + pattern)
            output = report["commands"][3]["output"]
            report["resume_checks"] = int(re.search(expected[2][1], output).group(1))
            report["scenarios"] = re.findall(r"^SCENARIO (.+)$", output, re.MULTILINE)
            if len(report["scenarios"]) != 9:
                raise AssertionError("Expected nine candidate resume scenarios")
            key_controller = re.search(r"^PASS: (\d+) production KeyNavigation timing checks\s*$",
                                       report["commands"][4]["output"], re.MULTILINE)
            key_wrapper = re.search(r"^PASS: (\d+) actual candidate key wrapper checks\s*$",
                                    report["commands"][5]["output"], re.MULTILINE)
            if not key_controller or not key_wrapper:
                raise AssertionError("Missing physical key controller/wrapper execution PASS")
            report["key_navigation_checks"] = int(key_controller.group(1))
            report["key_wrapper_checks"] = int(key_wrapper.group(1))
            report["key_wrapper_scenarios"] = re.findall(r"^KEY_SCENARIO (.+)$", report["commands"][5]["output"], re.MULTILINE)
            if len(report["key_wrapper_scenarios"]) != 7:
                raise AssertionError("Expected seven physical-key wrapper scenarios")
        after = {str(p): sha(p.read_bytes()) for p in sorted(args.candidate.rglob("*")) if p.is_file()}
        if after != inputs or any(sha(Path(path).read_bytes()) != digest for path, digest in controls.items()):
            raise AssertionError("Candidate/test input changed")
        report["passed"] = True
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        (args.work / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": True, "emit_only": args.emit_only,
                      "result": str(args.work / "result.json")}))


if __name__ == "__main__":
    main()
