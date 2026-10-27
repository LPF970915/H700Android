"""An observer retirement may repeat observation, never a preceding input."""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import audit


class PassiveRetryTest(unittest.TestCase):
    def observer(self):
        a=audit.Audit.__new__(audit.Audit)
        a.counter=0;a.navigation_version=None;a.observation_transport='adb'
        a.probe_identity_checked=True
        a.ensure_probe=Mock();a.key=Mock();a.command=Mock()
        return a

    def test_retired_observer_reobserved_without_keys(self):
        a=self.observer();queries=[]
        def read(command):
            queries.append(command)
            if len(queries)==1:raise subprocess.CalledProcessError(1,['adb','shell'])
            token=re.search(r'echo ([a-f0-9]{16}) >',command)[1]
            return json.dumps({'token':token,'snapshot':{'windows':[]}})
        with tempfile.TemporaryDirectory() as temp,patch.object(audit,'OUT',Path(temp)),patch.object(audit,'adb',side_effect=read),patch.object(audit.time,'sleep'):
            data,*_=a.snap('retirement')
            self.assertEqual(data,{'windows':[]})
            self.assertEqual(a.ensure_probe.call_count,2)
            a.key.assert_not_called();a.command.assert_not_called()

    def test_permanent_read_failure_stops_after_three_observations(self):
        a=self.observer()
        with tempfile.TemporaryDirectory() as temp,patch.object(audit,'OUT',Path(temp)),patch.object(audit,'adb',side_effect=subprocess.CalledProcessError(1,['adb'])) as read,patch.object(audit.time,'sleep'):
            with self.assertRaises(subprocess.CalledProcessError):a.snap('failed')
            self.assertEqual(read.call_count,3)
            a.key.assert_not_called();a.command.assert_not_called()


if __name__=='__main__':unittest.main()
