' Avvia Jarvis (Telegram + ascolto vocale) in background, senza finestre.
' Gli eventuali errori finiscono in jarvis.log e wake.log nella stessa cartella.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)

' All'accensione del PC aspetta 20 secondi, cosi' internet e audio sono pronti.
' Con doppio clic manuale parte subito.
If WScript.Arguments.Count > 0 Then WScript.Sleep 20000

sh.Run "cmd /c python -u jarvis.py >> jarvis.log 2>&1", 0, False
WScript.Sleep 3000
sh.Run "cmd /c python -u jarvis_wake.py >> wake.log 2>&1", 0, False
