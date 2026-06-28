#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import platform
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional


APP_NAME = "NetDiagPeer"
APP_VERSION = "2.0.0"
DEFAULT_HTTP_PORT = 47821
DEFAULT_DISCOVERY_PORT = 47822
DEFAULT_DISCOVERY_TIMEOUT = 5.0
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_STARTUP_DELAY = 2.0
DEFAULT_LINGER = 2.0
DEFAULT_SAVE_FORMAT = "auto"
SAVE_FORMATS = ("auto", "text", "json")


@dataclass
class RuntimeOptions:
    peer: Optional[str] = None
    port: int = DEFAULT_HTTP_PORT
    peer_port: Optional[int] = None
    discovery_port: int = DEFAULT_DISCOVERY_PORT
    discovery_timeout: float = DEFAULT_DISCOVERY_TIMEOUT
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    startup_delay: float = DEFAULT_STARTUP_DELAY
    linger: float = DEFAULT_LINGER
    session: str = "default"
    json_output: bool = False
    save_report: Optional[str] = None
    save_format: str = DEFAULT_SAVE_FORMAT
    windows_mode: bool = False


@dataclass
class LocalProfile:
    hostname: str
    fqdn: str
    platform: str
    python_version: str
    ipv4_addresses: List[str]
    started_at: float


@dataclass
class ReverseCheckResult:
    ok: bool
    callback_url: str
    detail: str


@dataclass
class CommandCheckResult:
    name: str
    ok: bool
    detail: str
    command: Optional[str] = None
    returncode: Optional[int] = None
    output: str = ""
    skipped: bool = False


@dataclass
class PeerProbeResult:
    peer_host: str
    peer_ip: Optional[str]
    resolved_ips: List[str]
    connect_ok: bool
    connect_detail: str
    http_ok: bool
    reverse_ok: bool
    reverse_detail: str
    warnings: List[str]
    local_name_resolution_ok: Optional[bool]
    remote_profile: Optional[Dict[str, object]]
    observed_by_peer_as: Optional[str]
    windows_checks: List[CommandCheckResult] = field(default_factory=list)


@dataclass
class DiagnosticReport:
    app: str
    version: str
    generated_at: str
    profile: LocalProfile
    settings: RuntimeOptions
    discovered_peers: List[Dict[str, object]]
    results: List[PeerProbeResult]


@dataclass
class DiscoveryReport:
    app: str
    version: str
    generated_at: str
    profile: LocalProfile
    settings: RuntimeOptions
    discovered_peers: List[Dict[str, object]]


class ServerState:
    def __init__(self, profile: LocalProfile, http_port: int, session: str, instance_id: str) -> None:
        self.profile = profile
        self.http_port = http_port
        self.session = session
        self.instance_id = instance_id


def collect_local_ipv4_addresses() -> List[str]:
    addresses = set()

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if not ip.startswith("127."):
                addresses.add(ip)
    except socket.gaierror:
        pass

    probe_targets = [("8.8.8.8", 80), ("1.1.1.1", 80), ("192.168.0.1", 80)]
    for target_host, target_port in probe_targets:
        sock: Optional[socket.socket] = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((target_host, target_port))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
        except OSError:
            pass
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    if not addresses:
        addresses.add("127.0.0.1")

    return sorted(addresses)


def build_local_profile() -> LocalProfile:
    return LocalProfile(
        hostname=socket.gethostname(),
        fqdn=socket.getfqdn(),
        platform=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        ipv4_addresses=collect_local_ipv4_addresses(),
        started_at=time.time(),
    )


def resolve_host(host: str) -> List[str]:
    resolved: List[str] = []
    seen = set()
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if ip not in seen:
                seen.add(ip)
                resolved.append(ip)
    except socket.gaierror:
        return []
    return resolved


def is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def looks_like_same_lan(local_ips: List[str], peer_ip: Optional[str]) -> Optional[bool]:
    if not peer_ip:
        return None

    try:
        peer_addr = ipaddress.ip_address(peer_ip)
    except ValueError:
        return None

    if peer_addr.is_loopback:
        return True

    for ip in local_ips:
        try:
            local_addr = ipaddress.ip_address(ip)
        except ValueError:
            continue

        if local_addr.is_loopback and peer_addr.is_loopback:
            return True

        if (
            local_addr.is_private
            and peer_addr.is_private
            and str(local_addr).split(".")[:3] == str(peer_addr).split(".")[:3]
        ):
            return True

    return False


