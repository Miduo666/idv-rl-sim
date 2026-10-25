# 把命令脚本推给 probe2 执行并取回结果。  .\send_cmd.ps1 cmd_phase.py 准备阶段
param([Parameter(Mandatory)][string]$Cmd, [string]$Tag = "out")
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$D = "/sdcard/Android/data/com.netease.dwrg/files"
$src = (Resolve-Path (Join-Path $PSScriptRoot $Cmd)).Path
$outDir = "C:\Users\31297\Desktop\逆向存档\2026.0917_b6f53566\captures\cmd"
New-Item -ItemType Directory -Force $outDir | Out-Null

& $adb push $src /sdcard/idv_cmd_tmp.py | Out-Null
& $adb shell "su -c 'rm -f $D/idv_cmd_out.txt; cp /sdcard/idv_cmd_tmp.py $D/idv_cmd.py && chown u0_a409:ext_data_rw $D/idv_cmd.py && chmod 660 $D/idv_cmd.py'"
& $adb shell "rm /sdcard/idv_cmd_tmp.py"

# 取回：用 adb pull 拿原始字节再按 UTF-8 解码。探针写的是 UTF-8，
# 直接 `adb shell cat` 会被 PowerShell 按系统 GBK 解码 → 中文乱码(ASCII 不受影响)。
$txt = $null
$tmp = Join-Path $env:TEMP "idv_cmd_out.txt"
for ($i = 0; $i -lt 20 -and -not $txt; $i++) {
    Start-Sleep -Milliseconds 700
    $ok = & $adb shell "su -c 'test -f $D/idv_cmd_out.txt && cp $D/idv_cmd_out.txt /sdcard/idv_cmd_out.txt && chmod 666 /sdcard/idv_cmd_out.txt && echo ok'"
    if ($ok -match 'ok') {
        Remove-Item $tmp -ErrorAction SilentlyContinue
        & $adb pull /sdcard/idv_cmd_out.txt $tmp 2>$null | Out-Null
        & $adb shell "rm -f /sdcard/idv_cmd_out.txt" | Out-Null
        if (Test-Path $tmp) { $txt = [IO.File]::ReadAllText($tmp, [Text.Encoding]::UTF8) -split "`r?`n" }
    }
}
if (-not $txt) { Write-Host "14 秒内没有输出：探针没在跑？"; exit 1 }
$f = Join-Path $outDir ("{0}_{1}.txt" -f (Get-Date -Format "HHmmss"), $Tag)
$txt | Set-Content $f -Encoding UTF8
$txt
# 提取 models.json 给 label_scene.py
$i = [Array]::IndexOf([string[]]$txt, "###MODELS###")
if ($i -ge 0) { $txt[$i + 1] | Set-Content (Join-Path $PSScriptRoot "models.json") -Encoding UTF8; Write-Host "`n[models.json 已更新]" }
Write-Host "[已存] $f"
