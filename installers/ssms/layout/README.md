# SSMS offline layout placeholder

This folder is reserved for a local offline SQL Server Management Studio layout.

The repository includes only the `vs_SSMS.exe` bootstrapper by default.

To prepare a reusable offline layout on a connected machine, run:

```powershell
..\create-offline-layout.ps1
```

After the layout is created in this folder, the main installer script can use it with `--noWeb` on offline machines.
