try:
    from .netdiag_gui import launch_gui
except ImportError:
    from netdiag_gui import launch_gui


if __name__ == "__main__":
    raise SystemExit(launch_gui())
