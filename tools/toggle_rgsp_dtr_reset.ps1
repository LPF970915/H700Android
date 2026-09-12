param([string]$Port='COM4')
$s=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$s.Handshake='None';$s.DtrEnable=$false;$s.RtsEnable=$false
try{$s.Open();$s.DtrEnable=$true;Start-Sleep -Milliseconds 800;$s.DtrEnable=$false;Start-Sleep -Milliseconds 800;$s.RtsEnable=$true;Start-Sleep -Milliseconds 300;$s.RtsEnable=$false}catch{}finally{if($s.IsOpen){$s.Close()};$s.Dispose()}
