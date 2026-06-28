#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ipaddress
import json
import platform
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional


APP_NAME = "NetDiagPeer"
APP_VERSION = "1.0.0"
DEFAULT_HTTP_PORT = 47821
DEFAULT_DISCOVERY_PORT = 47822
DEFAULT_DISCOVERY_TIMEOUT = 5.0
DEFAULT_CONNECT_TIMEOUT = 3.0


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
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((target_host, target_port))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                addresses.add(ip)
        except OSError:
            pass
        finally:
            try:
                sock.close()
            except Exception:
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
    resolved = []
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

    for ip in local_ips:
        try:
            local_addr = ipaddress.ip_address(ip)
        except ValueError:
            continue

        if local_addr.is_private and peer_addr.is_private and str(local_addr).split(".")[:3] == str(peer_addr).split(".")[:3]:
            return True

    return False


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


def discover_peers(
    state: ServerState,
    discovery_port: int,
    timeout: float,
) -> List[Dict[str, object]]:
    request = {
        "type": "discover",
        "session": state.session,
        "instance_id": state.instance_id,
    }
    peers = []
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


def choose_peer_targets(args: argparse.Namespace, discovered_peers: List[Dict[str, object]]) -> List[Dict[str, object]]:
    targets = []

    if args.peer:
        targets.append({"host": args.peer, "port": args.port})

    for peer in discovered_peers:
        source_ip = peer.get("source_ip")
        port = peer.get("http_port", args.port)
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


def probe_peer(
    target_host: str,
    target_port: int,
    profile: LocalProfile,
    callback_port: int,
    timeout: float,
) -> PeerProbeResult:
    warnings: List[str] = []
    peer_ip = target_host if is_ip_address(target_host) else None
    resolved_ips = []

    if not peer_ip:
        resolved_ips = resolve_host(target_host)
        if not resolved_ips:
            warnings.append("Имя узла не разрешается в IPv4-адрес.")
        else:
            peer_ip = resolved_ips[0]

    if looks_like_same_lan(profile.ipv4_addresses, peer_ip) is False:
        warnings.append("Пир не похож на узел из той же локальной подсети (эвристика по первым трем октетам).")

    if not peer_ip:
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
        )

    callback_token = secrets.token_hex(8)
    payload = {
        "hostname": profile.hostname,
        "fqdn": profile.fqdn,
        "ipv4_addresses": profile.ipv4_addresses,
        "callback_port": callback_port,
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        detail = f"{exc.__class__.__name__}: {exc}"
        warnings.append("TCP/HTTP соединение до пира не установлено. Проверьте firewall, порт и доступность хоста.")
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
        )
    except OSError as exc:
        detail = f"{exc.__class__.__name__}: {exc}"
        warnings.append("Соединение до пира завершилось ошибкой сокета.")
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
        )

    reverse_payload = response_payload.get("reverse_result") or {}
    reverse_ok = bool(reverse_payload.get("ok"))
    reverse_detail = reverse_payload.get("detail", "Пир не вернул результат обратной проверки.")

    if not reverse_ok:
        warnings.append("Пир не смог подключиться обратно к этому компьютеру. Возможна блокировка входящих подключений.")

    local_name_resolution_ok = response_payload.get("name_resolution_ok")
    if local_name_resolution_ok is False:
        warnings.append("Пир не смог сопоставить имя этого компьютера с адресом входящего соединения.")

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
    )


