@echo off
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*jarvis*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo.
echo Jarvis fermato.
echo.
pause
