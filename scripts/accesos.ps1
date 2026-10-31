param([string]$Repo = (Resolve-Path "$PSScriptRoot\..").Path)

$godot = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "Godot_v4*_mono_win64.exe" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike "*console*" } | Select-Object -First 1).FullName
if (-not $godot) { Write-Error "No encontré Godot 4 mono (winget install GodotEngine.GodotEngine.Mono)"; exit 1 }

$home2 = "$env:APPDATA\Sapo"
New-Item -ItemType Directory -Force -Path $home2 | Out-Null
$ico = "$home2\sapo.ico"
Copy-Item "$Repo\settings\build\icon.ico" $ico -Force -ErrorAction SilentlyContinue

$brain = "$Repo\brain\.venv\Scripts\sapo-brain.exe"
$voice = "$Repo\brain\.venv\Scripts\sapo-voice.exe"
$vbs = @"
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
If wmi.ExecQuery("select * from Win32_Process where Name='sapo-brain.exe'").Count = 0 Then sh.Run """$brain""", 0, False
If fs.FolderExists("$home2\models") Then
  If wmi.ExecQuery("select * from Win32_Process where Name='sapo-voice.exe'").Count = 0 Then sh.Run """$voice""", 0, False
End If
If wmi.ExecQuery("select * from Win32_Process where Name like 'Godot%'").Count = 0 Then sh.Run """$godot"" --path ""$Repo\pc""", 0, False
"@
Set-Content -Path "$home2\iniciar.vbs" -Value $vbs -Encoding ASCII

$menu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("$menu\Sapo.lnk")
$s.TargetPath = "$env:WINDIR\System32\wscript.exe"
$s.Arguments = "`"$home2\iniciar.vbs`""
$s.IconLocation = $ico
$s.Description = "Sapo-Jarvis"
$s.Save()

$prefs = "$Repo\settings\dist\SapoPreferencias\SapoPreferencias.exe"
if (Test-Path $prefs) {
  $p = $ws.CreateShortcut("$menu\Sapo Preferencias.lnk")
  $p.TargetPath = $prefs
  $p.WorkingDirectory = Split-Path $prefs
  $p.IconLocation = $ico
  $p.Description = "Preferencias del Sapo"
  $p.Save()
}
Write-Output "listo: $menu\Sapo.lnk"
