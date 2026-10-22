.PHONY: all clean program

all:
	powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1

program:
	powershell -NoProfile -ExecutionPolicy Bypass -File program.ps1

clean:
	powershell -NoProfile -Command "if (Test-Path -LiteralPath 'dist') { Remove-Item -LiteralPath 'dist' -Recurse -Force }"
