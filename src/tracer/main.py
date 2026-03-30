import multiprocessing
from pathlib import Path
import sys

from tracer.cli import run_cli, should_run_cli


def main() -> int:
    multiprocessing.freeze_support()
    executable_name = Path(sys.argv[0]).name.lower()
    force_cli_mode = "cli" in executable_name
    if force_cli_mode or should_run_cli(sys.argv):
        exit_code = run_cli(sys.argv[1:])
        if exit_code >= 0:
            return exit_code

    from tracer.app import create_application

    app, window = create_application()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
