; 学生积分管理 - 安装器 v1.2.0 (Inno Setup 6 脚本)
; 编译: ISCC.exe student_score.iss
; 功能: 1) 自动安装 Git(数据同步用,exe 已自带 Python 运行环境,无需装 Python)
;       2) 可自由选择安装路径(默认向导中文界面)
;       3) 部署打包好的 学生积分管理.exe
;       4) 创建开始菜单/桌面快捷方式
;       5) 从内置远程仓库克隆数据(https://github.com/linbufan-create/student-score)

#define MyAppName "学生积分管理"
#define MyAppVersion "1.2.0"
#define MyAppExeName "学生积分管理.exe"
#define MyAppId "8F3A2C4D-9B6E-4A11-B2D0-5C7E9F1A3D55"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=本地班级工具
; 默认安装目录,安装时用户可自由更改(下方"选择安装位置"页面)
DefaultDirName={localappdata}\StudentScoreManager
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..
OutputBaseFilename=学生积分管理-安装程序-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=no
RestartApplications=no
; 不允许装到可能被git误提交的旧版本残留,如已存在同版本直接覆盖
UsePreviousAppDir=yes

[Languages]
; 官方Inno Setup不含简中语言包,改用下方 [Messages] 覆写核心界面为中文

[Messages]
WelcomeLabel1=欢迎使用 %1 安装向导
WelcomeLabel2=本向导会把学生积分管理系统安装到你的电脑。学生数据统一存放在内置的 GitHub 远程仓库(https://github.com/linbufan-create/student-score),安装后每次运行都会自动同步。
SelectDirTitle=选择安装位置
SelectDirDesc=请选择把 %1 安装到哪个文件夹。
SelectDirLabel3=安装程序将把 %1 安装到以下文件夹:
SelectDirBrowseLabel=点击"下一步"继续。如需更改安装位置,请先点击"浏览"。
BrowseLabel=浏览(&B)...
SelectTasksTitle=选择附加任务
SelectTasksDesc=还需要执行哪些附加任务?
SelectTasksLabel2=请选择安装 %1 时要执行的附加任务,然后点击"下一步"。
ReadyLabel1=准备安装
ReadyLabel2=安装程序已准备好开始在你的电脑上安装 %1。
ReadyMemoStart=将应用以下设置:
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonCancel=取消
ButtonFinish=完成(&F)
InstallingLabel=正在安装 %1,请稍候...
FinishedHeadingLabel=正在完成 %1 安装向导
FinishedLabel=点击"完成"按钮退出安装向导。
; [Messages] 覆写结束

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent unchecked

[Code]
const
  WingetGit = 'Git.Git';
  DefaultRemoteUrl = 'https://github.com/linbufan-create/student-score';

{ ---------- 环境检测与自动安装(Git,exe已自带Python无需装) ---------- }
function GitWorks: Boolean;
var
  ResultCode: Integer;
begin
  Result := ExecAsOriginalUser('cmd.exe',
      '/c ""git" --version >nul 2>&1"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
      and (ResultCode = 0);
end;

procedure RunWinget(Id: String);
var
  ResultCode: Integer;
begin
  ExecAsOriginalUser('winget.exe',
    'install --exact --id ' + Id +
    ' --silent --accept-package-agreements --accept-source-agreements --disable-interactivity',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    { 第一步:检查并自动安装 Git }
    WizardForm.StatusLabel.Caption := '正在检查运行环境 (Git)...';
    if not GitWorks then
    begin
      WizardForm.StatusLabel.Caption := '正在自动安装 Git,请稍候...';
      RunWinget(WingetGit);
    end;
    { 第二步:从内置远程仓库克隆学生数据 }
    WizardForm.StatusLabel.Caption := '正在从内置远程仓库克隆学生数据...';
    SaveStringToFile(ExpandConstant('{tmp}\ssm_setup_repo.bat'),
      '@echo off' + #13#10 +
      'setlocal' + #13#10 +
      'set "APP=%~1"' + #13#10 +
      'set "URL=%~2"' + #13#10 +
      'set "TMPCL=%TEMP%\ssm_clone_tmp"' + #13#10 +
      'if exist "%TMPCL%" rmdir /s /q "%TMPCL%"' + #13#10 +
      'git clone "%URL%" "%TMPCL%" >nul 2>&1' + #13#10 +
      'if errorlevel 1 exit /b 1' + #13#10 +
      'robocopy "%TMPCL%\.git" "%APP%\.git" /E /NFL /NDL /NJH /NJS >nul' + #13#10 +
      'if errorlevel 8 exit /b 2' + #13#10 +
      'if exist "%APP%\*.json" del /q "%APP%\*.json"' + #13#10 +
      'robocopy "%TMPCL%" "%APP%" /E /XF *.py *.bat *.exe /NFL /NDL /NJH /NJS >nul' + #13#10 +
      'if errorlevel 8 exit /b 2' + #13#10 +
      'git -C "%APP%" config user.name "ScoreBot" >nul 2>&1' + #13#10 +
      'git -C "%APP%" config user.email "scorebot@local" >nul 2>&1' + #13#10 +
      'rmdir /s /q "%TMPCL%" 2>nul' + #13#10 +
      'exit /b 0' + #13#10,
      True);

    if ExecAsOriginalUser(ExpandConstant('{tmp}\ssm_setup_repo.bat'),
        AddQuotes(ExpandConstant('{app}')) + ' ' + AddQuotes(DefaultRemoteUrl),
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
       and (ResultCode = 0) then
      MsgBox('已从远程仓库克隆最新数据到本机,之后每次运行程序都会自动同步。',
        mbInformation, MB_OK)
    else
      MsgBox('从远程仓库克隆失败(错误码 ' + IntToStr(ResultCode) + ')。' +
        '请检查网络连接后重试;程序首次运行时也会自动用内置地址重试同步。',
        mbError, MB_OK);
  end;
end;