def command_to_string(command: List[str]) -> str:
    if platform.system() == "Windows":
        return subprocess.list2cmdline(command)
    return " ".join(command)


def run_command(command: List[str], timeout: float, name: str) -> CommandCheckResult:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=max(timeout, 1.0),
            check=False,
        )
        ok = completed.returncode == 0
        detail = "Команда завершилась успешно." if ok else f"Команда завершилась с кодом {completed.returncode}."
        return CommandCheckResult(
            name=name,
            ok=ok,
            detail=detail,
            command=command_to_string(command),
            returncode=completed.returncode,
            output=completed.stdout.strip(),
        )
    except FileNotFoundError:
        return CommandCheckResult(
            name=name,
            ok=False,
            detail="Команда недоступна в системе.",
            command=command_to_string(command),
            skipped=True,
        )
    except subprocess.TimeoutExpired as exc:
        output = ""
        if exc.stdout:
            output = str(exc.stdout).strip()
        return CommandCheckResult(
            name=name,
            ok=False,
            detail=f"Команда превысила таймаут {timeout:.1f} сек.",
            command=command_to_string(command),
            output=output,
        )
    except OSError as exc:
        return CommandCheckResult(
            name=name,
            ok=False,
            detail=f"{exc.__class__.__name__}: {exc}",
            command=command_to_string(command),
        )


def run_socket_check(host: Optional[str], port: int, timeout: float, name: str) -> CommandCheckResult:
    if not host:
        return CommandCheckResult(
            name=name,
            ok=False,
            detail="Проверка пропущена: неизвестен адрес пира.",
            skipped=True,
        )

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return CommandCheckResult(
                name=name,
                ok=True,
                detail=f"TCP-порт {port} доступен.",
                command=f"TCP connect {host}:{port}",
            )
    except OSError as exc:
        return CommandCheckResult(
            name=name,
            ok=False,
            detail=f"{exc.__class__.__name__}: {exc}",
            command=f"TCP connect {host}:{port}",
        )


def run_ping_check(target_host: str, timeout: float) -> CommandCheckResult:
    timeout_seconds = max(1, math.ceil(timeout))
    if platform.system() == "Windows":
        command = ["ping", "-n", "2", "-w", str(int(max(timeout, 1.0) * 1000)), target_host]
    else:
        command = ["ping", "-c", "2", "-W", str(timeout_seconds), target_host]
    result = run_command(command, timeout=max(timeout * 2, 3.0), name="Ping")
    if result.ok:
        result.detail = "ICMP-ответы получены."
    elif not result.skipped:
        result.detail = "ICMP-ответ не получен или команда завершилась ошибкой."
    return result


def run_net_view_check(target_host: str, timeout: float) -> CommandCheckResult:
    if platform.system() != "Windows":
        return CommandCheckResult(
            name="net view",
            ok=False,
            detail="Проверка доступна только на Windows.",
            skipped=True,
        )

    unc_target = f"\\\\{target_host}"
    result = run_command(["net", "view", unc_target], timeout=max(timeout * 3, 5.0), name="net view")
    if result.ok:
        result.detail = "Команда net view смогла получить SMB-ресурсы."
    elif not result.skipped:
        result.detail = "Команда net view не получила список SMB-ресурсов."
    return result


def run_nbtstat_ip_check(peer_ip: Optional[str], timeout: float) -> CommandCheckResult:
    if not peer_ip:
        return CommandCheckResult(
            name="nbtstat -A",
            ok=False,
            detail="Проверка пропущена: IPv4-адрес пира не определен.",
            skipped=True,
        )

    if platform.system() != "Windows":
        return CommandCheckResult(
            name="nbtstat -A",
            ok=False,
            detail="Проверка доступна только на Windows.",
            skipped=True,
        )

    result = run_command(["nbtstat", "-A", peer_ip], timeout=max(timeout * 3, 5.0), name="nbtstat -A")
    if result.ok:
        result.detail = "Удаленный NetBIOS по IP ответил."
    elif not result.skipped:
        result.detail = "Удаленный NetBIOS по IP не ответил."
    return result


