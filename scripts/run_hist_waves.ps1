$ErrorActionPreference = "Stop"
$done = "C:\Users\Abhinav\commuttify\outputs\hist_waves_done.txt"
Remove-Item $done -ErrorAction SilentlyContinue
$days = @('2026_10_01','2026_10_04','2026_10_05','2026_10_06',
          '2026_10_07','2026_10_08','2026_10_10','2026_10_11')

function Wait-FreeRam([int]$minGB) {
    for ($t = 0; $t -lt 10; $t++) {
        $os = Get-CimInstance Win32_OperatingSystem
        $free = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
        if ($free -ge $minGB) { return $true }
        Start-Sleep -Seconds 10
    }
    return $false
}

for ($i = 0; $i -lt $days.Count; $i += 2) {
    $end = [Math]::Min($i + 1, $days.Count - 1)
    $wave = @($days[$i], $days[$end]) | Select-Object -Unique
    if (-not (Wait-FreeRam 1)) {
        Add-Content $done "$(Get-Date -Format 'HH:mm:ss') WARN: low RAM, proceeding anyway"
    }
    $procs = @()
    foreach ($d in $wave) {
        $log = "C:\Users\Abhinav\commuttify\outputs\hist_$d.log"
        $err = "C:\Users\Abhinav\commuttify\outputs\hist_$d.err"
        Remove-Item $log, $err -ErrorAction SilentlyContinue
        try {
            $p = Start-Process -FilePath "python" -ArgumentList @("-m","backend.process_historical","--days",$d,"--chunksize","100000") -WorkingDirectory "C:\Users\Abhinav\commuttify" -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err -PassThru -ErrorAction Stop
        } catch {
            Add-Content $done "$(Get-Date -Format 'HH:mm:ss') FAIL launch $d : $_"
            $p = $null
        }
        if (-not $p) { continue }
        $procs += $p
        Add-Content $done "$(Get-Date -Format 'HH:mm:ss') started $d pid $($p.Id)"
    }
    foreach ($p in $procs) {
        try { $p.WaitForExit() } catch {}
    }
    Add-Content $done "$(Get-Date -Format 'HH:mm:ss') wave finished ($($wave -join ','))"
    Start-Sleep -Seconds 20
}
Add-Content $done "$(Get-Date -Format 'HH:mm:ss') ALL WAVES DONE"
