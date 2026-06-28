# AGENTS.md

## Cursor Cloud specific instructions

### Project overview
`NetDiagPeer` is a single-machine/peer-to-peer network diagnostics tool written in pure
Python (standard library only, no pip dependencies, Python 3.8+). Key entry points are
documented in `README.md`:
- `main.py` / `network_diagnostic.py` — CLI entry point (`netdiag_core.main`)
- `gui_main.py` — Tkinter GUI entry point (`netdiag_gui.launch_gui`)
- `netdiag_core.py` — diagnostic engine; `netdiag_gui.py` — Tkinter UI

### Running
Standard run commands are in `README.md` (e.g. `python3 main.py --session <name>`,
`python3 gui_main.py`). Non-obvious caveats for this environment:
- The GUI (`gui_main.py` / `python3 main.py --gui`) requires the `python3-tk` system
  package (Tkinter). It is not installed by `pip`; it is installed once during VM setup and
  persists in the snapshot. If `import tkinter` fails, reinstall with
  `sudo apt-get install -y python3-tk`.
- Quick end-to-end smoke test without a second machine: point the tool at itself with
  `python3 main.py --peer 127.0.0.1 --session test --startup-delay 0.5 --discovery-timeout 1 --linger 0`.
  A healthy run prints `Direct HTTP: OK` and `Reverse callback: OK`.
- Two local peers can be tested by running two instances that share the same `--session`
  and `--discovery-port` but use different `--port` values; they find each other over UDP
  broadcast on the container's network.
- Console/report text is intentionally in Russian — this is expected, not a bug.

### Lint / test / build
- There is no automated test suite and no linter config in the repo. Use
  `python3 -m py_compile *.py` as the syntax/sanity check.
- `build_windows.bat` builds a Windows `.exe` via PyInstaller and only runs on Windows; it
  is not used for development on this Linux environment.
