from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.imaging import combine_views, compare, decode_image, demo_photo, describe
from backend.hardware import rotate_one_view


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = Path(os.environ.get("FAR_DATA_DIR", ROOT / "local_data"))
IMAGES = DATA / "images"
DB_PATH = DATA / "find_return.sqlite3"
MAX_UPLOAD = 8 * 1024 * 1024

app = FastAPI(title="Find & Return", version="0.1.0", description="Local-first lost-and-found matching demo")


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    DATA.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_database() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                category TEXT NOT NULL,
                family_ref TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK(status IN ('registered','found','returned')),
                photo_path TEXT NOT NULL,
                found_photo_path TEXT,
                features_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                found_at TEXT,
                returned_at TEXT,
                is_demo INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY,
                photo_path TEXT NOT NULL,
                photos_json TEXT NOT NULL DEFAULT '[]',
                features_json TEXT NOT NULL,
                results_json TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','confirmed','logged_new')),
                item_id TEXT REFERENCES items(id),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL REFERENCES items(id),
                kind TEXT NOT NULL CHECK(kind IN ('matched','logged_new','returned')),
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """
        )
        scan_columns = {row["name"] for row in db.execute("PRAGMA table_info(scans)")}
        if "photos_json" not in scan_columns:
            db.execute("ALTER TABLE scans ADD COLUMN photos_json TEXT NOT NULL DEFAULT '[]'")
        count = db.execute("SELECT COUNT(*) FROM items WHERE is_demo = 1").fetchone()[0]
        if count == 0:
            _seed_demo(db)


def _seed_demo(db: sqlite3.Connection) -> None:
    demo_items = [
        ("Soft blue bottle", "Bottle", "Blue / wave pattern", "Sunflower room · L-028", "bottle", (194, 133, 44), (223, 193, 82)),
        ("Sunny lunchbox", "Lunchbox", "Yellow / small star", "Rainbow room · L-041", "lunchbox", (34, 202, 238), (12, 155, 192)),
        ("Striped ankle sock", "Clothing", "Coral and cream stripes", "Cloud room · L-016", "sock", (82, 108, 231), (216, 170, 74)),
        ("Navy sun hat", "Clothing", "Navy / soft brim", "Sunflower room · L-033", "hat", (138, 76, 39), (92, 119, 174)),
        ("Red toy bus", "Toy", "Red / four black wheels", "Rainbow room · L-052", "toy", (54, 64, 224), (37, 157, 242)),
        ("White canvas shoe", "Footwear", "White / blue heel tab", "Cloud room · L-009", "shoe", (215, 217, 218), (193, 132, 63)),
    ]
    for label, category, details, family_ref, kind, color, accent in demo_items:
        item_id = str(uuid.uuid4())
        filename = f"demo-{item_id}.jpg"
        image_bytes = demo_photo(kind, color, accent)
        (IMAGES / filename).write_bytes(image_bytes)
        features = describe(decode_image(image_bytes))
        db.execute(
            """INSERT INTO items
               (id,label,category,family_ref,status,photo_path,features_json,created_at,is_demo)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (item_id, label, category, details + " · " + family_ref, "registered", filename,
             json.dumps(features), now_iso()),
        )


def _photo_url(path: str | None) -> str | None:
    return f"/media/{path}" if path else None


def _item_dict(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"], "label": row["label"], "category": row["category"],
        "family_ref": row["family_ref"], "status": row["status"],
        "photo_url": _photo_url(row["found_photo_path"] or row["photo_path"]),
        "registered_photo_url": _photo_url(row["photo_path"]),
        "created_at": row["created_at"], "found_at": row["found_at"],
        "returned_at": row["returned_at"], "is_demo": bool(row["is_demo"]),
    }


async def _read_image(upload: UploadFile) -> tuple[bytes, object]:
    payload = await upload.read(MAX_UPLOAD + 1)
    if len(payload) > MAX_UPLOAD:
        raise HTTPException(413, "Image is too large. Please use a file smaller than 8 MB.")
    try:
        image = decode_image(payload)
        features = describe(image)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return payload, features


def _save_photo(payload: bytes) -> str:
    filename = f"{uuid.uuid4().hex}.jpg"
    (IMAGES / filename).write_bytes(payload)
    return filename


def _event(db: sqlite3.Connection, item_id: str, kind: str, note: str = "") -> None:
    db.execute("INSERT INTO events (id,item_id,kind,note,created_at) VALUES (?,?,?,?,?)",
               (str(uuid.uuid4()), item_id, kind, note, now_iso()))


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local-first"}


@app.post("/api/hardware/rotate")
def hardware_rotate() -> dict[str, object]:
    return rotate_one_view()


@app.get("/api/summary")
def summary() -> dict[str, int]:
    today = datetime.now(timezone.utc).date().isoformat()
    with database() as db:
        counts = {row["status"]: row["n"] for row in db.execute("SELECT status,COUNT(*) n FROM items GROUP BY status")}
        scans = db.execute("SELECT COUNT(*) FROM scans WHERE created_at LIKE ?", (today + "%",)).fetchone()[0]
        returned_today = db.execute("SELECT COUNT(*) FROM events WHERE kind='returned' AND created_at LIKE ?", (today + "%",)).fetchone()[0]
    return {"registered": counts.get("registered", 0), "found": counts.get("found", 0),
            "returned": counts.get("returned", 0), "scans_today": scans, "returned_today": returned_today}


