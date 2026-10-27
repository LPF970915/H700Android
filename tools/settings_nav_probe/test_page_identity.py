"""Keep scroll-dependent headers out of live page identity without ignoring windows."""
from pathlib import Path
import unittest
from unittest.mock import patch

with patch.object(Path,'read_text',return_value='{}'):
    from explore import page_key, fingerprint, same_window_parent_return, new_ui_crash, new_ui_service_fault
from audit import label


class PageIdentityTest(unittest.TestCase):
    def state(self,window_id=8):
        return dict(package='com.android.settings',window='关于手机',window_id=window_id)

    def header(self,visible=True,text='RGSP H700',kind='entity_header_title'):
        return dict(id='com.android.settings:id/'+kind,text=text,visible=visible,children=[])

    def test_scrolling_entity_header_is_same_page(self):
        self.assertEqual(page_key(self.header(True),self.state()),page_key(self.header(False),self.state()))

    def test_distinct_window_is_not_same_page(self):
        self.assertNotEqual(page_key({},self.state(8)),page_key({},self.state(9)))

    def test_dialog_title_remains_a_guard(self):
        self.assertNotEqual(page_key(self.header(text='A',kind='alertTitle'),self.state()),
                            page_key(self.header(text='B',kind='alertTitle'),self.state()))

    def test_template_dedup_does_not_use_transient_window_id(self):
        self.assertEqual(fingerprint(self.header(),self.state(8)),fingerprint(self.header(),self.state(9)))

    def test_nonfocusable_clickable_rows_distinguish_same_window_fragments(self):
        def row(text):
            return dict(text=text,visible=True,clickable=True,focusable=False,children=[])
        self.assertNotEqual(fingerprint(row('偏好设置'),self.state()),
                            fingerprint(row('自动大写'),self.state()))

    def test_scrolled_legacy_parent_requires_parent_specific_rows(self):
        before=('latin','settings',(),(),('向上导航','外观和布局','滑行输入','文字更正','高级'))
        current=('latin','settings',(),(),('向上导航','语言','偏好设置','外观和布局','滑行输入'))
        parent={'语言','偏好设置','外观和布局','滑行输入','文字更正','高级','向上导航'}
        self.assertTrue(same_window_parent_return(before,current,parent,{'向上导航','按键音量','按键长按延迟'}))
        child=('latin','settings',(),(),('向上导航','按键音量','按键长按延迟'))
        self.assertFalse(same_window_parent_return(before,child,parent,{'向上导航','按键音量','按键长按延迟'}))

    def test_shared_toolbar_alone_does_not_prove_parent_return(self):
        before=('latin','settings',(),(),('向上导航','偏好设置'))
        current=('latin','settings',(),(),('向上导航',))
        self.assertFalse(same_window_parent_return(before,current,{'向上导航','偏好设置'},{'向上导航','自动大写'}))

    def test_recent_app_card_summary_does_not_change_identity(self):
        def card(summary):
            return dict(id='com.android.settings:id/app1_view',children=[
                dict(id='com.android.settings:id/app_title',text='AT4K Launcher',children=[]),
                dict(id='com.android.settings:id/app_summary',text=summary,children=[])])
        self.assertEqual(label(card('1分钟前')),'AT4K Launcher')
        self.assertEqual(label(card('1分钟前')),label(card('6分钟前')))

    def test_new_native_role_crash_is_not_a_successful_transition(self):
        old='old crash\n'
        current=old+'FATAL EXCEPTION: main\nProcess: com.android.permissioncontroller, PID: 42\n'
        self.assertTrue(new_ui_crash(old,current))
        self.assertFalse(new_ui_crash(current,current))
        self.assertFalse(new_ui_crash(old,old+'Process: com.example.background, PID: 1\n'))

    def test_missing_optional_service_wtf_is_not_a_normal_return(self):
        old='--------- beginning of events\n'
        current=old+'I am_wtf : [0,16756,com.android.settings,684310213,SystemServiceRegistry,No service published for: appwidget]\n'
        self.assertTrue(new_ui_service_fault(old,current))
        self.assertFalse(new_ui_service_fault(current,current))
        self.assertFalse(new_ui_service_fault(old,old+'I am_wtf : [0,9,com.example.other,1,tag,message]\n'))

    def test_log_ring_eviction_does_not_make_old_ui_fault_new(self):
        old_ui='10-26 23:50:10 I am_wtf : [0,16756,com.android.settings,1,tag,old]\n'
        before='evicted earlier line\n'+old_ui
        after=old_ui+'10-27 00:10:00 I am_wtf : [0,1912,system_server,1,tag,unrelated]\n'
        self.assertFalse(new_ui_service_fault(before,after))
        old_crash='10-26 23:00:00 E AndroidRuntime: Process: com.android.permissioncontroller, PID: 42\n'
        self.assertFalse(new_ui_crash('evicted\n'+old_crash,old_crash+'new unrelated line\n'))


if __name__=='__main__':unittest.main()
