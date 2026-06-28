# NetDiagPeer

## Network diagnostic application

This folder contains a Python application for bidirectional network diagnostics between two computers.

### Files

- `main.py` - CLI entry point
- `gui_main.py` - GUI entry point for Tkinter and Windows `.exe` packaging
- `netdiag_core.py` - diagnostic engine shared by CLI and GUI
- `netdiag_gui.py` - Tkinter interface
- `network_diagnostic.py` - compatibility wrapper
- `build_windows.bat` - build script for a Windows executable with PyInstaller

## What the application checks

When launched on both computers, the application:

1. starts a local HTTP diagnostic service;
2. tries to discover the second computer via UDP broadcast;
3. can also connect directly to a peer by hostname or IP;
4. checks direct HTTP/TCP connectivity to the peer;
5. asks the peer to connect back and verifies reverse connectivity;
6. optionally runs Windows-oriented diagnostics:
   - `ping`
   - SMB TCP ports `445` and `139`
   - `net view`
   - `nbtstat -A` and `nbtstat -a`
7. reports likely issues such as:
   - hostname does not resolve;
   - incoming connections are blocked by firewall;
   - peer is not visible via broadcast;
   - the peer does not look like it is on the same LAN segment;
   - SMB or NetBIOS does not respond.

## Requirements

- Python 3.8 is recommended for Windows 7
- No external dependencies

### Windows 7 note

For Windows 7 support:

- use Python 3.8 for source-based launches and local builds;
- ensure Windows 7 SP1 has update `KB2533623` installed, or its newer replacement `KB3063858`;
- use the Windows build artifact produced by the Windows 7 build workflow, not the older Python 3.12-based artifact.

## Run

### Option 1: automatic discovery on the same LAN

Run this command on both computers from the repository root:

```bash
python netdiagpeer/main.py --session office-test
```

Use the same `--session` value on both machines so they look for each other.

### Option 2: direct test by IP or hostname

If broadcast discovery does not work, run on both computers and specify the peer manually:

```bash
python netdiagpeer/main.py --peer 192.168.1.20 --session office-test
```

On the second machine:

```bash
python netdiagpeer/main.py --peer 192.168.1.10 --session office-test
```

### Option 3: launch the GUI

```bash
python netdiagpeer/gui_main.py
```

or

```bash
python netdiagpeer/main.py --gui
```

The GUI allows you to:

- automatically discover peers on the current LAN session;
- review discovered peers in a separate table;
- double-click a discovered peer to copy its IP and HTTP port into the form;
- enter the peer hostname or IP;
- configure TCP and UDP ports;
- enable Windows-specific diagnostics;
- save the current report as `.txt` or `.json`;
- run diagnostics without using the command line.

## Useful options

```bash
python netdiagpeer/main.py --help
```

Main options:

- `--peer` - peer hostname or IPv4 address
- `--port` - TCP port for the built-in HTTP service
- `--peer-port` - peer TCP port if it differs from the local port
- `--discovery-port` - UDP broadcast port
- `--discovery-timeout` - how long to wait for discovery responses
- `--connect-timeout` - timeout for direct and reverse connection checks
- `--startup-delay` - wait time before starting discovery and probing
- `--linger` - keep the service alive briefly after the report
- `--session` - logical session name to isolate diagnostics
- `--windows-mode` - enable ping, SMB, `net view`, and NetBIOS checks
- `--json` - machine-readable JSON output
- `--save-report` - write the report to a file
- `--save-format` - `auto`, `text`, or `json`
- `--gui` - start the Tkinter interface

### Save report to file

Save a text report:

```bash
python netdiagpeer/main.py --peer 192.168.1.20 --session office-test --save-report report.txt
```

Save a JSON report:

```bash
python netdiagpeer/main.py --peer 192.168.1.20 --session office-test --windows-mode --save-report report.json
```

### Windows-oriented diagnostics

Use this mode when diagnosing Windows 7 / Windows 10 sharing issues:

```bash
python netdiagpeer/main.py --peer PC-WIN7 --session office-test --windows-mode
```

This adds:

- `Ping` - basic ICMP reachability
- `SMB TCP 445` - direct SMB port check
- `NetBIOS Session TCP 139` - legacy Windows file sharing path
- `net view` - SMB resource enumeration
- `nbtstat -A <ip>` - NetBIOS over TCP/IP by address
- `nbtstat -a <hostname>` - NetBIOS over TCP/IP by hostname

### GUI peer auto-discovery

In the GUI, use:

- `Search peers` - sends broadcast discovery requests and fills the `Discovered peers` table
- double-click on a row - copies the discovered peer IP and HTTP port into the form
- `Use selected peer` - does the same action from the current table selection

This is useful when both computers are already running the tool with the same `Session` value and you do not want to type the peer IP manually.

## Example output

```text
NetDiagPeer 2.0.0
============================================================
Local computer:
  Hostname: PC-01
  FQDN: PC-01.local
  Platform: Windows 10
  Python: 3.11.9
  IPv4: 192.168.1.10

Discovered peers:
  - PC-02 @ 192.168.1.20:47821

Check #1: 192.168.1.20
  Direct HTTP: OK
  Reverse callback: FAIL
  Windows/SMB checks:
    - Ping: OK
    - SMB TCP 445: OK
    - net view: FAIL
  Findings:
    - Peer could not connect back to this computer. Incoming connections may be blocked.
```

## Interpretation

- `Direct HTTP: FAIL`
  - peer is unreachable by TCP;
  - firewall may block the application port;
  - host/IP may be incorrect.

- `Reverse callback: FAIL`
  - the other computer received the request, but could not open a connection back;
  - this usually points to a local firewall or inbound filtering problem.

- `SMB TCP 445: FAIL`
  - SMB is blocked by firewall;
  - File and Printer Sharing may be disabled;
  - the Server service may not be available on the peer.

- `net view: FAIL`
  - Windows networking is partially broken even if IP reachability works;
  - credentials, SMB configuration, or browser-related components may be involved.

- `nbtstat: FAIL`
  - NetBIOS over TCP/IP may be disabled;
  - hostname resolution for older Windows discovery paths may be broken.

- `hostname does not resolve`
  - test by IP first;
  - then investigate DNS, NetBIOS, or local name resolution.

- `nothing found via UDP broadcast`
  - computers may be in different subnets or VLANs;
  - broadcast may be filtered by the network;
  - manual `--peer` mode should still be used.

## Build a Windows executable

On a Windows machine with Python 3.8 installed, run:

```bat
netdiagpeer\build_windows.bat
```

The script will:

1. update `pip`;
2. install the latest `PyInstaller`;
3. build a windowed one-file executable using Python 3.8 for Windows 7 compatibility;
4. place the result at:

```text
netdiagpeer\dist\NetDiagPeer.exe
```

## Windows 7 compatible CI build

The repository also contains a GitHub Actions workflow named:

```text
Build NetDiagPeer Windows 7 EXE
```

It builds the application on a Windows runner with Python 3.8 and uploads a downloadable artifact named:

```text
NetDiagPeer-windows7-exe
```