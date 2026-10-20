import sys

from simple_cabin import __version__


def self_test() -> int:
    """`Simple-Cabin --self-test`: checks a built app has everything it
    needs bundled (the release workflow runs this on each OS). Exit code
    0 if so."""
    checks = {}
    try:
        from simple_cabin.core import synth

        checks["sound synthesis"] = len(synth.tick()) > 0 and len(synth.chime("quarter_15")) > 0
    except Exception:
        checks["sound synthesis"] = False
    try:
        from simple_cabin.core import synth

        names = [*synth.RECORDED_BEATS, synth.FIRE_FILE]
        checks["recordings"] = all((synth.RECORDED_DIR / f"{n}.wav").is_file() for n in names)
    except Exception:
        checks["recordings"] = False
    try:
        from simple_cabin.core import weather

        checks["weather parsing"] = weather.condition_for(63) == weather.RAIN
    except Exception:
        checks["weather parsing"] = False
    if sys.platform.startswith("linux"):
        try:
            import jeepney.io.blocking  # noqa: F401  (keeping the screen awake)

            checks["keep awake"] = True
        except Exception:
            checks["keep awake"] = False
    try:
        import certifi  # noqa: F401

        checks["certificates"] = True
    except Exception:
        checks["certificates"] = False
    report = ", ".join(f"{name}: {'ok' if ok else 'MISSING'}" for name, ok in checks.items())
    try:
        print(f"Simple-Cabin {__version__} self-test — {report}", flush=True)
    except (AttributeError, OSError):  # no console (Windows GUI build)
        pass
    return 0 if all(checks.values()) else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    # Qt is imported only now, so --self-test runs even where there's no
    # display or graphics libraries (the release workflow's build machines).
    from PySide6.QtWidgets import QApplication

    from simple_cabin.core.diagnostics import enable_app_log, enable_crash_log, log_event
    from simple_cabin.gui.main_window import MainWindow

    enable_app_log(__version__)
    enable_crash_log()
    app = QApplication(sys.argv)
    app.setApplicationName("Simple-Cabin")
    app.setDesktopFileName("simple-cabin")
    window = MainWindow()
    window.show()
    code = app.exec()
    log_event(f"event loop finished (code {code})")
    return code


if __name__ == "__main__":
    sys.exit(main())
