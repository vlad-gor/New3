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
- the offline Python package bundle from `wheelhouse/py313-windows-x86_64`, installed globally into the installed Python 3.13
- the saved VS Code extensions from `vscode-extensions`

It also:

- enables the VS Code Explorer context menu entries
- adds VS Code and Python locations to the user PATH
- registers a ready-to-use Jupyter kernel named `Offline Dev Python 3.13`
- prints the installed Git, Python, pip, packaging-tool versions, and VS Code versions at the end