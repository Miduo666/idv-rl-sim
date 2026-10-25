# 一次性资源导出：推 cmd_resdump_built.py 给 probe2 → 轮询进度 → 拉回 resdump/。
# 用法（PowerShell）：  & "C:\Users\31297\Desktop\逆向存档\_scripts\run_resdump.ps1"
# 前提：注入已完成、probe2 在跑。想要碰撞真值(阶段D)就先进一局对局(训练局/自定义人机，最好是军工厂)再运行。
$ErrorActionPreference = "Continue"
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$D = "/sdcard/Android/data/com.netease.dwrg/files"
$cmd = Join-Path $PSScriptRoot "cmd_resdump_built.py"
$ts = Get-Date -Format "MMdd_HHmmss"
$localAscii = "C:\Users\31297\idv_resdump_$ts"          # adb 只能往 ASCII 路径写
$archive = "C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\res_pull\resdump_$ts"

if (-not (Test-Path $cmd)) { Write-Host "缺少 $cmd ，先跑 build_resdump.py"; exit 1 }
$dev = & $adb get-state 2>$null
if ($dev -ne "device") { Write-Host "设备没连上"; exit 1 }
$gpid = (& $adb shell "pidof com.netease.dwrg").Trim()
if (-not $gpid) { Write-Host "游戏没在运行"; exit 1 }
$uid = (& $adb shell "su -c 'stat -c %U /proc/$gpid'").Trim()
Write-Host "游戏 pid=$gpid uid=$uid"

# 推命令
& $adb push $cmd /sdcard/idv_cmd_tmp.py | Out-Null
& $adb shell "su -c 'rm -f $D/idv_cmd_out.txt; rm -rf $D/resdump; cp /sdcard/idv_cmd_tmp.py $D/idv_cmd.py && chown ${uid}:ext_data_rw $D/idv_cmd.py && chmod 660 $D/idv_cmd.py'"
& $adb shell "rm /sdcard/idv_cmd_tmp.py"

# 确认探针接收（命令被消费 + 输出出现）
$started = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Milliseconds 800
    $r = & $adb shell "su -c 'test -f $D/idv_cmd_out.txt && echo OUT; test -f $D/idv_cmd.py && echo PENDING'"
    if ($r -match "OUT") { $started = $true; break }
}
if (-not $started) { Write-Host "20 秒内探针没接收命令：probe2 没在跑，或 uid/chown 不对。没有任何东西被执行。"; exit 1 }
Write-Host "探针已接收，后台开始导出。"

# 轮询进度
$tmp = Join-Path $env:TEMP "resdump_progress.json"
$last = ""; $lastChange = Get-Date; $stage = ""
while ($true) {
    Start-Sleep -Seconds 3
    $ok = & $adb shell "su -c 'test -f $D/resdump/progress.json && cp $D/resdump/progress.json /sdcard/rp.json && chmod 666 /sdcard/rp.json && echo ok'"
    if ($ok -match "ok") {
        Remove-Item $tmp -ErrorAction SilentlyContinue
        & $adb pull /sdcard/rp.json $tmp 2>$null | Out-Null
        if (Test-Path $tmp) {
            $raw = Get-Content $tmp -Raw
            if ($raw -ne $last) { $last = $raw; $lastChange = Get-Date }
            try { $p = $raw | ConvertFrom-Json; $stage = $p.stage
                  Write-Host ("[{0,6}s] {1,-16} 取到 {2,5}  未命中 {3,5}  {4,8:N0} KB  导航块 {5,6}  射线 {6,6}  异常 {7}" -f $p.elapsed, $p.stage, $p.got, $p.miss, ($p.bytes/1KB), $p.tiles, $p.rays, $p.err) } catch {}
        }
    }
    if ($stage -eq "done" -or $stage -eq "fatal") { break }
    if (((Get-Date) - $lastChange).TotalSeconds -gt 60) { Write-Host "进度 60 秒没变化（游戏可能已崩溃/被踢），直接拉取已落盘的文件。"; break }
}

# 拉回
& $adb shell "su -c 'rm -rf /data/local/tmp/resdump_pull; cp -r $D/resdump /data/local/tmp/resdump_pull && chmod -R 755 /data/local/tmp/resdump_pull'"
New-Item -ItemType Directory -Force $localAscii | Out-Null
& $adb pull /data/local/tmp/resdump_pull/. $localAscii
& $adb shell "su -c 'rm -rf /data/local/tmp/resdump_pull'"
& $adb shell "rm -f /sdcard/rp.json"
New-Item -ItemType Directory -Force $archive | Out-Null
Copy-Item "$localAscii\*" $archive -Recurse -Force
Write-Host ""
Write-Host "本地(ASCII): $localAscii"
Write-Host "存档:        $archive"
Get-ChildItem $archive | Select-Object Name, Length | Format-Table -AutoSize
if (Test-Path "$archive\log.txt") { Get-Content "$archive\log.txt" -Encoding UTF8 -Tail 15 }
