"""Create a new offline signing identity once. Never prints private material."""
from pathlib import Path
import base64,datetime,hashlib,io,json,os,secrets,subprocess,tarfile
from package_h700_v6a import constrained
constrained()
os.umask(0o077)
base=Path('/home/lpf/.roc-os')
for parent in [base,base/'keys',base/'exports',base/'recovery-passphrases']:
 if parent.is_symlink():raise ValueError('Symlink private directory refused')
 parent.mkdir(mode=0o700,parents=True,exist_ok=True);parent.chmod(0o700)
root=base/'keys/production-v1';root.mkdir(mode=0o700) # Refuse overwrite or silent identity rotation.
roles=['releasekey','platform','shared','media','networkstack'];report={'schema':1,'identity':'ROC OS production-v1','created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'key_bits':4096,'roles':{},'external_backup_accepted':False}
def command(args,data=None):
 result=subprocess.run(args,input=data,capture_output=True)
 if result.returncode:raise RuntimeError('Cryptographic tool failed: '+args[0]+' (private output retained locally)')
 return result.stdout
def private_file(path,data):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
for role in roles:
 pem=command(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:4096'])
 der=command(['openssl','pkcs8','-topk8','-nocrypt','-outform','DER'],pem)
 pk8=root/(role+'.pk8');private_file(pk8,der)
 cert=command(['openssl','req','-new','-x509','-sha256','-days','10950','-keyform','DER','-key',str(pk8),'-subj','/CN=ROC OS '+role,'-addext','basicConstraints=critical,CA:FALSE','-addext','keyUsage=critical,digitalSignature'])
 certpath=root/(role+'.x509.pem');private_file(certpath,cert)
 pub=command(['openssl','pkey','-inform','DER','-in',str(pk8),'-pubout','-outform','DER'])
 certpub=command(['openssl','x509','-in',str(certpath),'-pubkey','-noout'])
 assert pub==command(['openssl','pkey','-pubin','-outform','DER'],certpub)
 fingerprint=hashlib.sha256(command(['openssl','x509','-in',str(certpath),'-outform','DER'])).hexdigest()
 report['roles'][role]={'certificate_sha256':fingerprint,'public_key_sha256':hashlib.sha256(pub).hexdigest()}
 print('SIGNING_ROLE_CREATED',role,fingerprint,flush=True)
private_file(root/'identity.public.json',(json.dumps(report,indent=2)+'\n').encode())
registry={'schema':1,'platform_sha256':report['roles']['platform']['certificate_sha256'],'presigned_certificates':{'LeanbackIME':['a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc']}}
private_file(root/'signing-policy.public.json',(json.dumps(registry,indent=2)+'\n').encode())
# Standard OpenPGP symmetric encryption, no custom encryption construction.
archive=io.BytesIO()
with tarfile.open(fileobj=archive,mode='w') as tf:
 for f in sorted(root.iterdir()):
  info=tarfile.TarInfo(f.name);data=f.read_bytes();info.size=len(data);info.mode=0o600;tf.addfile(info,io.BytesIO(data))
password=secrets.token_urlsafe(32).encode();passfile=base/'recovery-passphrases/production-v1.pass';private_file(passfile,password+b'\n')
home=base/'gpg-production-v1';home.mkdir(mode=0o700)
backup=base/'exports/ROC_OS_production_v1.tar.gpg'
def gpg(arguments,data=None):
 rd,wr=os.pipe();os.write(wr,password+b'\n');os.close(wr)
 try:
  return subprocess.run(['gpg','--homedir',str(home),'--batch','--pinentry-mode','loopback','--passphrase-fd',str(rd),*arguments],input=data,capture_output=True,pass_fds=(rd,))
 finally:os.close(rd)
result=gpg(['--symmetric','--cipher-algo','AES256','--s2k-digest-algo','SHA256','--s2k-count','65011712','--force-mdc','--compress-algo','none','--output',str(backup)],archive.getvalue());assert result.returncode==0
backup.chmod(0o600);restored=gpg(['--decrypt',str(backup)]);assert restored.returncode==0 and restored.stdout==archive.getvalue()
# Verify integrity rejection on a distinct, private tampered fixture.
bad=bytearray(backup.read_bytes());bad[len(bad)//2]^=1;badpath=base/'exports/DO_NOT_USE_tampered_test.gpg';private_file(badpath,bytes(bad));assert gpg(['--decrypt',str(badpath)]).returncode!=0
report.update(backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),encrypted_backup_decrypt_verified=True,tamper_rejected=True,private_keys_outside_repository=True)
out=Path('/mnt/d/Works/H700Android/out/source64-release-run-20261104');out.mkdir(exist_ok=True);(out/'keys.public.json').write_text(json.dumps(report,indent=2)+'\n')
private_file(root/'generation-complete.public.json',(json.dumps(report,indent=2)+'\n').encode())
print('SIGNING_IDENTITY_AND_ENCRYPTED_BACKUP_VERIFIED; EXTERNAL_COPY_STILL_REQUIRED',flush=True)
