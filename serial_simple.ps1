$port = new-Object System.IO.Ports.SerialPort COM4,115200,None,8,one
$port.ReadTimeout = 5000
$port.Open()

Write-Host "=== H700 Serial Diagnosis ===" -ForegroundColor Green

# Clear buffer
$port.ReadExisting() | Out-Null

# Send single enter to get prompt
$port.WriteLine("")
Start-Sleep -Milliseconds 800
$initial = $port.ReadExisting()
Write-Host "Initial prompt: $initial" -ForegroundColor Yellow

function Run-SimpleCmd($cmd, $desc) {
    Write-Host "`n[$desc]" -ForegroundColor Cyan
    $port.ReadExisting() | Out-Null
    $port.WriteLine($cmd)
    Start-Sleep -Milliseconds 2000
    $output = $port.ReadExisting()
    Write-Host $output
    return $output
}

# Test with simple commands first
Run-SimpleCmd "pwd" "Current directory"
Run-SimpleCmd "id" "User ID"
Run-SimpleCmd "uname -a" "Kernel info"

# Now try backlight
Run-SimpleCmd "ls -la /sys/class/" "Check sys class"

$port.Close()
Write-Host "`n=== Test Complete ===" -ForegroundColor Green
