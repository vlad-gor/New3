# New3

## Offline development suite install

PowerShell:

```powershell
.\install-offline-dev-suite.ps1
```

GUI:

```powershell
.\install-offline-dev-suite-gui.ps1
```

Command Prompt:

```bat
install-offline-dev-suite.cmd
```

GUI wrapper:

```bat
install-offline-dev-suite-gui.cmd
```

The installer script performs a setup of:

- Git for Windows
- Node.js
- Python 3.13
- PostgreSQL 15
- Visual Studio Code
- SQL Server 2022 Express
- SQL Server Management Studio (SSMS)
- the offline Python package bundle from `wheelhouse/py313-windows-x86_64`, installed globally into the installed Python 3.13
- the saved VS Code extensions from `vscode-extensions`

It also:

- enables the VS Code Explorer context menu entries
- adds VS Code and Python locations to the user PATH
- registers a ready-to-use Jupyter kernel named `Offline Dev Python 3.13`
- creates or updates VS Code user settings so `python.defaultInterpreterPath` points at the installed Python 3.13
- prints the installed Git, Node.js, Python, pip, packaging-tool versions, and VS Code versions at the end
- provides a GUI installer with checkbox-based component selection and live install logs

Notes:

- SQL Server Express is stored in split parts and rebuilt during installation.
- SSMS is stored as a bootstrapper; for fully offline SSMS installation, prepare a local layout in `installers/ssms/layout/`.
- PostgreSQL 15 is stored in split parts and rebuilt during installation.
- PostgreSQL 15 is installed together with command-line tools and pgAdmin by default unless pgAdmin is explicitly skipped.
- Installing Node.js, PostgreSQL 15, SQL Server Express, and SSMS requires running the installer from an elevated Administrator session.