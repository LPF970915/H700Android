"""Renew the two-hour passive hierarchy daemon without injecting any buttons."""
import datetime,json,time
from audit import Audit,OUT,adb
from probe_config import PROBE_JAR,PROBE_SHA

def main():
    a=Audit();r={'keys_injected':False};stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    try:
        digest=adb('sha256sum '+PROBE_JAR).split()[0]
        if digest!=PROBE_SHA:raise RuntimeError('Unexpected passive probe jar')
        d='/data/local/tmp/nav-passive-audit'
        a.command('touch '+d+'/stop')
        absent=0
        for _ in range(30):
            status=adb('ps -A -o ARGS | grep "^app_process /system/bin Dump --daemon" || true')
            absent=absent+1 if not status.strip() else 0
            # A reboot can leave a stale ready file after killing the daemon.
            if absent>=2:break
            time.sleep(.2)
        else:raise RuntimeError('Previous passive probe did not stop')
        a.command('rm -f '+d+'/request '+d+'/response '+d+'/stop '+d+'/ready')
        r['start']=a.command('nohup sh -c "CLASSPATH='+PROBE_JAR+' app_process /system/bin Dump --daemon '+d+'" > '+d+'/log 2>&1 < /dev/null & true')
        for _ in range(40):
            if adb('if [ -e '+d+'/ready ]; then echo READY; fi').strip()=='READY':break
            time.sleep(.2)
        else:raise RuntimeError('Passive probe not ready')
        r['state']=a.snap('probe-renewed-'+stamp)[3];r['status']='PASS_PASSIVE_DAEMON_RENEWED';print(r['status'],flush=True)
    except Exception as e:r.update(status='ERROR',error=repr(e));raise
    finally:a.close();(OUT/('probe-renewed-'+stamp+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