def run_nbtstat_name_check(target_host: str, timeout: float) -> CommandCheckResult:
    if is_ip_address(target_host):
        return CommandCheckResult(
            name="nbtstat -a",
            ok=False,
            detail="Проверка пропущена: для nbtstat -a нужно имя хоста.",
            skipped=True,
        )

    if platform.system() != "Windows":
        return CommandCheckResult(
            name="nbtstat -a",
            ok=False,
            detail="Проверка доступна только на Windows.",
            skipped=True,
        )

    result = run_command(["nbtstat", "-a", target_host], timeout=max(timeout * 3, 5.0), name="nbtstat -a")
    if result.ok:
        result.detail = "Удаленный NetBIOS по имени ответил."
    elif not result.skipped:
        result.detail = "Удаленный NetBIOS по имени не ответил."
    return result


def run_windows_peer_checks(target_host: str, peer_ip: Optional[str], timeout: float) -> List[CommandCheckResult]:
    return [
        run_ping_check(target_host, timeout),
        run_socket_check(peer_ip, 445, timeout, "SMB TCP 445"),
        run_socket_check(peer_ip, 139, timeout, "NetBIOS Session TCP 139"),
        run_net_view_check(target_host, timeout),
        run_nbtstat_ip_check(peer_ip, timeout),
        run_nbtstat_name_check(target_host, timeout),
    ]


def windows_warnings_from_checks(checks: List[CommandCheckResult]) -> List[str]:
    warnings: List[str] = []

    by_name = {check.name: check for check in checks}

    ping = by_name.get("Ping")
    if ping and not ping.ok and not ping.skipped:
        warnings.append("Ping до пира не проходит. Возможна проблема маршрутизации, ICMP или firewall.")

    smb_445 = by_name.get("SMB TCP 445")
    if smb_445 and not smb_445.ok and not smb_445.skipped:
        warnings.append("TCP-порт 445 недоступен. Возможна блокировка SMB или отключенный общий доступ.")

    net_view = by_name.get("net view")
    if net_view and not net_view.ok and not net_view.skipped:
        warnings.append("Команда net view не смогла получить сетевые ресурсы пира.")

    nbt_ip = by_name.get("nbtstat -A")
    if nbt_ip and not nbt_ip.ok and not nbt_ip.skipped:
        warnings.append("NetBIOS по IP не отвечает. Проверьте NetBIOS over TCP/IP и устаревшие механизмы обнаружения.")

    nbt_name = by_name.get("nbtstat -a")
    if nbt_name and not nbt_name.ok and not nbt_name.skipped:
        warnings.append("NetBIOS по имени не отвечает. Возможна проблема разрешения имен или NetBIOS.")

    return warnings


def try_callback(url: str, timeout: float) -> ReverseCheckResult:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            detail = payload.get("detail", "callback returned without detail")
            return ReverseCheckResult(True, url, detail)
    except urllib.error.URLError as exc:
        return ReverseCheckResult(False, url, f"{exc.__class__.__name__}: {exc}")
    except OSError as exc:
        return ReverseCheckResult(False, url, f"{exc.__class__.__name__}: {exc}")
    except json.JSONDecodeError:
        return ReverseCheckResult(False, url, "Peer callback returned invalid JSON")


