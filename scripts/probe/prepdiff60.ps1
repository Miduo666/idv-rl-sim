# 准备阶段 60 秒差分：我是监管、对面求生者在换天赋时跑。
#   .\prepdiff60.ps1            默认 60 秒
#   .\prepdiff60.ps1 -Seconds 90
# 每轮把 cmd_prepdiff.py 投给 probe2，取回快照存成 s_NNN.txt，结束后调用 prepdiff.py 出报告。
param([int]$Seconds = 60)
$ErrorActionPreference = "Stop"
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$py  = "C:\Users\31297\AppData\Local\Programs\Python\Python313\python.exe"
$D   = "/sdcard/Android/data/com.netease.dwrg/files"
$cmd = Join-Path $PSScriptRoot "cmd_prepdiff.py"
$out = "C:\Users\31297\Desktop\逆向存档\2026.0917_b6f53566\captures\cmd\prepdiff_{0}" -f (Get-Date -Format "MMdd_HHmmss")
New-Item -ItemType Directory -Force $out | Out-Null

& $adb push $cmd /sdcard/idv_cmd_tmp.py | Out-Null
$end = (Get-Date).AddSeconds($Seconds)
$i = 0; $miss = 0
Write-Host "开始采样 $Seconds 秒，输出目录 $out"
while ((Get-Date) -lt $end) {
    & $adb shell "su -c 'rm -f $D/idv_cmd_out.txt; cp /sdcard/idv_cmd_tmp.py $D/idv_cmd.py && chown u0_a310:ext_data_rw $D/idv_cmd.py && chmod 660 $D/idv_cmd.py'"
    $txt = $null
    for ($k = 0; $k -lt 12 -and -not $txt; $k++) {
        Start-Sleep -Milliseconds 400
        $txt = & $adb shell "su -c 'cat $D/idv_cmd_out.txt 2>/dev/null'"
    }
    if (-not $txt) { $miss++; Write-Host "  第 $i 轮没有输出(探针没在跑?)"; if ($miss -ge 3) { break }; continue }
    $i++
    $txt | Set-Content (Join-Path $out ("s_{0:D3}.txt" -f $i)) -Encoding UTF8
    $panel = ($txt | Where-Object { $_ -like "PANEL*" }) -join ""
    Write-Host ("  [{0:D3}] {1}  {2}" -f $i, (Get-Date -Format "HH:mm:ss"), $panel)
}
& $adb shell "rm -f /sdcard/idv_cmd_tmp.py"
Write-Host "采样结束，共 $i 个样本。生成报告..."
& $py (Join-Path $PSScriptRoot "prepdiff.py") $out
