import re
import sqlite3
import time
from pathlib import Path
from typing import Protocol

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, ts REAL NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL NOT NULL, name TEXT NOT NULL, boredom REAL NOT NULL);
CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, ts REAL NOT NULL, text TEXT NOT NULL UNIQUE);
"""


class Retriever(Protocol):
    def index(self, kind: str, rowid: int, text: str) -> None: ...

    def search(self, query: str, k: int) -> list[str]: ...


class KeywordRetriever:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def index(self, kind: str, rowid: int, text: str) -> None:
        return None

    def search(self, query: str, k: int) -> list[str]:
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 3][:6]
        if not words:
            return []
        where = " OR ".join("lower(text) LIKE ?" for _ in words)
        rows = self.db.execute(
            f"SELECT text FROM facts WHERE {where} ORDER BY id DESC LIMIT ?",
            [f"%{w}%" for w in words] + [k],
        ).fetchall()
        return [r[0] for r in rows]


class Memory:
    def __init__(self, path: Path | str, retriever: Retriever | None = None):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)
        self.db.commit()
        self.retriever = retriever or KeywordRetriever(self.db)

    def close(self) -> None:
        self.db.close()

    def add_message(self, role: str, text: str) -> int:
        cur = self.db.execute("INSERT INTO messages (ts, role, text) VALUES (?, ?, ?)", (time.time(), role, text))
        self.db.commit()
        rowid = cur.lastrowid or 0
        self.retriever.index("message", rowid, text)
        return rowid

    def recent_messages(self, n: int) -> list[tuple[str, str]]:
        rows = self.db.execute("SELECT role, text FROM messages ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return list(reversed(rows))

    def add_event(self, name: str, boredom: float) -> int:
        cur = self.db.execute("INSERT INTO events (ts, name, boredom) VALUES (?, ?, ?)", (time.time(), name, boredom))
        self.db.commit()
        return cur.lastrowid or 0

    def recent_events(self, n: int) -> list[tuple[str, float]]:
        rows = self.db.execute("SELECT name, boredom FROM events ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return list(reversed(rows))

    def add_fact(self, text: str) -> bool:
        text = " ".join(text.split())
        if not text:
            return False
        cur = self.db.execute("INSERT OR IGNORE INTO facts (ts, text) VALUES (?, ?)", (time.time(), text))
        self.db.commit()
        if cur.rowcount:
            self.retriever.index("fact", cur.lastrowid or 0, text)
        return bool(cur.rowcount)

    def facts(self, limit: int = 20) -> list[str]:
        rows = self.db.execute("SELECT text FROM facts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [r[0] for r in reversed(rows)]

    def search(self, query: str, k: int = 5) -> list[str]:
        return self.retriever.search(query, k)

    def last_chat_age(self) -> float | None:
        row = self.db.execute("SELECT ts FROM messages WHERE role = 'user' ORDER BY id DESC LIMIT 1").fetchone()
        return None if row is None else time.time() - row[0]
