; ============================================================================
;  Inno Setup - Contador de Tokens (Claude)
;  Instalador com assistente, entrada em "Programas e Recursos", desinstalador
;  registrado e instalacao automatica do runtime do WebView2 se faltar.
;
;  Como compilar:
;    1. Instale o Inno Setup 6 (https://jrsoftware.org/isdl.php)  [fora de rede corporativa]
;    2. Abra este app.iss no Inno Setup e clique em "Compile" (ou rode ISCC app.iss)
;    3. O instalador sai como "Instalador Contador de Tokens (Inno).exe" nesta pasta.
;
;  Arquivos necessarios nesta pasta (ja copiados):
;    - Contador de Tokens.exe
;    - MicrosoftEdgeWebview2Setup.exe
;    - claude.ico
; ============================================================================

#define AppName    "Contador de Tokens"
#define AppVersion "4.0"
#define AppPublisher "David Rufino"
#define AppExe     "Contador de Tokens.exe"
#define WV2Setup   "MicrosoftEdgeWebview2Setup.exe"

[Setup]
AppId={{7B3F0C9A-1E4D-4C2A-9B6E-A1B2C3D4E5F6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=.
OutputBaseFilename=Instalador Contador de Tokens (Inno)
SetupIconFile=claude.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "startupicon"; Description: "Iniciar o {#AppName} junto com o Windows"; GroupDescription: "Inicializacao:"
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; Flags: unchecked

[Files]
Source: "{#AppExe}";  DestDir: "{app}"; Flags: ignoreversion
Source: "{#WV2Setup}"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: startupicon

[Run]
; Instala o WebView2 apenas se o runtime nao estiver presente.
Filename: "{tmp}\{#WV2Setup}"; Parameters: "/silent /install"; \
    StatusMsg: "Instalando o runtime do WebView2..."; \
    Check: NeedsWebView2; Flags: waituntilterminated
; Abre o app ao final (a menos que instalacao silenciosa).
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed: Boolean;
var
  g: string;
begin
  g := '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result :=
    RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + g) or
    RegKeyExists(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + g) or
    RegKeyExists(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + g);
end;

function NeedsWebView2: Boolean;
begin
  Result := not WebView2Installed;
end;
