name: Worker (Task Executor)

on:
  workflow_dispatch:

jobs:
  worker:
    runs-on: windows-latest
    timeout-minutes: 360

    steps:
      - name: Install NetBird
        run: |
          choco install netbird -y
          if ($LASTEXITCODE -ne 0) {
            $installerUrl = "https://github.com/netbirdio/netbird/releases/latest/download/netbird_installer.exe"
            Invoke-WebRequest -Uri $installerUrl -OutFile "$env:TEMP\netbird_installer.exe"
            Start-Process -FilePath "$env:TEMP\netbird_installer.exe" -ArgumentList "/S" -Wait
          }

      - name: Connect to NetBird
        run: |
          $netbird = "${env:ProgramFiles}\NetBird\netbird.exe"
          & $netbird down 2>$null
          & $netbird up --setup-key C2E7F429-1F54-4FDC-AF61-FC67A5C59500 `
            --allow-server-ssh --enable-ssh-root

      - name: Worker main loop – discover, register, poll tasks every 10 sec
        run: |
          $netbird = "${env:ProgramFiles}\NetBird\netbird.exe"
          $adminIP = $null
          $registered = $false
          $lastHealthCheck = (Get-Date)

          function Invoke-WithRetry {
            param(
              [string]$Uri,
              [string]$Method = 'Get',
              $Body = $null,
              [int]$TimeoutSec = 10,
              [int]$MaxRetries = 3,
              [int]$RetryDelaySec = 2
            )
            for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
              try {
                $params = @{
                  Uri = $Uri
                  Method = $Method
                  TimeoutSec = $TimeoutSec
                }
                if ($Body) { $params.Body = $Body; $params.ContentType = 'application/json' }
                return Invoke-RestMethod @params
              } catch {
                Write-Host "Attempt $attempt failed: $_"
                if ($attempt -eq $MaxRetries) { throw }
                Start-Sleep -Seconds $RetryDelaySec
              }
            }
          }

          while ($true) {
            $now = Get-Date

            # Health check every 5 minutes
            if (($now - $lastHealthCheck).TotalSeconds -ge 300) {
              $lastHealthCheck = $now
              $status = & $netbird status 2>&1
              if ($status -match "Disconnected") {
                Write-Host "$(Get-Date -Format 'HH:mm:ss') - NetBird disconnected! Reconnecting..."
                & $netbird down 2>$null
                Start-Sleep -Seconds 5
                & $netbird up --setup-key C2E7F429-1F54-4FDC-AF61-FC67A5C59500 `
                  --allow-server-ssh --enable-ssh-root
                $adminIP = $null
                $registered = $false
              } else {
                Write-Host "$(Get-Date -Format 'HH:mm:ss') - NetBird healthy."
              }
            }

            # Discover admin
            if (-not $adminIP) {
              try {
                $json = & $netbird status --json | ConvertFrom-Json
                $peers = $json.peers.details
                $admin = $peers | Where-Object { $_.fqdn -like "*admin-node*" } | Select-Object -First 1
                if ($admin) {
                  $adminIP = $admin.netbirdIp
                  Write-Host "$(Get-Date -Format 'HH:mm:ss') - Admin found at $adminIP"
                }
              } catch {
                Write-Host "Error discovering admin: $_"
              }
            }

            # Register
            if ($adminIP -and -not $registered) {
              try {
                $myIP = (& $netbird status | Select-String "NetBird IP:").ToString().Split()[-1]
                $body = @{ ip = $myIP; name = $env:COMPUTERNAME } | ConvertTo-Json
                Invoke-WithRetry -Uri "http://$adminIP`:5000/api/workers" `
                  -Method Post -Body $body -TimeoutSec 10 -MaxRetries 3 -RetryDelaySec 2
                Write-Host "Registered with admin"
                $registered = $true
              } catch {
                Write-Host "Registration failed after retries: $_"
              }
            }

            # Task polling
            if ($adminIP) {
              try {
                $task = Invoke-WithRetry -Uri "http://$adminIP`:5000/api/tasks/pop" `
                  -Method Get -TimeoutSec 10 -MaxRetries 3 -RetryDelaySec 2
                if ($task -and $task.command) {
                  Write-Host "$(Get-Date -Format 'HH:mm:ss') - Received task: $($task.command)"
                  $output = & $task.command 2>&1 | Out-String
                  $result = @{
                    worker = $env:COMPUTERNAME
                    taskId = $task.id
                    output = $output
                  }
                  Invoke-WithRetry -Uri "http://$adminIP`:5000/api/results" `
                    -Method Post -Body ($result | ConvertTo-Json) -TimeoutSec 10 -MaxRetries 3 -RetryDelaySec 2
                  Write-Host "Task result sent."
                }
              } catch {
                if ($_.Exception.Response.StatusCode -ne 204) {
                  Write-Host "Task polling error: $_"
                }
              }
            } else {
              Write-Host "$(Get-Date -Format 'HH:mm:ss') - Admin not yet discovered."
            }

            Start-Sleep -Seconds 10
          }
