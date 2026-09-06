Option Explicit

Dim fso, shell, root, ps1, q, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = fso.BuildPath(root, "public\scripts\lancer_wopr_windows.ps1")
q = Chr(34)

If Not fso.FileExists(ps1) Then
    MsgBox "Le lanceur WOPR est introuvable :" & vbCrLf & ps1, vbCritical, "WOPR"
    WScript.Quit 1
End If

command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & q & ps1 & q
' 0 = fenêtre cachée ; False = ne pas bloquer WScript.
shell.Run command, 0, False
