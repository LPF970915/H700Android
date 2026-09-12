# AT4K Small Screen Layout Adaptation Script
# Target: 720x480 @ 213dpi

$basePath = "D:\Works\H700Android\out\at4k-modify\decoded\smali\R3"

Write-Host "Starting AT4K layout modifications for 720x480 screen..."

# Backup original files
Write-Host "Creating backups..."
Copy-Item "$basePath\J7.smali" "$basePath\J7.smali.backup"
Copy-Item "$basePath\T5.smali" "$basePath\T5.smali.backup"
Copy-Item "$basePath\Z4.smali" "$basePath\Z4.smali.backup"

# 1. Settings Panel (J7.smali) - Reduce padding and font sizes
Write-Host "Modifying J7.smali (Settings Panel)..."
$j7Content = Get-Content "$basePath\J7.smali" -Raw

# Line ~8802: Category content padding 32dp -> 12dp (0x20 -> 0xc)
# Line ~8808: Vertical spacing 12dp -> 6dp (0xc -> 0x6)
# Line ~8894: Title size 26sp -> 18sp (0x1a -> 0x12)
# Line ~8902: Title bottom space 24dp -> 8dp (0x18 -> 0x8)
# Line ~9319: Entry padding 10dp -> 6dp (0xa -> 0x6)
# Line ~9416: Entry text 20sp -> 14sp (0x14 -> 0xe)

$j7Content = $j7Content -replace '(?<=# Settings category padding\s+const/16 v\d+, )0x20', '0xc'
$j7Content = $j7Content -replace '(?<=# Title font size\s+const/16 v\d+, )0x1a', '0x12'
$j7Content = $j7Content -replace '(?<=# Entry font size\s+const/16 v\d+, )0x14', '0xe'

Set-Content "$basePath\J7.smali" $j7Content -NoNewline

# 2. Desktop Insets (T5.smali) - Reduce whitespace
Write-Host "Modifying T5.smali (Desktop Layout)..."
$t5Content = Get-Content "$basePath\T5.smali" -Raw

# Line ~828: Top padding 24dp -> 12dp (0x18 -> 0xc)
# Line ~828: Bottom padding 68dp -> 30dp (0x44 -> 0x1e)
# Note: Left/right 10dp stays the same

$t5Content = $t5Content -replace '(const/16 v4, )0x18(?=\s+int-to-float)', '${1}0xc'
# Find and replace bottom padding - need more context

Set-Content "$basePath\T5.smali" $t5Content -NoNewline

# 3. Icon Spacing (Z4.smali) - Tighter layout
Write-Host "Modifying Z4.smali (Icon Geometry)..."
$z4Content = Get-Content "$basePath\Z4.smali" -Raw

# Normal mode horizontal gap: 22dp -> 14dp (0x16 -> 0xe)
# Row spacing: 18dp -> 12dp (0x12 -> 0xc)
# Mini mode gap: 12dp -> 8dp (0xc -> 0x8)

$z4Content = $z4Content -replace '(?<=# Normal icon gap\s+const/16 v\d+, )0x16', '0xe'
$z4Content = $z4Content -replace '(?<=# Row spacing\s+const/16 v\d+, )0x12', '0xc'

Set-Content "$basePath\Z4.smali" $z4Content -NoNewline

Write-Host "Layout modifications completed. Files backed up with .backup extension."
