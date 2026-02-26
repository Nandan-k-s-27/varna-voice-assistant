; VARNA v2.3 — Inno Setup Installer Script
; Creates a professional Windows installer (.exe)
;
; Prerequisites:
;   1. Install Inno Setup: https://jrsoftware.org/isinfo.php
;   2. Build with PyInstaller first: pyinstaller varna.spec
;   3. Place varna_logo.ico in assets/ folder
;   4. Open this file in Inno Setup → Compile
;
; Output: VARNA_Setup_v2.3.exe

[Setup]
AppName=VARNA Voice Assistant
AppVersion=2.3
AppVerName=VARNA v2.3
AppPublisher=Nandan K S
AppPublisherURL=https://github.com/Nandan-k-s-27/varna-voice-assistant
AppSupportURL=https://github.com/Nandan-k-s-27/varna-voice-assistant/issues
DefaultDirName={autopf}\VARNA
DefaultGroupName=VARNA Voice Assistant
AllowNoIcons=yes
LicenseFile=LICENSE
OutputDir=installer_output
OutputBaseFilename=VARNA_Setup_v2.3
SetupIconFile=assets\varna_logo.ico
UninstallDisplayIcon={app}\assets\varna_logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copy the entire PyInstaller output folder
Source: "dist\VARNA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VARNA Voice Assistant"; Filename: "{app}\VARNA.exe"; IconFilename: "{app}\assets\varna_logo.ico"
Name: "{group}\Uninstall VARNA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VARNA Voice Assistant"; Filename: "{app}\VARNA.exe"; IconFilename: "{app}\assets\varna_logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\VARNA.exe"; Description: "Launch VARNA Voice Assistant"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\apps.json"
Type: files; Name: "{app}\macros.json"
Type: files; Name: "{app}\user_corrections.json"
