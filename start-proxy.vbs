Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python -u """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\host_proxy.py""", 0, False
