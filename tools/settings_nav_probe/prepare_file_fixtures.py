"""Prepare owned Unicode/photo/long-list fixtures; this is setup, not UI operation evidence."""
import hashlib,json,shlex,struct,subprocess,zlib
from audit import Audit,OUT,adb,ADB,TARGET
from files import FIXTURE

def chunk(kind,body):return struct.pack('!I',len(body))+kind+body+struct.pack('!I',zlib.crc32(kind+body)&0xffffffff)

def main():
    expected=hashlib.sha256(b'RGSP controller fixture 20261024\n').hexdigest()
    if adb('sha256sum '+FIXTURE+'/destination/T.txt').split()[0]!=expected:raise RuntimeError('Owned fixture signature missing')
    unicode_path=FIXTURE+'/source/中文 空格.txt';image_path=FIXTURE+'/source/audit_pixel.png';long=FIXTURE+'/long-list'
    for target in (unicode_path,image_path,long):
        if adb('if [ -e '+shlex.quote(target)+' ]; then echo EXISTS; fi').strip()=='EXISTS':raise RuntimeError('Refusing to replace fixture: '+target)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00\x00\xff\x00\x00\x00\x00\xff\xff\xff\x00'))+chunk(b'IEND',b'')
    local=OUT/'files-owned-pixel.png';local.write_bytes(png)
    a=Audit()
    try:
        a.command('cp '+FIXTURE+'/destination/T.txt '+shlex.quote(unicode_path))
        a.command('mkdir '+long+'; for item in $(seq 0 63); do name=$(printf item_%03d.txt "$item"); printf "RGSP owned long-list %s\\n" "$item" > '+long+'/"$name"; done')
        subprocess.run([ADB,'-s',TARGET,'push',str(local),image_path],check=True,capture_output=True)
        result={'setup_only':True,'unicode_path':unicode_path,'unicode_sha256':adb('sha256sum '+shlex.quote(unicode_path)).split()[0],'image_path':image_path,'image_sha256':hashlib.sha256(png).hexdigest(),'long_list':long,'count':int(adb('find '+long+' -type f | wc -l').strip())}
        if result['count']!=64:raise RuntimeError('Long-list fixture incomplete')
        (OUT/'files-extra-fixtures.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result,flush=True)
    finally:a.close()
if __name__=='__main__':main()
