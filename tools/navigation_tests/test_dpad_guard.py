"""Execute the exact scoped DPAD guard extracted from a new ViewRoot candidate.

Run through the project's capped wrapper. Android delivery/clock are virtual;
the full patched ViewRoot requires a separate real Android classpath compile.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess


HARNESS = r'''
import java.util.*;
public final class DpadGuardProbe {
    static int checks;
    static void check(boolean result, String reason) {
        checks++;
        if (!result) throw new AssertionError(reason);
    }
    boolean enabled=true, mAdded=true, mStopped=false;
    Object mView=new Object();
    final Attach mAttachInfo=new Attach();
    final Display mDisplay=new Display();
    final Handler mHandler=new Handler();
    final List<QueuedInputEvent> queued=new ArrayList<>();
    final List<QueuedInputEvent> queuePool=new ArrayList<>();
    final List<KeyEvent> passed=new ArrayList<>();
    boolean isRocNavigationGuardEnabled() {return enabled;}
    static final class Attach {boolean mHasWindowFocus=true;}
    static final class Display {
        static final int STATE_ON=2, STATE_OFF=1;
        int state=STATE_ON;
        int getState(){return state;}
        boolean valid=true;
        boolean isValid(){return valid;}
    }
    static final class SystemClock {
        static long now;
        static long uptimeMillis(){return now;}
    }
    static final class KeyEvent {
        static final int ACTION_DOWN=0,ACTION_UP=1;
        static final int KEYCODE_DPAD_UP=19,KEYCODE_DPAD_DOWN=20,
            KEYCODE_DPAD_LEFT=21,KEYCODE_DPAD_RIGHT=22;
        static final int FLAG_CANCELED=32,FLAG_LONG_PRESS=128,FLAG_FALLBACK=1024;
        final long down,time;
        final int action,key,repeat,meta,device,scan,flags,source;
        KeyEvent(long d,long t,int a,int k,int r,int m,int dev,int sc,int f,int so) {
            down=d;time=t;action=a;key=k;repeat=r;meta=m;device=dev;scan=sc;flags=f;source=so;
        }
        KeyEvent(KeyEvent e){this(e.down,e.time,e.action,e.key,e.repeat,e.meta,e.device,e.scan,e.flags,e.source);}
        int getAction(){return action;} int getKeyCode(){return key;}
        int getRepeatCount(){return repeat;} int getMetaState(){return meta;}
        int getDeviceId(){return device;} int getScanCode(){return scan;}
        int getFlags(){return flags;} int getSource(){return source;}
        long getDownTime(){return down;} long getEventTime(){return time;}
        boolean isCanceled(){return (flags&FLAG_CANCELED)!=0;}
        void recycle(){}
        // Actual Android10 KeyEvent dispatch recycling is deliberately a no-op.
        void recycleIfNeededAfterDispatch(){}
    }
    static final class QueuedInputEvent {
        static final int FLAG_ROC_DPAD_RELEASE=1<<7;
        static final int FLAG_ROC_DPAD_REPEAT=1<<8;
        static final int FLAG_ROC_JOYSTICK_GUARDED=1<<9;
        KeyEvent mEvent; int mFlags;
        QueuedInputEvent(KeyEvent e,int f){mEvent=e;mFlags=f;}
    }
    final class Handler {
        final Map<Runnable,Long> pending=new IdentityHashMap<>();
        void removeCallbacks(Runnable r){pending.remove(r);}
        void postDelayed(Runnable r,long delay){pending.put(r,SystemClock.now+delay);}
        void advance(long time){
            while(true){
                Runnable selected=null;long when=Long.MAX_VALUE;
                for(Map.Entry<Runnable,Long> e:pending.entrySet())
                    if(e.getValue()<=time && e.getValue()<when){selected=e.getKey();when=e.getValue();}
                if(selected==null)break;
                pending.remove(selected);SystemClock.now=when;selected.run();drain();
            }
            SystemClock.now=time;
        }
    }
    QueuedInputEvent obtainQueuedInputEvent(KeyEvent e,int flags){
        QueuedInputEvent q=queuePool.isEmpty()?new QueuedInputEvent(null,0):queuePool.remove(queuePool.size()-1);
        q.mEvent=e;q.mFlags=flags;return q;
    }
    void recycleQueuedInputEvent(QueuedInputEvent q){
        q.mEvent=null;
        if(queuePool.size()<10)queuePool.add(q);
    }
    void finishInputEvent(QueuedInputEvent q){
/* ACTUAL_FINISH_HOOK */
        q.mEvent.recycleIfNeededAfterDispatch();
        recycleQueuedInputEvent(q);
    }
    void enqueueInputEvent(KeyEvent e,Object receiver,int flags,boolean immediate){
        queued.add(obtainQueuedInputEvent(e,flags));
    }
    boolean key(KeyEvent e){
        QueuedInputEvent q=obtainQueuedInputEvent(e,0);
        boolean blocked=rocShouldBlockDpad(q);
        if(!blocked)passed.add(new KeyEvent(e));
        finishInputEvent(q);
        return blocked;
    }
    void drain(){
        while(!queued.isEmpty()){
            QueuedInputEvent q=queued.remove(0);
            if(!rocShouldBlockDpad(q))passed.add(new KeyEvent(q.mEvent));
            finishInputEvent(q);
        }
    }
    static DpadGuardProbe fresh(){SystemClock.now=100;return new DpadGuardProbe();}
    static KeyEvent event(long down,long time,int action,int key,int repeat,int device,int source,int scan,int flags){
        return new KeyEvent(down,time,action,key,repeat,0,device,scan,flags,source);
    }
    static KeyEvent down(long d,long t,int key,int repeat){return event(d,t,0,key,repeat,7,0x501,key,0);}
    static KeyEvent up(long d,long t,int key){return event(d,t,1,key,0,7,0x501,key,0);}
/* GUARD */
    static void normalAndHardwareDownTime(){
        DpadGuardProbe p=fresh();
        check(!p.key(down(100,100,22,0)),"fresh direction passes");
        SystemClock.now=200;
        check(p.key(down(200,200,22,0)),"hardware repeat before long-press threshold suppressed");
        SystemClock.now=499;
        check(p.key(down(499,499,22,1)),"still no repeat at 399ms");
        p.mHandler.advance(500);
        check(p.passed.size()==2,"own first repeat after precisely 400ms");
        check(p.key(down(500,500,22,1)),"native duplicate at first repeat time consumed");
        SystemClock.now=600;
        check(p.key(down(600,600,22,0)),"hardware repeat with refreshed downtime is rate limited");
        p.mHandler.advance(660);
        check(p.passed.size()==3,"next own repeat after precisely 160ms");
        check(p.key(down(660,660,22,0)),"native repeat not delivered a second time");
        check(p.mHandler.pending.size()==2,"native repeat does not add a timer");
        p.mHandler.advance(10100);p.drain();
        check(p.passed.size()==62,"initial DOWN plus sixty bounded repeats and one balancing UP");
        check(p.passed.get(61).action==1 && p.passed.get(61).isCanceled(),"release canceled");
        SystemClock.now=10101;
        check(p.key(down(10101,10101,22,0)),"fresh-looking hardware repeat cannot restart timeout");
        check(p.mHandler.pending.isEmpty(),"expired session remains without a timer");
        check(p.key(up(10101,10102,22)),"future release refused");
        SystemClock.now=10102;
        check(p.key(up(10101,10102,22)),"physical UP clears debt without duplicate forwarded UP");
        SystemClock.now=10103;
        check(!p.key(down(10103,10103,22,0)),"new press after physical release accepted");
    }
    static void sharedInputReaderDownTime(){
        DpadGuardProbe p=fresh();
        check(!p.key(down(100,100,22,0)),"right initial");
        SystemClock.now=200;check(!p.key(down(200,200,20,0)),"second key initial");
        SystemClock.now=300;
        check(!p.key(up(200,300,22)),"first key UP with another key downtime accepted");
        check(p.mHandler.pending.size()==2,"second held key keeps original deadline");
        SystemClock.now=400;check(!p.key(up(200,400,20)),"second UP accepted");
        check(p.mHandler.pending.isEmpty(),"all neutral removes deadline");
    }
    static void devicesSourcesAndScans(){
        DpadGuardProbe p=fresh();
        check(!p.key(down(100,100,22,0)),"first device");
        SystemClock.now=110;
        check(!p.key(event(110,110,0,22,1,8,0x501,22,0)),"second device fresh edge despite native repeat-count interference");
        check(!p.key(event(110,110,0,22,0,7,0x101,22,0)),"source independent");
        check(!p.key(event(110,110,0,22,0,7,0x501,88,0)),"scan independent");
        check(p.mHandler.pending.size()==7,"three deadlines plus four channel repeats");
        SystemClock.now=150;
        check(!p.key(up(100,150,22)),"one channel UP");
        check(p.mHandler.pending.size()==6,"other scan retains that stream");
    }
    static void noWindowAdoptionAndScreen(){
        DpadGuardProbe p=fresh();SystemClock.now=600;
        check(p.key(down(100,600,22,3)),"orphan native repeat not adopted");
        check(!p.key(down(600,600,22,0)),"fresh first DOWN retained");
        SystemClock.now=700;p.mDisplay.state=Display.STATE_OFF;p.rocCancelDpadForContext();p.drain();
        check(p.passed.size()==2,"screen loss balances one admitted key");
        p.mDisplay.state=Display.STATE_ON;SystemClock.now=800;
        check(p.key(down(100,800,22,3)),"old native repeat cannot be adopted after wake");
        check(!p.key(down(800,800,22,0)),"new physical first press after context loss retained");
        check(!p.key(event(800,800,0,21,0,9,0x501,21,0)),"unknown neutral device first press retained");
        SystemClock.now=900;check(!p.key(up(800,900,22)),"observed physical release ends new press");
        SystemClock.now=1000;check(!p.key(down(1000,1000,22,0)),"release then new DOWN works");
    }
    static void blockedSamplesAndNonDirection(){
        DpadGuardProbe p=fresh();p.mDisplay.state=1;
        check(p.key(down(100,100,22,0)),"offscreen DOWN observed but not delivered");
        SystemClock.now=200;p.mDisplay.state=2;
        check(p.key(down(200,200,22,0)),"offscreen-held state cannot restart on ON");
        check(!p.key(event(200,200,0,96,0,7,0x501,304,0)),"A remains unchanged");
        check(!p.key(event(200,200,0,24,0,7,0x101,115,0)),"volume remains unchanged");
        check(!p.rocShouldBlockDpad(new QueuedInputEvent(event(200,200,0,22,0,7,0x1000010,0,1024),1<<9)),"only guarded joystick producer bypasses key guard");
        check(!p.key(event(200,200,0,21,0,9,0x101,0,1024)),"other fallback first DOWN accepted");
        SystemClock.now=210;
        check(p.key(event(200,210,0,21,1,9,0x101,0,1024)),"other fallback duplicate suppressed");
        p.enabled=false;check(!p.key(down(100,200,22,5)),"unscoped game entirely bypasses guard");
    }
    static void queuedReleaseAndStaleGeneration(){
        DpadGuardProbe p=fresh();p.key(down(100,100,22,0));
        SystemClock.now=200;p.rocCancelDpadForContext();
        check(p.queued.size()==1,"one local release queued");
        SystemClock.now=210;check(p.key(up(100,210,22)),"real release after cancellation consumed once");
        SystemClock.now=220;check(!p.key(down(220,220,22,0)),"new valid key begins before old cancellation drains");
        p.drain();
        check(p.passed.size()==2,"old queued UP cannot release newer DOWN");
        check(p.mHandler.pending.size()==2,"new key timer survives old queue");
    }
    static void staleUpCanceledAndContextChecks(){
        DpadGuardProbe p=fresh();p.key(down(100,100,22,0));
        SystemClock.now=200;
        check(p.key(up(90,99,22)),"old UP cannot release current press");
        check(p.mHandler.pending.size()==2,"stale UP retains timer");
        check(!p.key(event(100,200,1,22,0,7,0x501,22,32)),"external canceled UP balances current press");
        SystemClock.now=210;check(!p.key(down(210,210,22,0)),"native canceled UP cannot create new physical debt");
        SystemClock.now=220;p.key(up(210,220,22));
        SystemClock.now=230;check(!p.key(down(230,230,22,0)),"physical release rearms cancellation debt");
        p.mStopped=true;SystemClock.now=240;
        check(p.key(down(230,240,22,1)),"stopped window stops repeats even with focus");p.drain();
        check(p.mHandler.pending.isEmpty(),"stopped path cancels timer");
    }
    static void exactDeadlineAndNoDirectionRenewal(){
        DpadGuardProbe p=fresh();p.key(down(100,100,22,0));
        SystemClock.now=9000;check(!p.key(down(9000,9000,21,0)),"opposite DOWN allowed before deadline");
        p.mHandler.advance(10100);p.drain();
        int count=0;for(KeyEvent e:p.passed)if(e.action==1)count++;
        check(count==2,"deadline balances every admitted direction");
        check(p.mHandler.pending.isEmpty(),"direction change did not extend deadline");
        SystemClock.now=10101;check(p.key(down(10101,10101,19,0)),"new direction cannot bypass expired stream");
        SystemClock.now=10102;p.key(up(100,10102,22));
        SystemClock.now=10103;check(p.key(down(10103,10103,19,0)),"one remaining physical debt still blocks stream");
        SystemClock.now=10104;p.key(up(9000,10104,21));
        SystemClock.now=10105;check(p.key(down(10105,10105,19,0)),"blocked new direction also owes a physical UP");
        SystemClock.now=10106;p.key(up(10101,10106,19));
        SystemClock.now=10107;check(!p.key(down(10107,10107,19,0)),"all observed held keys released; new session accepted");
    }
    static void deadlineBeforeTimeoutCallback(){
        DpadGuardProbe p=fresh();p.key(down(100,100,22,0));
        // Move the clock without dispatching the queued timeout Runnable.
        SystemClock.now=10100;
        check(p.key(down(10100,10100,21,0)),"new direction at deadline is blocked before timeout callback");
        p.drain();
        SystemClock.now=10101;p.key(up(100,10101,22));
        SystemClock.now=10102;
        check(p.key(down(10102,10102,21,0)),"new direction seen at expiry retains its own release debt");
        SystemClock.now=10103;p.key(up(10100,10103,21));
        SystemClock.now=10104;
        check(!p.key(down(10104,10104,21,0)),"both real releases rearm after deadline race");
    }
    static void repeatDeliveryAfterDeadline(){
        DpadGuardProbe p=fresh();p.key(down(100,100,22,0));
        SystemClock.now=500;
        p.mRocDpadKeyGuard.streams.get(0).presses.get(0).repeatTask.run();
        check(p.queued.size()==1,"repeat queued without immediate delivery");
        SystemClock.now=10100;p.drain();
        check(p.passed.size()==2 && p.passed.get(1).action==1,
            "queued repeat delayed beyond deadline is suppressed and balanced");
        check(p.mHandler.pending.isEmpty(),"delayed repeat ends the session before timeout callback");
    }
    static void upstreamFinishAndQueueReuse(){
        DpadGuardProbe p=fresh();p.key(down(100,100,22,0));
        QueuedInputEvent last=null;
        KeyEvent lastRepeat=null;
        for(int i=0;i<32;i++){
            SystemClock.now=500+i*160;
            p.mRocDpadKeyGuard.streams.get(0).presses.get(0).repeatTask.run();
            check(p.mRocDpadKeyGuard.repeats.size()==1,"only one pending repeat token");
            last=p.queued.remove(0);lastRepeat=last.mEvent;
            // Model IME/pre-IME/drop consuming the event before ViewPostIme.
            p.finishInputEvent(last);
            check(p.mRocDpadKeyGuard.repeats.isEmpty(),"upstream-consumed repeat token released at finish");
        }
        check(last.mEvent==null,"finished queue item clears its event before reuse");
        QueuedInputEvent reused=p.obtainQueuedInputEvent(event(6000,6000,0,96,0,7,0x501,304,0),0);
        check(reused==last && reused.mFlags==0,"actual queue identity reused with fresh flags");
        check(!p.rocShouldBlockDpad(reused),"recycled queue item delivers ordinary A unchanged");
        p.finishInputEvent(reused);
        check(p.rocShouldBlockDpad(new QueuedInputEvent(lastRepeat,1<<8)),
            "finished repeat identity no longer authorizes delivery");
        SystemClock.now=10100;
        p.mRocDpadKeyGuard.streams.get(0).timeout.run();
        check(p.mRocDpadKeyGuard.releases.size()==1,"timeout queued one release token");
        QueuedInputEvent release=p.queued.remove(0);KeyEvent oldRelease=release.mEvent;
        p.finishInputEvent(release);
        check(p.mRocDpadKeyGuard.releases.isEmpty(),"upstream-consumed release token released at finish");
        check(p.rocShouldBlockDpad(new QueuedInputEvent(oldRelease,1<<7)),
            "finished cancellation identity cannot be delivered again");
        check(p.mRocDpadKeyGuard.streams.get(0).presses.get(0).needsUp,
            "finish cleanup does not pay timeout physical-release debt");
        SystemClock.now=10101;check(p.key(down(10101,10101,22,0)),"queue reuse cannot restart timed-out press");
        SystemClock.now=10102;p.key(up(100,10102,22));
        SystemClock.now=10103;check(!p.key(down(10103,10103,22,0)),"real release rearms after upstream consumption");
    }
    public static void main(String[] args){
        normalAndHardwareDownTime();sharedInputReaderDownTime();devicesSourcesAndScans();
        noWindowAdoptionAndScreen();blockedSamplesAndNonDirection();
        queuedReleaseAndStaleGeneration();staleUpCanceledAndContextChecks();exactDeadlineAndNoDirectionRenewal();
        deadlineBeforeTimeoutCallback();repeatDeliveryAfterDeadline();
        upstreamFinishAndQueueReuse();
        System.out.println("PASS: "+checks+" actual DPAD guard checks; 11 scenarios");
    }
}
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--javac', type=Path, required=True)
    ap.add_argument('--java', type=Path, required=True)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'hardware_reproduction': False,
              'scope': 'exact extracted guard; virtual Android boundary', 'commands': []}
    try:
        raw = args.source.read_bytes()
        source = raw.decode('utf-8')
        start = source.index('    private RocDpadKeyGuard mRocDpadKeyGuard;')
        end = source.index('    private boolean isRocNavigationGuardEnabled()', start)
        fragment = source[start:end]
        report.update({'source_sha256': sha(raw), 'fragment_sha256': sha(fragment.encode()),
                       'script_sha256': sha(Path(__file__).read_bytes())})
        # Check real integration anchors rather than testing an unattached class.
        assert source.count('if (rocShouldBlockDpad(q)) return FINISH_HANDLED;') == 1
        assert source.count('rocCancelDpadForContext();') >= 3
        assert 'public static final int FLAG_ROC_DPAD_RELEASE = 1 << 7;' in source
        finish_start = source.index('    private void finishInputEvent(QueuedInputEvent q) {')
        finish_end = source.index('    static boolean isTerminalInputEvent(', finish_start)
        finish = source[finish_start:finish_end]
        finish_hook = '        rocFinishDpadInputEvent(q);'
        assert source.count(finish_hook) == 1
        assert finish.index(finish_hook) < finish.index('q.mReceiver.finishInputEvent(')
        assert finish.index(finish_hook) < finish.index('q.mEvent.recycleIfNeededAfterDispatch();')
        assert finish.index(finish_hook) < finish.index('recycleQueuedInputEvent(q);')
        queue_start = source.index('    private static final class QueuedInputEvent {')
        queue_end = source.index('    private QueuedInputEvent obtainQueuedInputEvent(', queue_start)
        flags = re.findall(r'\b(FLAG_[A-Z_]+) = 1 << (\d+);', source[queue_start:queue_end])
        assert len(flags) == 10 and len({int(bit) for _, bit in flags}) == 10
        assert dict(flags)['FLAG_ROC_DPAD_RELEASE'] == '7'
        assert dict(flags)['FLAG_ROC_DPAD_REPEAT'] == '8'
        assert dict(flags)['FLAG_ROC_JOYSTICK_GUARDED'] == '9'
        java_file = args.work / 'DpadGuardProbe.java'
        java_file.write_text(HARNESS.replace('/* GUARD */', fragment)
                             .replace('/* ACTUAL_FINISH_HOOK */', finish_hook), encoding='utf-8')
        for name, argv in (
            ('compile', [str(args.javac), '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-d', str(args.work), str(java_file)]),
            ('run', [str(args.java), '-cp', str(args.work), 'DpadGuardProbe']),
        ):
            result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            (args.work / (name+'.log')).write_text(result.stdout, encoding='utf-8')
            report['commands'].append({'argv': argv, 'returncode': result.returncode, 'output': result.stdout})
            if result.returncode: raise RuntimeError(name+' failed')
        match = re.search(r'PASS: (\d+) actual DPAD guard checks; (\d+) scenarios', result.stdout)
        assert match
        report.update({'passed': True, 'checks': int(match.group(1)), 'scenarios': int(match.group(2)),
                       'finish_hook_before_recycle': True, 'private_queue_flags_unique': True,
                       'upstream_consumption_and_queue_reuse': True})
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (args.work/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'checks': report['checks'], 'result': str(args.work/'result.json')}))


if __name__ == '__main__':
    main()
