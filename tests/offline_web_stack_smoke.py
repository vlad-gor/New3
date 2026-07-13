from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
from pathlib import Path


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def run_django_smoke(base_dir: Path) -> None:
    django_root = base_dir / "django_app"
    package_dir = django_root / "django_smoke"

    write_file(
        package_dir / "__init__.py",
        """
        """,
    )
    write_file(
        package_dir / "settings.py",
        """
        SECRET_KEY = "offline-smoke-secret"
        DEBUG = True
        ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
        ROOT_URLCONF = "django_smoke.urls"
        MIDDLEWARE = []
        INSTALLED_APPS = []
        TEMPLATES = []
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        }
        USE_TZ = True
        """,
    )
    write_file(
        package_dir / "urls.py",
        """
        from django.http import JsonResponse
        from django.urls import path

        def health(request):
            return JsonResponse({"framework": "django", "status": "ok"})

        urlpatterns = [
            path("health/", health),
        ]
        """,
    )

    sys.path.insert(0, str(django_root))
    os.environ["DJANGO_SETTINGS_MODULE"] = "django_smoke.settings"
    try:
        import django

        django.setup()
        from django.core.management import call_command
        from django.test import Client

        call_command("check", verbosity=0)
        client = Client()
        response = client.get("/health/")
        assert response.status_code == 200, response.status_code
        payload = response.json()
        assert payload["framework"] == "django", payload
        assert payload["status"] == "ok", payload
        print("django-smoke=ok")
    finally:
        sys.path.pop(0)
        os.environ.pop("DJANGO_SETTINGS_MODULE", None)


def run_flask_smoke(base_dir: Path) -> None:
    flask_app_path = base_dir / "flask_app.py"
    write_file(
        flask_app_path,
        """
        from flask import Flask, jsonify

        app = Flask(__name__)

        @app.get("/health")
        def health():
            return jsonify({"framework": "flask", "status": "ok"})
        """,
    )

    spec = importlib.util.spec_from_file_location("flask_app", flask_app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    client = module.app.test_client()
    response = client.get("/health")
    assert response.status_code == 200, response.status_code
    payload = response.get_json()
    assert payload["framework"] == "flask", payload
    assert payload["status"] == "ok", payload
    print("flask-smoke=ok")


def wait_for_port(host: str, port: int, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def run_fastapi_smoke(base_dir: Path) -> None:
    fastapi_app_path = base_dir / "fastapi_app.py"
    write_file(
        fastapi_app_path,
        """
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/health")
        def health():
            return {"framework": "fastapi", "status": "ok"}
        """,
    )

    host = "127.0.0.1"
    port = 8123
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "fastapi_app:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=base_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_port(host, port)
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["framework"] == "fastapi", payload
        assert payload["status"] == "ok", payload
        print("fastapi-smoke=ok")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="offline-web-smoke-") as temp_dir:
        base_dir = Path(temp_dir)
        run_django_smoke(base_dir)
        run_flask_smoke(base_dir)
        run_fastapi_smoke(base_dir)
    print("web-stack-smoke=ok")


if __name__ == "__main__":
    main()
