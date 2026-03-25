@echo off
REM ============================================================================
REM Setup script for RedTrust Automation
REM This script will clone the repository, set up the environment, and install dependencies
REM ============================================================================

echo.
echo ============================================================================
echo           REDTRUST AUTOMATION SETUP SCRIPT
echo ============================================================================
echo.
echo This script will:
echo 1. Check and install Git (if needed)
echo 2. Check and install Python (if needed)
echo 3. Install RedTrust Agent
echo 4. Navigate to workspace directory
echo 5. Clone the RedTrust Automation repository
echo 6. Set up Python virtual environment
echo 7. Install dependencies
echo 8. Copy required Chrome and ChromeDriver files
echo 9. Copy .env configuration file
echo 10. Start the worker
echo.

pause

REM Step 1: Check Git installation with 3 retries
echo.
echo [1/10] Checking Git installation...
setlocal enabledelayedexpansion
set "max_retries=3"
set "GIT_RETRIES=0"
:check_git
git --version >nul 2>&1
if %errorlevel% equ 0 (
    git --version
    echo SUCCESS: Git is already installed
    endlocal
    goto after_git_check
) else (
    set /a GIT_RETRIES+=1
    if !GIT_RETRIES! gtr !max_retries! (
        echo ERROR: Git is not installed after !max_retries! attempts. Please install manually and rerun this script.
        pause
        endlocal
        exit /b 1
    )
    echo WARNING: Git is not installed or not found in PATH (Attempt !GIT_RETRIES! of !max_retries!)
    echo Looking for Git installer in Downloads folder...
    set "GIT_INSTALLER="
    for %%f in ("%USERPROFILE%\Downloads\Git-*-64-bit.exe") do set "GIT_INSTALLER=%%f"
    if defined GIT_INSTALLER (
        if exist "!GIT_INSTALLER!" (
            echo Found Git installer: !GIT_INSTALLER!
            echo Starting silent Git installation...
            "!GIT_INSTALLER!" /VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES
            echo Waiting for Git installation to complete...
            timeout /t 15 /nobreak >nul
            echo.
            echo Git installation completed. Checking again...
            set "PATH=%PATH%;%ProgramFiles%\Git\cmd"
        )
    ) else (
        echo Git installer not found in Downloads folder.
        echo Please download Git from: https://github.com/git-for-windows/git/releases/download/v2.51.0.windows.2/Git-2.51.0.2-64-bit.exe
        echo Save it to your Downloads folder and run this script again.
        echo Opening download page in browser...
        start https://github.com/git-for-windows/git/releases/download/v2.51.0.windows.2/Git-2.51.0.2-64-bit.exe
        echo After downloading, please run this script again.
        pause
        endlocal
        exit /b 1
    )
    goto check_git
)
:after_git_check

