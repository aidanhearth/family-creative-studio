"""Bounded child processes. Cancellation terminates each entire tool process group."""
from __future__ import annotations
import os
from pathlib import Path
import signal
import subprocess
import time

class Cancelled(RuntimeError):
    pass

class Runner:
    def __init__(self, store, job, work: Path):
        self.store, self.job, self.work = store, job, work
        from .paths import SOURCES
        from .runtime import browser_executable
        self.env = dict({k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TZ','HOME','USER','LOGNAME','TMPDIR','FONTCONFIG_PATH','XDG_CACHE_HOME','STUDIO_BROWSER','STUDIO_SOURCES','STUDIO_DATA') if k in os.environ}, PYTHONDONTWRITEBYTECODE="1", CADGEN_TELEMETRY="0", DO_NOT_TRACK="1", CADGEN_DAEMON="0", CADGEN_UPDATE_CHECK="0", ARCHIFY_UPDATE_CHECK_DISABLED="1",
            CADGEN_CACHE_DIR=str(store.root / "cad-cache"), CADGEN_DAEMON_STATE_DIR=str(store.root / "cad-daemon"),
            OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")

        # Children run inside a job directory; resolve operator overrides first.
        self.env['STUDIO_SOURCES'] = str(SOURCES)
        self.env['STUDIO_DATA'] = str(store.root.resolve())
        if 'STUDIO_BROWSER' in self.env:
            self.env['STUDIO_BROWSER'] = browser_executable()

    def check(self):
        if self.store.job(self.job['id'])['cancel']:
            raise Cancelled('Render cancelled; previous published results remain available')

    def stage(self, name):
        self.check()
        self.store.update(self.job['id'], stage=name)

    def run(self, args: list[str], *, label: str, timeout=180, cwd=None):
        self.check()
        log = self.work / (label + '.log')
        start = time.monotonic()
        with log.open('wb') as stream:
            proc = subprocess.Popen(['bwrap','--unshare-net','--unshare-pid','--die-with-parent','--bind','/','/','--dev','/dev','--proc','/proc','--']+[str(x) for x in args], cwd=cwd or self.work, env=self.env,
                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while proc.poll() is None:
                    self.check()
                    if time.monotonic()-start > timeout:
                        raise TimeoutError(f'{label}: timed out after {timeout}s')
                    if log.stat().st_size > 8 * 1024 * 1024:
                        raise RuntimeError(f'{label}: diagnostic log exceeded 8 MiB')
                    time.sleep(.15)
                if proc.returncode:
                    raise RuntimeError(f'{label} failed (exit {proc.returncode}); inspect {log.name}')
            except BaseException:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL); proc.wait()
                raise
        return log
