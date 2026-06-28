from __future__ import annotations

import platform
import queue
import subprocess
import threading
from typing import Dict, List, Optional

try:
    from .netdiag_core import (
        DEFAULT_HTTP_PORT,
        DEFAULT_SAVE_FORMAT,
        DiagnosticReport,
        DiscoveryReport,
        RuntimeOptions,
        discover_only,
        run_diagnostics,
        save_report_to_path,
    )
except ImportError:
    from netdiag_core import (
        DEFAULT_HTTP_PORT,
        DEFAULT_SAVE_FORMAT,
        DiagnosticReport,
        DiscoveryReport,
        RuntimeOptions,
        discover_only,
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
        self.root.geometry("860x620")

        self.queue = queue.Queue()
        self.worker = None  # type: Optional[threading.Thread]
        self.current_report = None  # type: Optional[DiagnosticReport]
        self.current_discovery_report = None  # type: Optional[DiscoveryReport]
        self.current_text_report = ""
        self.discovered_peers = []  # type: List[Dict[str, object]]

        self.settings_window = None  # type: Optional[tk.Toplevel]
        self.settings_peers_table = None
        self.settings_status_var = tk.StringVar(value="")
        self.search_button = None
        self.use_selected_button = None

        self.peer_var = tk.StringVar()
        self.peer_port_var = tk.StringVar()
        self.session_var = tk.StringVar(value="default")
        self.save_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Готово к проверке.")

        self._build_layout()
        self.root.after(100, self._poll_queue)

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        style = ttk.Style()
        style.configure("Primary.TButton", font=("Segoe UI", 12, "bold"))

        header = ttk.Frame(self.root, padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Проверка сети между Windows 7 и Windows 10",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                "Запустите программу на обоих компьютерах и нажмите кнопку ниже. "
                "Если приложение найдет ошибки, они появятся в журнале."
            ),
            wraplength=780,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 16))

        button_frame = ttk.Frame(header)
        button_frame.grid(row=2, column=0, sticky="ew")
        button_frame.columnconfigure(3, weight=1)

        self.run_button = ttk.Button(
            button_frame,
            text="Проверить подключение",
            command=self._run_diagnostics,
            style="Primary.TButton",
        )
        self.run_button.grid(row=0, column=0, padx=(0, 10))

        self.settings_button = ttk.Button(
            button_frame,
            text="Дополнительные настройки",
            command=self._open_settings_window,
        )
        self.settings_button.grid(row=0, column=1, padx=(0, 10))

        self.save_button = ttk.Button(
            button_frame,
            text="Сохранить лог",
            command=self._save_current_report,
        )
        self.save_button.grid(row=0, column=2)

        ttk.Label(header, textvariable=self.status_var).grid(row=3, column=0, sticky="w", pady=(12, 0))

        output_frame = ttk.Frame(self.root, padding=(16, 0, 16, 16))
        output_frame.grid(row=1, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        log_frame = ttk.LabelFrame(output_frame, text="Журнал ошибок и подсказок", padding=10)
        log_frame.grid(row=0, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.output = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.output.grid(row=0, column=0, sticky="nsew")
        self.output.insert(
            tk.END,
            "1. Запустите программу на двух компьютерах.\n"
            "2. Нажмите «Проверить подключение».\n"
            "3. Если возникнут проблемы, они появятся здесь.\n",
        )
        self.output.configure(state=tk.DISABLED)

    def _open_settings_window(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.focus_set()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Дополнительные настройки")
        self.settings_window.geometry("860x620")
        self.settings_window.transient(self.root)
        self.settings_window.protocol("WM_DELETE_WINDOW", self._close_settings_window)
        self.settings_window.columnconfigure(0, weight=1)
        self.settings_window.rowconfigure(2, weight=1)

        header = ttk.Frame(self.settings_window, padding=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(
            header,
            text="Здесь можно вручную указать второй компьютер или открыть сетевые настройки Windows.",
            wraplength=780,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(header, text="IP или имя второго компьютера").grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(header, textvariable=self.peer_var).grid(row=1, column=1, sticky="ew")
        ttk.Button(header, text="Очистить", command=lambda: self.peer_var.set("")).grid(row=1, column=2, padx=(8, 0))

        save_frame = ttk.LabelFrame(self.settings_window, text="Сохранение лога", padding=12)
        save_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        save_frame.columnconfigure(1, weight=1)

        ttk.Label(save_frame, text="Файл для сохранения").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(save_frame, textvariable=self.save_path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(save_frame, text="Обзор...", command=self._browse_save_path).grid(row=0, column=2, padx=(8, 0))

        body = ttk.Frame(self.settings_window, padding=(12, 0, 12, 12))
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        peers_frame = ttk.LabelFrame(body, text="Найденные компьютеры", padding=10)
        peers_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        peers_frame.columnconfigure(0, weight=1)
        peers_frame.rowconfigure(1, weight=1)

        ttk.Label(
            peers_frame,
            text="Если адрес второго ПК неизвестен, нажмите «Найти компьютеры».",
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.settings_peers_table = ttk.Treeview(
            peers_frame,
            columns=("hostname", "source_ip", "http_port"),
            show="headings",
            height=10,
        )
        self.settings_peers_table.heading("hostname", text="Компьютер")
        self.settings_peers_table.heading("source_ip", text="IP")
        self.settings_peers_table.heading("http_port", text="Порт")
        self.settings_peers_table.column("hostname", width=160, anchor="w")
        self.settings_peers_table.column("source_ip", width=130, anchor="w")
        self.settings_peers_table.column("http_port", width=70, anchor="center")
        self.settings_peers_table.grid(row=1, column=0, sticky="nsew")
        self.settings_peers_table.bind("<Double-1>", self._on_peer_double_click)

        peers_scrollbar = ttk.Scrollbar(peers_frame, orient="vertical", command=self.settings_peers_table.yview)
        peers_scrollbar.grid(row=1, column=1, sticky="ns")
        self.settings_peers_table.configure(yscrollcommand=peers_scrollbar.set)

        peer_buttons = ttk.Frame(peers_frame)
        peer_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.search_button = ttk.Button(peer_buttons, text="Найти компьютеры", command=self._search_peers)
        self.search_button.grid(row=0, column=0, padx=(0, 8))
        self.use_selected_button = ttk.Button(
            peer_buttons,
            text="Использовать выбранный",
            command=self._use_selected_peer,
        )
        self.use_selected_button.grid(row=0, column=1)
        ttk.Label(peers_frame, textvariable=self.settings_status_var).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )

        actions_frame = ttk.LabelFrame(body, text="Изменение сетевых настроек Windows", padding=10)
        actions_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        actions_frame.columnconfigure(0, weight=1)
        actions_frame.columnconfigure(1, weight=1)

        ttk.Label(
            actions_frame,
            text=(
                "Эти кнопки помогут открыть стандартные окна Windows или включить "
                "сетевое обнаружение и общий доступ."
            ),
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        actions = [
            ("Открыть центр управления сетями", self._open_network_center),
            ("Открыть сетевые адаптеры", self._open_network_adapters),
            ("Включить сетевое обнаружение", self._enable_network_discovery),
            ("Включить общий доступ к файлам", self._enable_file_sharing),
            ("Открыть брандмауэр", self._open_firewall),
            ("Открыть службы", self._open_services),
        ]
        for index, (title, callback) in enumerate(actions, start=1):
            row = ((index - 1) // 2) + 1
            column = (index - 1) % 2
            ttk.Button(actions_frame, text=title, command=callback).grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 6 if column == 0 else 0),
                pady=6,
            )

        self._refresh_peers_table(self.discovered_peers)
        self._set_busy(self.worker is not None and self.worker.is_alive())

    def _close_settings_window(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        self.settings_window = None
        self.settings_peers_table = None
        self.settings_status_var.set("")

    def _browse_save_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить лог проверки",
            defaultextension=".txt",
            filetypes=(("Text report", "*.txt"), ("JSON report", "*.json"), ("All files", "*.*")),
        )
        if path:
            self.save_path_var.set(path)

    def _set_output_text(self, text: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _append_log_line(self, text: str) -> None:
        self.output.configure(state=tk.NORMAL)
        if self.output.get("1.0", tk.END).strip():
            self.output.insert(tk.END, "\n")
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _clear_output(self) -> None:
        self.current_report = None
        self.current_text_report = ""
        self._set_output_text("")
        self.status_var.set("Журнал очищен.")

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.run_button.config(state=state)
        self.settings_button.config(state=state)
        self.save_button.config(state=state)
        if self.search_button is not None:
            self.search_button.config(state=state)
        if self.use_selected_button is not None:
            self.use_selected_button.config(state=state)

    def _refresh_peers_table(self, peers: List[Dict[str, object]]) -> None:
        self.discovered_peers = peers
        if not self.settings_peers_table:
            return

        for item_id in self.settings_peers_table.get_children():
            self.settings_peers_table.delete(item_id)

        for index, peer in enumerate(peers):
            self.settings_peers_table.insert(
                "",
                "end",
                iid="peer-{0}".format(index),
                values=(
                    str(peer.get("hostname", "unknown")),
                    str(peer.get("source_ip", "")),
                    str(peer.get("http_port", "")),
                ),
            )

    def _selected_peer(self) -> Optional[Dict[str, object]]:
        if not self.settings_peers_table:
            return None

        selection = self.settings_peers_table.selection()
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
        self.peer_var.set(source_ip or hostname)
        http_port = peer.get("http_port")
        self.peer_port_var.set(str(http_port) if http_port is not None else "")
        self.status_var.set("Выбран второй компьютер: {0}".format(self.peer_var.get()))
        self.settings_status_var.set("Выбран компьютер: {0}".format(self.peer_var.get()))
        return True

    def _use_selected_peer(self) -> None:
        if not self._apply_selected_peer():
            messagebox.showinfo("NetDiagPeer", "Сначала выберите компьютер из списка.")

    def _on_peer_double_click(self, _event: object) -> None:
        self._apply_selected_peer()

    def _collect_options(self) -> RuntimeOptions:
        peer_text = self.peer_var.get().strip() or None
        peer_port_text = self.peer_port_var.get().strip()
        peer_port = int(peer_port_text) if peer_port_text else None
        save_path = self.save_path_var.get().strip() or None

        return RuntimeOptions(
            peer=peer_text,
            port=DEFAULT_HTTP_PORT,
            peer_port=peer_port,
            discovery_port=DEFAULT_HTTP_PORT + 1,
            discovery_timeout=5.0,
            connect_timeout=3.0,
            startup_delay=2.0,
            linger=2.0,
            session=self.session_var.get().strip() or "default",
            save_report=save_path,
            save_format=DEFAULT_SAVE_FORMAT,
            windows_mode=True,
        )

    def _format_gui_report(self, report: DiagnosticReport) -> str:
        lines = []  # type: List[str]
        problems = []  # type: List[str]

        if not report.results:
            lines.append("Ошибка: не удалось проверить второй компьютер.")
            if report.settings.peer:
                lines.append("- Проверьте правильность IP или имени второго компьютера: {0}".format(report.settings.peer))
                lines.append("- Убедитесь, что на втором компьютере тоже запущено это приложение.")
            else:
                lines.append("- Второй компьютер не найден автоматически.")
                lines.append("- Запустите программу на втором компьютере и нажмите «Проверить подключение».")
                lines.append("- Если не помогает, откройте «Дополнительные настройки» и укажите IP вручную.")
            if not report.discovered_peers:
                lines.append("- Возможно, сетевое обнаружение отключено или брандмауэр блокирует доступ.")
            return "\n".join(lines)

        for result in report.results:
            peer_name = result.peer_host
            if result.remote_profile and result.remote_profile.get("hostname"):
                peer_name = str(result.remote_profile.get("hostname"))

            peer_problems = []  # type: List[str]
            if not result.http_ok:
                peer_problems.append("нет прямого подключения к {0}".format(peer_name))
            if not result.reverse_ok:
                peer_problems.append("второй компьютер {0} не может подключиться обратно".format(peer_name))
            if result.local_name_resolution_ok is False:
                peer_problems.append("имя этого компьютера не разрешается на втором ПК")

            for warning in result.warnings:
                if warning not in peer_problems:
                    peer_problems.append(warning)

            for check in result.windows_checks:
                if check.skipped or check.ok:
                    continue
                mapped_message = self._map_windows_check_to_message(check.name)
                if mapped_message not in peer_problems:
                    peer_problems.append(mapped_message)

            if peer_problems:
                problems.append("[{0}]".format(peer_name))
                for item in peer_problems:
                    problems.append("- {0}".format(item))

        if problems:
            lines.append("Найдены проблемы с подключением:")
            lines.extend(problems)
            lines.append("")
            lines.append("Попробуйте открыть «Дополнительные настройки» и включить сетевое обнаружение и общий доступ.")
        else:
            lines.append("Ошибок не найдено.")
            lines.append("Подключение между компьютерами выглядит рабочим.")

        return "\n".join(lines)

    def _map_windows_check_to_message(self, check_name: str) -> str:
        mapping = {
            "Ping": "команда Ping не проходит",
            "SMB TCP 445": "порт 445 (SMB) недоступен",
            "NetBIOS Session TCP 139": "порт 139 (NetBIOS) недоступен",
            "net view": "Windows не смог получить сетевые общие ресурсы",
            "nbtstat -A": "NetBIOS по IP не отвечает",
            "nbtstat -a": "NetBIOS по имени не отвечает",
        }
        return mapping.get(check_name, "{0}: ошибка".format(check_name))

    def _run_diagnostics(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("NetDiagPeer", "Проверка уже выполняется.")
            return

        options = self._collect_options()
        self._set_busy(True)
        self.status_var.set("Идет проверка подключения...")
        self._set_output_text("Идет проверка подключения...\nПодождите несколько секунд.")

        def worker() -> None:
            try:
                report = run_diagnostics(options)
                text_report = self._format_gui_report(report)
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
            messagebox.showinfo("NetDiagPeer", "Сейчас уже выполняется проверка или поиск.")
            return

        options = self._collect_options()
        self._set_busy(True)
        self.status_var.set("Поиск компьютеров...")
        self.settings_status_var.set("Поиск компьютеров...")

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
                    self._set_output_text(text_report)
                    if saved_path:
                        self.status_var.set("Проверка завершена. Лог сохранен в {0}".format(saved_path))
                    else:
                        self.status_var.set("Проверка завершена.")
                elif kind == "discovery_success":
                    discovery_report = payload
                    self.current_discovery_report = discovery_report
                    self._refresh_peers_table(discovery_report.discovered_peers)
                    if discovery_report.discovered_peers:
                        self.settings_status_var.set(
                            "Найдено компьютеров: {0}. Выберите нужный компьютер из списка.".format(
                                len(discovery_report.discovered_peers)
                            )
                        )
                        self.status_var.set("Поиск завершен. Компьютеры найдены.")
                    else:
                        self.settings_status_var.set("Компьютеры не найдены.")
                        self.status_var.set("Поиск завершен. Компьютеры не найдены.")
                else:
                    self.status_var.set("Проверка завершилась ошибкой.")
                    messagebox.showerror("NetDiagPeer", str(payload))
                self._set_busy(False)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _save_current_report(self) -> None:
        if not self.current_report or not self.current_text_report:
            messagebox.showinfo("NetDiagPeer", "Сначала выполните проверку подключения.")
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
                DEFAULT_SAVE_FORMAT,
            )
        except Exception as exc:
            messagebox.showerror("NetDiagPeer", str(exc))
            return

        self.status_var.set("Лог сохранен в {0}".format(saved_path))
        messagebox.showinfo("NetDiagPeer", "Лог сохранен:\n{0}".format(saved_path))

    def _ensure_windows(self) -> bool:
        if platform.system() == "Windows":
            return True
        messagebox.showinfo("NetDiagPeer", "Эта кнопка работает только на Windows.")
        return False

    def _launch_windows_target(self, command: str, success_message: str) -> None:
        if not self._ensure_windows():
            return
        try:
            subprocess.Popen(command, shell=True)
        except OSError as exc:
            messagebox.showerror("NetDiagPeer", str(exc))
            return
        self.status_var.set(success_message)
        self._append_log_line(success_message)

    def _run_windows_command(self, command: List[str], success_message: str, failure_message: str) -> None:
        if not self._ensure_windows():
            return

        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=15,
            )
        except OSError as exc:
            messagebox.showerror("NetDiagPeer", str(exc))
            return

        if completed.returncode == 0:
            self.status_var.set(success_message)
            self._append_log_line(success_message)
            return

        output = completed.stdout.strip()
        details = failure_message
        if output:
            details = "{0}\n{1}".format(failure_message, output)
        self.status_var.set("Команда Windows завершилась с ошибкой.")
        self._append_log_line(details)
        messagebox.showwarning("NetDiagPeer", details)

    def _open_network_center(self) -> None:
        self._launch_windows_target(
            'control.exe /name Microsoft.NetworkAndSharingCenter',
            "Открыт центр управления сетями и общим доступом.",
        )

    def _open_network_adapters(self) -> None:
        self._launch_windows_target(
            "control.exe ncpa.cpl",
            "Открыт список сетевых адаптеров.",
        )

    def _open_firewall(self) -> None:
        self._launch_windows_target(
            'control.exe /name Microsoft.WindowsFirewall',
            "Открыт брандмауэр Windows.",
        )

    def _open_services(self) -> None:
        self._launch_windows_target(
            "services.msc",
            "Открыт список служб Windows.",
        )

    def _enable_network_discovery(self) -> None:
        self._run_windows_command(
            ["netsh", "advfirewall", "firewall", "set", "rule", 'group="Network Discovery"', "new", "enable=Yes"],
            "Сетевое обнаружение включено или уже было включено.",
            "Не удалось включить сетевое обнаружение. Возможно, нужны права администратора.",
        )

    def _enable_file_sharing(self) -> None:
        self._run_windows_command(
            ["netsh", "advfirewall", "firewall", "set", "rule", 'group="File and Printer Sharing"', "new", "enable=Yes"],
            "Общий доступ к файлам и принтерам включен или уже был включен.",
            "Не удалось включить общий доступ к файлам и принтерам. Возможно, нужны права администратора.",
        )


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