def make_handler(state: ServerState):
    class DiagnosticHandler(BaseHTTPRequestHandler):
        server_version = f"{APP_NAME}/{APP_VERSION}"

        def _write_json(self, payload: Dict[str, object], status: int = 200) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/health":
                self._write_json(
                    {
                        "app": APP_NAME,
                        "version": APP_VERSION,
                        "instance_id": state.instance_id,
                        "session": state.session,
                        "profile": asdict(state.profile),
                    }
                )
                return

            if parsed.path == "/callback":
                query = urllib.parse.parse_qs(parsed.query)
                token = query.get("token", [""])[0]
                self._write_json(
                    {
                        "ok": True,
                        "detail": f"Reverse callback reached {state.profile.hostname} with token {token}",
                        "instance_id": state.instance_id,
                    }
                )
                return

            self._write_json({"error": "Not found"}, status=404)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/probe":
                self._write_json({"error": "Not found"}, status=404)
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._write_json({"error": "Invalid content length"}, status=400)
                return

            try:
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except json.JSONDecodeError:
                self._write_json({"error": "Invalid JSON payload"}, status=400)
                return

            callback_port = payload.get("callback_port")
            callback_token = payload.get("callback_token")
            remote_ip = self.client_address[0]

            reverse_result = None
            if isinstance(callback_port, int) and isinstance(callback_token, str):
                callback_url = f"http://{remote_ip}:{callback_port}/callback?token={urllib.parse.quote(callback_token)}"
                reverse_result = try_callback(callback_url, DEFAULT_CONNECT_TIMEOUT)

            remote_hostname = payload.get("hostname")
            name_resolution_ok = None
            if isinstance(remote_hostname, str) and remote_hostname:
                resolved_ips = resolve_host(remote_hostname)
                name_resolution_ok = remote_ip in resolved_ips

            self._write_json(
                {
                    "app": APP_NAME,
                    "version": APP_VERSION,
                    "session": state.session,
                    "instance_id": state.instance_id,
                    "profile": asdict(state.profile),
                    "observed_remote_ip": remote_ip,
                    "reverse_result": asdict(reverse_result) if reverse_result else None,
                    "name_resolution_ok": name_resolution_ok,
                }
            )

    return DiagnosticHandler


class DiscoveryResponder(threading.Thread):
    def __init__(self, state: ServerState, discovery_port: int, stop_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self.state = state
        self.discovery_port = discovery_port
        self.stop_event = stop_event

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.discovery_port))
        sock.settimeout(0.5)

        try:
            while not self.stop_event.is_set():
                try:
                    data, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    break

                try:
                    payload = json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

                if payload.get("type") != "discover":
                    continue
                if payload.get("session") != self.state.session:
                    continue
                if payload.get("instance_id") == self.state.instance_id:
                    continue

                response = {
                    "type": "discover_response",
                    "session": self.state.session,
                    "instance_id": self.state.instance_id,
                    "hostname": self.state.profile.hostname,
                    "http_port": self.state.http_port,
                    "ipv4_addresses": self.state.profile.ipv4_addresses,
                }
                try:
                    sock.sendto(json.dumps(response).encode("utf-8"), address)
                except OSError:
                    continue
        finally:
            sock.close()


def start_http_server(state: ServerState) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("0.0.0.0", state.http_port), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def discover_peers(state: ServerState, discovery_port: int, timeout: float) -> List[Dict[str, object]]:
    request = {
        "type": "discover",
        "session": state.session,
        "instance_id": state.instance_id,
    }
    peers: List[Dict[str, object]] = []
    seen = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 0))
    sock.settimeout(0.5)

    deadline = time.time() + timeout

    try:
        while time.time() < deadline:
            try:
                sock.sendto(json.dumps(request).encode("utf-8"), ("255.255.255.255", discovery_port))
            except OSError:
                break

            round_end = min(deadline, time.time() + 1.0)
            while time.time() < round_end:
                try:
                    data, address = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    break

                try:
                    payload = json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

                if payload.get("type") != "discover_response":
                    continue
                if payload.get("session") != state.session:
                    continue
                if payload.get("instance_id") == state.instance_id:
                    continue

                key = (payload.get("instance_id"), address[0], payload.get("http_port"))
                if key in seen:
                    continue
                seen.add(key)
                payload["source_ip"] = address[0]
                peers.append(payload)
    finally:
        sock.close()

    return peers


