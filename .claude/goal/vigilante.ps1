# Relanza Claude cada 20 min si se queda sin creditos, hasta que exista .claude/goal/HECHO.
# Solo ASCII en este fichero: PowerShell 5.1 lee los .ps1 sin BOM como ANSI.
$raiz     = 'C:\Users\emili\OneDrive\Escritorio\Story-Maker'
$dir      = Join-Path $raiz '.claude\goal'
$hecho    = Join-Path $dir 'HECHO'
$estado   = Join-Path $dir 'ESTADO.md'
$log      = Join-Path $dir 'vigilante.log'
$espera   = 20 * 60
$patron   = 'usage limit|limit reached|rate.?limit|credit balance|out of credits|overloaded|sin cr.ditos'
# Errores que no se arreglan esperando: el vigilante para y lo dice.
$fatal    = 'Goal condition is limited|not recognized|no se reconoce|Invalid API key|Please run /login'
# /goal admite como maximo 4.000 caracteres: la condicion va corta y las instrucciones en OBJETIVO.md.
$objetivo = '/goal Se cumplen a la vez las cuatro condiciones de parada de .claude/goal/OBJETIVO.md (filtros restaurados, auditoria sin ningun ENT en rojo, amarillo ni naranja, backend y frontend en marcha, y las novelas prueba, corta y breve cerradas en modo estricto por escalera) y existe el fichero .claude/goal/HECHO. Antes de hacer nada, lee .claude/goal/OBJETIVO.md entero: son tus instrucciones y reglas, y las sigues al pie de la letra.'
$reanudar = 'Reanuda el objetivo. Lee .claude/goal/OBJETIVO.md, ESTADO.md e INTENTOS.md y sigue desde el ultimo paso registrado. Comprueba que backend y frontend responden. Si una tirada quedo a medias, reanudala desde su ultimo capitulo congelado. Cuando se cumplan todas las condiciones de parada, crea .claude/goal/HECHO.'

Set-Location $raiz
while (-not (Test-Path $hecho)) {
    $inicio = Get-Date
    if (-not (Test-Path $estado)) {
        $salida = claude -p $objetivo --permission-mode auto 2>&1 | Out-String
    } else {
        $salida = claude --continue -p $reanudar --permission-mode auto 2>&1 | Out-String
    }
    $codigo = $LASTEXITCODE
    $cola = $salida.Substring([Math]::Max(0, $salida.Length - 2000))
    Add-Content $log "[$inicio] codigo=$codigo`n$cola`n"
    if ($salida -match $fatal) {
        Add-Content $log "[$(Get-Date)] Error que no se arregla esperando: el vigilante para. Corrigelo y vuelve a lanzarlo.`n"
        exit 1
    }
    if ($salida -match $patron -or $codigo -ne 0) {
        Add-Content $log "[$(Get-Date)] Sin creditos o error: reintento en 20 min.`n"
        Start-Sleep -Seconds $espera
    } else {
        Start-Sleep -Seconds 60
    }
}
Add-Content $log "[$(Get-Date)] Objetivo cumplido: existe HECHO."
