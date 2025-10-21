@echo off
chcp 65001 >nul
echo ╔════════════════════════════════════════╗
echo ║     II-Agent: Управление системой      ║
echo ╚════════════════════════════════════════╝
echo.
echo Выберите действие:
echo.
echo [1] Быстрый перезапуск (без пересборки)
echo [2] Пересборка бэкенда (после изменений кода)
echo [3] Полная пересборка (если что-то сломалось)
echo [4] Остановка
echo [5] Выход
echo.
set /p choice="Ваш выбор (1-5): "

cd /d E:\ii-agent\docker

if "%choice%"=="1" goto quick
if "%choice%"=="2" goto rebuild
if "%choice%"=="3" goto full
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto end

echo Неверный выбор!
timeout /t 2 >nul
goto end

:quick
echo.
echo ════════════════════════════════════════
echo   Быстрый перезапуск...
echo ════════════════════════════════════════
echo.
docker-compose restart
timeout /t 2 >nul
goto status

:rebuild
echo.
echo ════════════════════════════════════════
echo   Пересборка бэкенда...
echo ════════════════════════════════════════
echo.
echo [1/3] Остановка...
docker-compose down
echo.
echo [2/3] Пересборка...
docker-compose build backend
echo.
echo [3/3] Запуск...
docker-compose up -d
timeout /t 3 >nul
goto status

:full
echo.
echo ════════════════════════════════════════
echo   ПОЛНАЯ ПЕРЕСБОРКА
echo ════════════════════════════════════════
echo.
echo Это займёт несколько минут...
echo.
pause
echo [1/4] Остановка...
docker-compose down
echo.
echo [2/4] Очистка кэша...
docker-compose build --no-cache backend
echo.
echo [3/4] Пересборка всех контейнеров...
docker-compose build
echo.
echo [4/4] Запуск...
docker-compose up -d
timeout /t 3 >nul
goto status

:stop
echo.
echo ════════════════════════════════════════
echo   Остановка контейнеров...
echo ════════════════════════════════════════
echo.
docker-compose down
echo.
echo ✓ Контейнеры остановлены
echo.
pause
goto end

:status
echo.
echo ════════════════════════════════════════
echo   Статус контейнеров:
echo ════════════════════════════════════════
echo.
docker-compose ps
echo.
echo ════════════════════════════════════════
echo   ✓ Готово!
echo ════════════════════════════════════════
echo.
echo 🌐 Открой: http://localhost:3000
echo 📊 Статус: http://localhost:8000/health
echo 📝 Логи: docker-compose logs backend -f
echo.
pause
goto end

:end
