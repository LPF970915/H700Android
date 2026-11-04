import hashlib,json,os,shutil,struct,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import inventory,recovery,audit_release
class ReleaseTests(unittest.TestCase):
 def setUp(self):
  base=Path(os.environ['ROC_RELEASE_TEST_FIXTURES']) if 'ROC_RELEASE_TEST_FIXTURES' in os.environ else Path(tempfile.mkdtemp(prefix='roc-release-tests-'))
  base.mkdir(parents=True,exist_ok=True);self.root=base/self._testMethodName;self.root.mkdir()
 def tearDown(self):pass # Keep regular-file fixtures and failed evidence.
 def test_inventory_drift_links_and_added_files(self):
  source=self.root/'source';source.mkdir();(source/'a').write_bytes(b'pin');(source/'link').symlink_to('a');m=self.root/'manifest';inventory.inventory(source,m);self.assertTrue(inventory.verify(source,m));(source/'a').write_bytes(b'bad')
  with self.assertRaises(AssertionError):inventory.verify(source,m)
  (source/'a').write_bytes(b'pin');(source/'extra').write_text('x')
  with self.assertRaises(AssertionError):inventory.verify(source,m)
 def test_recovery_round_trip_and_protected_ranges(self):
  image=self.root/'disk.img';image.write_bytes(b'P'*4096+b'D'*4096+b'T'*4096)
  g={'image_bytes':12288,'start':4096,'bytes':4096,'filesystem_uuid':'fixture','gpt_sha256':'fixture'}
  bundle=self.root/'backup'
  with patch.object(recovery,'geometry',return_value=g.copy()):
   recovery.backup(image,bundle);before=image.read_bytes();image.write_bytes(b'P'*4096+b'X'*4096+b'T'*4096)
   self.assertEqual(recovery.restore(image,bundle)['mode'],'plan');self.assertNotEqual(image.read_bytes(),before)
   recovery.restore(image,bundle,True);self.assertEqual(image.read_bytes(),before)
   image.write_bytes(b'Z'+before[1:]);unchanged=image.read_bytes()
   with self.assertRaises(ValueError):recovery.restore(image,bundle,True)
   self.assertEqual(image.read_bytes(),unchanged)
 def test_corrupt_backup_rejected_before_write(self):
  image=self.root/'disk.img';image.write_bytes(b'P'*4096+b'D'*4096+b'T'*4096);g={'image_bytes':12288,'start':4096,'bytes':4096,'filesystem_uuid':'fixture','gpt_sha256':'fixture'};bundle=self.root/'backup'
  with patch.object(recovery,'geometry',return_value=g.copy()):
   recovery.backup(image,bundle);(bundle/'userdata.ext4').write_bytes(b'broken');before=image.read_bytes()
   with self.assertRaises(ValueError):recovery.restore(image,bundle,True)
   self.assertEqual(image.read_bytes(),before)
 def test_real_ext4_backup_restore_after_corruption(self):
  import layout
  fs=self.root/'fs';
  with fs.open('wb') as f:f.truncate(64*1024**2)
  subprocess.run(['mke2fs','-q','-F','-t','ext4','-U',str(layout.DATA_FS_UUID),'-O','^metadata_csum,^64bit',str(fs)],check=True,capture_output=True)
  sentinel=self.root/'save';sentinel.write_text('save must survive\n');subprocess.run(['debugfs','-w','-R','write '+str(sentinel)+' /save',str(fs)],check=True,capture_output=True)
  image=self.root/'offline.img';image.write_bytes(b'P'*4096+fs.read_bytes()+b'T'*4096);size=fs.stat().st_size
  g={'image_bytes':size+8192,'start':4096,'bytes':size,'filesystem_uuid':str(layout.DATA_FS_UUID),'gpt_sha256':'small-ext4-engine-fixture'}
  with patch.object(recovery,'geometry',return_value=g.copy()):
   recovery.backup(image,self.root/'bundle')
   with image.open('r+b') as f:f.seek(4096);f.write(b'broken filesystem superblock'+b'\0'*8192)
   recovery.restore(image,self.root/'bundle',True)
  with image.open('rb') as src,fs.open('wb') as dst:src.seek(4096);dst.write(src.read(size))
  result=subprocess.run(['e2fsck','-f','-n',str(fs)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  saved=subprocess.check_output(['debugfs','-R','cat /save',str(fs)],stderr=subprocess.DEVNULL,text=True);self.assertEqual(saved,sentinel.read_text())
 def test_regular_paths_only(self):
  f=self.root/'file';f.write_bytes(b'x');link=self.root/'link';link.symlink_to(f)
  with self.assertRaises(ValueError):recovery.regular(link)
  hard=self.root/'hard';os.link(f,hard)
  with self.assertRaises(ValueError):recovery.regular(f)
  with self.assertRaises(ValueError):recovery.regular('/dev/null')
 def test_actual_compact_GPT_and_wrong_UUID(self):
  import layout
  # Real source64 GPT geometry with sparse regular file, never a block device.
  from_path=Path('/home/lpf/h700-dualabi-image-20261031/prefix.candidate.raw')
  with from_path.open('rb') as f:head,tail=layout.derive(f.read(2048))
  p=self.root/'gpt.img'
  with p.open('wb') as f:
   f.truncate(layout.SEED_BYTES);f.write(head);f.seek(layout.SEED_BYTES-len(tail));f.write(tail);f.seek(layout.DATA_START+1024+56);f.write(b'\x53\xef');f.seek(layout.DATA_START+1024+104);f.write(layout.DATA_FS_UUID.bytes)
  self.assertEqual(recovery.geometry(p)['start'],layout.DATA_START)
  with p.open('r+b') as f:f.seek(layout.DATA_START+1024+104);f.write(b'\0'*16)
  with self.assertRaises(ValueError):recovery.geometry(p)
  self.assertEqual(recovery.geometry(p,check_fs=False)['start'],layout.DATA_START)
  with p.open('r+b') as f:f.seek(512+16);f.write(b'\0'*4)
  with self.assertRaises(ValueError):recovery.geometry(p,check_fs=False)
 def test_release_gate_fails_closed(self):
  self.assertFalse(audit_release.evaluate({},'',None)['release_allowed']);props=dict(audit_release.POLICY['properties']);props.update({'ro.build.type':'user','ro.build.tags':'release-keys'});e={x:True for x in audit_release.POLICY['required_evidence']}
  self.assertTrue(audit_release.evaluate(props,'','androidboot.selinux=enforcing',True,e)['release_allowed'])
  for rc,cmd in [('service console /system/bin/sh','enforcing'),(' seclabel u:r:su:s0','enforcing'),('','androidboot.selinux=permissive')]:self.assertFalse(audit_release.evaluate(props,rc,cmd,True,e)['release_allowed'])
 def test_signing_registry_rejects_test_and_partial_sets(self):
  names=['SystemUI','Settings','ROCNavigation','H700Lid','H700Rotation','AT4K'];formal='a'*64;test='b'*64;signers={n:[formal] for n in names}
  self.assertTrue(audit_release.signing_allowed(signers,{'platform_sha256':formal},{test}))
  self.assertFalse(audit_release.signing_allowed(signers,{'platform_sha256':formal},{formal}))
  del signers['Settings'];self.assertFalse(audit_release.signing_allowed(signers,{'platform_sha256':formal},{test}))
 def test_release_product_requires_user_and_external_keys(self):
  product=Path(__file__).resolve().parents[2]/'android/h700-android10/device/roc/roc_os_release_candidate'
  self.assertEqual((product/'release_properties.mk').read_bytes(),Path(__file__).with_name('roc_release_properties.mk').read_bytes())
  mk=self.root/'Makefile';mk.write_text('TARGET_PRODUCT := roc_os_release_candidate\nTARGET_BUILD_VARIANT := eng\ninclude '+str(product/'roc_os_release_candidate.mk')+'\nall:\n\t@echo allowed\n')
  blocked=subprocess.run(['make','-s','-f',str(mk)],capture_output=True,text=True);self.assertNotEqual(blocked.returncode,0);self.assertIn('requires user variant',blocked.stderr)
  mk.write_text(mk.read_text().replace(':= eng',':= user'));blocked=subprocess.run(['make','-s','-f',str(mk)],capture_output=True,text=True);self.assertNotEqual(blocked.returncode,0);self.assertIn('separately managed',blocked.stderr)
 def test_make_overlay_effective_values(self):
  mk=self.root/'Makefile';overlay=Path(__file__).with_name('roc_release_properties.mk');mk.write_text('PRODUCT_PROPERTY_OVERRIDES := ro.adb.secure=0 persist.sys.usb.config=adb keep=yes\nPRODUCT_SYSTEM_DEFAULT_PROPERTIES := ro.debuggable=1\nPRODUCT_PACKAGES := su Superuser AT4K\ninclude '+str(overlay)+'\nall:\n\t@echo "$(PRODUCT_PROPERTY_OVERRIDES) $(PRODUCT_SYSTEM_DEFAULT_PROPERTIES) $(PRODUCT_PACKAGES)"\n')
  result=subprocess.check_output(['make','-s','-f',str(mk)],text=True);self.assertNotIn('ro.adb.secure=0',result);self.assertNotIn('ro.debuggable=1',result);self.assertNotIn(' su ',result);self.assertIn('ro.adb.secure=1',result);self.assertIn('AT4K',result);self.assertIn('keep=yes',result)
if __name__=='__main__':unittest.main()
