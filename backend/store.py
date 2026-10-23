"""Atomic local snapshots with explicit source failure and review states."""

from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

import requests

from .parsers import KST, MAX_ICS_BYTES, MAX_PDF_BYTES, calendar_events, midnight, parse_calendar, parse_leave_text, read_pdf
from .teams import TEAMS, annotate
from .browser_import import load_snapshot, merge_leave


def now() -> str:
    return datetime.now(KST).isoformat()


def atomic_write(path: Path, contents: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as output:
        output.write(contents)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


class Store:
    def __init__(self, data_dir: Path, leave_dir: Path, calendar_url: str):
        self.data_dir, self.leave_dir, self.calendar_url = data_dir, leave_dir, calendar_url
        self.lock = threading.RLock()
        self.state = {
            "version": 1, "lastSync": None, "files": {}, "history": [], "reviews": [],
            "sources": {
                "calendar": {"status": "configured" if calendar_url else "unconfigured", "lastSuccess": None, "error": None, "eventCount": 0},
                "leave": {"status": "configured", "lastSuccess": None, "error": None, "fileCount": 0, "eventCount": 0, "reviewCount": 0},
            },
        }
        self.raw_ics = b""
        if (data_dir / "state.json").exists():
            # Corrupt state must not silently erase history.
            saved = json.loads((data_dir / "state.json").read_text("utf-8"))
            if saved.get("version") != 1:
                raise ValueError("지원하지 않는 저장 데이터 버전입니다.")
            self.state = saved
        if calendar_url and (data_dir / "calendar.ics").exists():
            self.raw_ics = (data_dir / "calendar.ics").read_bytes()

    def _calendar_sync(self):
        source = self.state["sources"]["calendar"]
        if not self.calendar_url:
            source.update(status="unconfigured", error="캘린더 연결이 설정되지 않았습니다.")
            return
        try:
            parsed = urlsplit(self.calendar_url)
            permitted = parsed.scheme == "https" and parsed.hostname == "outlook.office365.com" and not parsed.username and not parsed.password and parsed.port in {None, 443}
        except ValueError:
            permitted = False
        if not permitted:
            source.update(status="error", error="허용된 Outlook HTTPS 캘린더 주소가 아닙니다.")
            return
        try:
            with requests.get(self.calendar_url, timeout=(8, 30), stream=True, allow_redirects=False) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("unexpected response")
                pieces, size = [], 0
                for part in response.iter_content(65536):
                    size += len(part)
                    if size > MAX_ICS_BYTES:
                        raise ValueError("oversized calendar")
                    pieces.append(part)
            raw = b"".join(pieces)
            calendar = parse_calendar(raw)
            atomic_write(self.data_dir / "calendar.ics", raw)
            self.raw_ics = raw
            source.update(status="ok", lastSuccess=now(), error=None, eventCount=len(calendar.walk("VEVENT")))
        except (requests.RequestException, ValueError, OSError, TypeError):
            source.update(status="error", error="캘린더를 갱신하지 못했습니다. 마지막 성공 데이터를 유지합니다." if self.raw_ics else "캘린더를 가져오지 못했습니다.")

    def _leave_sync(self):
        source = self.state["sources"]["leave"]
        try:
            if not self.leave_dir.is_dir():
                raise OSError("folder unavailable")
            paths = sorted(p for p in self.leave_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
        except OSError:
            source.update(status="error", error="휴가 폴더에 접근하지 못했습니다. 기존 데이터를 유지합니다.")
            return
        reviews, observed = [], set()
        files = self.state["files"]
        hash_cache = {record["hash"]: record for record in files.values() if record.get("hash") and not record.get("issues")}
        for path in paths:
            relative = path.relative_to(self.leave_dir).as_posix()
            observed.add(relative)
            previous = files.get(relative)
            try:
                if path.stat().st_size > MAX_PDF_BYTES:
                    raise ValueError("oversized")
                raw = path.read_bytes()
                digest = sha256(raw).hexdigest()
                if previous and previous.get("hash") == digest and not previous.get("issues"):
                    continue
                if digest in hash_cache:
                    events, issues = deepcopy(hash_cache[digest]["events"]), []
                    for event in events:
                        event["source"] = path.name
                else:
                    events, issues = parse_leave_text(read_pdf(raw), path.name)
                if issues:
                    for message in issues:
                        reviews.append({"id": sha256(f"{relative}|{message}".encode()).hexdigest()[:20], "file": path.name, "message": message})
                    if previous:
                        previous["issues"] = issues
                    else:
                        files[relative] = {"hash": digest, "events": [], "issues": issues, "processedAt": now()}
                    continue
                if previous and previous.get("hash") != digest:
                    self.state["history"].append({"file": relative, "replacedAt": now(), "previous": deepcopy(previous)})
                files[relative] = {"hash": digest, "events": events, "issues": [], "processedAt": now()}
                hash_cache[digest] = files[relative]
            except Exception:
                # PDF libraries can raise many parser-specific exceptions. Do not expose document internals.
                reviews.append({"id": sha256(relative.encode()).hexdigest()[:20], "file": path.name, "message": "파일을 읽지 못했습니다. OneDrive 다운로드 상태와 PDF 형식을 확인하세요."})
        for relative in files.keys() - observed:
            reviews.append({"id": sha256((relative + "missing").encode()).hexdigest()[:20], "file": Path(relative).name, "message": "기존 파일이 폴더에서 사라졌습니다. 휴가 취소로 간주하지 않고 마지막 데이터를 유지합니다."})
        unique_events = {event["id"]: event for record in files.values() for event in record["events"]}
        conflicts = set()
        by_person = {}
        for event in unique_events.values():
            for other in by_person.setdefault(event["person"], []):
                if event["start"] < other["end"] and event["end"] > other["start"]:
                    # Explicit morning and afternoon halves can coexist.
                    if {event["leaveType"], other["leaveType"]} == {"오전반차", "오후반차"}:
                        continue
                    conflicts.update([event["id"], other["id"]])
            by_person[event["person"]].append(event)
        for identity in sorted(conflicts):
            event = unique_events[identity]
            reviews.append({"id": identity + "-conflict", "file": event["source"], "message": f"{event['person']}의 같은 날짜에 서로 다른 휴가 기록이 있습니다. 중복 또는 수정 여부 확인 전 표시를 보류합니다."})
        self.state["conflicts"] = sorted(conflicts)
        self.state["reviews"] = reviews
        unique = set(unique_events) - conflicts
        source.update(status="error" if reviews else "ok" if paths else "empty", lastSuccess=now() if not reviews else source.get("lastSuccess"), error=f"{len(reviews)}개 항목의 확인이 필요합니다." if reviews else None,
                      fileCount=len(paths), eventCount=len(unique), reviewCount=len(reviews))

    def sync(self, calendar_only: bool = False) -> dict:
        with self.lock:
            # Leave-only dashboard: no Outlook requests.
            if not calendar_only:
                self._leave_sync()
            self.state["lastSync"] = now()
            atomic_write(self.data_dir / "state.json", json.dumps(self.state, ensure_ascii=False, indent=2).encode())
            return {"sources": {k: deepcopy(v) for k, v in self.state["sources"].items() if k != "calendar"}, "lastSync": self.state["lastSync"], "reviews": deepcopy(self.state["reviews"])}

    def dashboard(self, start: date, end: date) -> dict:
        with self.lock:
            events = []
            sources = deepcopy(self.state["sources"])
            sources.pop("calendar", None)
            lo, hi = midnight(start), midnight(end)
            conflicts = set(self.state.get("conflicts", []))
            leave_events = []
            for record in self.state["files"].values():
                leave_events.extend(event for event in record["events"] if event["id"] not in conflicts)
            imported, sources["ecount"], import_reviews = load_snapshot(self.data_dir / "ecount-snapshot.json")
            leaves, merge_reviews = merge_leave(leave_events, imported)
            events.extend(event for event in leaves if datetime.fromisoformat(event["start"]) < hi and datetime.fromisoformat(event["end"]) > lo)
            events = sorted({event["id"]: event for event in events}.values(), key=lambda item: (item["start"], item["title"]))
            return {"events": [annotate(event) for event in events], "teams": deepcopy(TEAMS), "sources": sources, "reviews": deepcopy(self.state["reviews"]) + import_reviews + merge_reviews, "lastSync": self.state["lastSync"]}
