# Find what's using COM37
Write-Host "=== COM Port Devices ==="
Get-WmiObject Win32_SerialPort | ForEach-Object {
    Write-Host "$($_.DeviceID) - $($_.Name) - $($_.Status)"
}

Write-Host ""
Write-Host "=== PNP Devices with COM ==="
Get-PnpDevice | Where-Object { $_.FriendlyName -like "*COM37*" } | Format-List Status, Class, FriendlyName, InstanceId

Write-Host ""
Write-Host "=== Process check ==="
Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*serial*" -or $_.ProcessName -like "*arduino*" } | Format-Table Id, ProcessName, MainWindowTitle
