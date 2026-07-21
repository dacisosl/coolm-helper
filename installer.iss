; ── 쿨메신저 일정 도우미 설치파일 (Inno Setup 6) ──────────────
; 사용법: build.bat 실행 후, Inno Setup Compiler로 이 파일을 열어 컴파일.
; 결과: Output\CoolmHelper-Setup.exe

#define AppName "쿨메신저 일정 도우미"
#define AppVersion "0.16.0"
#define AppExe "CoolmHelper.exe"

[Setup]
AppId={{8E1A4C51-53B0-4F2E-9C58-coolmhelper1}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\CoolmHelper
DefaultGroupName={#AppName}
OutputBaseFilename=CoolmHelper-Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=assets\app.ico
; 사용자별 데이터(config, store)는 설치 폴더가 아니라 실행 시 exe 옆에 생성됨
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[InstallDelete]
; 업데이트 설치 전에 옛 프로그램 부품을 깨끗이 지운다 — 파이썬 버전이
; 다른 빌드가 겹쳐 "python3xx.dll conflicts" 오류가 나는 것을 방지.
; 사용자 데이터(store, config.json, students.txt)는 건드리지 않는다.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\python*.dll"
Type: files; Name: "{app}\*.pyd"

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
Source: "dist\CoolmHelper\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면 아이콘 만들기"; GroupDescription: "추가 작업:"

[Run]
Filename: "{app}\개인정보고지.md"; Description: "개인정보 처리 안내 읽기"; \
  Flags: postinstall shellexec skipifsilent unchecked
; skipifsilent 없음 — 자동 업데이트(/SILENT 설치) 후에도 앱이 다시 실행되게 한다
Filename: "{app}\{#AppExe}"; Description: "지금 실행"; Flags: postinstall nowait
