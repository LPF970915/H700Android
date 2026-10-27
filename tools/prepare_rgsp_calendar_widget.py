"""Avoid Calendar widget callbacks dereferencing an unavailable AppWidget service."""
import argparse,hashlib,json
from pathlib import Path
EDITS=[('packages/apps/Calendar/src/com/android/calendar/widget/CalendarAppWidgetProvider.java', '8af7a42d6d754f229cc0aad1936f15eb70c18487203cce56d5ce370c9b1634f5', '    public void onReceive(Context context, Intent intent) {\n        // Handle calendar-specific updates', '    public void onReceive(Context context, Intent intent) {\n        // Widget hosting is optional on controller/TV products. The calendar\n        // itself remains available when the framework has no widget service.\n        if (AppWidgetManager.getInstance(context) == null) return;\n        // Handle calendar-specific updates'), ('packages/apps/Calendar/src/com/android/calendar/widget/CalendarAppWidgetService.java', 'bf5aea744cd939e2aabc1105737f1da871887b309845310f40d5995db028e7c7', '                AppWidgetManager widgetManager = AppWidgetManager.getInstance(mContext);\n                if (mAppWidgetId == -1) {', '                AppWidgetManager widgetManager = AppWidgetManager.getInstance(mContext);\n                if (widgetManager == null) return;\n                if (mAppWidgetId == -1) {')]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();updates=[]
    for rel,before,old,new in EDITS:
        target=a.source/rel;text=target.read_text();base=text.replace(new,old,1)
        if hashlib.sha256(base.encode()).hexdigest()!=before:raise SystemExit('Unrecognized widget edits; no files changed: '+rel)
        if base.count(old)!=1:raise SystemExit('Ambiguous widget guard anchor')
        updates.append((target,base.replace(old,new,1),before))
    proof={}
    for target,text,before in updates:
        target.write_text(text);proof[target.relative_to(a.source).as_posix()]={'before':before,'after':hashlib.sha256(text.encode()).hexdigest()}
    (a.source/'out/rgsp-calendar-widget-inputs.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('CALENDAR_OPTIONAL_WIDGET_GUARDS_PREPARED')
if __name__=='__main__':main()
