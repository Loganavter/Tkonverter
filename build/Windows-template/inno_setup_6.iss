; -- Tkonverter Inno Setup Script --
; Сборка: после PyInstaller запустить Inno Setup и скомпилировать этот скрипт.
; Или: iscc build\Windows-template\inno_setup_6.iss (из корня репозитория).

#define MyAppName "Tkonverter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Tkonverter"
#define MyAppURL "https://github.com/your-org/Tkonverter"
#define MyAppExeName "Tkonverter.exe"
#define MyAppSetupName "Tkonverter_Setup_v1.0.0"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename={#MyAppSetupName}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=icons\icon.ico
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\Tkonverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{localappdata}\Tkonverter"
