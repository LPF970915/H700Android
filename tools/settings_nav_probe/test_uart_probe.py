import base64,gzip,hashlib,json,unittest
from audit import decode_uart_probe
class UartProbeTest(unittest.TestCase):
    def frame(self,token='abcdef'):
        raw=json.dumps({'token':token,'snapshot':{'label':'设置','windows':[]}},ensure_ascii=False).encode()
        data=base64.b64encode(raw).decode();lines='\r\n'.join(data[i:i+20] for i in range(0,len(data),20))
        return f'echo NVBEGIN_{token}; ignored echoed command\r\nNVBEGIN_{token}\r\n{lines}\r\n{hashlib.sha256(raw).hexdigest()}  /data/local/tmp/nav-passive-audit/response\r\nNVEND_{token}\r\n'
    def test_console_log_between_base64_lines_is_ignored(self):
        frame=self.frame().replace('NVBEGIN_abcdef\r\n','NVBEGIN_abcdef\r\n[123.456] kernel log\r\n')
        self.assertEqual('设置',decode_uart_probe(frame,'abcdef')['label'])
    def test_corruption_is_rejected_instead_of_replaying_keys(self):
        frame=self.frame().replace('eyJ0','eyJ1')
        with self.assertRaises(ValueError):decode_uart_probe(frame,'abcdef')
    def test_compressed_payload_keeps_original_json_checksum(self):
        raw=json.dumps({'token':'abcdef','snapshot':{'windows':[]}},ensure_ascii=False).encode()
        payload=base64.b64encode(gzip.compress(raw)).decode()
        frame=f'NVBEGIN_abcdef\n{payload}\n{hashlib.sha256(raw).hexdigest()}  /data/local/tmp/nav-passive-audit/response\nNVEND_abcdef\n'
        self.assertEqual({'windows':[]},decode_uart_probe(frame,'abcdef'))
    def test_stale_token_frame_is_rejected(self):
        with self.assertRaises(ValueError):decode_uart_probe(self.frame(),'fedcba')
if __name__=='__main__':unittest.main()
