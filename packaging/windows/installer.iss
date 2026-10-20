; Inno Setup script for Simple-Cabin.
; Built with: iscc packaging\windows\installer.iss
; Expects dist\Simple-Cabin\ (PyInstaller onedir output) to already
; exist, and the version passed in via /DAppVersion=x.y.z (the release
; workflow does this so the .iss file never has to be hand-edited per
; release).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Simple-Cabin"
#define RepoRoot AddBackslash(SourcePath) + "..\.."

[Setup]
AppId={{D7A0ECC4-D34E-4A0B-8B80-E98A22C565F9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Mike Hellyer
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\Simple-Cabin.exe
OutputDir={#RepoRoot}\dist
OutputBaseFilename=Simple-Cabin-{#AppVersion}-Windows-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#RepoRoot}\packaging\icons\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#RepoRoot}\dist\Simple-Cabin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Simple-Cabin.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Simple-Cabin.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Simple-Cabin.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
