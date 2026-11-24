$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$main = Join-Path $root "preview.html"
if (!(Test-Path -LiteralPath $main)) { throw "preview.html non trovato nella cartella del progetto." }
Start-Process -FilePath $main
