@echo off
setlocal EnableDelayedExpansion

:: Script para eliminar archivos y carpetas temporales con "temp_profile" en el nombre
:: Ruta: %USERPROFILE%\AppData\Local\Temp

echo ========================================
echo  Limpieza de archivos temporales
echo  Patron: *temp_profile*
echo ========================================
echo.

:: Obtener la ruta del directorio temporal del usuario actual
set "TEMP_DIR=%USERPROFILE%\AppData\Local\Temp"

:: Verificar que el directorio existe
if not exist "%TEMP_DIR%" (
    echo ERROR: El directorio %TEMP_DIR% no existe.
    pause
    exit /b 1
)

echo Directorio objetivo: %TEMP_DIR%
echo.

:: Buscar y mostrar archivos que contienen "temp_profile" en el nombre
echo Buscando archivos y carpetas con "temp_profile" en el nombre...
echo.

set "FOUND_ITEMS=0"

:: Buscar archivos
for /f "delims=" %%i in ('dir "%TEMP_DIR%\*temp_profile*" /b /a 2^>nul') do (
    set /a FOUND_ITEMS+=1
    echo [ARCHIVO] %%i
)

:: Buscar directorios
for /f "delims=" %%i in ('dir "%TEMP_DIR%\*temp_profile*" /b /ad 2^>nul') do (
    set /a FOUND_ITEMS+=1
    echo [CARPETA] %%i
)

if !FOUND_ITEMS! equ 0 (
    echo No se encontraron archivos o carpetas con "temp_profile" en el nombre.
    echo.
    pause
    exit /b 0
)

echo.
echo Se encontraron !FOUND_ITEMS! elementos para eliminar.
echo.

:: Confirmación del usuario
set /p "CONFIRM=¿Desea continuar con la eliminación? (S/N): "
if /i not "%CONFIRM%"=="S" (
    echo Operación cancelada por el usuario.
    pause
    exit /b 0
)

echo.
echo Iniciando eliminación...
echo.

set "DELETED_COUNT=0"
set "ERROR_COUNT=0"

:: Eliminar archivos
for /f "delims=" %%i in ('dir "%TEMP_DIR%\*temp_profile*" /b /a-d 2^>nul') do (
    echo Eliminando archivo: %%i
    del /f /q "%TEMP_DIR%\%%i" 2>nul
    if !errorlevel! equ 0 (
        set /a DELETED_COUNT+=1
        echo   ^> Eliminado correctamente
    ) else (
        set /a ERROR_COUNT+=1
        echo   ^> ERROR: No se pudo eliminar
    )
)

:: Eliminar directorios
for /f "delims=" %%i in ('dir "%TEMP_DIR%\*temp_profile*" /b /ad 2^>nul') do (
    echo Eliminando carpeta: %%i
    rmdir /s /q "%TEMP_DIR%\%%i" 2>nul
    if !errorlevel! equ 0 (
        set /a DELETED_COUNT+=1
        echo   ^> Eliminado correctamente
    ) else (
        set /a ERROR_COUNT+=1
        echo   ^> ERROR: No se pudo eliminar ^(puede estar en uso^)
    )
)

echo.
echo ========================================
echo  Resumen de la operación
echo ========================================
echo Elementos eliminados correctamente: !DELETED_COUNT!
echo Elementos con errores: !ERROR_COUNT!
echo.

if !ERROR_COUNT! gtr 0 (
    echo NOTA: Algunos archivos no se pudieron eliminar.
    echo Esto puede deberse a que están siendo utilizados por otros procesos.
    echo Intente cerrar las aplicaciones y ejecutar el script nuevamente.
)

echo.
echo Operación completada.
pause
