$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.ReadTimeout = 3000
$port.Open()

Write-Host "=== Attempting to enable WiFi ADB ===" -ForegroundColor Green

# Clear buffer
Start-Sleep -Milliseconds 500
$port.ReadExisting() | Out-Null

# Try to enable ADB over network on port 5555
Write-Host "Sending: setprop service.adb.tcp.port 5555"
$port.WriteLine("setprop service.adb.tcp.port 5555")
Start-Sleep -Milliseconds 2000
Write-Host $port.ReadExisting()

Write-Host "`nSending: stop adbd"
$port.WriteLine("stop adbd")
Start-Sleep -Milliseconds 2000
Write-Host $port.ReadExisting()

Write-Host "`nSending: start adbd"
$port.WriteLine("start adbd")
Start-Sleep -Milliseconds 2000
Write-Host $port.ReadExisting()

Write-Host "`nGetting IP address..."
$port.WriteLine("ip addr show wlan0")
Start-Sleep -Milliseconds 2000
$result = $port.ReadExisting()
Write-Host $result

$port.Close()

Write-Host "`nIf you see an IP address above, try connecting with:" -ForegroundColor Yellow
Write-Host "adb connect <IP_ADDRESS>:5555" -ForegroundColor Cyan
