# New3

## Offline development suite install

PowerShell:

```powershell
.\install-offline-dev-suite.ps1
```

Command Prompt:

```bat
install-offline-dev-suite.cmd
```

The installer script performs a per-user setup of:

- Git for Windows
- Python 3.13
- Visual Studio Code
- the offline Python package bundle from `wheelhouse/py313-windows-x86_64`
- the saved VS Code extensions from `vscode-extensions`