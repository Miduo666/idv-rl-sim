# 治疗 / 自愈连续采样(2026-09-25)。probe2 已注入、人在局内时跑：
#   .\heal60.ps1                       默认 60 秒，每 0.25 秒一帧
#   .\heal60.ps1 -Seconds 90 -Interval 0.5
# 采样在游戏进程里自己的线程跑(cmd_heal60.py)，这边只负责投递、等结束、拉文件、出报告(heal60_report.py)。
param([int]$Seconds = 60, [double]$Interval = 0.25)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$py  = "C:\Users\31297\AppData\Local\Programs\Python\Python313\python.exe"
$D   = "/sdcard/Android/data/com.netease.dwrg/files"
$out = "C:\Users\31297\Desktop\逆向存档\2026.0917_b6f53566\captures\cmd\heal60_{0}" -f (Get-Date -Format "MMdd_HHmmss")
New-Item -ItemType Directory -Force $out | Out-Null

# 参数写在命令最前面，发出去的那份留档
$inv = [Globalization.CultureInfo]::InvariantCulture
$hdr = "SECONDS = {0}`nINTERVAL = {1}`n" -f $Seconds, $Interval.ToString($inv)
$src = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "cmd_heal60.py"), [Text.Encoding]::UTF8)
$sent = Join-Path $out "cmd_sent.py"
[IO.File]::WriteAllText($sent, $hdr + $src, (New-Object Text.UTF8Encoding $false))

& $adb push $sent /sdcard/idv_cmd_tmp.py | Out-Null
& $adb shell "su -c 'rm -f $D/idv_cmd_out.txt $D/idv_heal60.jsonl; cp /sdcard/idv_cmd_tmp.py $D/idv_cmd.py && chown u0_a310:ext_data_rw $D/idv_cmd.py && chmod 660 $D/idv_cmd.py'"
& $adb shell "rm -f /sdcard/idv_cmd_tmp.py"

$txt = $null
for ($k = 0; $k -lt 20 -and -not $txt; $k++) {
    Start-Sleep -Milliseconds 400
    $txt = & $adb shell "su -c 'cat $D/idv_cmd_out.txt 2>/dev/null'"
}
if (-not $txt) { Write-Host "8 秒内没有回应：探针没在跑？"; exit 1 }
$txt | Set-Content (Join-Path $out "cmd_out.txt") -Encoding UTF8
$txt
if (-not ($txt -match "^STARTED")) { Write-Host "采样线程没起来，看上面的输出"; exit 1 }

Write-Host "`n开始采样 $Seconds 秒 —— 现在去受伤 / 倒地 / 自愈 / 被队友治疗"
$t0 = Get-Date
$done = $false
while (-not $done) {
    Start-Sleep -Seconds 5
    $sec = [int]((Get-Date) - $t0).TotalSeconds
    $n = (& $adb shell "su -c 'wc -l < $D/idv_heal60.jsonl 2>/dev/null'") -join ""
    $last = (& $adb shell "su -c 'tail -n 1 $D/idv_heal60.jsonl 2>/dev/null'") -join ""
    $done = $last -match '"end": true|"fatal"'
    Write-Host ("  t+{0,3}s  已写 {1} 行" -f $sec, $n.Trim())
    if (-not $done -and $sec -gt $Seconds + 30) { Write-Host "超时还没看到结束标记，直接拉回已有部分"; break }
}

$local = Join-Path $out "idv_heal60.jsonl"
& $adb shell "su -c 'cp $D/idv_heal60.jsonl /sdcard/idv_heal60.jsonl && chmod 644 /sdcard/idv_heal60.jsonl'"
& $adb pull /sdcard/idv_heal60.jsonl $local | Out-Null
& $adb shell "rm -f /sdcard/idv_heal60.jsonl"
if (-not (Test-Path $local)) { Write-Host "拉取失败"; exit 1 }
Write-Host "采样结束，已拉回 $local。生成报告..."
& $py (Join-Path $PSScriptRoot "heal60_report.py") $out
