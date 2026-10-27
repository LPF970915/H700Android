param(
    [ValidatePattern('^COM[0-9]+$')][string]$Port = 'COM4',
    [string]$RunDirectory,
    [ValidateRange(60, 3600)][int]$TimeoutSeconds = 1800,
    [switch]$Arm,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-BootstrapDecision([string]$Text, [double]$BootAge) {
    if (-not $Text.Contains('HELLO! BOOT0 is starting!')) { return 'Wait' }
    if ($Text -match '(?m)(?:^|\r)console:/ \$') { return 'RefuseDuplicate' }
    if (-not $Text.Contains('[rgsp-single-card] universal v5 ramdisk running') -or
        -not $Text.Contains('[rgsp-single-card] single-card init reached')) { return 'Wait' }
    if ($Text -notmatch '(?m)(?:^|\r)rgsp:/ #(?:[ \r\n]|$)') { return 'Wait' }
    if ($BootAge -gt 20) { return 'RefuseLate' }
    return 'Inject'
}

if ($SelfTest) {
    $boot = "HELLO! BOOT0 is starting!`n"
    $v5 = "[rgsp-single-card] universal v5 ramdisk running`n"
    $init = "[rgsp-single-card] single-card init reached`n"
    $root = 'rgsp:/ #'
    $cases = @(
        @{ Text = $root; Age = 0; Want = 'Wait' },
        @{ Text = $boot + $root; Age = 4; Want = 'Wait' },
        @{ Text = $boot + $v5 + $root; Age = 4; Want = 'Wait' },
        @{ Text = $boot + $v5 + $init + $root; Age = 10; Want = 'Inject' },
        @{ Text = $boot + $v5 + $init + $root; Age = 21; Want = 'RefuseLate' },
        @{ Text = $boot + $v5 + $init + 'console:/ $'; Age = 10; Want = 'RefuseDuplicate' },
        @{ Text = $boot + $v5 + $init + $root + "`nconsole:/ `$"; Age = 10; Want = 'RefuseDuplicate' },
        @{ Text = $boot + $v5 + $init + "rgsp:/ # [ 11.1] kernel`n"; Age = 11; Want = 'Inject' }
    )
    foreach ($case in $cases) {
        $actual = Get-BootstrapDecision $case.Text $case.Age
        if ($actual -ne $case.Want) { throw "Expected $($case.Want), got $actual" }
    }
    Write-Output "PASS: $($cases.Count) bootstrap decision tests; no serial port opened."
    exit 0
}

if ([string]::IsNullOrWhiteSpace($RunDirectory)) { throw 'RunDirectory is required.' }
$adapter = @(Get-PnpDevice -PresentOnly | Where-Object {
    $_.InstanceId -eq 'USB\VID_1A86&PID_55D3\5CDA070915' -and
    $_.FriendlyName -match ("\(" + [regex]::Escape($Port) + "\)$") -and
    $_.Status -eq 'OK'
})
if ($adapter.Count -ne 1) { throw 'Expected RGSP CH343 adapter was not uniquely identified.' }

$run = [IO.Path]::GetFullPath($RunDirectory)
[IO.Directory]::CreateDirectory($run) | Out-Null
$statePath = Join-Path $run 'state.json'
$rawPath = Join-Path $run 'uart.log'
$token = [Guid]::NewGuid().ToString('N')
$marker = "__RGSP_UART_$($token)__"
$status = @{
    pid = $PID
    port = $Port
    armed = [bool]$Arm
    state = 'STARTING'
    uart_log = $rawPath
    command_sent = $false
    recovery_verified = $false
    rollback = 'setprop ctl.start console'
}
function Save-State([string]$Name) {
    $status.state = $Name
    $status.updated = (Get-Date).ToString('o')
    [IO.File]::WriteAllText($statePath, ($status | ConvertTo-Json))
    Write-Output "$($status.updated) $Name"
}

# The complete line is parsed by the sole early root shell before the donor
# console starts. No further input is sent while the delayed stop is pending.
$command = 'if [ "$(getprop ro.product.device)" = rgsp ]; then sleep 8; ' +
    "setprop ctl.stop console; printf '\n$($marker):%s:%s:%s\n' " +
    '"$(getprop init.svc.console)" "$(getprop init.svc.rgsp-console)" "$(id -u)"; fi'
$expected = "(?m)^" + [regex]::Escape($marker) + ":stopped:running:0\r?$"

$serial = [IO.Ports.SerialPort]::new($Port, 115200, 'None', 8, 'One')
$serial.Handshake = 'None'
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 250
$serial.WriteTimeout = 1000
$serial.Encoding = [Text.Encoding]::UTF8
$raw = $null
$buffer = [byte[]]::new(4096)
$recent = ''
$bootAt = $null
$sentAt = $null
$canInject = [bool]$Arm
$timer = [Diagnostics.Stopwatch]::StartNew()
try {
    $raw = [IO.File]::Open($rawPath, 'CreateNew', 'Write', 'Read')
    $serial.Open()
    Save-State 'WAITING_NEW_BOOT'
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $available = $serial.BytesToRead
        if ($available -gt 0) {
            $count = $serial.Read($buffer, 0, [Math]::Min($available, $buffer.Length))
            $raw.Write($buffer, 0, $count)
            $raw.Flush()
            $recent += [Text.Encoding]::UTF8.GetString($buffer, 0, $count)
            if ($recent.Length -gt 65536) { $recent = $recent.Substring($recent.Length - 65536) }
            if ($null -eq $bootAt) {
                $index = $recent.IndexOf('HELLO! BOOT0 is starting!')
                if ($index -ge 0) {
                    $recent = $recent.Substring($index)
                    $bootAt = $timer.Elapsed.TotalSeconds
                    Save-State 'NEW_BOOT_SEEN'
                }
            }
            if ($canInject -and $null -ne $bootAt) {
                $decision = Get-BootstrapDecision $recent ($timer.Elapsed.TotalSeconds - $bootAt)
                if ($decision -like 'Refuse*') {
                    $canInject = $false
                    Save-State $decision
                } elseif ($decision -eq 'Inject') {
                    $canInject = $false
                    $status.command_sent = $true
                    $sentAt = $timer.Elapsed.TotalSeconds
                    Save-State 'SENDING_ONCE'
                    $serial.Write($command + "`r")
                    Save-State 'WAITING_SERVICE_PROOF'
                }
            }
            if ($status.command_sent -and -not $status.recovery_verified -and $recent -match $expected) {
                $status.recovery_verified = $true
                Save-State 'UART_RECOVERY_VERIFIED'
            }
        }
        if ($null -ne $sentAt -and -not $status.recovery_verified -and
            $status.state -eq 'WAITING_SERVICE_PROOF' -and
            ($timer.Elapsed.TotalSeconds - $sentAt) -gt 25) {
            Save-State 'NO_VERIFIED_RECOVERY_NO_RETRY'
        }
        Start-Sleep -Milliseconds 20
    }
    Save-State 'CAPTURE_DEADLINE_REACHED'
} catch {
    $status.error = $_.Exception.Message
    Save-State 'ERROR'
    throw
} finally {
    $serial.Dispose()
    if ($null -ne $raw) { $raw.Dispose() }
}
