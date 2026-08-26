$ErrorActionPreference = 'Stop'
$env:CDYM_PORT = if ($env:CDYM_IA_PORT) { $env:CDYM_IA_PORT } else { '8001' }
& '..\.venv\Scripts\python.exe' manage.py runserver "127.0.0.1:$env:CDYM_PORT"