def render_text_report(profile: LocalProfile, discovered_peers: List[Dict[str, object]], results: List[PeerProbeResult]) -> str:
    lines = []
    lines.append(f"{APP_NAME} {APP_VERSION}")
    lines.append("=" * 60)
    lines.append("Локальный компьютер:")
    lines.append(f"  Hostname: {profile.hostname}")
    lines.append(f"  FQDN: {profile.fqdn}")
    lines.append(f"  Platform: {profile.platform}")
    lines.append(f"  Python: {profile.python_version}")
    lines.append(f"  IPv4: {', '.join(profile.ipv4_addresses)}")
    lines.append("")

    lines.append("Обнаруженные узлы:")
    if discovered_peers:
        for peer in discovered_peers:
            lines.append(
                f"  - {peer.get('hostname', 'unknown')} @ {peer.get('source_ip', 'unknown')}:{peer.get('http_port', '?')}"
            )
    else:
        lines.append("  - Ничего не найдено по UDP broadcast. Это может означать другой сегмент сети или блокировку UDP broadcast.")
    lines.append("")

    if not results:
        lines.append("Проверки не выполнены: не найден peer и не указан параметр --peer.")
        return "\n".join(lines)

    for index, result in enumerate(results, start=1):
        lines.append(f"Проверка #{index}: {result.peer_host}")
        lines.append(f"  Peer IPv4: {result.peer_ip or 'unknown'}")
        if result.resolved_ips:
            lines.append(f"  Resolved IPv4: {', '.join(result.resolved_ips)}")
        lines.append(f"  Direct HTTP: {'OK' if result.http_ok else 'FAIL'} ({result.connect_detail})")
        lines.append(f"  Reverse callback: {'OK' if result.reverse_ok else 'FAIL'} ({result.reverse_detail})")
        if result.local_name_resolution_ok is None:
            lines.append("  Name resolution on peer: not checked")
        else:
            lines.append(
                f"  Name resolution on peer: {'OK' if result.local_name_resolution_ok else 'FAIL'}"
            )
        if result.observed_by_peer_as:
            lines.append(f"  Peer saw this host as: {result.observed_by_peer_as}")
        if result.remote_profile:
            remote_name = result.remote_profile.get("hostname", "unknown")
            remote_ips = result.remote_profile.get("ipv4_addresses", [])
            lines.append(f"  Remote hostname: {remote_name}")
            lines.append(f"  Remote IPv4: {', '.join(remote_ips) if isinstance(remote_ips, list) else remote_ips}")
        if result.warnings:
            lines.append("  Findings:")
            for warning in result.warnings:
                lines.append(f"    - {warning}")
        else:
            lines.append("  Findings:")
            lines.append("    - Критичных проблем по базовым TCP/HTTP проверкам не найдено.")
        lines.append("")

    lines.append("Подсказки:")
    lines.append("  - Если direct HTTP не проходит, проверьте firewall и доступность TCP-порта приложения.")
    lines.append("  - Если reverse callback не проходит, обычно блокируются входящие подключения на локальном ПК.")
    lines.append("  - Если имя не разрешается, попробуйте запуск с --peer <IP> и отдельно проверьте DNS/NetBIOS.")
    lines.append("  - Если узел не находится через broadcast, компьютеры могут быть в разных VLAN/подсетях.")
    return "\n".join(lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Двусторонняя диагностика сети между двумя компьютерами без внешних зависимостей."
    )
    parser.add_argument("--peer", help="Имя хоста или IPv4 адрес второго компьютера.")
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT, help="TCP-порт встроенного HTTP-сервиса.")
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
        help="Таймаут HTTP/TCP-подключения к пиру.",
    )
    parser.add_argument(
        "--session",
        default="default",
        help="Логическое имя сеанса, чтобы два ПК искали только друг друга.",
    )
    parser.add_argument("--json", action="store_true", help="Вывести отчет в JSON вместо текста.")
    return parser.parse_args(argv)


def run(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    profile = build_local_profile()
    instance_id = secrets.token_hex(8)
    state = ServerState(profile, args.port, args.session, instance_id)
    stop_event = threading.Event()

    try:
        http_server, _thread = start_http_server(state)
    except OSError as exc:
        print(f"Не удалось открыть TCP-порт {args.port}: {exc}", file=sys.stderr)
        return 2

    responder = DiscoveryResponder(state, args.discovery_port, stop_event)
    responder.start()

    try:
        time.sleep(0.2)
        discovered_peers = discover_peers(state, args.discovery_port, args.discovery_timeout)
        targets = choose_peer_targets(args, discovered_peers)
        results = [
            probe_peer(target["host"], target["port"], profile, args.port, args.connect_timeout)
            for target in targets
        ]

        if args.json:
            output = {
                "app": APP_NAME,
                "version": APP_VERSION,
                "profile": asdict(profile),
                "discovered_peers": discovered_peers,
                "results": [asdict(result) for result in results],
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(render_text_report(profile, discovered_peers, results))
        return 0
    finally:
        stop_event.set()
        http_server.shutdown()
        http_server.server_close()


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
