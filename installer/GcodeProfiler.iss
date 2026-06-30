; Inno Setup script for Gcode Profiler
; Build: iscc /DMyAppVersion=0.1.0 installer\GcodeProfiler.iss
; AppId must stay constant across all releases (do not regenerate).
;
; SELF-CONTAINED INSTALLER GUARANTEE:
;   - Inno Setup (ISCC.exe) is a BUILD-machine tool only. It is NOT bundled and
;     NOT required by end users.
;   - The compiled GcodeProfiler-Setup-<version>-x64.exe embeds the COMPLETE
;     PyInstaller --onedir output (which includes the Python runtime and Qt).
;     End users do NOT need Python, pip, PyInstaller, Inno Setup, the project
;     source, or an internet connection to install or run the application.
;   - This script must never download anything, run ISCC, invoke pip/python, or
;     compile source at INSTALL time. The only [Run] entry launches the app.
;   - Do not add ISCC.exe / Inno Setup files to [Files].

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "Gcode Profiler"
#define MyAppPublisher "Shusei Aida"
#define MyAppExeName "GcodeProfiler.exe"
#ifndef SourceDir
  #define SourceDir "..\dist\app\GcodeProfiler"
#endif

[Setup]
AppId={{B7E9F2A1-3C4D-4E5F-9A8B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Gcode Profiler
DefaultGroupName=Gcode Profiler
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=GcodeProfiler-Setup-{#MyAppVersion}-x64
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "gcodeassoc"; Description: "Register ""Open with Gcode Profiler"" for .gcode files"; GroupDescription: "File associations:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\THIRD_PARTY_LICENSES.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; ProgID for "Open with Gcode Profiler" (per-machine, optional task). Not a default-handler takeover.
Root: HKLM; Subkey: "Software\Classes\GcodeProfiler.GCode"; ValueType: string; ValueData: "G-code File"; Flags: uninsdeletekey; Tasks: gcodeassoc
Root: HKLM; Subkey: "Software\Classes\GcodeProfiler.GCode\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Tasks: gcodeassoc
Root: HKLM; Subkey: "Software\Classes\GcodeProfiler.GCode\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: gcodeassoc
Root: HKLM; Subkey: "Software\Classes\.gcode\OpenWithProgids"; ValueType: string; ValueName: "GcodeProfiler.GCode"; ValueData: ""; Flags: uninsdeletevalue; Tasks: gcodeassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; User data in %LOCALAPPDATA%\GcodeProfiler is intentionally NOT removed on uninstall.
