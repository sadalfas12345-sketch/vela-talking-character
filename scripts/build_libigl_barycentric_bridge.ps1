param(
    [Parameter(Mandatory = $true)][string]$LibiglInclude,
    [Parameter(Mandatory = $true)][string]$EigenInclude,
    [string]$Clang = "C:\Program Files\LLVM\bin\clang++.exe",
    [string]$Output = "native\libigl_barycentric_bridge.pyd"
)

$python = python -c "import sys; print(sys.prefix)"
$pybind = python -c "import pybind11; print(pybind11.get_include())"
$numpy = python -c "import numpy; print(numpy.get_include())"
$source = Join-Path (Get-Location) "native\libigl_barycentric_bridge.cpp"
$pythonInclude = Join-Path $python "include"
$pythonLib = Join-Path $python "libs"

& $Clang -std=c++17 -O2 -shared -DMS_WIN64 `
    "-I$pybind" "-I$numpy" "-I$EigenInclude" "-I$LibiglInclude" "-I$pythonInclude" `
    $source "-L$pythonLib" -lpython311 -o $Output
if ($LASTEXITCODE -ne 0) { throw "libigl barycentric bridge build failed" }
