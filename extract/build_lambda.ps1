   # Build the Lambda package folder: code + dependencies
   Remove-Item build -Recurse -Force -ErrorAction SilentlyContinue
   pip install tzdata --target build --no-deps --quiet
   Copy-Item entsoe_extract.py build\
   Write-Host "Lambda package ready in extract\build"