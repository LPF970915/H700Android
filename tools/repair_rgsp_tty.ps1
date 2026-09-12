param([string]$Port = 'COM4')
$s = [IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$s.Handshake='None'; $s.ReadTimeout=200; $s.WriteTimeout=1000; $s.DtrEnable=$false; $s.RtsEnable=$false
try {
  $s.Open()
  $s.BaseStream.Write([byte[]](3),0,1)
  Start-Sleep -Milliseconds 300
  $s.BaseStream.Write([byte[]](10),0,1)
  Start-Sleep -Milliseconds 300
  $s.Write("stty sane`n")
  Start-Sleep -Milliseconds 500
  $s.BaseStream.Write([byte[]](10),0,1)
  Start-Sleep -Milliseconds 300
  $s.Write("/sbin/reboot -f`n")
  Start-Sleep -Milliseconds 500
  Start-Sleep -Milliseconds 500
  Write-Host $s.ReadExisting()
} finally {
  if ($s.IsOpen) { $s.Close() }
  $s.Dispose()
}
