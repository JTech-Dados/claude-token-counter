# Diagnostico do token do Claude — NAO expoe o token, so o formato/estado.
# Roda em PowerShell puro (nao precisa de Python).
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Security | Out-Null

Write-Output "=== Diagnostico do token do Claude (colega) ==="
Write-Output ("hora: {0}" -f (Get-Date))
Write-Output ("usuario: {0}" -f $env:USERNAME)

function Find-ClaudeDir {
    $cands = @()
    foreach ($b in @($env:APPDATA, $env:LOCALAPPDATA)) {
        if ($b) { $cands += (Join-Path $b 'Claude'); $cands += (Join-Path $b 'AnthropicClaude') }
    }
    $pk = Join-Path $env:LOCALAPPDATA 'Packages'
    if (Test-Path $pk) {
        Get-ChildItem $pk -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match 'Claude|Anthropic' } | ForEach-Object {
                $cands += (Join-Path $_.FullName 'LocalCache\Roaming\Claude')
                $cands += (Join-Path $_.FullName 'LocalCache\Local\Claude')
            }
    }
    foreach ($c in $cands) {
        if ((Test-Path (Join-Path $c 'config.json')) -and (Test-Path (Join-Path $c 'Local State'))) {
            return $c
        }
    }
    return $null
}

$dir = Find-ClaudeDir
Write-Output "`n-- Pasta do Claude --"
Write-Output ("  {0}" -f ($(if ($dir) { $dir } else { 'NAO ENCONTRADA (config.json + Local State)' })))
if (-not $dir) { Write-Output "`n=== fim ==="; return }

# 1) Chave AES via DPAPI (do Local State)
Write-Output "`n-- Chave AES (DPAPI do Local State) --"
try {
    $ls = Get-Content (Join-Path $dir 'Local State') -Raw | ConvertFrom-Json
    $b64 = $ls.os_crypt.encrypted_key
    $enc = [Convert]::FromBase64String($b64)
    $dpapiPrefix = [System.Text.Encoding]::ASCII.GetString($enc[0..4])
    if ($dpapiPrefix -eq 'DPAPI') { $enc = $enc[5..($enc.Length - 1)] }
    $key = [System.Security.Cryptography.ProtectedData]::Unprotect($enc, $null, 'CurrentUser')
    Write-Output ("  DPAPI unprotect OK  (chave de {0} bytes)" -f $key.Length)
} catch {
    Write-Output ("  DPAPI unprotect FALHOU: {0}" -f $_.Exception.Message)
}

# 2) Formato dos blobs do token (prefixo v10/v20) — SEM mostrar o conteudo
Write-Output "`n-- Formato do token no config.json --"
try {
    $cfg = Get-Content (Join-Path $dir 'config.json') -Raw | ConvertFrom-Json
    foreach ($name in @('oauth:tokenCacheV2', 'oauth:tokenCache')) {
        $prop = $cfg.PSObject.Properties[$name]
        if ($prop -and $prop.Value) {
            $raw = [Convert]::FromBase64String([string]$prop.Value)
            $prefix = [System.Text.Encoding]::ASCII.GetString($raw[0..2])
            Write-Output ("  {0}: prefixo='{1}'  tamanho={2} bytes" -f $name, $prefix, $raw.Length)
        } else {
            Write-Output ("  {0}: ausente" -f $name)
        }
    }
    # tambem checa se existe a chave app-bound (indicativo de bloqueio)
    if ($ls.os_crypt.PSObject.Properties['app_bound_encrypted_key']) {
        Write-Output "  >> Local State TEM 'app_bound_encrypted_key' (app-bound encryption ativa)"
    }
} catch {
    Write-Output ("  Erro ao ler config.json: {0}" -f $_.Exception.Message)
}

Write-Output "`nLegenda: prefixo 'v10' = decifravel normalmente | 'v20' = app-bound (bloqueado p/ apps externos)"
Write-Output "=== fim ==="
