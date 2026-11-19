@echo off
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Jarvis.lnk'); $s.TargetPath='wscript.exe'; $s.Arguments='%~dp0avvia_jarvis.vbs boot'; $s.WorkingDirectory='%~dp0'; $s.Save()"
echo.
echo Fatto! Jarvis partira da solo ad ogni accensione del PC.
echo Per provarlo subito senza riavviare: doppio clic su avvia_jarvis.vbs
echo.
pause
