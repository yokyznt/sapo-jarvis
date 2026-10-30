#ifndef AppVersion
  #define AppVersion "0.5.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\Sapo"
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif

[Setup]
AppId={{3109A472-B495-4AB1-B39F-A92AC80695FE}
AppName=Sapo
AppVersion={#AppVersion}
AppVerName=Sapo {#AppVersion}
AppPublisher=Sapo-Jarvis
AppPublisherURL=https://github.com/
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Sapo
DefaultGroupName=Sapo
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=Sapo-Setup-{#AppVersion}
SetupIconFile=..\pc\icon.ico
UninstallDisplayIcon={app}\Sapo.exe
UninstallDisplayName=Sapo
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
UsedUserAreasWarning=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
es.Autostart=Arrancar Sapo con Windows
es.OpenSapo=Abrir Sapo ahora
es.Prefs=Sapo Preferencias

[Tasks]
Name: "autostart"; Description: "{cm:Autostart}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sapo"; Filename: "{app}\Sapo.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:Prefs}"; Filename: "{app}\SapoPreferencias.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,Sapo}"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Sapo"; ValueData: """{app}\Sapo.exe"""; Tasks: autostart

[Run]
Filename: "{app}\Sapo.exe"; Description: "{cm:OpenSapo}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
const
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

procedure KillOurs(Dir: String);
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM Sapo.exe /IM sapo-brain.exe /IM sapo-voice.exe /IM SapoPreferencias.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(800);
end;

procedure RemoveRun(Dir: String);
var
  Value: String;
begin
  if RegQueryStringValue(HKCU, RunKey, 'Sapo', Value) then
    if Pos(Lowercase(AddBackslash(Dir)), Lowercase(Value)) > 0 then
      RegDeleteValue(HKCU, RunKey, 'Sapo');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillOurs(ExpandConstant('{app}'));
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and not WizardIsTaskSelected('autostart') then
    RemoveRun(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    KillOurs(ExpandConstant('{app}'));
    RemoveRun(ExpandConstant('{app}'));
  end;
end;
