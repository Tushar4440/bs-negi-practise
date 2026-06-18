$ErrorActionPreference = 'Stop';

$pathToRemove = Get-AppInstallLocation Tesseract-OCR

foreach ($registryPath in 'hklm:\system\currentcontrolset\control\session manager\environment', 'hkcu:\environment') {
  $p = (Get-Itemproperty -path "$registryPath" -Name Path).Path
  if ("$p" | Select-String -SimpleMatch "$pathToRemove"){
    $newPath = ("$p" -split ';' | ForEach-Object { if (-not ($_ -eq "$pathToRemove")) { $_ } } ) -join ';'
    Set-ItemProperty -path "$registryPath" -Name Path -Value $NewPath
  }
}
