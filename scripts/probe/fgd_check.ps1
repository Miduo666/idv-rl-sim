# 准备阶段"求生者天赋0条"时跑：进程内打出 final_genius_dict 的真实样子，再在 PC 侧按 C++ 的读法读一遍内存。
#   .\fgd_check.ps1
# 跑的时候保持准备界面、**别让对面在这几秒里换天赋**(PC 侧要按进程内给的地址去读，字典被替换就对不上了)。
$py  = "C:\Users\31297\AppData\Local\Programs\Python\Python313\python.exe"
$outDir = "C:\Users\31297\Desktop\逆向存档\2026.0917_b6f53566\captures\cmd"
& (Join-Path $PSScriptRoot "send_cmd.ps1") cmd_fgd.py fgd_fail
if ($LASTEXITCODE -ne 0) { Write-Host "探针没有输出，先确认探针在跑"; exit 1 }
$f = Get-ChildItem $outDir -Filter "*_fgd_fail.txt" | Sort-Object LastWriteTime | Select-Object -Last 1
Write-Host "`n==================== PC 侧按 C++ 读法复查 ===================="
& $py (Join-Path $PSScriptRoot "fgd_mem.py") $f.FullName 2>&1 | Tee-Object -FilePath ($f.FullName -replace '\.txt$', '_mem.txt')
Write-Host "`n[已存] $($f.FullName) 以及 _mem.txt"
