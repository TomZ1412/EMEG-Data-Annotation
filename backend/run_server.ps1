$ErrorActionPreference = "Stop"

$env:HOST = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$env:PORT = if ($env:PORT) { $env:PORT } else { "10000" }
$env:ANNO_PROFILE = if ($env:ANNO_PROFILE) { $env:ANNO_PROFILE } else { "not_used" }

python -m uvicorn main:app --host $env:HOST --port $env:PORT
