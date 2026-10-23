"""SQLite revisions and immutable jobs; workers publish only fully checked outputs."""
from __future__ import annotations
import contextlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
from .paths import data_root, contained, sha256
from .schema import Manifest, targets_checked

class Conflict(ValueError):
    pass

class Store:
    def __init__(self, root: Path | None = None):
        self.root = (root or data_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.db = self.root / "studio.sqlite3"
        with self.connect() as c:
            c.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS revisions(project_id TEXT NOT NULL, revision INTEGER NOT NULL, manifest TEXT NOT NULL, PRIMARY KEY(project_id,revision));
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                    manifest TEXT NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, snapshot TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    targets TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL DEFAULT '',
                    created REAL NOT NULL, updated REAL NOT NULL, cancel INTEGER NOT NULL DEFAULT 0,
                    error TEXT, artifacts TEXT, reused_from TEXT);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state,created);
            """)
        self.db.chmod(0o600)
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO revisions SELECT id,revision,manifest FROM projects")

    @contextlib.contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=15)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def save(self, manifest: Manifest, expected_revision: int | None = None):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT revision FROM projects WHERE id=?", (manifest.id,)).fetchone()
            revision = row[0] if row else 0
            if (row and expected_revision is None) or (expected_revision is not None and expected_revision != revision):
                raise Conflict(f"Revision conflict: current revision is {revision}")
            c.execute("INSERT OR REPLACE INTO projects VALUES(?,?,?,?)", (manifest.id, revision + 1, manifest.canonical(), time.time()))
            c.execute("INSERT INTO revisions VALUES(?,?,?)", (manifest.id,revision+1,manifest.canonical()))
        return self.project(manifest.id)

    def project(self, project_id: str):
        with self.connect() as c:
            row = c.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise KeyError(project_id)
        result = dict(row)
        result["manifest"] = Manifest.model_validate_json(result["manifest"]).model_dump()
        return result

    def compare(self, project_id, before, after=None):
        from .operations import changes_between
        current=self.project(project_id)
        after=current['revision'] if after is None else after
        with self.connect() as c:
            rows={r['revision']:json.loads(r['manifest']) for r in c.execute("SELECT revision,manifest FROM revisions WHERE project_id=? AND revision IN (?,?)",(project_id,before,after))}
        if before not in rows or after not in rows:raise KeyError('Revision not retained')
        a,b=Manifest.model_validate(rows[before]).model_dump(),Manifest.model_validate(rows[after]).model_dump()
        return {'project_id':project_id,'before':before,'after':after,'changes':changes_between(a,b),'geometry_changed':a['solids']!=b['solids']}

    def projects(self):
        with self.connect() as c:
            rows = c.execute("SELECT id,revision,updated,manifest FROM projects ORDER BY updated DESC").fetchall()
        return [{"id": r["id"], "revision": r["revision"], "updated": r["updated"], "title": json.loads(r["manifest"])["title"]} for r in rows]

    def enqueue(self, project_id: str, targets: list[str] | None = None, *, force=False, expected_revision=None):
        from .provenance import engine_fingerprint
        p = self.project(project_id)
        if expected_revision is not None and p["revision"] != expected_revision:
            raise Conflict("Project changed before render submission")
        manifest = Manifest.model_validate(p["manifest"])
        targets = targets_checked(manifest.output_targets if targets is None else targets)
        manifest.resolved()
        from .media_assets import preflight
        preflight(self,manifest,targets)
        import hashlib
        fingerprint = hashlib.sha256((manifest.canonical() + json.dumps(targets) + engine_fingerprint()).encode()).hexdigest()
        job_id = "j-" + uuid.uuid4().hex
        previous = None
        if not force:
            with self.connect() as c:
                rows = c.execute("SELECT * FROM jobs WHERE fingerprint=? AND state='succeeded' ORDER BY created DESC", (fingerprint,)).fetchall()
            for row in rows:
                candidate = self._job(row)
                if self.valid_artifacts(candidate):
                    previous = candidate
                    break
        now = time.time()
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            active = c.execute("SELECT id FROM jobs WHERE fingerprint=? AND state IN ('queued','running') AND cancel=0 ORDER BY created LIMIT 1", (fingerprint,)).fetchone()
            if active:
                return self.job(active[0])
            c.execute("INSERT INTO jobs(id,project_id,revision,snapshot,fingerprint,targets,state,stage,created,updated,artifacts,reused_from) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, project_id, p["revision"], manifest.canonical(), fingerprint, json.dumps(targets),
                 "succeeded" if previous else "queued", "cache" if previous else "queued", now, now,
                 json.dumps(previous["artifacts"]) if previous else None, (previous["reused_from"] or previous["id"]) if previous else None))
        return self.job(job_id)

    @staticmethod
    def _job(row):
        if row is None:
            raise KeyError("Unknown job")
        out = dict(row)
        for key in ("snapshot", "targets", "artifacts"):
            out[key] = json.loads(out[key]) if out[key] else None
        return out

    def job(self, job_id: str):
        with self.connect() as c:
            return self._job(c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def jobs(self, project_id: str | None = None):
        with self.connect() as c:
            rows = c.execute("SELECT * FROM jobs WHERE (? IS NULL OR project_id=?) ORDER BY created DESC LIMIT 50", (project_id, project_id)).fetchall()
        return [self._job(row) for row in rows]

    def claim(self):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT id FROM jobs WHERE state='queued' AND cancel=0 ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            c.execute("UPDATE jobs SET state='running',stage='prepare',updated=? WHERE id=?", (time.time(), row[0]))
        return self.job(row[0])

    def cancel(self, job_id: str):
        self.job(job_id)
        with self.connect() as c:
            c.execute("UPDATE jobs SET cancel=1,state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END,updated=? WHERE id=? AND state IN ('queued','running')", (time.time(), job_id))
        return self.job(job_id)

    def update(self, job_id: str, **values):
        allowed = {"state", "stage", "error", "artifacts"}
        if not values or set(values) - allowed:
            raise ValueError("Invalid job update")
        if "artifacts" in values:
            values["artifacts"] = json.dumps(values["artifacts"])
        values["updated"] = time.time()
        with self.connect() as c:
            c.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in values) + " WHERE id=? AND state='running'", (*values.values(), job_id))

    def recover(self):
        # Caller holds the single worker lock. Never silently retry stale work.
        with self.connect() as c:
            c.execute("UPDATE jobs SET state='interrupted',error='Worker stopped before publication; retry this snapshot.',updated=? WHERE state='running'", (time.time(),))

    def artifact_root(self, job):
        return self.root / "runs" / (job["reused_from"] or job["id"]) / "output"

    def valid_artifacts(self, job):
        try:
            return bool(job["artifacts"]) and all(
                contained(self.artifact_root(job), a["path"]).is_file() and
                sha256(contained(self.artifact_root(job), a["path"])) == a["sha256"]
                for a in job["artifacts"])
        except (OSError, ValueError):
            return False

    def retry(self, job_id: str):
        from hashlib import sha256 as digest
        from .provenance import engine_fingerprint
        old = self.job(job_id)
        if old["state"] in ("queued", "running"):
            raise Conflict("Job is already active")
        new_id, now = "j-" + uuid.uuid4().hex, time.time()
        snapshot = Manifest.model_validate(old["snapshot"]).canonical()
        fp = digest((snapshot + json.dumps(old["targets"]) + engine_fingerprint()).encode()).hexdigest()
        with self.connect() as c:
            c.execute("INSERT INTO jobs(id,project_id,revision,snapshot,fingerprint,targets,state,created,updated) VALUES(?,?,?,?,?,?,'queued',?,?)",
                (new_id, old["project_id"], old["revision"], snapshot, fp, json.dumps(old["targets"]), now, now))
        return self.job(new_id)

    def publish(self, job_id, artifacts):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            result = c.execute("UPDATE jobs SET state='succeeded',stage='complete',artifacts=?,updated=? WHERE id=? AND state='running' AND cancel=0", (json.dumps(artifacts), time.time(), job_id))
            return result.rowcount == 1
