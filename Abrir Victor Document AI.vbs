Option Explicit

Dim archivos, carpetaProyecto, pythonw, aplicacion, shell

Set archivos = CreateObject("Scripting.FileSystemObject")
carpetaProyecto = archivos.GetParentFolderName(WScript.ScriptFullName)
pythonw = carpetaProyecto & "\.venv\Scripts\pythonw.exe"
aplicacion = carpetaProyecto & "\src\main.py"

If Not archivos.FileExists(pythonw) Then
    MsgBox "No se encontró el entorno virtual en:" & vbCrLf & pythonw, _
        vbCritical, "Victor Document AI"
    WScript.Quit 1
End If

If Not archivos.FileExists(aplicacion) Then
    MsgBox "No se encontró la aplicación en:" & vbCrLf & aplicacion, _
        vbCritical, "Victor Document AI"
    WScript.Quit 1
End If

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = carpetaProyecto
shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & aplicacion & Chr(34), 0, False