REM Step 2: Check Python installation with 3 retries
echo.
echo [2/10] Checking Python installation...
setlocal enabledelayedexpansion
set "max_retries=3"
set "PYTHON_RETRIES=0"
:check_python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python --version
    echo SUCCESS: Python is already installed
    endlocal
    goto after_python_check
) else (
    set /a PYTHON_RETRIES+=1
    if !PYTHON_RETRIES! gtr !max_retries! (
        echo ERROR: Python is not installed after !max_retries! attempts. Please install manually and rerun this script.
        pause
        endlocal
        exit /b 1
    )
    echo WARNING: Python is not installed or not found in PATH (Attempt !PYTHON_RETRIES! of !max_retries!)
    echo Looking for Python installer in Downloads folder...
    set "PYTHON_INSTALLER="
    for %%f in ("%USERPROFILE%\Downloads\python-*-amd64.exe") do set "PYTHON_INSTALLER=%%f"
    if defined PYTHON_INSTALLER (
        if exist "!PYTHON_INSTALLER!" (
            echo Found Python installer: !PYTHON_INSTALLER!
            echo Starting silent Python installation...
            "!PYTHON_INSTALLER!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
            echo Waiting for Python installation to complete...
            timeout /t 20 /nobreak >nul
            echo.
            echo Python installation completed. Checking again...
            set "PATH=%PATH%;%ProgramFiles%\Python313\Scripts;%ProgramFiles%\Python313"
        )
    ) else (
        echo Python installer not found in Downloads folder.
        echo Please download Python from: https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe
        echo Save it to your Downloads folder and run this script again.
        echo Opening download page in browser...
        start https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe
        echo After downloading, please run this script again.
        pause
        endlocal
        exit /b 1
    )

REM Step 3: Install RedTrust Agent
echo.
echo [3/10] Installing RedTrust Agent...
set "REDTRUST_MSI=\\Server-doc\escaneado-mariela\Instalaciones\rt-agent-3.61.2-generic-LocalUsers\rt-agent-x64-3.61.2-93614707-MS-WO.msi"
if exist "!REDTRUST_MSI!" (
    echo Found RedTrust installer: !REDTRUST_MSI!
    echo Starting silent RedTrust installation...
    msiexec /i "!REDTRUST_MSI!" /quiet /norestart
    echo Waiting for RedTrust installation to complete...
    timeout /t 20 /nobreak >nul
    echo SUCCESS: RedTrust Agent installed (if no errors above)
) else (
    echo WARNING: RedTrust installer not found at: !REDTRUST_MSI!
    echo Please ensure the installer is available and try again.
    pause
)
    goto check_python
)
:after_python_check

REM Step 4: Navigate to workspace directory
echo.
echo [4/10] Navigating to workspace directory...
if not exist "%USERPROFILE%\Documents\workspace" (
    echo INFO: Workspace directory does not exist. Creating...
    mkdir "%USERPROFILE%\Documents\workspace"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create workspace directory
        pause
        exit /b 1
    )
)
cd /d "%USERPROFILE%\Documents\workspace"
if %errorlevel% neq 0 (
    echo ERROR: Could not navigate to workspace directory
    echo Please make sure the directory exists: %USERPROFILE%\Documents\workspace
    pause
    exit /b 1
)
echo SUCCESS: Currently in %CD%

REM Step 5: Clone repository
echo.
echo [5/10] Cloning RedTrust Automation repository...
if exist "redtrust-automation" (
    echo WARNING: redtrust-automation directory already exists
    echo Skipping clone step...
) else (
    git clone https://<TOKEN>@github.com/adrimm6661604086/redtrust-automation.git
    echo Waiting for repository to be cloned...
    timeout /t 60 /nobreak >nul
    if %errorlevel% neq 0 (
        echo ERROR: Failed to clone repository
        echo Please check your internet connection and Git credentials
        pause
        exit /b 1
    )
    echo SUCCESS: Repository cloned successfully
)

REM Step 6: Navigate to project directory
echo.
echo [6/10] Entering project directory...
cd redtrust-automation
if %errorlevel% neq 0 (
    echo ERROR: Could not navigate to redtrust-automation directory
    pause
    exit /b 1
)
echo SUCCESS: Currently in %CD%

REM Step 7: Configure Git credentials
echo.
echo [7/10] Configuring Git credentials...
git config --global credential.helper store
git checkout master
git pull origin master
echo Waiting for git pull to complete...
timeout /t 8 /nobreak >nul
if %errorlevel% neq 0 (
    echo WARNING: Could not pull latest changes from master branch
    echo Continuing with existing code...
)

REM Step 8: Create Python virtual environment and install dependencies
echo.
echo [8/10] Creating Python virtual environment and installing dependencies...
if exist ".venv" (
    echo INFO: Virtual environment already exists
) else (
    python -m venv .venv
    echo Waiting for virtual environment creation...
    timeout /t 30 /nobreak >nul
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Please make sure Python is installed and available in PATH
        pause
        exit /b 1
    )
    echo SUCCESS: Virtual environment created
)

call .\.venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

pip install -r requirements.txt
echo Waiting for dependencies installation...
timeout /t 30 /nobreak >nul
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo SUCCESS: Dependencies installed successfully

