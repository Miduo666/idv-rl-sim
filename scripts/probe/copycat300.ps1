# 模仿者模式 5 分钟采样：进局、看到自己身份之后跑。
#   .\copycat300.ps1               默认 300 秒
#   .\copycat300.ps1 -Seconds 180
# 开始 / 中途 / 结束各投一次 cmd_copycat_full.py(广度搜索)，其余时间连续投 cmd_copycat_tick.py(轻量快照)。
# 结束后调用 copycat_report.py 出报告。
param([int]$Seconds = 300)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8   # adb 输出是 UTF-8，不设的话中文玩家名按 GBK 解码成乱码
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$py  = "C:\Users\31297\AppData\Local\Programs\Python\Python313\python.exe"
$D   = "/sdcard/Android/data/com.netease.dwrg/files"
$out = "C:\Users\31297\Desktop\逆向存档\2026.0917_b6f53566\captures\cmd\copycat_{0}" -f (Get-Date -Format "MMdd_HHmmss")
New-Item -ItemType Directory -Force $out | Out-Null

& $adb push (Join-Path $PSScriptRoot "cmd_copycat_tick.py") /sdcard/idv_cc_tick.py | Out-Null
& $adb push (Join-Path $PSScriptRoot "cmd_copycat_full.py") /sdcard/idv_cc_full.py | Out-Null

function Invoke-Probe([string]$remote) {
    & $adb shell "su -c 'rm -f $D/idv_cmd_out.txt; cp $remote $D/idv_cmd.py && chown u0_a310:ext_data_rw $D/idv_cmd.py && chmod 660 $D/idv_cmd.py'"
    $txt = $null
    for ($k = 0; $k -lt 15 -and -not $txt; $k++) {
        Start-Sleep -Milliseconds 400
        $txt = & $adb shell "su -c 'cat $D/idv_cmd_out.txt 2>/dev/null'"
    }
    return $txt
}

function Save-Full([string]$tag) {
    $txt = Invoke-Probe "/sdcard/idv_cc_full.py"
    if (-not $txt) { Write-Host "  [full $tag] 没有输出(探针没在跑?)"; return }
    $txt | Set-Content (Join-Path $out "full_$tag.txt") -Encoding UTF8
    $end = ($txt | Where-Object { $_ -like "END*" -or $_ -like "TRUNC*" }) -join "  "
    Write-Host ("  [full {0}] {1}  {2}" -f $tag, (Get-Date -Format "HH:mm:ss"), $end)
}

Write-Host "输出目录 $out"
Save-Full "start"
$t0 = Get-Date
$end = $t0.AddSeconds($Seconds)
$mid = $t0.AddSeconds($Seconds / 2); $midDone = $false
$i = 0; $miss = 0
while ((Get-Date) -lt $end) {
    if (-not $midDone -and (Get-Date) -ge $mid) { Save-Full "mid"; $midDone = $true; continue }
    $txt = Invoke-Probe "/sdcard/idv_cc_tick.py"
    if (-not $txt) { $miss++; Write-Host "  第 $i 轮没有输出(探针没在跑?)"; if ($miss -ge 3) { break }; continue }
    $miss = 0; $i++
    $txt | Set-Content (Join-Path $out ("s_{0:D3}.txt" -f $i)) -Encoding UTF8
    $sec = [int]((Get-Date) - $t0).TotalSeconds
    $e = ($txt | Where-Object { $_ -like "END*" }) -join ""
    $w = (($txt | Where-Object { $_ -like "WORLD*" }) -join "") -replace "`t", " "
    Write-Host ("  [{0:D3}] t+{1,3}s {2}  {3}  {4}" -f $i, $sec, (Get-Date -Format "HH:mm:ss"), $w, $e)
}
Save-Full "end"
& $adb shell "rm -f /sdcard/idv_cc_tick.py /sdcard/idv_cc_full.py"
Write-Host "采样结束，共 $i 个快照。生成报告..."
& $py (Join-Path $PSScriptRoot "copycat_report.py") $out
