"""Prevent menu metadata from turning execution/confirmation buttons into test entries."""
from pathlib import Path
import unittest
from unittest.mock import patch

# Classification tests must not depend on a private device's generated catalog.
with patch.object(Path,'read_text',return_value='{}'):
    from explore import classify, CATALOG


class ClassifierTest(unittest.TestCase):
    def node(self,title,kind='android.widget.Button',**extra):
        return dict(text=title,id='',**{'class':kind},enabled=True,clickable=True,children=[],**extra)

    def result(self,node,in_dialog=False):
        return classify(node,{},dict(window='测试',package='com.android.settings'),in_dialog)

    def test_final_buttons_never_follow_same_title_menu_metadata(self):
        for title in ('加密手机','清除所有数据（恢复出厂设置）','重置设置','保存','确定','启用','删除'):
            CATALOG[title]=[dict(type='PreferenceScreen',fragment='ExampleFragment',intent=None)]
            for kind in ('android.widget.Button','android.widget.ImageButton'):
                with self.subTest(title=title,kind=kind):
                    self.assertNotIn(self.result(self.node(title,kind)),('menu','dialog','expand'))

    def test_unknown_intents_are_not_navigation_metadata(self):
        CATALOG['未识别动作']=[dict(type='Preference',fragment='',intent={'action':'wipe'})]
        self.assertEqual('unclassified',self.result(self.node('未识别动作','android.widget.LinearLayout')))

    def test_recent_app_cards_require_a_real_app_title(self):
        node=self.node('AT4K / 0分钟前','android.widget.LinearLayout')
        node['id']='com.android.settings:id/app1_view'
        self.assertEqual('unclassified',self.result(node))
        node['children']=[dict(id='com.android.settings:id/app_title',text='AT4K')]
        self.assertEqual('menu',self.result(node))

    def test_nested_preference_screen_is_a_menu(self):
        CATALOG['嵌套设置']=[dict(type='PreferenceScreen',fragment='',intent=None)]
        self.assertEqual('menu',self.result(self.node('嵌套设置','android.widget.LinearLayout')))

    def test_dialog_choices_and_disabled_entries_are_focus_only(self):
        self.assertEqual('focus-only',self.result(self.node('WLAN'),True))
        node=self.node('嵌套设置','android.widget.LinearLayout');node['enabled']=False
        self.assertEqual('focus-only',self.result(node))

    def test_encryption_parent_is_read_only_navigation_but_execution_row_is_blocked(self):
        self.assertEqual('menu',self.result(self.node('加密与凭据','android.widget.LinearLayout')))
        self.assertEqual('focus-only-action',self.result(self.node('加密手机','android.widget.LinearLayout')))

    def test_keyboard_advanced_is_a_fragment_not_settings_inline_expansion(self):
        CATALOG['高级']=[dict(type='PreferenceScreen',fragment='AdvancedSettingsFragment',intent=None)]
        self.assertEqual('menu',classify(self.node('高级','android.widget.LinearLayout'),{},
            dict(window='键盘设置',package='com.android.inputmethod.latin'),False))

    def test_storage_usage_progress_does_not_hide_its_navigation_row(self):
        node=self.node('内部共享存储空间','android.widget.LinearLayout')
        node['children']=[dict(id='',**{'class':'android.widget.ProgressBar'},range={'min':0,'max':100,'current':15})]
        self.assertEqual('menu',self.result(node))
        node['children'][0]['class']='android.widget.SeekBar'
        self.assertEqual('focus-only-range-container',self.result(node))

    def test_channel_body_opens_menu_but_secondary_switch_is_never_activated(self):
        switch=dict(id='com.android.settings:id/switchWidget',**{'class':'android.widget.Switch'},checkable=True,children=[])
        widget=dict(id='android:id/widget_frame',clickable=True,children=[switch])
        divider=dict(id='com.android.settings:id/two_target_divider',visible=True,children=[])
        body=self.node('后台通知','android.widget.LinearLayout');body['children']=[divider,widget]
        state=dict(window='通知',package='com.android.settings')
        self.assertEqual('menu',classify(body,{},state,False))
        secondary=self.node('后台通知','android.widget.FrameLayout');secondary['id']=widget['id'];secondary['children']=[switch]
        self.assertEqual('focus-only',classify(secondary,{},state,False))
        body['children']=[widget]
        self.assertEqual('focus-only',classify(body,{},state,False))


if __name__=='__main__': unittest.main()
