"""Validate a manually captured eCount snapshot; never poll the browser."""

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path

from .parsers import midnight
from .teams import normalize, team_for, team_for_department, ALIASES


def identity(person):
    normalized = normalize(person)
    return ALIASES.get(normalized, normalized)


def review(key, message):
    return {"id": "ecount-" + sha256(key.encode()).hexdigest()[:16], "file": "eCount 근태현황", "message": message}


def load_snapshot(path: Path):
    source = {"status": "unconfigured", "lastSuccess": None, "capturedAt": None, "rangeStart": None, "rangeEnd": None, "eventCount": 0, "error": None}
    if not path.exists():
        return [], source, []
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError
        data = json.loads(path.read_text("utf-8-sig"))
        if data.get("version") != 1 or data.get("statusFilter") != "확인":
            raise ValueError
        captured = datetime.fromisoformat(data["capturedAt"])
        begin, end = date.fromisoformat(data["rangeStart"]), date.fromisoformat(data["rangeEnd"])
        if captured.utcoffset() != timedelta(hours=9) or not 0 < (end - begin).days <= 1830:
            raise ValueError
        rows = data["rows"]
        filter_mode = data.get("filterMode", "person")
        if filter_mode not in {"person", "department"}:
            raise ValueError
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        message = "eCount 저장 자료의 형식·기간·확인 상태를 검증하지 못했습니다. 다시 가져오세요."
        source.update(status="error", error=message)
        return [], source, [review("schema", message)]
    source.update(status="snapshot", lastSuccess=captured.isoformat(), capturedAt=captured.isoformat(), rangeStart=begin.isoformat(), rangeEnd=end.isoformat())
    events, reviews = [], []
    for number, row in enumerate(rows):
        try:
            day = date.fromisoformat(row["date"])
            person, kind, amount, slot = row["person"], row["type"], row["amount"], row["slot"]
            if not isinstance(person, str) or not person.strip() or not begin <= day < end:
                raise ValueError
            if filter_mode == "department" or "department" in row:
                department = row.get("department")
                if not isinstance(department, str) or team_for_department(department) == "unassigned":
                    raise ValueError
            elif team_for(person) == "unassigned":
                raise ValueError
            if isinstance(amount, bool) or amount not in {0.5, 1} or slot not in {None, "am", "pm"}:
                raise ValueError
            if kind not in {"연차", "반차", "오전반차", "오후반차"} or (slot is not None and amount != 0.5):
                raise ValueError
            if kind == "오전반차" and slot != "am" or kind == "오후반차" and slot != "pm" or kind == "반차" and amount != 0.5:
                raise ValueError
            label = "오전반차" if slot == "am" else "오후반차" if slot == "pm" else "연차" if amount == 1 else "반차"
            key = f"{identity(person)}|{day}|{kind}|{slot}|{amount}"
            events.append({"id": "ecount-" + sha256(key.encode()).hexdigest()[:24], "title": f"{person} · {label}", "kind": "leave", "start": midnight(day).isoformat(), "end": midnight(day + timedelta(days=1)).isoformat(), "allDay": True, "person": person, "leaveType": label, "amount": float(amount), "location": None, "url": None, "source": "eCount 근태현황", "sourceType": "ecount"})
            if "department" in row:
                events[-1]["department"] = row["department"]
        except (ValueError, TypeError, KeyError):
            reviews.append(review(str(number), f"eCount {number + 1}번째 행의 팀원·근태일자·휴가 구분을 확인해야 합니다."))
    events = list({event["id"]: event for event in events}.values())
    source["eventCount"] = len(events)
    if reviews:
        source.update(status="error", error=f"{len(reviews)}개 eCount 행의 확인이 필요합니다.")
    return events, source, reviews


def merge_leave(pdf_events, imported):
    """Prefer explicit browser half-day labels over equivalent generic PDF rows."""
    pdf_events = list({event["id"]: event for event in pdf_events}.values())
    imported = list({event["id"]: event for event in imported}.values())
    combined = list(imported)
    for pdf in pdf_events:
        duplicates = [event for event in imported if identity(event["person"]) == identity(pdf["person"]) and event["start"] == pdf["start"] and event["end"] == pdf["end"] and event["amount"] == pdf["amount"] and (event["leaveType"] == pdf["leaveType"] or pdf["leaveType"] in {"연차", "반차"} and pdf["amount"] == 0.5)]
        if not duplicates:
            combined.append(pdf)
    held, reviews = set(), []
    for i, event in enumerate(combined):
        for other in combined[i + 1:]:
            if identity(event["person"]) != identity(other["person"]) or event["start"] >= other["end"] or event["end"] <= other["start"]:
                continue
            if {event["leaveType"], other["leaveType"]} == {"오전반차", "오후반차"}:
                continue
            if event["amount"] == other["amount"] and event["leaveType"] == other["leaveType"] and event["start"] == other["start"] and event["end"] == other["end"]:
                held.add(other["id"])
                continue
            held.update([event["id"], other["id"]])
            reviews.append(review(event["id"] + other["id"], f"{event['person']}의 겹치는 휴가 기록이 서로 다릅니다. 확인 전 해당 기록 표시를 보류합니다."))
    return [event for event in combined if event["id"] not in held], reviews
