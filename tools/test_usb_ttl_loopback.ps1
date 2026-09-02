param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [int]$BaudRate = 115200
)

$ErrorActionPreference = "Stop"
$availablePorts = [System.IO.Ports.SerialPort]::GetPortNames()
if ($Port -notin $availablePorts) {
    throw "Serial port '$Port' is not present. Available ports: $($availablePorts -join ', ')"
}

$serial = [System.IO.Ports.SerialPort]::new(
    $Port,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.ReadTimeout = 1500
$serial.WriteTimeout = 1500
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.Encoding = [System.Text.Encoding]::ASCII

$token = "RGSP_UART_LOOPBACK_" + [Guid]::NewGuid().ToString("N")

try {
    $serial.Open()
    $serial.DiscardInBuffer()
    $serial.DiscardOutBuffer()
    $serial.WriteLine($token)
    $received = $serial.ReadLine().Trim()

    if ($received -eq $token) {
        Write-Host "PASS: USB-TTL TX and RX loopback succeeded on $Port at $BaudRate 8N1."
        exit 0
    }

    Write-Error "FAIL: Received unexpected data: '$received'"
    exit 1
} catch [System.TimeoutException] {
    Write-Error "FAIL: No loopback data received. Confirm that only USB-TTL TX and RX are connected together."
    exit 1
} finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}

