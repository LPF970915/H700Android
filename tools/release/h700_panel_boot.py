"""Guarded in-memory LCD selection using the retained U-Boot's LCD probe.

Only regular image files are consumed by callers. No live device writes.
The Android HWC already reads FBIOGET_VSCREENINFO; never force wm size.
"""
import hashlib,struct,zlib

ENV_OFFSET=138412032
ENV_SIZE=131072
PANEL='/soc@03000000/lcd0@01c0c000'
# Stock BSP panel data, selected properties only (no imported GPIO/phandles).
# knulli-cfw/knulli-linux, package/boot/uboot-h700/rg35xx-h/boot_package/rg35xx-h.dts
LCD_640={
 'lcd_x':640,'lcd_y':480,'lcd_dclk_freq':24,'lcd_hbp':46,'lcd_ht':770,
 'lcd_hspw':20,'lcd_vbp':15,'lcd_vt':520,'lcd_vspw':4,
 'lcd_hv_clk_phase':2,'lcd_hv_sync_polarity':3,
}

def padded_dtb(blob,extra=16384):
 """Preserve every property; reserve bounded space for U-Boot's longer name."""
 magic,size=struct.unpack_from('>II',blob)
 assert magic==0xd00dfeed and size==len(blob)
 result=bytearray(blob)+bytes(extra)
 struct.pack_into('>I',result,4,len(result))
 return bytes(result)

def script(dtb_address):
 raise ValueError('WITHDRAWN: actual 720x480 RG SP also reports lcd_type=old; no validated panel identity')
 # Historical implementation below is unreachable and retained for diagnosis.
 assert 0x45000000 < dtb_address < 0x49000000
 commands=[f'if fdt addr {dtb_address:x}; then',
  'if test "${lcd_type}" = "old"; then',
  'echo ROC_LCD_AUTO=640x480_old']
 # This exact retained kernel registers rg34xxsp_v1, whose FJ035 callback
 # already consumes lcd_type. Do not import another kernel's driver alias.
 commands += [f"fdt set {PANEL} {k} '<0x{v:x}>'" for k,v in LCD_640.items()]
 commands += ['else','echo ROC_LCD_AUTO=retained_720x480 lcd_type=${lcd_type}','fi',
              'else','echo ROC_LCD_AUTO=unavailable_retaining_boot','fi']
 return ';'.join(commands).replace('then;','then ').replace('else;','else ')

def decode_env(block):
 assert len(block)==ENV_SIZE
 expected=struct.unpack_from('<I',block)[0]
 assert zlib.crc32(block[4:])==expected,'Original U-Boot environment CRC mismatch'
 body=block[4:];end=body.find(b'\0\0');assert end>=0
 rows=body[:end].split(b'\0')
 # This pinned vendor environment has one leading empty entry. himport_r
 # skips it; retain it byte-for-byte instead of deleting unknown input.
 assert all(b'=' in r or (i==0 and r==b'') for i,r in enumerate(rows))
 return [(r.split(b'=',1)[0].decode('ascii'),r.split(b'=',1)[1].decode('ascii')) if r else ('','') for r in rows]

def patch_env(prefix,dtb_address):
 raise ValueError('Test2 packaging disabled after physical display regression; preserve the original boot environment')
 # Historical implementation below is unreachable and retained for diagnosis.
 result=bytearray(prefix)
 old=bytes(result[ENV_OFFSET:ENV_OFFSET+ENV_SIZE]);rows=decode_env(old)
 values=dict(rows)
 assert values['boot_normal']=='sunxi_flash read 45000000 boot;bootm 45000000'
 assert 'roc_panel_apply' not in values,'Refuse replay on already patched environment'
 changes={'boot_normal':'sunxi_flash read 45000000 boot;run roc_panel_apply;bootm 45000000',
          'roc_panel_apply':script(dtb_address)}
 rows=[(k,changes.get(k,v)) for k,v in rows]
 rows.append(('roc_panel_apply',changes['roc_panel_apply']))
 body=b'\0'.join((k+'='+v).encode('ascii') if k else b'' for k,v in rows)+b'\0\0'
 assert len(body)<ENV_SIZE-4
 body=body.ljust(ENV_SIZE-4,b'\0')
 new=struct.pack('<I',zlib.crc32(body))+body
 result[ENV_OFFSET:ENV_OFFSET+ENV_SIZE]=new
 after=dict(decode_env(new))
 assert {k:v for k,v in after.items() if k not in changes}=={k:v for k,v in values.items() if k not in changes}
 assert bytes(result[:ENV_OFFSET])==bytes(prefix[:ENV_OFFSET])
 assert bytes(result[ENV_OFFSET+ENV_SIZE:])==bytes(prefix[ENV_OFFSET+ENV_SIZE:])
 return bytes(result),{'before_sha256':hashlib.sha256(old).hexdigest(),
  'after_sha256':hashlib.sha256(new).hexdigest(),'changed_variables':changes,
  'retained_hardware_probe':'lcd_type old/boe set by original U-Boot panel init',
  'unknown_probe_keeps_parent_panel_and_boot_continues':True}
