# 找"每帧自己变的治疗进度字段"(2026-09-25)。**有人正在被治疗 / 自愈时**跑：  .\healscan.ps1
# 投递 cmd_healscan.py(游戏里 3 次全量数值快照，间隔 1 秒)，等它写完 idv_healscan.txt 再拉回来打印。
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$D   = "/sdcard/Android/data/com.netease.dwrg/files"
$outDir = "C:\Users\31297\Desktop\逆向存档\2026.0917_b6f53566\captures\cmd"

& $adb push (Join-Path $PSScriptRoot "cmd_healscan.py") /sdcard/idv_cmd_tmp.py | Out-Null
& $adb shell "su -c 'rm -f $D/idv_cmd_out.txt $D/idv_healscan.txt; cp /sdcard/idv_cmd_tmp.py $D/idv_cmd.py && chown u0_a310:ext_data_rw $D/idv_cmd.py && chmod 660 $D/idv_cmd.py'"
& $adb shell "rm -f /sdcard/idv_cmd_tmp.py"

$txt = $null
for ($k = 0; $k -lt 20 -and -not $txt; $k++) {
    Start-Sleep -Milliseconds 400
    $txt = & $adb shell "su -c 'cat $D/idv_cmd_out.txt 2>/dev/null'"
}
if (-not $txt) { Write-Host "8 秒内没有回应：探针没在跑？"; exit 1 }
$txt
if (-not ($txt -match "^STARTED")) { exit 1 }

$res = $null
for ($k = 0; $k -lt 40; $k++) {
    Start-Sleep -Milliseconds 500
    $res = & $adb shell "su -c 'cat $D/idv_healscan.txt 2>/dev/null'"
    if ($res -and ($res -match "^END")) { break }
}
if (-not $res) { Write-Host "20 秒内没有结果"; exit 1 }
$f = Join-Path $outDir ("healscan_{0}.txt" -f (Get-Date -Format "MMdd_HHmmss"))
$res | Set-Content $f -Encoding UTF8
$res | Select-Object -First 120
Write-Host "`n[已存] $f"