REM Step 9: Copy ChromeDriver and Chrome browser files
echo.
echo [9/10] Copying ChromeDriver and Chrome browser files...
set "SOURCE_CHROMEDRIVER=\\192.168.184.162\c$\Users\Adria Martinez\Documents\workspace\redtrust-automation\app\utils\chromedriver-win64-126.zip"
set "DEST_CHROMEDRIVER=.\app\utils\chromedriver-win64-126.zip"

if exist "%SOURCE_CHROMEDRIVER%" (
    copy "%SOURCE_CHROMEDRIVER%" "%DEST_CHROMEDRIVER%"
    if %errorlevel% equ 0 (
        echo SUCCESS: ChromeDriver copied successfully
        echo Extracting ChromeDriver...
        powershell -command "Expand-Archive -Path '%DEST_CHROMEDRIVER%' -DestinationPath '.\app\utils\' -Force"
        if %errorlevel% equ 0 (
            echo SUCCESS: ChromeDriver extracted successfully
        ) else (
            echo WARNING: Failed to extract ChromeDriver automatically
            echo Please extract manually: %DEST_CHROMEDRIVER%
        )
    ) else (
        echo WARNING: Failed to copy ChromeDriver from network location
        echo Please copy manually: %SOURCE_CHROMEDRIVER% to %DEST_CHROMEDRIVER%
    )
) else (
    echo WARNING: ChromeDriver source not found at: %SOURCE_CHROMEDRIVER%
    echo Please copy the ChromeDriver manually to: %DEST_CHROMEDRIVER%
)

set "SOURCE_CHROME=\\192.168.184.162\c$\Users\Adria Martinez\AppData\Local\Google\chrome-win64-126.zip"
set "DEST_CHROME=%USERPROFILE%\AppData\Local\Google\chrome-win64-126.zip"

if exist "%SOURCE_CHROME%" (
    if not exist "%USERPROFILE%\AppData\Local\Google" mkdir "%USERPROFILE%\AppData\Local\Google"
    copy "%SOURCE_CHROME%" "%DEST_CHROME%"
    if %errorlevel% equ 0 (
        echo SUCCESS: Chrome browser copied successfully
        echo Extracting Chrome browser...
        powershell -command "Expand-Archive -Path '%DEST_CHROME%' -DestinationPath '%USERPROFILE%\AppData\Local\Google\' -Force"
        if %errorlevel% equ 0 (
            echo SUCCESS: Chrome browser extracted successfully
        ) else (
            echo WARNING: Failed to extract Chrome browser automatically
            echo Please extract manually: %DEST_CHROME%
        )
    ) else (
        echo WARNING: Failed to copy Chrome browser from network location
        echo Please copy manually: %SOURCE_CHROME% to %DEST_CHROME%
    )
) else (
    echo WARNING: Chrome browser source not found at: %SOURCE_CHROME%
    echo Please copy the Chrome browser manually to: %DEST_CHROME%
)

REM Step 10: Copy .env file
echo.
echo [10/10] Copying .env configuration file...
set "SOURCE_ENV=\\192.168.184.162\c$\Users\Adria Martinez\Documents\workspace\redtrust-automation\.env"
set "DEST_ENV=.\.env"

if exist "%SOURCE_ENV%" (
    copy "%SOURCE_ENV%" "%DEST_ENV%" /Y
    if %errorlevel% equ 0 (
        echo SUCCESS: .env file copied successfully
    ) else (
        echo WARNING: Failed to copy .env file automatically
        echo Please copy manually: %SOURCE_ENV% to %DEST_ENV%
    )
) else (
    echo WARNING: .env source not found at: %SOURCE_ENV%
    echo Please copy the .env file manually to: %DEST_ENV%
)

REM Final step: Start worker
echo.
echo ============================================================================
echo SETUP COMPLETED SUCCESSFULLY!
echo ============================================================================
echo.
echo The setup is complete. The worker will now start.
echo Press any key to start the worker, or close this window to exit.
pause

echo.
echo Starting worker...
call .\app\api\start_worker.bat

echo.
echo Worker has stopped or encountered an error.
echo Check the logs for more information.
pause