def choose_peer_targets(options: RuntimeOptions, discovered_peers: List[Dict[str, object]]) -> List[Dict[str, object]]:
    targets = []

    if options.peer:
        targets.append({"host": options.peer, "port": options.peer_port or options.port})

    for peer in discovered_peers:
        source_ip = peer.get("source_ip")
        port = peer.get("http_port", options.port)
        if isinstance(source_ip, str):
            targets.append({"host": source_ip, "port": int(port)})

    unique_targets = []
    seen = set()
    for target in targets:
        key = (target["host"], target["port"])
        if key in seen:
            continue
        seen.add(key)
        unique_targets.append(target)

    return unique_targets


def create_server_state(options: RuntimeOptions) -> tuple[LocalProfile, ServerState, threading.Event]:
    profile = build_local_profile()
    instance_id = secrets.token_hex(8)
    state = ServerState(profile, options.port, options.session, instance_id)
    return profile, state, threading.Event()


def start_runtime_services(
    state: ServerState,
    stop_event: threading.Event,
    discovery_port: int,
) -> tuple[ThreadingHTTPServer, threading.Thread, DiscoveryResponder]:
    try:
        http_server, http_thread = start_http_server(state)
    except OSError as exc:
        raise RuntimeError(f"Не удалось открыть TCP-порт {state.http_port}: {exc}") from exc

    responder = DiscoveryResponder(state, discovery_port, stop_event)
    responder.start()
    return http_server, http_thread, responder


def stop_runtime_services(http_server: ThreadingHTTPServer, stop_event: threading.Event) -> None:
    stop_event.set()
    http_server.shutdown()
    http_server.server_close()


def probe_peer(
    target_host: str,
    target_port: int,
    profile: LocalProfile,
    options: RuntimeOptions,
) -> PeerProbeResult:
    warnings: List[str] = []
    peer_ip = target_host if is_ip_address(target_host) else None
    resolved_ips: List[str] = []
    windows_checks: List[CommandCheckResult] = []

    if not peer_ip:
        resolved_ips = resolve_host(target_host)
        if not resolved_ips:
            warnings.append("Имя узла не разрешается в IPv4-адрес.")
        else:
            peer_ip = resolved_ips[0]

    if looks_like_same_lan(profile.ipv4_addresses, peer_ip) is False:
        warnings.append("Пир не похож на узел из той же локальной подсети (эвристика по первым трем октетам).")

    if not peer_ip:
        if options.windows_mode:
            windows_checks = run_windows_peer_checks(target_host, None, options.connect_timeout)
            warnings.extend(windows_warnings_from_checks(windows_checks))
        return PeerProbeResult(
            peer_host=target_host,
            peer_ip=None,
            resolved_ips=resolved_ips,
            connect_ok=False,
            connect_detail="Невозможно определить IPv4-адрес пира.",
            http_ok=False,
            reverse_ok=False,
            reverse_detail="Проверка не выполнялась.",
            warnings=warnings,
            local_name_resolution_ok=None,
            remote_profile=None,
            observed_by_peer_as=None,
            windows_checks=windows_checks,
        )

    callback_token = secrets.token_hex(8)
    payload = {
        "hostname": profile.hostname,
        "fqdn": profile.fqdn,
        "ipv4_addresses": profile.ipv4_addresses,
        "callback_port": options.port,
        "callback_token": callback_token,
    }
    probe_url = f"http://{peer_ip}:{target_port}/probe"
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        probe_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=options.connect_timeout) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        detail = f"{exc.__class__.__name__}: {exc}"
        warnings.append("TCP/HTTP соединение до пира не установлено. Проверьте firewall, порт и доступность хоста.")
        if options.windows_mode:
            windows_checks = run_windows_peer_checks(target_host, peer_ip, options.connect_timeout)
            warnings.extend(windows_warnings_from_checks(windows_checks))
        return PeerProbeResult(
            peer_host=target_host,
            peer_ip=peer_ip,
            resolved_ips=resolved_ips,
            connect_ok=False,
            connect_detail=detail,
            http_ok=False,
            reverse_ok=False,
            reverse_detail="Проверка не выполнялась.",
            warnings=warnings,
            local_name_resolution_ok=None,
            remote_profile=None,
            observed_by_peer_as=None,
            windows_checks=windows_checks,
        )
    except OSError as exc:
        detail = f"{exc.__class__.__name__}: {exc}"
        warnings.append("Соединение до пира завершилось ошибкой сокета.")
        if options.windows_mode:
            windows_checks = run_windows_peer_checks(target_host, peer_ip, options.connect_timeout)
            warnings.extend(windows_warnings_from_checks(windows_checks))
        return PeerProbeResult(
            peer_host=target_host,
            peer_ip=peer_ip,
            resolved_ips=resolved_ips,
            connect_ok=False,
            connect_detail=detail,
            http_ok=False,
            reverse_ok=False,
            reverse_detail="Проверка не выполнялась.",
            warnings=warnings,
            local_name_resolution_ok=None,
            remote_profile=None,
            observed_by_peer_as=None,
            windows_checks=windows_checks,
        )

    reverse_payload = response_payload.get("reverse_result") or {}
    reverse_ok = bool(reverse_payload.get("ok"))
    reverse_detail = reverse_payload.get("detail", "Пир не вернул результат обратной проверки.")

    if not reverse_ok:
        warnings.append("Пир не смог подключиться обратно к этому компьютеру. Возможна блокировка входящих подключений.")

    local_name_resolution_ok = response_payload.get("name_resolution_ok")
    if local_name_resolution_ok is False:
        warnings.append("Пир не смог сопоставить имя этого компьютера с адресом входящего соединения.")

    if options.windows_mode:
        windows_checks = run_windows_peer_checks(target_host, peer_ip, options.connect_timeout)
        warnings.extend(windows_warnings_from_checks(windows_checks))

    return PeerProbeResult(
        peer_host=target_host,
        peer_ip=peer_ip,
        resolved_ips=resolved_ips,
        connect_ok=True,
        connect_detail="HTTP-соединение установлено.",
        http_ok=True,
        reverse_ok=reverse_ok,
        reverse_detail=reverse_detail,
        warnings=warnings,
        local_name_resolution_ok=local_name_resolution_ok,
        remote_profile=response_payload.get("profile"),
        observed_by_peer_as=response_payload.get("observed_remote_ip"),
        windows_checks=windows_checks,
    )


