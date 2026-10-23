from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import requests

from backend import app as api
from backend.parsers import calendar_events, parse_leave_text
from backend.store import Store


SLIP = """휴가 신청서
기안번호 : 2026/10/19 -5
근태전표
전표일자 : 2026/10/19 - 2
사원명 근태일자 근태명칭 근태(일/시간) 적요
테스트팀원2026/10/20연차 1.00 PTO
"""

ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Calendar//EN
BEGIN:VEVENT
UID:repeating
DTSTART:20261019T000000Z
DTEND:20261019T010000Z
RRULE:FREQ=DAILY;COUNT=3
EXDATE:20261020T000000Z
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
UID:repeating
RECURRENCE-ID:20261021T000000Z
DTSTART:20261021T020000Z
DTEND:20261021T030000Z
SUMMARY:Moved standup
END:VEVENT
END:VCALENDAR
"""


def test_attendance_date_not_approval_date():
    events, issues = parse_leave_text(SLIP, "slip.pdf")
    assert issues == []
    assert len(events) == 1
    assert events[0]["person"] == "테스트팀원"
    assert events[0]["start"] == "2026-10-20T00:00:00+09:00"
    assert events[0]["end"] == "2026-10-21T00:00:00+09:00"
    assert events[0]["amount"] == 1.0


@pytest.mark.parametrize("text", [SLIP.replace("2026/10/20", "2026/02/30"), SLIP.replace("1.00", "4.00"), SLIP + "취소", "스캔 이미지", SLIP + "다른이름2026/10/21알수없음 1.00"])
def test_ambiguous_documents_are_held(text):
    events, issues = parse_leave_text(text, "slip.pdf")
    assert not events
    assert issues


def test_half_day_does_not_invent_morning():
    events, issues = parse_leave_text(SLIP.replace("연차 1.00", "반차 0.50"), "slip.pdf")
    assert not issues
    assert events[0]["leaveType"] == "반차"
    assert events[0]["allDay"] is True
    assert events[0]["amount"] == 0.5


def test_recurrence_exception_and_korean_timezone():
    events = calendar_events(ICS, date(2026, 10, 19), date(2026, 10, 23))
    assert len(events) == 2
    assert events[0]["start"] == "2026-10-19T09:00:00+09:00"
    assert events[1]["start"] == "2026-10-21T11:00:00+09:00"
    assert events[1]["title"] == "Moved standup"
    assert calendar_events(ICS, date(2026, 10, 20), date(2026, 10, 21)) == []


def test_all_day_exclusive_end_and_cancelled():
    raw = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:day\r\nDTSTART;VALUE=DATE:20261020\r\nDTEND;VALUE=DATE:20261022\r\nSUMMARY:Away\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    assert len(calendar_events(raw, date(2026, 10, 21), date(2026, 10, 22))) == 1
    assert not calendar_events(raw, date(2026, 10, 22), date(2026, 10, 23))
    cancelled = raw.replace(b"SUMMARY:Away", b"STATUS:CANCELLED\r\nSUMMARY:Away")
    assert not calendar_events(cancelled, date(2026, 10, 20), date(2026, 10, 23))


def test_duplicate_pdfs_and_removed_file_retains_history(tmp_path, monkeypatch):
    folder = tmp_path / "imports"
    folder.mkdir()
    one = folder / "one.pdf"
    two = folder / "two.pdf"
    one.write_bytes(b"first document")
    two.write_bytes(b"first document")
    monkeypatch.setattr("backend.store.read_pdf", lambda raw: SLIP)
    store = Store(tmp_path / "data", folder, "")
    store.sync()
    snapshot = store.dashboard(date(2026, 10, 19), date(2026, 10, 22))
    assert len(snapshot["events"]) == 1
    assert snapshot["sources"]["leave"]["fileCount"] == 2
    assert one.read_bytes() == b"first document"
    one.unlink()
    two.unlink()
    store.sync()
    assert len(store.dashboard(date(2026, 10, 19), date(2026, 10, 22))["events"]) == 1
    assert store.state["sources"]["leave"]["reviewCount"] == 2
    restored = Store(tmp_path / "data", folder, "")
    assert restored.state == store.state


def test_changed_invalid_pdf_preserves_prior_events(tmp_path, monkeypatch):
    folder = tmp_path / "imports"
    folder.mkdir()
    pdf = folder / "one.pdf"
    pdf.write_bytes(b"valid")
    monkeypatch.setattr("backend.store.read_pdf", lambda raw: SLIP if raw == b"valid" else "unreadable")
    store = Store(tmp_path / "data", folder, "")
    store.sync()
    pdf.write_bytes(b"invalid")
    store.sync()
    assert len(store.dashboard(date(2026, 10, 19), date(2026, 10, 22))["events"]) == 1
    assert store.state["reviews"]
    assert store.state["sources"]["leave"]["status"] == "error"


def test_leave_only_sync_never_fetches_or_exposes_calendar(tmp_path, monkeypatch):
    folder = tmp_path / "imports"
    folder.mkdir()
    store = Store(tmp_path / "data", folder, "https://outlook.office365.com/private-secret/calendar.ics")
    store.raw_ics = ICS
    def fail(*args, **kwargs):
        pytest.fail("Leave-only sync must not fetch Outlook")
    monkeypatch.setattr("backend.store.requests.get", fail)
    store.sync()
    result = store.dashboard(date(2026, 10, 19), date(2026, 10, 23))
    assert result["events"] == []
    assert "calendar" not in result["sources"]
    assert "private-secret" not in str(result)


def test_missing_folder_is_not_empty(tmp_path):
    store = Store(tmp_path / "data", tmp_path / "missing", "")
    store.sync()
    assert store.state["sources"]["leave"]["status"] == "error"


def test_calendar_only_refresh_does_not_rescan_pdf(tmp_path, monkeypatch):
    store = Store(tmp_path / "data", tmp_path / "missing", "")
    calls = []
    monkeypatch.setattr(store, "_calendar_sync", lambda: calls.append("calendar"))
    monkeypatch.setattr(store, "_leave_sync", lambda: calls.append("leave"))
    store.sync(calendar_only=True)
    assert calls == []
    store.sync()
    assert calls == ["leave"]


def test_historical_calendar_is_not_exposed(tmp_path):
    store = Store(tmp_path / "data", tmp_path / "missing", "")
    store.raw_ics = b"historical private meeting cache"
    result = store.dashboard(date(2026, 10, 1), date(2026, 11, 1))
    assert result['events'] == []
    assert 'calendar' not in result['sources']


def test_conflicting_documents_require_review(tmp_path, monkeypatch):
    folder = tmp_path / "imports"
    folder.mkdir()
    (folder / "one.pdf").write_bytes(b"one")
    (folder / "two.pdf").write_bytes(b"two")
    monkeypatch.setattr("backend.store.read_pdf", lambda raw: SLIP if raw == b"one" else SLIP.replace("연차 1.00", "반차 0.50"))
    store = Store(tmp_path / "data", folder, "")
    store.sync()
    result = store.dashboard(date(2026, 10, 19), date(2026, 10, 22))
    assert not result["events"]
    assert len(result["reviews"]) == 2
    assert result["sources"]["leave"]["eventCount"] == 0


def test_api_range_validation_and_cross_origin(tmp_path, monkeypatch):
    folder = tmp_path / "imports"
    folder.mkdir()
    monkeypatch.setattr(api, "make_store", lambda: Store(tmp_path / "data", folder, ""))
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["ok"] is True
        assert client.get("/api/dashboard?start=2026-10-01&end=2026-10-08").status_code == 200
        assert client.get("/api/dashboard?start=2026-10-01&end=2026-10-01").status_code == 422
        assert client.get("/api/dashboard?start=2026-01-01&end=2026-10-01").status_code == 422
        assert client.post("/api/sync", headers={"Origin": "https://unrelated.example"}).status_code == 403
        assert client.post("/api/sync").status_code == 200
