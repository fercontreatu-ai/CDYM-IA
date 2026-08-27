$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$requirementsStamp = Join-Path $PSScriptRoot '.venv\requirements.sha256'
$env:CDYM_PORT = if ($env:CDYM_IA_PORT) { $env:CDYM_IA_PORT } else { '8001' }

function Update-ProjectFromGit {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.git'))) {
        return
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host 'Git no está disponible; se iniciará la versión local.' -ForegroundColor Yellow
        return
    }

    Write-Host 'Buscando actualizaciones del proyecto...' -ForegroundColor Cyan
    & git fetch --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'No fue posible consultar el repositorio. Se iniciará la versión local.' -ForegroundColor Yellow
        return
    }

    $upstream = (& git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $upstream) {
        Write-Host 'La rama actual no tiene una rama remota asociada; se iniciará la versión local.' -ForegroundColor Yellow
        return
    }

    $pendientes = [int](& git rev-list --count "HEAD..$upstream")
    if ($LASTEXITCODE -ne 0 -or $pendientes -le 0) {
        Write-Host 'El proyecto está actualizado.' -ForegroundColor Green
        return
    }

    Write-Host "Hay una nueva versión disponible ($pendientes cambio(s) pendiente(s))." -ForegroundColor Yellow
    $respuesta = Read-Host '¿Desea actualizar ahora? [S/N]'
    if ($respuesta.Trim().ToUpperInvariant() -notin @('S', 'SI', 'SÍ', 'Y', 'YES')) {
        Write-Host 'Se iniciará la versión local sin actualizar.' -ForegroundColor Yellow
        return
    }

    & git pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        throw 'No fue posible actualizar. Revise si existen cambios locales que entren en conflicto con el repositorio.'
    }

    Write-Host 'Actualización terminada. Reiniciando el lanzador...' -ForegroundColor Green
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath
    exit $LASTEXITCODE
}

function Invoke-SystemPython {
    param([string[]]$Arguments)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Arguments
    }
    else {
        throw 'Python no está instalado o no está disponible en PATH. Instale Python 3 y marque la opción "Add Python to PATH".'
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python terminó con código de error $LASTEXITCODE."
    }
}

try {
    Update-ProjectFromGit

    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host 'Creando el entorno virtual .venv...' -ForegroundColor Cyan
        Invoke-SystemPython -Arguments @('-m', 'venv', '.venv')
    }

    $hashActual = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $hashInstalado = if (Test-Path -LiteralPath $requirementsStamp) {
        (Get-Content -LiteralPath $requirementsStamp -Raw).Trim()
    } else { '' }

    if ($hashActual -ne $hashInstalado) {
        Write-Host 'Instalando dependencias del proyecto...' -ForegroundColor Cyan
        & $venvPython -m pip install -r $requirements
        if ($LASTEXITCODE -ne 0) {
            throw "No fue posible instalar las dependencias (código $LASTEXITCODE). Verifique la conexión a Internet."
        }
        Set-Content -LiteralPath $requirementsStamp -Value $hashActual -Encoding ASCII
    }
    else {
        Write-Host 'Dependencias verificadas.' -ForegroundColor Green
    }

    Write-Host 'Verificando la base de datos...' -ForegroundColor Cyan
    & $venvPython manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        throw "No fue posible aplicar las migraciones (código $LASTEXITCODE)."
    }

    $url = "http://127.0.0.1:$env:CDYM_PORT"
    Write-Host "Iniciando CDYM en $url" -ForegroundColor Green
    Write-Host 'Para detenerlo, cierre esta ventana o presione Ctrl+C.'
    & $venvPython manage.py runserver "127.0.0.1:$env:CDYM_PORT" --noreload
}
catch {
    Write-Host ''
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Presione Enter para cerrar.'
    Read-Host | Out-Null
    exit 1
}