def discover_only(options: RuntimeOptions) -> DiscoveryReport:
    profile, state, stop_event = create_server_state(options)
    http_server, _thread, _responder = start_runtime_services(state, stop_event, options.discovery_port)

    try:
        time.sleep(max(0.0, options.startup_delay))
        discovered_peers = discover_peers(state, options.discovery_port, options.discovery_timeout)
        return DiscoveryReport(
            app=APP_NAME,
            version=APP_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            profile=profile,
            settings=options,
            discovered_peers=discovered_peers,
        )
    finally:
        stop_runtime_services(http_server, stop_event)


def run_diagnostics(options: RuntimeOptions) -> DiagnosticReport:
    profile, state, stop_event = create_server_state(options)
    http_server, _thread, _responder = start_runtime_services(state, stop_event, options.discovery_port)

    try:
        time.sleep(max(0.0, options.startup_delay))
        discovered_peers = discover_peers(state, options.discovery_port, options.discovery_timeout)
        targets = choose_peer_targets(options, discovered_peers)
        results = [probe_peer(target["host"], target["port"], profile, options) for target in targets]

        if options.linger > 0:
            time.sleep(options.linger)

        return DiagnosticReport(
            app=APP_NAME,
            version=APP_VERSION,
            generated_at=datetime.now(timezone.utc).isoformat(),
            profile=profile,
            settings=options,
            discovered_peers=discovered_peers,
            results=results,
        )
    finally:
        stop_runtime_services(http_server, stop_event)


def report_to_dict(report: DiagnosticReport) -> Dict[str, object]:
    return asdict(report)


def render_json_report(report: DiagnosticReport) -> str:
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=2)


def format_check_output(output: str, max_lines: int = 10) -> List[str]:
    if not output:
        return []

    lines = output.splitlines()
    if len(lines) <= max_lines:
        return lines
    trimmed = lines[:max_lines]
    trimmed.append(f"... ({len(lines) - max_lines} more lines)")
    return trimmed


