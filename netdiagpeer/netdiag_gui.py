from __future__ import annotations

import platform
import queue
import threading
from typing import Optional

from netdiag_core import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_DISCOVERY_PORT,
    DEFAULT_DISCOVERY_TIMEOUT,
    DEFAULT_HTTP_PORT,
    DEFAULT_LINGER,
    DEFAULT_STARTUP_DELAY,
    DEFAULT_SAVE_FORMAT,
    DiagnosticReport,
    DiscoveryReport,
    RuntimeOptions,
    discover_only,
    render_text_report,
    run_diagnostics,
    save_report_to_path,
)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    TKINTER_IMPORT_ERROR: Optional[Exception] = None
except ModuleNotFoundError as exc:
    tk = None
    filedialog = None
    messagebox = None
    scrolledtext = None
    ttk = None
    TKINTER_IMPORT_ERROR = exc


class NetDiagGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("NetDiagPeer")
        self.root.geometry("980x760")

        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.current_report: Optional[DiagnosticReport] = None
        self.current_discovery_report: Optional[DiscoveryReport] = None
        self.current_text_report = ""
        self.discovered_peers: list[dict[str, object]] = []

        self.peer_var = tk.StringVar()
        self.port_var = tk.StringVar(value=str(DEFAULT_HTTP_PORT))
        self.peer_port_var = tk.StringVar()
        self.discovery_port_var = tk.StringVar(value=str(DEFAULT_DISCOVERY_PORT))
        self.discovery_timeout_var = tk.StringVar(value=str(DEFAULT_DISCOVERY_TIMEOUT))
        self.connect_timeout_var = tk.StringVar(value=str(DEFAULT_CONNECT_TIMEOUT))
        self.startup_delay_var = tk.StringVar(value=str(DEFAULT_STARTUP_DELAY))
        self.linger_var = tk.StringVar(value=str(DEFAULT_LINGER))
        self.session_var = tk.StringVar(value="default")
        self.save_path_var = tk.StringVar()
        self.save_format_var = tk.StringVar(value=DEFAULT_SAVE_FORMAT)
        self.windows_mode_var = tk.BooleanVar(value=platform.system() == "Windows")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_layout()
        self.root.after(100, self._poll_queue)

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        fields = [
            ("Peer hostname/IP", self.peer_var, 0, 0),
            ("Session", self.session_var, 0, 2),
            ("Local HTTP port", self.port_var, 1, 0),
            ("Peer HTTP port", self.peer_port_var, 1, 2),
            ("Discovery UDP port", self.discovery_port_var, 2, 0),
            ("Discovery timeout", self.discovery_timeout_var, 2, 2),
            ("Connect timeout", self.connect_timeout_var, 3, 0),
            ("Startup delay", self.startup_delay_var, 3, 2),
            ("Linger after report", self.linger_var, 4, 0),
        ]

        for label_text, variable, row, column in fields:
            ttk.Label(top, text=label_text).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(top, textvariable=variable).grid(row=row, column=column + 1, sticky="ew", pady=4)

        options_frame = ttk.Frame(top)
        options_frame.grid(row=4, column=2, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(
            options_frame,
            text="Enable Windows diagnostics (ping / SMB / net view / NetBIOS)",
            variable=self.windows_mode_var,
        ).grid(row=0, column=0, sticky="w")

        save_frame = ttk.LabelFrame(top, text="Report saving", padding=8)
        save_frame.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        save_frame.columnconfigure(1, weight=1)

        ttk.Label(save_frame, text="Path").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(save_frame, textvariable=self.save_path_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(save_frame, text="Browse...", command=self._browse_save_path).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(save_frame, text="Format").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            save_frame,
            textvariable=self.save_format_var,
            values=("auto", "text", "json"),
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", pady=4)

        button_frame = ttk.Frame(top)
        button_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        button_frame.columnconfigure(5, weight=1)

        self.search_button = ttk.Button(button_frame, text="Search peers", command=self._search_peers)
        self.search_button.grid(row=0, column=0, padx=(0, 8))
        self.run_button = ttk.Button(button_frame, text="Run diagnostics", command=self._run_diagnostics)
        self.run_button.grid(row=0, column=1, padx=(0, 8))
        self.use_selected_button = ttk.Button(button_frame, text="Use selected peer", command=self._use_selected_peer)
        self.use_selected_button.grid(row=0, column=2, padx=(0, 8))
        ttk.Button(button_frame, text="Save current report", command=self._save_current_report).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(button_frame, text="Clear output", command=self._clear_output).grid(row=0, column=4, padx=(0, 8))
        ttk.Label(button_frame, textvariable=self.status_var).grid(row=0, column=5, sticky="e")

        output_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        output_frame.grid(row=1, column=0, sticky="nsew")
        output_frame.rowconfigure(1, weight=1)
        output_frame.columnconfigure(0, weight=1)

        peers_frame = ttk.LabelFrame(output_frame, text="Discovered peers", padding=8)
        peers_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        peers_frame.columnconfigure(0, weight=1)
        peers_frame.rowconfigure(0, weight=1)

        self.peers_table = ttk.Treeview(
            peers_frame,
            columns=("hostname", "source_ip", "http_port", "ipv4_addresses"),
            show="headings",
            height=6,
        )
        self.peers_table.heading("hostname", text="Hostname")
        self.peers_table.heading("source_ip", text="Source IP")
        self.peers_table.heading("http_port", text="HTTP port")
        self.peers_table.heading("ipv4_addresses", text="Reported IPv4")
        self.peers_table.column("hostname", width=180, anchor="w")
        self.peers_table.column("source_ip", width=140, anchor="w")
        self.peers_table.column("http_port", width=90, anchor="center")
        self.peers_table.column("ipv4_addresses", width=420, anchor="w")
        self.peers_table.grid(row=0, column=0, sticky="nsew")
        self.peers_table.bind("<Double-1>", self._on_peer_double_click)

        peers_scrollbar = ttk.Scrollbar(peers_frame, orient="vertical", command=self.peers_table.yview)
        peers_scrollbar.grid(row=0, column=1, sticky="ns")
        self.peers_table.configure(yscrollcommand=peers_scrollbar.set)

        ttk.Label(
            peers_frame,
            text="Double-click a row or use 'Use selected peer' to copy the peer IP and HTTP port into the form.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.output.grid(row=1, column=0, sticky="nsew")

    def _browse_save_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save diagnostic report",
            defaultextension=".txt",
            filetypes=(
                ("Text report", "*.txt"),
                ("JSON report", "*.json"),
                ("All files", "*.*"),
            ),
        )
        if path:
            self.save_path_var.set(path)

    def _append_output(self, text: str) -> None:
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def _clear_output(self) -> None:
        self.output.delete("1.0", tk.END)
        self.current_report = None
        self.current_text_report = ""
        self.status_var.set("Output cleared.")

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.run_button.config(state=state)
        self.search_button.config(state=state)
        self.use_selected_button.config(state=state)

    def _refresh_peers_table(self, peers: list[dict[str, object]]) -> None:
        self.discovered_peers = peers
        for item_id in self.peers_table.get_children():
            self.peers_table.delete(item_id)

        for index, peer in enumerate(peers):
            hostname = str(peer.get("hostname", "unknown"))
            source_ip = str(peer.get("source_ip", ""))
            http_port = str(peer.get("http_port", ""))
            ipv4_addresses = peer.get("ipv4_addresses", [])
            if isinstance(ipv4_addresses, list):
                reported_ipv4 = ", ".join(str(value) for value in ipv4_addresses)
            else:
                reported_ipv4 = str(ipv4_addresses)
            self.peers_table.insert(
                "",
                "end",
                iid=f"peer-{index}",
                values=(hostname, source_ip, http_port, reported_ipv4),
            )

    def _selected_peer(self) -> Optional[dict[str, object]]:
        selection = self.peers_table.selection()
        if not selection:
            return None

        selected_id = selection[0]
        try:
            index = int(selected_id.split("-", 1)[1])
        except (IndexError, ValueError):
            return None
        if index < 0 or index >= len(self.discovered_peers):
            return None
        return self.discovered_peers[index]

    def _apply_selected_peer(self) -> bool:
        peer = self._selected_peer()
        if not peer:
            return False

        source_ip = str(peer.get("source_ip", "")).strip()
        hostname = str(peer.get("hostname", "")).strip()
        peer_value = source_ip or hostname
        if not peer_value:
            return False

        self.peer_var.set(peer_value)
        http_port = peer.get("http_port")
        if http_port is not None:
            self.peer_port_var.set(str(http_port))

        self.status_var.set(f"Selected peer {peer_value}")
        return True

    def _use_selected_peer(self) -> None:
        if not self._apply_selected_peer():
            messagebox.showinfo("NetDiagPeer", "Select a discovered peer first.")

    def _on_peer_double_click(self, _event: object) -> None:
        self._apply_selected_peer()

    def _collect_options(self) -> RuntimeOptions:
        try:
            port = int(self.port_var.get().strip())
            discovery_port = int(self.discovery_port_var.get().strip())
            discovery_timeout = float(self.discovery_timeout_var.get().strip())
            connect_timeout = float(self.connect_timeout_var.get().strip())
            startup_delay = float(self.startup_delay_var.get().strip())
            linger = float(self.linger_var.get().strip())
        except ValueError as exc:
            raise ValueError("Ports must be integers and timeout values must be numeric.") from exc

        peer_text = self.peer_var.get().strip() or None
        peer_port_text = self.peer_port_var.get().strip()
        peer_port = int(peer_port_text) if peer_port_text else None
        session = self.session_var.get().strip() or "default"
        save_path = self.save_path_var.get().strip() or None

        return RuntimeOptions(
            peer=peer_text,
            port=port,
            peer_port=peer_port,
            discovery_port=discovery_port,
            discovery_timeout=discovery_timeout,
            connect_timeout=connect_timeout,
            startup_delay=startup_delay,
            linger=linger,
            session=session,
            save_report=save_path,
            save_format=self.save_format_var.get().strip() or DEFAULT_SAVE_FORMAT,
            windows_mode=self.windows_mode_var.get(),
        )

    def _run_diagnostics(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("NetDiagPeer", "Diagnostics are already running.")
            return

        try:
            options = self._collect_options()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        self._set_busy(True)
        self.status_var.set("Running diagnostics...")
        self._append_output("Running diagnostics...\n")

        def worker() -> None:
            try:
                report = run_diagnostics(options)
                text_report = render_text_report(report)
                saved_path = None
                if options.save_report:
                    saved_path = save_report_to_path(report, text_report, options.save_report, options.save_format)
                self.queue.put(("diagnostics_success", (report, text_report, saved_path)))
            except Exception as exc:
                self.queue.put(("error", exc))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _search_peers(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("NetDiagPeer", "Diagnostics or discovery is already running.")
            return

        try:
            options = self._collect_options()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        self._set_busy(True)
        self.status_var.set("Searching for peers...")
        self._append_output("Searching for peers...\n")

        def worker() -> None:
            try:
                discovery_report = discover_only(options)
                self.queue.put(("discovery_success", discovery_report))
            except Exception as exc:
                self.queue.put(("error", exc))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "diagnostics_success":
                    report, text_report, saved_path = payload
                    self.current_report = report
                    self.current_text_report = text_report
                    self.current_discovery_report = None
                    self._refresh_peers_table(report.discovered_peers)
                    self._append_output(text_report)
                    if saved_path:
                        self.status_var.set(f"Diagnostics complete. Saved to {saved_path}")
                    else:
                        self.status_var.set("Diagnostics complete.")
                elif kind == "discovery_success":
                    discovery_report = payload
                    self.current_discovery_report = discovery_report
                    self._refresh_peers_table(discovery_report.discovered_peers)
                    self.current_report = None
                    self.current_text_report = ""
                    if discovery_report.discovered_peers:
                        self._append_output(
                            f"Discovered {len(discovery_report.discovered_peers)} peer(s).\n"
                            "Double-click a row to use it for diagnostics.\n"
                        )
                        self.status_var.set(
                            f"Found {len(discovery_report.discovered_peers)} peer(s). Double-click a row to select one."
                        )
                    else:
                        self._append_output("No peers discovered for the current session.\n")
                        self.status_var.set("No peers found for the current session.")
                else:
                    self.status_var.set("Diagnostics failed.")
                    messagebox.showerror("Diagnostics failed", str(payload))
                self._set_busy(False)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _save_current_report(self) -> None:
        if not self.current_report or not self.current_text_report:
            messagebox.showinfo("NetDiagPeer", "No report is available yet.")
            return

        path = self.save_path_var.get().strip()
        if not path:
            self._browse_save_path()
            path = self.save_path_var.get().strip()
            if not path:
                return

        try:
            saved_path = save_report_to_path(
                self.current_report,
                self.current_text_report,
                path,
                self.save_format_var.get().strip() or DEFAULT_SAVE_FORMAT,
            )
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        self.status_var.set(f"Report saved to {saved_path}")
        messagebox.showinfo("NetDiagPeer", f"Report saved to:\n{saved_path}")


def launch_gui() -> int:
    if TKINTER_IMPORT_ERROR is not None or tk is None:
        raise RuntimeError(
            "Tkinter is not available in this Python environment. "
            "Install the Tk/Tcl package for Python and try again."
        ) from TKINTER_IMPORT_ERROR

    root = tk.Tk()
    NetDiagGui(root)
    root.mainloop()
    return 0
