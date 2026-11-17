"""Exercise SHA-bound candidate fragments with a virtual Android boundary.

The real complete guard, routed legacy class, SyntheticInputStage and actual
DisplayListener/onMovedToDisplay methods are extracted without rewriting Java.
Scheduling and Android delivery are test doubles, not hardware acceptance.
Run javac/java only through tools/public_build/run-limited.sh.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess

from test_navigation_service_fix import extract


def sha(data):
    return hashlib.sha256(data).hexdigest()


HARNESS = r'''
import java.util.*;

public final class RocJoystickCandidateTest {
    static int checks;
    static final List<String> scenarios = new ArrayList<>();
    static void check(boolean value, String reason) {
        checks++;
        if (!value) throw new AssertionError(reason);
    }
    final AttachInfo mAttachInfo = new AttachInfo();
    final Context mContext = new Context();
    final String mTag = "RocJoystickCandidateTest";
    Display mDisplay = new Display(0, Display.STATE_ON);
    View mView = new View();
    boolean mAdded=true,mStopped=false,mNewSurfaceNeeded;
    static final boolean DEBUG_DRAW=false;
    final List<WindowStoppedCallback> mWindowStoppedCallbacks=new ArrayList<>();
    SurfaceHolder mSurfaceHolder;final Surface mSurface=new Surface();
    boolean mFullRedrawNeeded;
    InputStage mSyntheticInputStage;
    final List<KeyEvent> delivered = new ArrayList<>();
    final List<Integer> deliveryFlags = new ArrayList<>();
    final List<QueuedInputEvent> pendingKeys = new ArrayList<>();
    final HostPostImeStage mHostPostIme = new HostPostImeStage();
    final UnhandledKeyManager mUnhandledKeyManager = new UnhandledKeyManager();
    final FallbackEventHandler mFallbackEventHandler = new FallbackEventHandler();
    final InputCompatProcessor mInputCompatProcessor = new InputCompatProcessor();
    boolean autoDispatch=true,dispatching;
    int dispatchFlags,recycled;
    RocJoystickCandidateTest(String packageName) {
        mContext.name=packageName; mSyntheticInputStage=new SyntheticInputStage();
    }
    void enqueueInputEvent(KeyEvent event) {enqueueInputEvent(event,null,0,false);}
    void enqueueInputEvent(InputEvent event,InputEventReceiver receiver,int flags,boolean immediate) {
        check(receiver==null&&!immediate,"guard queues locally with no external receiver");
        QueuedInputEvent q=new QueuedInputEvent(event);q.mFlags=flags;q.mReceiver=receiver;pendingKeys.add(q);
        if(autoDispatch&&!dispatching)drain();
    }
    void drain(){
        dispatching=true;
        try{while(!pendingKeys.isEmpty())dispatch(pendingKeys.remove(0));}finally{dispatching=false;}
    }
    void dispatch(QueuedInputEvent q){
        dispatchFlags=q.mFlags;
        // InputStage drops every event before onProcess when its root was removed.
        if(mView!=null&&mAdded)mHostPostIme.processKeyEvent(q);
        finishInputEvent(q);
    }
    void recycleQueuedInputEvent(QueuedInputEvent q){
        check(q.mEvent!=null,"finish cleanup precedes queue recycle");
        if((q.mFlags&QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED)!=0
                &&mSyntheticInputStage instanceof SyntheticInputStage){
            check(!guard().mDeliveries.containsKey(q.mEvent),"delivery metadata cleared before queue recycle");
        }
        q.mEvent=null;q.mFlags=0;recycled++;
    }
    static class InputEventReceiver {void finishInputEvent(InputEvent event,boolean handled){}}
    static class InputCompatProcessor {InputEvent processInputEventBeforeFinish(InputEvent event){return event;}}
    static class Trace {static final long TRACE_TAG_VIEW=8;static void asyncTraceEnd(long tag,String name,int sequence){}
        static void traceBegin(long tag,String name){}static void traceEnd(long tag){}}
    static class UnhandledKeyManager {boolean preViewDispatch(KeyEvent event){return false;}
        boolean dispatch(View view,KeyEvent event){return false;}}
    static class FallbackEventHandler {boolean dispatchKeyEvent(KeyEvent event){return false;}}
    boolean performKeyboardGroupNavigation(int direction){return false;}
    boolean performFocusNavigation(KeyEvent event){return false;}
    void pokeDrawLockIfNeeded() {}
    void scheduleTraversals() {}
    void checkThread() {}String getTitle(){return "host fixture";}
    void notifySurfaceDestroyed() {}void destroySurface() {}
    void updateInternalDisplay(int id, Object resources) { mDisplay=new Display(id,Display.STATE_ON); }
    static class Context { String name; String getPackageName() {return name;} }
    static class AttachInfo {
        boolean mHasWindowFocus=true;int mDisplayState=Display.STATE_ON;
        ThreadedRenderer mThreadedRenderer;
    }
    interface WindowStoppedCallback {void windowStopped(boolean stopped);}
    static class ThreadedRenderer {void setStopped(boolean stopped){}void destroyHardwareResources(View view){}}
    static class SurfaceHolder {}static class Surface {boolean isValid(){return false;}}
    interface DisplayListener {
        void onDisplayChanged(int id); void onDisplayRemoved(int id); void onDisplayAdded(int id);
    }
    static class Display {
        static final int STATE_UNKNOWN=0,STATE_OFF=1,STATE_ON=2,STATE_DOZE=3;
        static final int STATE_DOZE_SUSPEND=4,STATE_VR=5,STATE_ON_SUSPEND=6;
        final int id; int state;boolean valid=true;
        Display(int id,int state) {this.id=id;this.state=state;}
        int getDisplayId() {return id;} int getState() {return state;}boolean isValid(){return valid;}
    }
    final class View {
        static final int SCREEN_STATE_OFF=0,SCREEN_STATE_ON=1;
        static final int FOCUS_FORWARD=2,FOCUS_BACKWARD=1;
        int changes,moves;
        boolean dispatchKeyEvent(KeyEvent event){delivered.add(event);deliveryFlags.add(dispatchFlags);return true;}
        boolean dispatchKeyShortcutEvent(KeyEvent event){return false;}
        void dispatchScreenStateChanged(int state) {changes++;}
        void dispatchMovedToDisplay(Display display,Configuration configuration) {moves++;}
        Object getResources() {return null;}
    }
    static class Configuration {}
    static class SystemClock {static long now;static long uptimeMillis() {return now;}}
    static class ViewConfiguration {
        static int getKeyRepeatTimeout() {return 500;} static int getKeyRepeatDelay() {return 50;}
    }
    static class Log {
        static void e(String tag,String text) {throw new AssertionError(text);}
        static void w(String tag,String text) {throw new AssertionError(text);}
        static void d(String tag,String text) {}
    }
    static class SparseArray<T> {
        final TreeMap<Integer,T> values=new TreeMap<>();
        int size() {return values.size();}
        T valueAt(int index) {return new ArrayList<T>(values.values()).get(index);}
        void put(int key,T value) {values.put(key,value);} void clear() {values.clear();}
    }
    static class Message {
        int what;Object obj;long when,serial;boolean asynchronous;
        void setAsynchronous(boolean value) {asynchronous=value;}
    }
    static class Handler {
        static final List<Handler> all=new ArrayList<>();static long sequence;
        final List<Message> messages=new ArrayList<>();
        Handler(boolean asynchronous) {all.add(this);}
        public void handleMessage(Message message) {}
        Message obtainMessage(int what,Object obj) {
            Message result=new Message();result.what=what;result.obj=obj;return result;
        }
        boolean sendMessageDelayed(Message message,long delay) {
            if (delay<0) throw new AssertionError("negative schedule");
            message.when=SystemClock.now+delay;message.serial=++sequence;
            messages.add(message);return true;
        }
        void removeMessages(int what) {
            for (Iterator<Message> i=messages.iterator();i.hasNext();) if(i.next().what==what)i.remove();
        }
        void removeMessages(int what,Object token) {
            for (Iterator<Message> i=messages.iterator();i.hasNext();) {
                Message message=i.next();if(message.what==what&&message.obj==token)i.remove();
            }
        }
        static void advance(long milliseconds) {
            long until=SystemClock.now+milliseconds;int callbacks=0;
            while(true) {
                Message next=null;Handler owner=null;
                for(Handler handler:all)for(Message candidate:handler.messages) {
                    if(candidate.when<=until&&(next==null||candidate.when<next.when
                            ||candidate.when==next.when&&candidate.serial<next.serial)) {
                        next=candidate;owner=handler;
                    }
                }
                if(next==null)break;
                if(++callbacks>100000)throw new AssertionError("unbounded virtual schedule");
                owner.messages.remove(next);SystemClock.now=next.when;owner.handleMessage(next);
            }
            SystemClock.now=until;
        }
        static int pending() {int count=0;for(Handler handler:all)count+=handler.messages.size();return count;}
    }
    static class InputDevice {
        static final int SOURCE_CLASS_TRACKBALL=4,SOURCE_CLASS_JOYSTICK=16;
        static final int SOURCE_TOUCH_NAVIGATION=0x200000;
        static final int JOYSTICK=0x1000010,OTHER_SOURCE=0x1000410;
        static final Map<Integer,InputDevice> devices=new HashMap<>();
        int sources;
        InputDevice(int value) {sources=value;}
        static InputDevice getDevice(int id) {return devices.get(id);}
        int getSources() {return sources;}
    }
    static class InputEvent {
        static int nextSequence;int sequence=++nextSequence;
        int getSource() {return 0;}int getSequenceNumber(){return sequence;}
        void recycleIfNeededAfterDispatch(){}
    }
    static class KeyEvent extends InputEvent {
        static final int ACTION_DOWN=0,ACTION_UP=1;
        static final int KEYCODE_UNKNOWN=0,KEYCODE_DPAD_UP=19,KEYCODE_DPAD_DOWN=20;
        static final int KEYCODE_DPAD_LEFT=21,KEYCODE_DPAD_RIGHT=22;
        static final int KEYCODE_TAB=61,META_META_ON=65536,META_SHIFT_ON=1;
        static final int FLAG_FALLBACK=0x400,FLAG_CANCELED=0x20;
        final long downTime,eventTime;
        final int action,keyCode,repeat,metaState,deviceId,scanCode,flags,source;
        KeyEvent(long downTime,long eventTime,int action,int keyCode,int repeat,
                int metaState,int deviceId,int scanCode,int flags,int source) {
            this.downTime=downTime;this.eventTime=eventTime;this.action=action;this.keyCode=keyCode;
            this.repeat=repeat;this.metaState=metaState;this.deviceId=deviceId;this.scanCode=scanCode;
            this.flags=flags;this.source=source;
        }
        long getDownTime(){return downTime;}int getKeyCode(){return keyCode;}int getAction(){return action;}
        int getMetaState(){return metaState;}int getRepeatCount(){return repeat;}
        static boolean metaStateHasModifiers(int state,int modifiers){return state==modifiers;}
        static boolean metaStateHasNoModifiers(int state){return state==0;}
        static boolean isModifierKey(int key){return false;}
        @Override int getSource(){return source;}
        static KeyEvent changeTimeRepeat(KeyEvent old,long time,int repeat) {
            return new KeyEvent(old.downTime,time,old.action,old.keyCode,repeat,
                    old.metaState,old.deviceId,old.scanCode,old.flags,old.source);
        }
    }
    static class MotionEvent extends InputEvent {
        static final int ACTION_MOVE=2,ACTION_CANCEL=3;
        static final int AXIS_X=0,AXIS_Y=1,AXIS_Z=11,AXIS_RZ=14,AXIS_HAT_X=15,AXIS_HAT_Y=16;
        final int action,deviceId,source;long time=SystemClock.now;
        final float[] axes=new float[17];
        final List<float[]> history=new ArrayList<>();final List<Long> times=new ArrayList<>();
        MotionEvent(int action,int device,int source,float x,float y,float hx,float hy) {
            this.action=action;this.deviceId=device;this.source=source;
            axes[AXIS_X]=x;axes[AXIS_Y]=y;axes[AXIS_HAT_X]=hx;axes[AXIS_HAT_Y]=hy;
        }
        MotionEvent history(long time,float x,float y,float hx,float hy) {
            float[] values=new float[17];values[AXIS_X]=x;values[AXIS_Y]=y;
            values[AXIS_HAT_X]=hx;values[AXIS_HAT_Y]=hy;history.add(values);times.add(time);return this;
        }
        int getActionMasked(){return action;}int getHistorySize(){return history.size();}
        long getEventTime(){return time;}long getHistoricalEventTime(int h){return times.get(h);}
        float getHistoricalAxisValue(int axis,int pointer,int h){return history.get(h)[axis];}
        float getAxisValue(int axis){return axes[axis];}int getMetaState(){return 3;}
        int getDeviceId(){return deviceId;}@Override int getSource(){return source;}
    }
    static class QueuedInputEvent {
        static final int FLAG_RESYNTHESIZED=1,FLAG_UNHANDLED=2;
        static final int FLAG_FINISHED_HANDLED=1<<3,FLAG_MODIFIED_FOR_COMPATIBILITY=1<<6;
        private static final int FLAG_ROC_JOYSTICK_GUARDED=1<<9;
        int mFlags;InputEvent mEvent;InputEventReceiver mReceiver;
        QueuedInputEvent(InputEvent event){mEvent=event;}
    }
    static class InputStage {
        static final int FINISH_HANDLED=1,FINISH_NOT_HANDLED=2,FORWARD=0;
        InputStage(Object next){}protected int onProcess(QueuedInputEvent q){return FORWARD;}
        protected void onDeliverToNext(QueuedInputEvent q){}
        protected void onWindowFocusChanged(boolean focus){}protected void onDetachedFromWindow(){}
        boolean shouldDropInputEvent(QueuedInputEvent q){return false;}
    }
    static class SyntheticTrackballHandler {void process(MotionEvent e){}void cancel(){}}
    static class SyntheticTouchNavigationHandler {void process(MotionEvent e){}void cancel(MotionEvent e){}}
    static class SyntheticKeyboardHandler {void process(KeyEvent e){}}

/* EXACT_CANDIDATE_FRAGMENTS */

    final class HostPostImeStage extends InputStage {
        HostPostImeStage(){super(null);}
/* EXACT_POST_IME_KEY_METHOD */
    }

    SyntheticJoystickHandler joystick(){return ((SyntheticInputStage)mSyntheticInputStage).mJoystick;}
    RocJoystickGuard guard(){return joystick().mRocGuard;}
    static RocJoystickCandidateTest fresh(){return fresh("com.overdevs.at4k");}
    static RocJoystickCandidateTest fresh(String packageName){
        Handler.all.clear();Handler.sequence=0;SystemClock.now=0;InputDevice.devices.clear();
        InputEvent.nextSequence=0;
        InputDevice.devices.put(7,new InputDevice(InputDevice.OTHER_SOURCE));
        InputDevice.devices.put(8,new InputDevice(InputDevice.OTHER_SOURCE));
        return new RocJoystickCandidateTest(packageName);
    }
    static MotionEvent move(int device,float x,float y,float hx,float hy){
        return sourceMove(device,InputDevice.JOYSTICK,x,y,hx,hy);
    }
    static MotionEvent sourceMove(int device,int source,float x,float y,float hx,float hy){
        return new MotionEvent(MotionEvent.ACTION_MOVE,device,source,x,y,hx,hy);
    }
    void process(MotionEvent event){
        check(mSyntheticInputStage.onProcess(new QueuedInputEvent(event))==InputStage.FINISH_HANDLED,
                "actual stage routes joystick fallback");
    }
    int count(int action,int key){int total=0;for(KeyEvent e:delivered)if(e.action==action&&e.keyCode==key)total++;return total;}
    int downs(){int total=0;for(KeyEvent e:delivered)if(e.action==KeyEvent.ACTION_DOWN)total++;return total;}
    void focus(boolean value){mAttachInfo.mHasWindowFocus=value;mSyntheticInputStage.onWindowFocusChanged(value);}
    void screen(int state){mDisplay.state=state;mDisplayListener.onDisplayChanged(mDisplay.id);}
    static String identity(KeyEvent e){return e.deviceId+":"+e.source+":"+e.keyCode+":"+e.downTime;}
    static void balanced(RocJoystickCandidateTest root){
        Set<String> active=new HashSet<>();
        for(KeyEvent e:root.delivered){
            String key=identity(e);
            if(e.action==KeyEvent.ACTION_DOWN&&e.repeat==0)check(active.add(key),"no duplicate initial DOWN: "+key);
            else if(e.action==KeyEvent.ACTION_DOWN)check(active.contains(key),"repeat belongs to held DOWN: "+key);
            else check(active.remove(key),"UP belongs to exactly one held DOWN: "+key);
        }
        check(active.isEmpty(),"all accepted DOWNs balanced");
        int expectedFlags=root.isRocNavigationGuardEnabled()?QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED:0;
        for(int flags:root.deliveryFlags)check(flags==expectedFlags,
                "guarded fallback has private queue provenance; game legacy has none");
    }
    static void testDeadlineWithoutMove(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));
        check(r.downs()==1,"one immediate X down");check(Handler.pending()==2,"one repeat and independent deadline");
        Handler.advance(399);check(r.downs()==1,"short press does not repeat before 400ms");
        Handler.advance(1);check(r.downs()==2&&r.delivered.get(1).eventTime==400,"first long-press repeat at 400ms");
        Handler.advance(159);check(r.downs()==2,"no extra repeat before 160ms interval");
        Handler.advance(1);check(r.downs()==3&&r.delivered.get(2).eventTime==560,"navigation repeat interval is 160ms");
        Handler.advance(9999-SystemClock.now);check(r.downs()>1,"normal repeat before deadline");
        check(r.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==0,"no early forced release");
        Handler.advance(1);check(Handler.pending()==0,"all callbacks stop at exact deadline without MOVE");
        KeyEvent up=r.delivered.get(r.delivered.size()-1);
        check(up.action==KeyEvent.ACTION_UP&&up.eventTime==10000,"deadline independent of repeat cadence");
        check((up.flags&KeyEvent.FLAG_CANCELED)!=0&&up.downTime==0,"balanced canceled release retains downTime");
        int count=r.delivered.size();Handler.advance(60000);check(r.delivered.size()==count,"no delayed resurrection");
        balanced(r);scenarios.add("absolute-10s-without-further-MOVE");
    }
    static void testMoveReverseAndRecovery(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));Handler.advance(9000);
        Object deadline=r.guard().mSessions.get(0).deadline;
        r.process(move(7,-1,0,0,0));
        check(r.guard().mSessions.get(0).deadline==deadline,"direction reversal does not renew session");
        Handler.advance(900);r.process(move(7,-1,0,0,0));
        check(r.guard().mSessions.get(0).deadline==deadline,"duplicate nonzero MOVE does not renew session");
        Handler.advance(100);int count=r.downs();
        r.process(move(7,1,0,0,0));r.process(move(7,-1,0,0,0));
        check(r.downs()==count,"reversal cannot unlock a timed out channel");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));
        check(r.downs()==count+1,"observed channel neutral rearms next press");
        r.joystick().cancel();balanced(r);scenarios.add("MOVE-and-direction-change-never-renew;neutral-rearms");
    }
    static void testHatPriorityAndIndependentDimensions(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,1,-1,0));
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==0,"HAT owns opposed horizontal sample");
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT)==1,"only HAT horizontal DOWN");
        Handler.advance(600);int y=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_DOWN);
        r.process(move(7,1,1,0,0));check(r.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_LEFT)==1,"HAT balances own UP");
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==0,"deflected stick cannot take over on HAT release");
        Handler.advance(160);check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_DOWN)>y,"horizontal release retains vertical repeat token");
        r.process(move(7,-1,1,0,0));check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT)>0,"existing HAT history only");
        int left=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT);
        r.process(move(7,-1,1,0,0));check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT)==left,"stick reversal does not bypass neutral debt");
        r.process(move(7,0,1,0,0));r.process(move(7,1,1,0,0));
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"stick neutral restores independent horizontal press");
        r.process(move(7,0,0,0,0));check(Handler.pending()==0,"all-neutral clears deadline");
        balanced(r);scenarios.add("HAT-priority;blocked-stick-requires-neutral;X-Y-token-isolation");
    }
    static void testDevicesAndSources(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));r.process(move(8,-1,0,0,0));
        r.process(sourceMove(7,InputDevice.OTHER_SOURCE,0,1,0,0));
        check(r.downs()==3&&r.guard().mSessions.size()==3,"device and source keep separate state");
        r.process(new MotionEvent(MotionEvent.ACTION_CANCEL,7,InputDevice.JOYSTICK,0,0,0,0));
        check(r.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"one identity CANCEL releases only own key");
        int left=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT);
        int down=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_DOWN);Handler.advance(600);
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT)>left,"other device keeps repeat");
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_DOWN)>down,"other source keeps repeat");
        r.process(move(7,1,0,0,0));check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"CANCEL retains only matching neutral debt");
        r.joystick().cancel();balanced(r);scenarios.add("device-source-isolation-and-identity-CANCEL");
    }
    static void testFocusAndObservedNeutral(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));Handler.advance(100);r.focus(false);
        check(Handler.pending()==0,"actual SyntheticInputStage focus hook cancels");
        r.focus(true);int down=r.downs();r.process(move(7,1,0,0,0));check(r.downs()==down,"focus restore cannot rearm held channel");
        r.process(move(7,1,-1,0,0));check(r.downs()==down+1,"previously neutral Y accepts first real press without extra neutral");
        r.joystick().cancel();balanced(r);
        r=fresh();r.focus(false);r.process(move(7,1,0,0,0));check(r.downs()==0,"unfocused nonzero sample observed but not emitted");
        r.focus(true);r.process(move(7,1,0,0,0));check(r.downs()==0,"unfocused observed nonzero needs neutral");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));check(r.downs()==1,"neutral rearms blocked sample");
        r.joystick().cancel();balanced(r);scenarios.add("focus-loss;blocked-observation;neutral-and-unknown-channel-recovery");
    }
    static void testRealDisplayForwarding(){
        int[] states={Display.STATE_OFF,Display.STATE_DOZE,Display.STATE_DOZE_SUSPEND,Display.STATE_UNKNOWN,
                Display.STATE_VR,Display.STATE_ON_SUSPEND};
        for(int state:states){
            RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));r.screen(state);
            check(r.mAttachInfo.mHasWindowFocus,"screen fixture retains focus; screen is independent");
            check(Handler.pending()==0,"actual DisplayListener forwards state "+state);
            int down=r.downs();r.process(move(7,0,-1,0,0));check(r.downs()==down,"non-ON cannot accept new axis");
            r.screen(Display.STATE_ON);r.process(move(7,0,-1,0,0));check(r.downs()==down,"wake cannot rearm nonzero observed while off");
            r.process(move(7,0,0,0,0));r.process(move(7,0,-1,0,0));check(r.downs()==down+1,"wake neutral then press works");
            r.joystick().cancel();balanced(r);
        }
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));
        r.mDisplayListener.onDisplayChanged(99);check(Handler.pending()==2,"unrelated display change does not cancel");
        r.mDisplayListener.onDisplayRemoved(99);check(Handler.pending()==2,"unrelated display removal does not cancel");
        r.mDisplayListener.onDisplayRemoved(0);check(Handler.pending()==0,"matching actual removal callback cancels");balanced(r);
        r=fresh();r.process(move(7,1,0,0,0));r.mDisplay.valid=false;r.mDisplayListener.onDisplayRemoved(0);
        check(r.mAttachInfo.mDisplayState==Display.STATE_ON,"removed-display fixture retains stale cached ON state");
        int down=r.downs();r.process(move(7,0,-1,0,0));check(r.downs()==down,"invalid removed display blocks a previously neutral new channel");
        check(Handler.pending()==0,"invalid display cannot rearm deadline or repeat");balanced(r);
        r=fresh();r.process(move(7,1,0,0,0));r.onMovedToDisplay(1,new Configuration());
        check(r.mView.moves==1&&Handler.pending()==0,"actual moved-display method cancels prior display state");balanced(r);
        r=fresh();r.mSyntheticInputStage=null;r.screen(Display.STATE_OFF);r.mDisplayListener.onDisplayRemoved(0);
        r.onMovedToDisplay(1,new Configuration());check(true,"display callbacks safe before synthetic stage initialization");
        scenarios.add("actual-DisplayListener-OFF-DOZE-UNKNOWN-and-move-remove-null-safety");
    }
    static void testInvalidAndThresholds(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,0.49f,-0.49f,0,0));check(r.downs()==0,"legacy 0.5 threshold retained");
        r.process(move(7,0.5f,-0.5f,0,0));check(r.downs()==2,"inclusive positive and negative threshold retained");
        r.process(move(7,Float.NaN,-0.5f,0,0));check(r.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"NaN stops affected dimension");
        int right=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT);r.process(move(7,1,-0.5f,0,0));
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==right,"NaN is not neutral unlock");
        r.process(move(7,0,-0.5f,0,0));r.process(move(7,Float.POSITIVE_INFINITY,-0.5f,0,0));
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==right,"infinity cannot create direction");
        int up=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_UP);Handler.advance(600);
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_UP)>up,"malformed X does not cancel Y repeat");
        r.joystick().cancel();balanced(r);scenarios.add("thresholds-retained;nonfinite-not-neutral;dimension-isolation");
    }
    static void testOldTokensAndDisconnect(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));
        Message staleRepeat=null,staleDeadline=null;
        for(Message message:r.guard().messages){if(message.what==1)staleRepeat=message;else staleDeadline=message;}
        r.process(move(7,0,0,0,0));r.process(move(7,-1,0,0,0));int count=r.delivered.size();
        r.guard().handleMessage(staleRepeat);r.guard().handleMessage(staleDeadline);
        check(r.delivered.size()==count&&Handler.pending()==2,"old repeat/deadline token cannot revive or cancel new state");
        InputDevice.devices.remove(7);Handler.advance(500);
        check(Handler.pending()==0,"device disappearance stops pending repeat and deadline");
        InputDevice.devices.put(7,new InputDevice(InputDevice.OTHER_SOURCE));count=r.downs();
        r.process(move(7,-1,0,0,0));check(r.downs()==count,"reconnected nonzero must first be neutral");
        r.process(move(7,0,0,0,0));r.process(move(7,-1,0,0,0));check(r.downs()==count+1,"reconnected neutral permits next press");
        r.joystick().cancel();balanced(r);scenarios.add("stale-token-invalidation;disconnect-and-reconnect-neutral");
    }
    static void testHistoryAndStaleBoundary(){
        RocJoystickCandidateTest r=fresh();SystemClock.now=9000;
        r.process(move(7,-1,0,0,0).history(0,1,0,0,0));
        check(r.guard().mSessions.get(0).deadline.when==10000,"history first press owns absolute deadline");
        Handler.advance(1000);check(Handler.pending()==0,"newest reverse MOVE cannot extend historical session");balanced(r);
        r=fresh();r.process(move(7,1,0,0,0));Handler.advance(100);r.focus(false);r.focus(true);int count=r.downs();
        r.process(move(7,1,0,0,0).history(0,0,0,0,0));
        check(r.downs()==count,"pre-boundary historical neutral cannot unlock canceled channel");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));check(r.downs()==count+1,"post-boundary neutral works");
        r.joystick().cancel();balanced(r);scenarios.add("batched-history-cannot-renew-or-cross-lifecycle-neutral-boundary");
    }
    static void testScopeLegacyAndRightStick(){
        for(String name:new String[]{"com.overdevs.at4k","com.android.settings","com.android.documentsui","com.android.systemui"}){
            RocJoystickCandidateTest r=fresh(name);check(r.isRocNavigationGuardEnabled(),"exact scope "+name);
            r.process(move(7,1,0,0,0));Handler.advance(10000);check(Handler.pending()==0,"scope cap "+name);balanced(r);
        }
        for(String name:new String[]{"org.example.game","com.overdevs.at4k.debug","Com.Android.Settings","com.android.settings.extra"}){
            RocJoystickCandidateTest r=fresh(name);check(!r.isRocNavigationGuardEnabled(),"exact exclusion "+name);
            r.process(move(7,1,0,0,0));r.screen(Display.STATE_OFF);Handler.advance(11000);
            check(r.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==0&&Handler.pending()==1,"game/unlisted legacy long hold retained");
            r.joystick().cancel();balanced(r);
        }
        RocJoystickCandidateTest r=fresh();MotionEvent event=move(7,0,0,0,0);
        event.axes[MotionEvent.AXIS_Z]=1;event.axes[MotionEvent.AXIS_RZ]=-1;r.process(event);
        check(r.delivered.isEmpty()&&Handler.pending()==0,"right stick remains unsynthesized");
        scenarios.add("four-exact-packages-only;game-legacy-unchanged;right-stick-unchanged");
    }
    static void testActualConsumedAndDetachHooks(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));
        r.mSyntheticInputStage.onDeliverToNext(new QueuedInputEvent(move(7,1,0,0,0)));
        check(Handler.pending()==0,"actual prior-consumer hook cancels fallback");
        int count=r.downs();r.process(move(7,1,0,0,0));check(r.downs()==count,"prior-consumer cancel retains nonzero debt");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));r.mSyntheticInputStage.onDetachedFromWindow();
        check(Handler.pending()==0,"actual detach hook cancels");balanced(r);
        r=fresh();r.process(move(7,1,0,0,0));r.process(move(8,0,1,0,0));
        r.mSyntheticInputStage.onDeliverToNext(new QueuedInputEvent(move(7,1,0,0,0)));
        int other=r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_DOWN);Handler.advance(400);
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_DOWN)>other,"prior consumer does not cancel another device identity");
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"prior consumer stops only consumed identity");
        r.joystick().cancel();balanced(r);
        r=fresh();r.mSyntheticInputStage.onDeliverToNext(new QueuedInputEvent(move(7,1,0,0,0)));
        r.process(move(7,1,0,0,0));check(r.downs()==0,"prior-consumed nonzero continuation is not a fresh press");
        r.mSyntheticInputStage.onDeliverToNext(new QueuedInputEvent(move(7,0,0,0,0)));
        r.process(move(7,1,0,0,0));check(r.downs()==1,"valid consumed neutral can discharge its own channel debt");
        r.joystick().cancel();balanced(r);
        scenarios.add("actual-prior-consumer-and-detach-lifecycle-hooks");
    }
    static void testTimestampValidation(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));Handler.advance(100);
        MotionEvent future=move(7,0,0,0,0);future.time=101;r.process(future);
        check(Handler.pending()==0,"future sample stops current session");
        check(r.guard().mSessions.get(0).lastSampleTime==0,"future sample cannot advance accepted sample time");
        int down=r.downs();r.process(move(7,1,0,0,0));check(r.downs()==down,"future neutral cannot discharge held channel debt");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));check(r.downs()==down+1,"valid neutral rearms after rejected future");
        MotionEvent older=move(7,0,0,0,0);older.time=99;r.process(older);down=r.downs();
        check(r.guard().mSessions.get(0).lastSampleTime==100,"out-of-order sample cannot roll back accepted sample time");
        r.process(move(7,1,0,0,0));check(r.downs()==down,"out-of-order neutral cannot unlock channel");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));
        MotionEvent negative=move(7,0,0,0,0);negative.time=-1;r.process(negative);down=r.downs();
        r.process(move(7,1,0,0,0));check(r.downs()==down,"negative neutral timestamp cannot unlock channel");
        r.joystick().cancel();balanced(r);
        r=fresh();MotionEvent futureFirst=move(7,1,0,0,0);futureFirst.time=1;r.process(futureFirst);
        check(r.downs()==0&&Handler.pending()==0,"future first sample cannot emit or start timers");
        scenarios.add("future-negative-out-of-order-timestamps-never-discharge-neutral-debt");
    }
    static void testStoppedAndAttachedContext(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));Handler.advance(100);r.setWindowStopped(true);
        check(r.mStopped&&r.mAttachInfo.mHasWindowFocus&&Handler.pending()==0,"actual stopped hook cancels while focus remains true");
        int down=r.downs();r.process(move(7,1,0,0,0));check(r.downs()==down,"stopped view cannot emit navigation");
        r.setWindowStopped(false);r.process(move(7,1,0,0,0));check(r.downs()==down,"restart cannot rearm nonzero held through stop");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));check(r.downs()==down+1,"restart valid neutral then press works");
        r.joystick().cancel();balanced(r);
        r=fresh();r.mAdded=false;r.process(move(7,1,0,0,0));check(r.downs()==0,"unattached view cannot start fallback");
        r.mAdded=true;r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));r.mView=null;Handler.advance(400);
        check(Handler.pending()==0,"missing view is checked by callback even without a focus notification");
        check(r.downs()==1&&r.guard().mDeliveries.isEmpty(),"removed window drops terminal event and clears delivery metadata");
        r=fresh();r.process(move(7,1,0,0,0));r.mDisplay=null;Handler.advance(400);
        check(Handler.pending()==0,"missing display is checked by callback without notification");balanced(r);
        r=fresh();r.mSyntheticInputStage=null;r.setWindowStopped(true);check(r.mStopped,"stopped before input stage initialization is null-safe");
        scenarios.add("actual-setWindowStopped-hook;attached-view-liveness;early-stop-null-safety");
    }
    static void testPerSessionStopBoundary(){
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));Handler.advance(10000);
        MotionEvent staleNeutral=move(7,0,0,0,0);staleNeutral.time=5000;r.process(staleNeutral);
        int down=r.downs();r.process(move(7,1,0,0,0));check(r.downs()==down,"neutral predating deadline cannot discharge stop debt");
        check(r.guard().mSessions.get(0).boundary==10000,"deadline records session's stop boundary");
        r.process(move(7,0,0,0,0));r.process(move(7,1,0,0,0));check(r.downs()==down+1,"post-deadline neutral restores next press");
        Handler.advance(100);r.process(new MotionEvent(MotionEvent.ACTION_CANCEL,7,InputDevice.JOYSTICK,0,0,0,0));
        MotionEvent beforeCancel=move(7,0,0,0,0);beforeCancel.time=10050;r.process(beforeCancel);down=r.downs();
        r.process(move(7,1,0,0,0));check(r.downs()==down,"neutral predating identity CANCEL cannot discharge stop debt");
        r.joystick().cancel();balanced(r);scenarios.add("per-session-deadline-and-identity-CANCEL-boundary-reject-old-neutral");
    }
    static void testQueuedNaturalTapAndDeadline(){
        RocJoystickCandidateTest r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));
        Handler.advance(50);r.process(move(7,0,0,0,0));
        check(r.delivered.isEmpty()&&r.pendingKeys.size()==2,"short tap may wait in an earlier input stage");
        r.drain();check(r.downs()==1&&r.delivered.size()==2,"queued natural DOWN/UP tap survives release before delivery");
        check(r.guard().mDeliveries.isEmpty()&&r.recycled==2,"natural tap metadata removed before both queue records recycle");
        balanced(r);
        r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));Handler.advance(10000);
        check(r.pendingKeys.size()>2&&Handler.pending()==0,"initial DOWN, repeats and deadline UP can all be deferred");
        r.drain();check(r.delivered.isEmpty(),"expired queued DOWNs do not become a late press or orphan UP");
        check(r.guard().mDeliveries.isEmpty(),"all deferred deadline metadata cleaned");balanced(r);
        r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));SystemClock.now=10000;
        check(Handler.pending()==2,"fixture leaves repeat/deadline callbacks unserviced");r.drain();
        check(r.delivered.isEmpty()&&Handler.pending()==0,"post-IME delivery gate itself enforces immutable deadline");
        check(r.guard().mDeliveries.isEmpty(),"deadline gate cleans both rejected DOWN and generated UP");balanced(r);
        scenarios.add("actual-postIME-and-finish;queued-natural-tap;expired-DOWN-suppression-without-timer");
    }
    static void testQueuedLifecycleAndOldHeldIsolation(){
        for(boolean display:new boolean[]{false,true}){
            RocJoystickCandidateTest r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));Handler.advance(50);
            if(display){r.screen(Display.STATE_OFF);r.screen(Display.STATE_ON);}else{r.focus(false);r.focus(true);}
            r.drain();check(r.delivered.isEmpty(),"old deferred DOWN cannot revive after "+(display?"screen":"focus")+" restore");
            r.process(move(7,0,0,0,0));r.process(move(7,-1,0,0,0));r.drain();
            check(r.downs()==1,"new neutral and fresh press still work after rejected old queue");
            r.joystick().cancel();r.drain();check(r.guard().mDeliveries.isEmpty(),"lifecycle delayed metadata cleaned");balanced(r);
        }
        RocJoystickCandidateTest r=fresh();r.process(move(7,1,0,0,0));r.autoDispatch=false;Handler.advance(400);
        r.screen(Display.STATE_OFF);r.screen(Display.STATE_ON);r.process(move(7,0,0,0,0));r.process(move(7,-1,0,0,0));
        r.drain();check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"old IME-deferred repeat is blocked after wake");
        check(r.count(KeyEvent.ACTION_UP,KeyEvent.KEYCODE_DPAD_RIGHT)==1,"old actually delivered DOWN receives exactly one UP");
        check(r.count(KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT)==1&&Handler.pending()==2,
                "late old repeat and UP cannot cancel fresh opposite held key");
        r.joystick().cancel();r.drain();check(r.guard().mDeliveries.isEmpty(),"old and new held metadata both cleaned");balanced(r);
        scenarios.add("deferred-DOWN-does-not-survive-focus-or-screen-epoch;old-UP-balances-without-canceling-new-held");
    }
    static void testDeliveryProvenanceAndEarlyFinish(){
        RocJoystickCandidateTest r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));
        QueuedInputEvent consumed=r.pendingKeys.remove(0);r.finishInputEvent(consumed);
        check(consumed.mEvent==null&&consumed.mFlags==0&&r.guard().mDeliveries.isEmpty(),
                "actual finish cleans an initial DOWN consumed before post-IME and recycles queue fields");
        Handler.advance(400);r.drain();check(r.delivered.isEmpty(),"a repeat cannot substitute for the consumed initial DOWN");
        r.joystick().cancel();r.drain();check(r.delivered.isEmpty()&&r.guard().mDeliveries.isEmpty(),
                "no orphan UP after earlier stage consumed first DOWN");balanced(r);
        r=fresh();KeyEvent forged=new KeyEvent(0,0,KeyEvent.ACTION_DOWN,KeyEvent.KEYCODE_DPAD_LEFT,0,0,7,0,
                KeyEvent.FLAG_FALLBACK,InputDevice.JOYSTICK);
        QueuedInputEvent q=new QueuedInputEvent(forged);q.mFlags=QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED;r.dispatch(q);
        check(r.delivered.isEmpty()&&q.mEvent==null&&q.mFlags==0,"private provenance alone does not authorize an unregistered event");
        r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));q=r.pendingKeys.remove(0);
        q.mEvent.sequence++;r.dispatch(q);check(r.delivered.isEmpty()&&r.guard().mDeliveries.isEmpty(),
                "same object with changed sequence cannot reuse an older delivery token");
        r.joystick().cancel();r.drain();check(r.delivered.isEmpty(),"sequence-rejected initial DOWN has no delivered UP");balanced(r);
        r=fresh();r.autoDispatch=false;r.process(move(7,1,0,0,0));q=r.pendingKeys.remove(0);KeyEvent old=(KeyEvent)q.mEvent;
        r.dispatch(q);check(r.guard().mDeliveries.isEmpty(),"valid DOWN metadata already cleaned before object can be reused");
        old.sequence++;q.mEvent=old;q.mFlags=QueuedInputEvent.FLAG_ROC_JOYSTICK_GUARDED;r.dispatch(q);
        check(r.downs()==1,"reused queue record and event identity do not resurrect a finished token");
        r.joystick().cancel();r.drain();check(r.guard().mDeliveries.isEmpty(),"reuse control leaves no delivery metadata");balanced(r);
        scenarios.add("actual-finish-cleans-upstream-consume;private-provenance-and-object-sequence-token;queue-reuse");
    }
    public static void main(String[] args){
        testDeadlineWithoutMove();testMoveReverseAndRecovery();testHatPriorityAndIndependentDimensions();
        testDevicesAndSources();testFocusAndObservedNeutral();testRealDisplayForwarding();
        testInvalidAndThresholds();testOldTokensAndDisconnect();testHistoryAndStaleBoundary();
        testScopeLegacyAndRightStick();testActualConsumedAndDetachHooks();
        testTimestampValidation();testStoppedAndAttachedContext();
        testPerSessionStopBoundary();
        testQueuedNaturalTapAndDeadline();testQueuedLifecycleAndOldHeldIsolation();
        testDeliveryProvenanceAndEarlyFinish();
        for(String scenario:scenarios)System.out.println("SCENARIO "+scenario);
        System.out.println("PASS: "+checks+" exact candidate source checks");
    }
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--javac", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    generator = Path(__file__).parents[1] / "navigation_guard" / "apply_joystick_guard.py"
    spec = importlib.util.spec_from_file_location("roc_joystick_candidate_transform", generator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = {"passed": False, "hardware_reproduction": False, "installable": False,
              "scope": "exact candidate source fragments with virtual Android boundary",
              "script_sha256": sha(Path(__file__).read_bytes()),
              "transformer_sha256": sha(generator.read_bytes()), "source": str(args.source),
              "Android_framework_built": False, "production_source_modified": False}
    try:
        original = args.source.read_bytes()
        candidate, manifest = module.make_candidate(original)
        report["candidate_manifest"] = manifest
        # Negative source control: even one altered byte must fail before output.
        try:
            module.make_candidate(original + b"\n")
        except ValueError:
            report["negative_source_sha_rejected"] = True
        else:
            raise AssertionError("source SHA gate accepted mutation")
        if module.make_candidate(original)[0] != candidate:
            raise AssertionError("candidate generation not deterministic")
        (args.work / "ViewRootImpl.java").write_bytes(candidate)
        text = candidate.decode("utf-8")
        patterns = [(r"    private boolean isRocNavigationGuardEnabled\(\) \{", False),
                    (r"    private void onRocNavigationDisplayChanged\(\) \{", False),
                    (r"    private void enqueueRocJoystickEvent\(KeyEvent event\) \{", False),
                    (r"    private boolean rocShouldBlockJoystick\(QueuedInputEvent q\) \{", False),
                    (r"    private void rocFinishJoystickEvent\(QueuedInputEvent q\) \{", False),
                    (r"    private void finishInputEvent\(QueuedInputEvent q\) \{", False),
                    (r"    private final DisplayListener mDisplayListener = new DisplayListener\(\) \{", True),
                    (r"    public void onMovedToDisplay\(int displayId, Configuration config\) \{", False),
                    (r"    void setWindowStopped\(boolean stopped\) \{", False),
                    (r"    final class SyntheticInputStage extends InputStage \{", False),
                    (r"    final class RocJoystickGuard extends Handler \{", False),
                    (r"    final class SyntheticJoystickHandler extends Handler \{", False)]
        fragments = [extract(text, pattern, field=field) for pattern, field in patterns]
        post_stage = extract(text, r"    final class ViewPostImeInputStage extends InputStage \{")
        post_key = extract(post_stage, r"        private int processKeyEvent\(QueuedInputEvent q\) \{")
        # Retained legacy mechanics are byte-exact; only scoped routing is new.
        original_text = original.decode("utf-8")
        legacy_pattern = r"    final class SyntheticJoystickHandler extends Handler \{"
        legacy = extract(original_text, legacy_pattern)
        routed_legacy = fragments[-1]
        stripped = routed_legacy.replace("        private final RocJoystickGuard mRocGuard = new RocJoystickGuard();\n\n", "", 1)
        stripped = stripped.replace("            if (isRocNavigationGuardEnabled()) {\n                mRocGuard.process(event);\n                return;\n            }\n", "", 1)
        stripped = stripped.replace("            if (isRocNavigationGuardEnabled()) {\n                mRocGuard.cancel();\n                return;\n            }\n", "", 1)
        stripped = stripped.replace("        void onRocDisplayStateChanged() {\n            if (isRocNavigationGuardEnabled()) mRocGuard.cancel();\n        }\n\n", "", 1)
        stripped = stripped.replace("        private void cancel(MotionEvent event) {\n            if (isRocNavigationGuardEnabled()) {\n                mRocGuard.cancel(event);\n            } else {\n                cancel();\n            }\n        }\n\n", "", 1)
        if stripped != legacy:
            raise AssertionError("non-scoped legacy handler changed")
        report["legacy_core_byte_exact"] = True
        report["legacy_fragment_sha256"] = sha(legacy.encode())
        report["fragment_sha256"] = [sha(fragment.encode()) for fragment in fragments]
        report["post_ime_process_key_sha256"] = sha(post_key.encode())
        java_file = args.work / "RocJoystickCandidateTest.java"
        java_file.write_text(HARNESS.replace("/* EXACT_CANDIDATE_FRAGMENTS */", "\n\n".join(fragments))
                             .replace("/* EXACT_POST_IME_KEY_METHOD */", post_key),
                             encoding="utf-8", newline="\n")
        report["harness_sha256"] = sha(java_file.read_bytes())
        classes = args.work / "classes"
        classes.mkdir()
        commands = [[str(args.javac), "-encoding", "UTF-8", "-source", "8", "-target", "8", "-d", str(classes), str(java_file)],
                    [str(args.java), "-cp", str(classes), "RocJoystickCandidateTest"]]
        report["commands"] = []
        for index, command in enumerate(commands):
            run = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
            (args.work / ("compile.log" if index == 0 else "run.log")).write_text(run.stdout, encoding="utf-8", newline="\n")
            report["commands"].append({"argv": command, "returncode": run.returncode, "output": run.stdout})
            if run.returncode:
                raise RuntimeError("candidate host command failed: " + str(run.returncode))
        match = re.search(r"PASS: (\d+) exact candidate source checks", run.stdout)
        if not match:
            raise AssertionError("explicit candidate PASS missing")
        report["checks"] = int(match.group(1))
        report["scenarios"] = re.findall(r"^SCENARIO (.+)$", run.stdout, re.MULTILINE)
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        (args.work / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": True, "checks": report["checks"], "result": str(args.work / "result.json")}))


if __name__ == "__main__":
    main()
