#define MyAppName "Subtitle Studio"
#define MyAppVersion "0.2.1"

[Setup]
AppId={{90C99486-E344-4175-8DC1-48CE1472AA84}
AppName={#MyAppName} (Online)
AppVersion={#MyAppVersion}
AppPublisher=Subtitle Studio
DefaultDirName={localappdata}\Programs\SubtitleStudioOnline
DefaultGroupName=Subtitle Studio Online
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=SubtitleStudio-Setup-0.2.1-Online-x64
LicenseFile=..\LICENSE
InfoBeforeFile=online-info.txt
SetupIconFile=..\assets\icon.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\app\assets\icon.ico
VersionInfoVersion={#MyAppVersion}.0

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\build\public-installer-source\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "bootstrap.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "launch.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Subtitle Studio Online"; Filename: "{app}\launch.cmd"; WorkingDir: "{app}"; IconFilename: "{app}\app\assets\icon.ico"

[Run]
Filename: "{app}\launch.cmd"; Description: "{cm:LaunchProgram,Subtitle Studio}"; Flags: shellexec nowait postinstall skipifsilent unchecked
