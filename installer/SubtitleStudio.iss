#define MyAppName "Subtitle Studio"
#define MyAppVersion "0.2.1"
#define MyAppExeName "SubtitleStudio.exe"

[Setup]
AppId={{2B60A64D-053F-40CF-B11A-1B1B2B39A358}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Subtitle Studio
DefaultDirName={localappdata}\Programs\SubtitleStudio
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=SubtitleStudio-Setup-{#MyAppVersion}-x64
LicenseFile=..\LICENSE
InfoBeforeFile=installation-info.txt
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#MyAppVersion}.0

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
polish.DesktopShortcut=Utwórz skrót na pulpicie
english.DesktopShortcut=Create a desktop shortcut
polish.LaunchApplication=Uruchom Subtitle Studio
english.LaunchApplication=Launch Subtitle Studio

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\SubtitleStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApplication}"; Flags: nowait postinstall skipifsilent unchecked
