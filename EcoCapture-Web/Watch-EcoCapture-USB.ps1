param([string]$Serial='2954148814', [int]$Port=8080)
$ErrorActionPreference='Stop'
$taskMutex=[Threading.Mutex]::new($false,'Local\EcoCaptureWebUsbWatcher')
try { if(-not $taskMutex.WaitOne(0)){exit} } catch [Threading.AbandonedMutexException] { }
$taskAdb=Join-Path $PSScriptRoot '..\other\uno_q_tools\platform-tools\adb.exe'
$taskStateDir=Join-Path $env:LOCALAPPDATA 'EcoCapture-Web'
New-Item -ItemType Directory -Force $taskStateDir | Out-Null
$taskLog=Join-Path $taskStateDir 'usb-watcher.log'
function Write-WatcherLog([string]$Text){
    if((Test-Path $taskLog) -and (Get-Item $taskLog).Length -gt 262144){Move-Item -LiteralPath $taskLog -Destination "$taskLog.old" -Force}
    Add-Content -LiteralPath $taskLog -Value "$([DateTime]::Now.ToString('s')) $Text"
}
function Invoke-Adb([string]$Arguments){
    $taskStart=[Diagnostics.ProcessStartInfo]::new($taskAdb,$Arguments)
    $taskStart.UseShellExecute=$false;$taskStart.CreateNoWindow=$true
    $taskStart.RedirectStandardOutput=$true;$taskStart.RedirectStandardError=$true
    $taskProcess=[Diagnostics.Process]::Start($taskStart)
    try{
        $taskOutput=$taskProcess.StandardOutput.ReadToEndAsync()
        $taskError=$taskProcess.StandardError.ReadToEndAsync()
        if(-not $taskProcess.WaitForExit(10000)){$taskProcess.Kill();return ''}
        return $taskOutput.GetAwaiter().GetResult()
    }finally{$taskProcess.Dispose()}
}
try{
    Write-WatcherLog 'Watcher started; waiting for UNO Q USB.'
    $taskOpened=$false;$taskMissing=0;$taskNextAttempt=[DateTime]::MinValue
    $taskNextRecovery=[DateTime]::MinValue;$taskLastState='';$taskNextForward=[DateTime]::MinValue
    while($true){
        try{
            $taskDevices=Invoke-Adb 'devices'
            $taskConnected=$taskDevices -match ("(?m)^"+[regex]::Escape($Serial)+"\s+device\s*$")
            $taskOffline=$taskDevices -match ("(?m)^"+[regex]::Escape($Serial)+"\s+offline\s*$")
            $taskState=if($taskConnected){'ready'}elseif($taskOffline){'offline'}else{'absent'}
            if($taskState -ne $taskLastState){Write-WatcherLog "USB state: $taskState";$taskLastState=$taskState}
            if(-not $taskConnected){
                $taskMissing++
                if($taskMissing -ge 2){$taskOpened=$false}
                if($taskOffline -and [DateTime]::Now -ge $taskNextRecovery){
                    $taskNextRecovery=[DateTime]::Now.AddSeconds(30)
                    $null=Invoke-Adb "-s $Serial reconnect"
                    Write-WatcherLog 'Requested recovery of offline UNO Q USB connection.'
                }elseif($taskState -eq 'absent' -and $taskMissing -ge 2 -and [DateTime]::Now -ge $taskNextRecovery){
                    $taskNextRecovery=[DateTime]::Now.AddSeconds(30)
                    $taskUsb=Get-PnpDevice -PresentOnly -InstanceId "USB\VID_2341&PID_0078\$Serial" -ErrorAction SilentlyContinue
                    if($taskUsb){
                        $null=Invoke-Adb 'kill-server'
                        $null=Invoke-Adb 'start-server'
                        Write-WatcherLog 'Recovered ADB discovery for the present UNO Q USB device.'
                    }
                }
            }else{
                $taskMissing=0
                if([DateTime]::Now -ge $taskNextForward){
                    $null=Invoke-Adb "-s $Serial forward tcp:$Port tcp:8080"
                    $taskNextForward=[DateTime]::Now.AddSeconds(15)
                }
                if(-not $taskOpened -and [DateTime]::Now -ge $taskNextAttempt){
                    $taskNextAttempt=[DateTime]::Now.AddSeconds(2)
                    $null=Invoke-Adb "-s $Serial forward tcp:$Port tcp:8080"
                    try{
                        $taskStatus=Invoke-RestMethod "http://127.0.0.1:$Port/api/status" -TimeoutSec 2
                        if($taskStatus.version -and $taskStatus.source -in @('stm32-dummy','logger-v2-hardware')){
                            Start-Process "http://127.0.0.1:$Port/"
                            $taskOpened=$true;Write-WatcherLog 'UNO Q ready; opened the default browser.'
                        }
                    }catch{}
                }
            }
        }catch{Write-WatcherLog $_.Exception.Message;Start-Sleep -Seconds 3}
        Start-Sleep -Milliseconds 1000
    }
}finally{$taskMutex.ReleaseMutex();$taskMutex.Dispose()}
