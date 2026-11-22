; Script generated for Inno Setup 6
; SYS-SENTINEL Desktop Companion Installer

#define MyAppName "SYS-SENTINEL"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Uddish"
#define MyAppURL "https://github.com/uddish-collab/sys-sentinel"
#define MyAppExeName "SENTI.exe"

[Setup]
AppId={{9F64B8E1-D74A-4B9F-83C1-4D9D81283F41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\SYS-SENTINEL
DefaultGroupName=SYS-SENTINEL
AllowNoIcons=yes
OutputDir=dist\installer
OutputBaseFilename=SENTI-Setup-v1.0.0
SetupIconFile=assets\senti.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=no
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Launch SYS-SENTINEL automatically on Windows startup"; GroupDescription: "Windows Integration:"

[Files]
Source: "dist\SENTI.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Sentinel"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
