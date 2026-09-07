Option Explicit

Dim fso, shell, root, ps1, q, command, psExe
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = fso.BuildPath(root, "public\scripts\lancer_wopr_windows.ps1")
q = Chr(34)

If Not fso.FileExists(ps1) Then
    MsgBox "Le lanceur WOPR est introuvable :" & vbCrLf & ps1, vbCritical, "WOPR"
    WScript.Quit 1
End If

psExe = shell.ExpandEnvironmentStrings("%ProgramFiles%\PowerShell\7\pwsh.exe")
If Not fso.FileExists(psExe) Then
    psExe = "powershell.exe"
End If

command = q & psExe & q & " -NoProfile -ExecutionPolicy Bypass -File " & q & ps1 & q
' 1 = fenêtre normale et visible ; elle se ferme quand le script se termine.
shell.Run command, 1, False
