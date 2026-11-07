; Inno-Setup-Installer für Windows: dist\Vorleser\ → dist\Vorleser-<Version>-windows-setup.exe
; Installiert ohne Administratorrechte nach %LOCALAPPDATA%\Programs\Vorleser.
; Aufruf:  iscc /DAppVersion=2.0.0 packaging\vorleser.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E1B7C52-4D0A-4C1E-9F43-7A8C2B9D0E11}
AppName=Vorleser
AppVersion={#AppVersion}
AppPublisher=Simon Schnetzer
AppPublisherURL=https://github.com/SimonSchneZzer
AppCopyright=© 2026 Simon Schnetzer
VersionInfoCompany=Simon Schnetzer
VersionInfoCopyright=© 2026 Simon Schnetzer
DefaultDirName={autopf}\Vorleser
DefaultGroupName=Vorleser
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Vorleser-{#AppVersion}-windows-setup
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\Vorleser.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Vorleser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Vorleser"; Filename: "{app}\Vorleser.exe"
Name: "{autodesktop}\Vorleser"; Filename: "{app}\Vorleser.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Vorleser.exe"; Description: "{cm:LaunchProgram,Vorleser}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
de.DeleteData=Sollen auch deine Texte, eigenen Stimmen, Modelle und Einstellungen gelöscht werden?%n%nDas lässt sich nicht rückgängig machen.
en.DeleteData=Also delete your texts, own voices, models and settings?%n%nThis cannot be undone.

[Code]
// Deinstallation über Windows „Apps“: nachfragen, ob die persönlichen Daten mit gelöscht werden.
// Aus der App heraus läuft der Uninstaller still – dann löscht der App-Helfer die Daten selbst.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    if MsgBox(CustomMessage('DeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\Vorleser'), True, True, True);
end;
