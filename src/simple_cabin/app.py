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
        from simple_cabin.core import remote_server

        checks["phone remote"] = b"Cabin Remote" in remote_server._page() and bool(remote_server.qr_matrix("http://x/"))
    except Exception:
        checks["phone remote"] = False
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


def sound_test() -> int:
    """`Simple-Cabin --sound-test`: report the audio output and play each
    kind of sound in turn (for when something can't be heard)."""
    from pathlib import Path

    from platformdirs import user_cache_dir
    from PySide6.QtCore import QCoreApplication, QTimer

    from simple_cabin.gui.audio import AudioEngine

    app = QCoreApplication(sys.argv)
    audio = AudioEngine(Path(user_cache_dir("Simple-Cabin")) / "sounds")
    audio.set_volumes(80, 70, 22, 75)

    def say(text: str) -> None:
        print(text, flush=True)

    say(f"Simple-Cabin {__version__} sound test")
    audio.start()
    say(f"  output: {audio.status}")
    say("  you should hear the fire, and the clock ticking every second…")
    steps = [
        (5000, lambda: (say("  …now a quarter-hour chime"), audio._play_chime("quarter_15"))),
        (9000, lambda: (say("  …now distant thunder"), audio.thunder(0))),
        (5000, lambda: say(f"  done: {audio.status}; sink now {audio.state_text()}")),
        (300, lambda: (audio.shutdown(), app.quit())),
    ]
    t = 0
    for delay, fn in steps:
        t += delay
        QTimer.singleShot(t, fn)
    app.exec()
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if "--sound-test" in sys.argv:
        return sound_test()
    if "--remote-test" in sys.argv:
        from simple_cabin.core import remote_check

        return remote_check.main()

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
    window.show_at_start(fullscreen="--fullscreen" in sys.argv)
    code = app.exec()
    log_event(f"event loop finished (code {code})")
    return code


if __name__ == "__main__":
    sys.exit(main())
