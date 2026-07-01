@echo off
echo Ruhusu BiyeMu kwenye port 5000 (inahitaji Admin)...
netsh advfirewall firewall delete rule name="BiyeMu Dev" >nul 2>&1
netsh advfirewall firewall add rule name="BiyeMu Dev" dir=in action=allow protocol=TCP localport=5000
if %errorlevel%==0 (
  echo Firewall imeruhusu port 5000.
) else (
  echo Imeshindwa. Bofya panya-kulia faili hii ^> Run as administrator
)
pause