# New3

## Network diagnostic application

This repository now contains a Python application for bidirectional network diagnostics between two computers.

### Files

- `main.py` - entry point
- `network_diagnostic.py` - full application
- `rename_dirs.sh` - separate Bash utility from the previous task

## What the application checks

When launched on both computers, the application:

1. starts a local HTTP diagnostic service;
2. tries to discover the second computer via UDP broadcast;
3. can also connect directly to a peer by hostname or IP;
4. checks direct HTTP/TCP connectivity to the peer;
5. asks the peer to connect back and verifies reverse connectivity;
6. reports likely issues such as:
   - hostname does not resolve;
   - incoming connections are blocked by firewall;
   - peer is not visible via broadcast;
   - the peer does not look like it is on the same LAN segment.

## Requirements

- Python 3.8+
- No external dependencies

## Run

### Option 1: automatic discovery on the same LAN

Run this command on both computers:

```bash
python main.py --session office-test
```

Use the same `--session` value on both machines so they look for each other.

### Option 2: direct test by IP or hostname

If broadcast discovery does not work, run on both computers and specify the peer manually:

```bash
python main.py --peer 192.168.1.20 --session office-test
```

On the second machine:

```bash
python main.py --peer 192.168.1.10 --session office-test
```

## Useful options

```bash
python main.py --help
```

Main options:

- `--peer` - peer hostname or IPv4 address
- `--port` - TCP port for the built-in HTTP service
- `--discovery-port` - UDP broadcast port
- `--discovery-timeout` - how long to wait for discovery responses
- `--connect-timeout` - timeout for direct and reverse connection checks
- `--session` - logical session name to isolate diagnostics
- `--json` - machine-readable JSON output

## Example output

```text
NetDiagPeer 1.0.0
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

- `hostname does not resolve`
  - test by IP first;
  - then investigate DNS, NetBIOS, or local name resolution.

- `nothing found via UDP broadcast`
  - computers may be in different subnets or VLANs;
  - broadcast may be filtered by the network;
  - manual `--peer` mode should still be used.