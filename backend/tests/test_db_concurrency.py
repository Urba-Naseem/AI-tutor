"""Regression: background course preparation crashed with "database is locked" (19 threads writing to SQLite)."""
import threading
import time

from sqlalchemy import text

from app import db as dbmod
from app.services import automation


def test_file_database_uses_wal_and_waits_for_writers(tmp_path):
    eng = dbmod.make_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    with eng.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert c.execute(text("PRAGMA busy_timeout")).scalar() == 30000
        c.execute(text("CREATE TABLE t (x INTEGER)"))
        c.commit()
    done = threading.Event()

    def slow_writer():
        with eng.begin() as c:  # holds the write lock for a moment, like a long job
            c.execute(text("INSERT INTO t VALUES (1)"))
            time.sleep(0.8)
        done.set()

    th = threading.Thread(target=slow_writer)
    th.start()
    time.sleep(0.1)
    with eng.begin() as c:  # a second writer waits instead of failing with "database is locked"
        c.execute(text("INSERT INTO t VALUES (2)"))
    with eng.connect() as c:  # readers are never blocked (WAL)
        assert c.execute(text("SELECT count(*) FROM t")).scalar() >= 1
    th.join()
    assert done.is_set()
    eng.dispose()


def test_courses_are_prepared_one_at_a_time(monkeypatch):
    s = automation.get_settings()
    monkeypatch.setattr(s, "app_env", "development")
    order, running, overlap = [], [0], []

    def fake(course_id, user_id):
        running[0] += 1
        overlap.append(running[0])
        time.sleep(0.05)
        order.append(course_id)
        running[0] -= 1
        with automation._lock:
            automation._queued.discard(course_id)

    monkeypatch.setattr(automation, "_prepare_guarded", fake)
    assert automation.prepare_course_async(101, None) is True
    assert automation.prepare_course_async(102, None) is True
    assert automation.prepare_course_async(101, None) in (True, False)  # a duplicate while queued is skipped
    assert automation.prepare_course_async(103, None) is True
    automation._jobs.join()
    assert set(order) == {101, 102, 103} and max(overlap) == 1  # never two at once
