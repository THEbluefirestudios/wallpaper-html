@echo off
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
python -m PyInstaller --noconfirm --clean --noconsole --onedir ^
 --name "Wallpaper.HTML" ^
 --icon "internal\icon.ico" ^
 --collect-all webview ^
 --collect-all sv_ttk ^
 --collect-all pythonnet ^
 --collect-all clr_loader ^
 --hidden-import pystray._win32 ^
 --hidden-import pynput.mouse._win32 ^
 --hidden-import pynput.keyboard._win32 ^
 --hidden-import pywinstyles ^
 --hidden-import win32timezone ^
 wallpaper.html.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)
robocopy "internal" "dist\Wallpaper.HTML\internal" /E /XF settings.json wallpaper_ready
robocopy "wallpapers" "dist\Wallpaper.HTML\wallpapers" /E
echo Done: dist\Wallpaper.HTML\Wallpaper.HTML.exe
pause