@app.get("/api/items")
def list_items(status: str | None = None, search: str | None = None) -> list[dict[str, object]]:
    allowed = {"registered", "found", "returned"}
    if status and status not in allowed:
        raise HTTPException(400, "Unknown item status.")
    with database() as db:
        query = "SELECT * FROM items"
        params: list[str] = []
        conditions = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if search:
            conditions.append("(label LIKE ? OR category LIKE ? OR family_ref LIKE ?)")
            params.extend([f"%{search}%"] * 3)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY CASE status WHEN 'found' THEN 0 WHEN 'registered' THEN 1 ELSE 2 END, created_at DESC"
        rows = db.execute(query, params).fetchall()
    return [_item_dict(row) for row in rows]


@app.get("/api/activity")
def activity() -> list[dict[str, object]]:
    with database() as db:
        rows = db.execute(
            """SELECT e.id,e.kind,e.note,e.created_at,i.label,i.category,i.photo_path
               FROM events e JOIN items i ON i.id=e.item_id ORDER BY e.created_at DESC LIMIT 12"""
        ).fetchall()
    return [{"id": r["id"], "kind": r["kind"], "note": r["note"], "created_at": r["created_at"],
             "label": r["label"], "category": r["category"], "photo_url": _photo_url(r["photo_path"])} for r in rows]


@app.post("/api/items")
async def register_item(label: str = Form(...), category: str = Form(...), family_ref: str = Form(""),
                        photo: UploadFile = File(...)) -> dict[str, object]:
    label, category = label.strip(), category.strip()
    if not label or not category:
        raise HTTPException(400, "Add an item name and a category.")
    payload, features = await _read_image(photo)
    item_id = str(uuid.uuid4())
    photo_path = _save_photo(payload)
    created_at = now_iso()
    with database() as db:
        db.execute(
            """INSERT INTO items (id,label,category,family_ref,status,photo_path,features_json,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (item_id, label, category, family_ref.strip(), "registered", photo_path,
             json.dumps(features), created_at),
        )
    with database() as db:
        return _item_dict(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())


@app.post("/api/scans")
async def create_scan(photos: list[UploadFile] = File(...)) -> dict[str, object]:
    if not photos or len(photos) > 3:
        raise HTTPException(400, "Capture one to three views of the item.")
    payloads: list[bytes] = []
    features_by_view: list[dict[str, object]] = []
    for photo in photos:
        payload, features = await _read_image(photo)
        payloads.append(payload)
        features_by_view.append(features)
    query_features = combine_views(features_by_view)
    scan_id = str(uuid.uuid4())
    photo_paths = [_save_photo(payload) for payload in payloads]
    photo_path = photo_paths[0]
    matches: list[dict[str, object]] = []
    with database() as db:
        rows = db.execute("SELECT * FROM items WHERE status='registered'").fetchall()
        for row in rows:
            scores = compare(query_features, json.loads(row["features_json"]))
            item = _item_dict(row)
            matches.append({**item, "scores": scores})
        matches.sort(key=lambda match: match["scores"]["overall"], reverse=True)
        matches = matches[:5]
        db.execute("INSERT INTO scans (id,photo_path,photos_json,features_json,results_json,created_at) VALUES (?,?,?,?,?,?)",
                   (scan_id, photo_path, json.dumps(photo_paths), json.dumps(query_features), json.dumps(matches), now_iso()))
    return {"scan_id": scan_id, "photo_url": _photo_url(photo_path), "features": {
        "dominant_color": query_features["color_name"], "pattern_hint": "textured" if query_features["edge_density"] > 0.12 else "mostly plain",
    }, "views": len(payloads), "matches": matches}


@app.post("/api/scans/{scan_id}/confirm")
def confirm_match(scan_id: str, item_id: str = Form(...)) -> dict[str, object]:
    with database() as db:
        scan = db.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not scan or scan["state"] != "pending":
            raise HTTPException(404, "This scan is no longer waiting for review.")
        if not item or item["status"] != "registered":
            raise HTTPException(409, "That registered item is no longer available to match.")
        db.execute("UPDATE items SET status='found',found_photo_path=?,found_at=? WHERE id=?",
                   (scan["photo_path"], now_iso(), item_id))
        db.execute("UPDATE scans SET state='confirmed',item_id=? WHERE id=?", (item_id, scan_id))
        _event(db, item_id, "matched", "Staff confirmed a visual match")
    with database() as db:
        return _item_dict(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())


@app.post("/api/scans/{scan_id}/log-new")
def log_new_found(scan_id: str, label: str = Form(...), category: str = Form(...)) -> dict[str, object]:
    with database() as db:
        scan = db.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        if not scan or scan["state"] != "pending":
            raise HTTPException(404, "This scan is no longer waiting for review.")
        item_id, created_at = str(uuid.uuid4()), now_iso()
        db.execute(
            """INSERT INTO items (id,label,category,family_ref,status,photo_path,found_photo_path,features_json,created_at,found_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (item_id, label.strip() or "Unidentified item", category.strip() or "Other", "No registered match yet",
             "found", scan["photo_path"], scan["photo_path"], scan["features_json"], created_at, created_at),
        )
        db.execute("UPDATE scans SET state='logged_new',item_id=? WHERE id=?", (item_id, scan_id))
        _event(db, item_id, "logged_new", "Found item logged without a registry match")
    with database() as db:
        return _item_dict(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())


@app.post("/api/items/{item_id}/return")
def return_item(item_id: str) -> dict[str, object]:
    with database() as db:
        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            raise HTTPException(404, "Item not found.")
        if item["status"] != "found":
            raise HTTPException(409, "Only found items can be marked returned.")
        returned_at = now_iso()
        db.execute("UPDATE items SET status='returned',returned_at=? WHERE id=?", (returned_at, item_id))
        _event(db, item_id, "returned", "Staff recorded the item as returned")
    with database() as db:
        return _item_dict(db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")
app.mount("/media", StaticFiles(directory=IMAGES, check_dir=False), name="media")
