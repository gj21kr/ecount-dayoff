import json

import pytest

from backend.browser_import import load_snapshot, merge_leave
from backend.parsers import parse_leave_text


def write_snapshot(path, rows, **overrides):
    data = {"version": 1, "capturedAt": "2026-10-23T12:00:00+09:00", "rangeStart": "2026-01-01", "rangeEnd": "2027-01-01", "statusFilter": "확인", "rows": rows, **overrides}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def row(**overrides):
    return {"date": "2026-10-20", "person": "가상개발자", "type": "연차", "amount": 1, "slot": None, **overrides}


def test_snapshot_uses_attendance_date_and_read_only(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(voucherDate="2026-10-19")])
    before = path.read_bytes()
    events, source, reviews = load_snapshot(path)
    assert not reviews
    assert source["status"] == "snapshot"
    assert events[0]["start"] == "2026-10-20T00:00:00+09:00"
    assert events[0]["sourceType"] == "ecount"
    assert path.read_bytes() == before


def test_bad_schema_explicit_error(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [], statusFilter="미확인")
    events, source, reviews = load_snapshot(path)
    assert not events
    assert source["status"] == "error" and reviews


@pytest.mark.parametrize("bad", [row(person="미등록팀원"), row(date="2027-01-01"), row(date="2026-02-30"), row(amount=1, slot="pm"), row(amount=0.25), row(amount=True)])
def test_invalid_row_held_without_losing_valid_rows(tmp_path, bad):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(), bad])
    events, source, reviews = load_snapshot(path)
    assert len(events) == 1
    assert source["status"] == "error" and len(reviews) == 1


def test_pdf_duplicate_and_am_pm_preserved(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(amount=0.5, slot="am"), row(amount=0.5, slot="pm")])
    events, _, _ = load_snapshot(path)
    pdf, _ = parse_leave_text("근태전표\n사원명 근태일자 근태명칭 근태(일/시간)\n가상개발자2026/10/20연차 0.50", "sample.pdf")
    result, reviews = merge_leave(pdf, events)
    assert len(result) == 2 and not reviews
    assert {event["leaveType"] for event in result} == {"오전반차", "오후반차"}
    assert all(event["allDay"] for event in result)


def test_full_vs_half_conflict_holds_only_affected_records(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(amount=0.5, slot="pm"), row(person="가상팀원가")])
    events, _, _ = load_snapshot(path)
    pdf, _ = parse_leave_text("근태전표\n사원명 근태일자 근태명칭 근태(일/시간)\n가상개발자2026/10/20연차 1.00", "sample.pdf")
    result, reviews = merge_leave(pdf, events)
    assert len(result) == 1 and result[0]["person"] == "가상팀원가"
    assert reviews