def render_text_report(report: DiagnosticReport) -> str:
    profile = report.profile
    lines = []
    lines.append(f"{report.app} {report.version}")
    lines.append("=" * 60)
    lines.append(f"Сформирован: {report.generated_at}")
    lines.append("Локальный компьютер:")
    lines.append(f"  Hostname: {profile.hostname}")
    lines.append(f"  FQDN: {profile.fqdn}")
    lines.append(f"  Platform: {profile.platform}")
    lines.append(f"  Python: {profile.python_version}")
    lines.append(f"  IPv4: {', '.join(profile.ipv4_addresses)}")
    lines.append("")

    lines.append("Параметры запуска:")
    lines.append(f"  Session: {report.settings.session}")
    lines.append(f"  Local HTTP port: {report.settings.port}")
    lines.append(f"  Discovery UDP port: {report.settings.discovery_port}")
    lines.append(f"  Windows mode: {'ON' if report.settings.windows_mode else 'OFF'}")
    lines.append("")

    lines.append("Обнаруженные узлы:")
    if report.discovered_peers:
        for peer in report.discovered_peers:
            lines.append(
                f"  - {peer.get('hostname', 'unknown')} @ {peer.get('source_ip', 'unknown')}:{peer.get('http_port', '?')}"
            )
    else:
        lines.append("  - Ничего не найдено по UDP broadcast. Это может означать другой сегмент сети или блокировку UDP broadcast.")
    lines.append("")

    if not report.results:
        lines.append("Проверки не выполнены: не найден peer и не указан параметр --peer.")
        return "\n".join(lines)

    for index, result in enumerate(report.results, start=1):
        lines.append(f"Проверка #{index}: {result.peer_host}")
        lines.append(f"  Peer IPv4: {result.peer_ip or 'unknown'}")
        if result.resolved_ips:
            lines.append(f"  Resolved IPv4: {', '.join(result.resolved_ips)}")
        lines.append(f"  Direct HTTP: {'OK' if result.http_ok else 'FAIL'} ({result.connect_detail})")
        lines.append(f"  Reverse callback: {'OK' if result.reverse_ok else 'FAIL'} ({result.reverse_detail})")
        if result.local_name_resolution_ok is None:
            lines.append("  Name resolution on peer: not checked")
        else:
            lines.append(f"  Name resolution on peer: {'OK' if result.local_name_resolution_ok else 'FAIL'}")
        if result.observed_by_peer_as:
            lines.append(f"  Peer saw this host as: {result.observed_by_peer_as}")
        if result.remote_profile:
            remote_name = result.remote_profile.get("hostname", "unknown")
            remote_ips = result.remote_profile.get("ipv4_addresses", [])
            lines.append(f"  Remote hostname: {remote_name}")
            lines.append(f"  Remote IPv4: {', '.join(remote_ips) if isinstance(remote_ips, list) else remote_ips}")

        if result.windows_checks:
            lines.append("  Windows/SMB checks:")
            for check in result.windows_checks:
                status = "SKIP" if check.skipped else ("OK" if check.ok else "FAIL")
                lines.append(f"    - {check.name}: {status} ({check.detail})")
                if check.command:
                    lines.append(f"      command: {check.command}")
                for output_line in format_check_output(check.output):
                    lines.append(f"      {output_line}")

        if result.warnings:
            lines.append("  Findings:")
            for warning in result.warnings:
                lines.append(f"    - {warning}")
        else:
            lines.append("  Findings:")
            lines.append("    - Критичных проблем по базовым проверкам не найдено.")
        lines.append("")

    lines.append("Подсказки:")
    lines.append("  - Если direct HTTP не проходит, проверьте firewall и доступность TCP-порта приложения.")
    lines.append("  - Если reverse callback не проходит, обычно блокируются входящие подключения на локальном ПК.")
    lines.append("  - Если Ping и SMB TCP 445 не проходят, проверьте сетевой профиль Windows и правила File and Printer Sharing.")
    lines.append("  - Если net view или nbtstat падают только на Windows, проверьте SMB/NetBIOS и разрешение имен.")
    lines.append("  - Если узел не находится через broadcast, компьютеры могут быть в разных VLAN/подсетях.")
    return "\n".join(lines)


