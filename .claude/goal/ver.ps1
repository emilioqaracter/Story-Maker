# Muestra que esta haciendo el Claude del vigilante: si esta vivo y sus ultimas acciones.
$vivo = Get-CimInstance Win32_Process -Filter "Name='claude.exe'" | Where-Object CommandLine -match 'Reanuda|/goal'
if ($vivo) { "Trabajando (proceso $($vivo.ProcessId))" } else { "No hay ninguna ronda en marcha: mira vigilante.log" }
""
$dir = Join-Path $env:USERPROFILE '.claude\projects\c--Users-emili-OneDrive-Escritorio-Story-Maker'
$f = Get-ChildItem $dir -Filter *.jsonl | Where-Object { Select-String -Path $_.FullName -Pattern '"entrypoint":"sdk-cli"' -Quiet } |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
"Ultima actividad: $($f.LastWriteTime)"
""
Get-Content $f.FullName -Encoding UTF8 -Tail 200 | ForEach-Object {
    try { $j = $_ | ConvertFrom-Json } catch { return }
    if (-not $j.timestamp) { return }
    $hora = ([datetime]$j.timestamp).ToLocalTime().ToString('HH:mm')
    foreach ($c in @($j.message.content)) {
        if ($c.type -eq 'tool_use') {
            $que = @($c.input.description, $c.input.file_path, $c.input.command) | Where-Object { $_ } | Select-Object -First 1
            "$hora  $($c.name): $que"
        } elseif ($c.type -eq 'text' -and $j.type -eq 'assistant') {
            "$hora  >> $($c.text.Substring(0, [Math]::Min(200, $c.text.Length)))"
        }
    }
} | Select-Object -Last 15
