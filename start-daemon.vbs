Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python -u """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\connection_persister.py"" --daemon", 0, False