def detect_save_format(path: str, requested_format: str) -> str:
    if requested_format == "json":
        return "json"
    if requested_format == "text":
        return "text"
    return "json" if path.lower().endswith(".json") else "text"


def save_report_to_path(report: DiagnosticReport, text_report: str, path: str, save_format: str = DEFAULT_SAVE_FORMAT) -> str:
    resolved_format = detect_save_format(path, save_format)
    target_path = Path(path)
    if target_path.parent and str(target_path.parent) != ".":
        target_path.parent.mkdir(parents=True, exist_ok=True)

    if resolved_format == "json":
        target_path.write_text(render_json_report(report), encoding="utf-8")
    else:
        target_path.write_text(text_report, encoding="utf-8")
    return str(target_path)


def namespace_to_options(args: argparse.Namespace) -> RuntimeOptions:
    save_format = args.save_format
    if save_format not in SAVE_FORMATS:
        raise ValueError(f"Unsupported save format: {save_format}")

    return RuntimeOptions(
        peer=args.peer,
        port=args.port,
        peer_port=args.peer_port,
        discovery_port=args.discovery_port,
        discovery_timeout=args.discovery_timeout,
        connect_timeout=args.connect_timeout,
        startup_delay=args.startup_delay,
        linger=args.linger,
        session=args.session,
        json_output=args.json,
        save_report=args.save_report,
        save_format=save_format,
        windows_mode=args.windows_mode,
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Двусторонняя диагностика сети между двумя компьютерами с текстовым и GUI режимом."
    )
    parser.add_argument("--peer", help="Имя хоста или IPv4 адрес второго компьютера.")
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT, help="TCP-порт встроенного HTTP-сервиса.")
    parser.add_argument("--peer-port", type=int, help="TCP-порт пира, если он отличается от локального --port.")
    parser.add_argument(
        "--discovery-port",
        type=int,
        default=DEFAULT_DISCOVERY_PORT,
        help="UDP-порт для broadcast-обнаружения.",
    )
    parser.add_argument(
        "--discovery-timeout",
        type=float,
        default=DEFAULT_DISCOVERY_TIMEOUT,
        help="Сколько секунд ждать ответов UDP discovery.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=DEFAULT_CONNECT_TIMEOUT,
        help="Таймаут HTTP/TCP/SMB-подключений.",
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=DEFAULT_STARTUP_DELAY,
        help="Сколько секунд подождать после старта сервиса, прежде чем начинать discovery и probe.",
    )
    parser.add_argument(
        "--linger",
        type=float,
        default=DEFAULT_LINGER,
        help="Сколько секунд оставить сервис активным после печати отчета, чтобы второй узел успел проверить соединение.",
    )
    parser.add_argument(
        "--session",
        default="default",
        help="Логическое имя сеанса, чтобы два ПК искали только друг друга.",
    )
    parser.add_argument("--windows-mode", action="store_true", help="Включить дополнительные Windows-проверки: ping, net view, SMB и NetBIOS.")
    parser.add_argument("--json", action="store_true", help="Вывести отчет в JSON вместо текста.")
    parser.add_argument("--save-report", help="Сохранить отчет в файл (.txt или .json).")
    parser.add_argument(
        "--save-format",
        choices=SAVE_FORMATS,
        default=DEFAULT_SAVE_FORMAT,
        help="Формат сохранения отчета: auto, text или json.",
    )
    parser.add_argument("--gui", action="store_true", help="Запустить графический интерфейс tkinter.")
    return parser.parse_args(argv)


def run_cli(options: RuntimeOptions) -> int:
    try:
        report = run_diagnostics(options)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if options.json_output:
        stdout_payload = render_json_report(report)
    else:
        stdout_payload = render_text_report(report)

    print(stdout_payload)

    if options.save_report:
        saved_path = save_report_to_path(report, render_text_report(report), options.save_report, options.save_format)
        print(f"\nReport saved to: {saved_path}", file=sys.stderr)

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.gui:
        try:
            from netdiag_gui import launch_gui

            return launch_gui()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    return run_cli(namespace_to_options(args))


if __name__ == "__main__":
    raise SystemExit(main())
