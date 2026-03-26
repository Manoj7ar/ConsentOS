$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"

if (Test-Path $venvPython) {
  & $venvPython (Join-Path $scriptDir "bootstrap_env.py") @args
  exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
  & py (Join-Path $scriptDir "bootstrap_env.py") @args
  exit $LASTEXITCODE
}

& python (Join-Path $scriptDir "bootstrap_env.py") @args
exit $LASTEXITCODE
