# scripts/deploy.ps1

# Activamos el modo estricto para detectar errores simples antes.
Set-StrictMode -Version Latest

# Si un comando falla, el script se detiene.
$ErrorActionPreference = "Stop"

# Ruta del directorio donde está este script.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Ruta raíz del proyecto, subiendo un nivel desde /scripts.
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

function Write-Info {
    param (
        [string]$Message
    )

    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param (
        [string]$Message
    )

    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-ErrorMessage {
    param (
        [string]$Message
    )

    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Assert-CommandExists {
    param (
        [string]$CommandName
    )

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue

    if ($null -eq $command) {
        throw "No se ha encontrado el comando '$CommandName'. Revisa que esté instalado y disponible en el PATH."
    }
}

function Assert-FileExists {
    param (
        [string]$FilePath
    )

    if (-not (Test-Path $FilePath)) {
        throw "No se ha encontrado el archivo obligatorio: $FilePath"
    }
}

function Invoke-DockerCompose {
    param (
        [string[]]$Arguments
    )

    Write-Info "Ejecutando: docker $($Arguments -join ' ')"

    & docker @Arguments

    if ($LASTEXITCODE -ne 0) {
        throw "El comando docker $($Arguments -join ' ') ha fallado."
    }
}

function Wait-HttpEndpoint {
    param (
        [string]$Url,
        [int]$Retries = 10,
        [int]$SecondsBetweenRetries = 3
    )

    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            Write-Info "Comprobando endpoint $Url intento $attempt/$Retries"

            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5

            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Success "Endpoint disponible: $Url"
                return
            }
        }
        catch {
            Start-Sleep -Seconds $SecondsBetweenRetries
        }
    }

    throw "El endpoint $Url no responde después de $Retries intentos."
}

try {
    Write-Info "Iniciando despliegue local de Archivum."

    Set-Location $ProjectRoot

    Assert-CommandExists "docker"
    Assert-FileExists (Join-Path $ProjectRoot "docker-compose.yml")
    Assert-FileExists (Join-Path $ProjectRoot ".env.docker")

    Write-Info "Deteniendo contenedores anteriores si existen."
    Invoke-DockerCompose @("compose", "down")

    Write-Info "Construyendo y arrancando servicios."
    Invoke-DockerCompose @("compose", "up", "--build", "-d")

    Write-Info "Aplicando migraciones de base de datos con Alembic."
    Invoke-DockerCompose @("compose", "exec", "-T", "backend", "alembic", "upgrade", "head")

    Write-Info "Mostrando estado de los contenedores."
    Invoke-DockerCompose @("compose", "ps")

    Wait-HttpEndpoint "http://localhost:8000/docs"
    Wait-HttpEndpoint "http://localhost:8080"
    Wait-HttpEndpoint "http://localhost:9090"

    Write-Success "Despliegue completado correctamente."
    Write-Info "Backend Swagger: http://localhost:8000/docs"
    Write-Info "Frontend: http://localhost:8080"
    Write-Info "Prometheus: http://localhost:9090"
}
catch {
    Write-ErrorMessage $_.Exception.Message
    Write-ErrorMessage "El despliegue no se ha completado. Revisa los mensajes anteriores, porque Docker no lee mentes todavía."
    exit 1
}