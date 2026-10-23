from backend.browser_import import load_snapshot
from backend.teams import annotate
from test_browser_import import write_snapshot, row


def test_department_accepts_new_member_and_overrides_legacy_roster(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(person="새가상팀원", department="Example Engineering"),
                          row(department="Example Engineering")], filterMode="department")
    events, source, reviews = load_snapshot(path)
    assert len(events) == 2 and not reviews
    assert all(annotate(event)["team"] == "SW" for event in events)


def test_department_mode_does_not_fall_back_to_person(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(), row(department="Unknown"), row(department=None)],
                   filterMode="department")
    events, source, reviews = load_snapshot(path)
    assert not events and len(reviews) == 3


def test_legacy_snapshot_still_supported(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row()])
    events, _, reviews = load_snapshot(path)
    assert not reviews and annotate(events[0])["team"] == "AI"


def test_blank_person_not_accepted_under_valid_department(tmp_path):
    path = tmp_path / "snapshot.json"
    write_snapshot(path, [row(person=" ", department="Example Research")], filterMode="department")
    events, _, reviews = load_snapshot(path)
    assert not events and reviews
