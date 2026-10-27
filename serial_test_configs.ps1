# Try different serial configurations
$configs = @(
    @{Name="Standard 8N1"; Baud=115200; Parity="None"; DataBits=8; StopBits="One"; Handshake="None"},
    @{Name="With XON/XOFF"; Baud=115200; Parity="None"; DataBits=8; StopBits="One"; Handshake="XOnXOff"},
    @{Name="With RTS/CTS"; Baud=115200; Parity="None"; DataBits=8; StopBits="One"; Handshake="RequestToSend"}
)

foreach($config in $configs) {
    Write-Host "`n=== Testing: $($config.Name) ===" -ForegroundColor Cyan

    try {
        $port = new-Object System.IO.Ports.SerialPort "COM4", $config.Baud, $config.Parity, $config.DataBits, $config.StopBits
        $port.Handshake = $config.Handshake
        $port.ReadTimeout = 2000
        $port.WriteTimeout = 2000
        $port.Open()

        # Clear and send simple command
        Start-Sleep -Milliseconds 500
        $port.ReadExisting() | Out-Null

        $port.WriteLine("echo TEST123")
        Start-Sleep -Milliseconds 1500
        $result = $port.ReadExisting()

        Write-Host "Result: $result"

        if($result -match "TEST123") {
            Write-Host "SUCCESS with $($config.Name)!" -ForegroundColor Green
        }

        $port.Close()
    } catch {
        Write-Host "Failed: $($_.Exception.Message)" -ForegroundColor Red
    }

    Start-Sleep -Milliseconds 500
}
