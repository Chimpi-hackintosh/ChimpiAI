#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#define AppName "ChimpiAI"
#define AppPublisher "Chimpi-hackintosh"

[Setup]
AppId=Chimpi-hackintosh.ChimpiAI
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/Chimpi-hackintosh/ChimpiAI
AppSupportURL=https://github.com/Chimpi-hackintosh/ChimpiAI/issues
DefaultDirName={localappdata}\Programs\ChimpiAI
DefaultGroupName=ChimpiAI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=ChimpiAI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ChimpiAI.exe
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
SetupLogging=yes

[Files]
Source: "..\dist\ChimpiAI\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\ChimpiAI"; Filename: "{app}\ChimpiAI.exe"
Name: "{autodesktop}\ChimpiAI"; Filename: "{app}\ChimpiAI.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
Filename: "{app}\ChimpiAI.exe"; Description: "Abrir ChimpiAI"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
