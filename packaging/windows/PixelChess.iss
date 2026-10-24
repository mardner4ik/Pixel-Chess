#ifndef AppVersion
  #define AppVersion "1.2.3"
#endif

[Setup]
AppId={{ABF67928-9CFB-4DF1-AE69-FAC340945133}
AppName=Pixel Chess
AppVersion={#AppVersion}
AppPublisher=mardner4ik
DefaultDirName={autopf}\Pixel Chess
DefaultGroupName=Pixel Chess
OutputDir=Release
OutputBaseFilename=PixelChess-{#AppVersion}-Windows-Setup
SetupIconFile=..\..\assets\pixelchess-icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\PixelChess\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Pixel Chess"; Filename: "{app}\PixelChess.exe"
Name: "{autodesktop}\Pixel Chess"; Filename: "{app}\PixelChess.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PixelChess.exe"; Description: "Launch Pixel Chess"; Flags: postinstall nowait skipifsilent
