Param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host '== Pre-commit hooks =='
try { pre-commit run --all-files } catch { Write-Warning $_; }

Write-Host '== Contracts validate =='
python scripts/contracts_validate.py

Write-Host '== Registry codegen check =='
try {
  python scripts/registry_codegen.py --check
} catch {
  Write-Error "Registry outputs not up-to-date. Run: python scripts/registry_codegen.py"
  exit 1
}

Write-Host '== Schema diff (if PR) =='
try { python scripts/schema_diff.py } catch { Write-Warning $_ }

Write-Host '== Tests =='
try { pytest -q --cov=services } catch { Write-Warning $_ }

Write-Host 'All checks executed. Review outputs above.'

