"""Read published calendars and eCount attendance slips without changing sources."""

from datetime import date, datetime, time, timedelta
from hashlib import sha256
from io import BytesIO
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from icalendar import Calendar
from pypdf import PdfReader
import recurring_ical_events

KST = ZoneInfo("Asia/Seoul")
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_ICS_BYTES = 10 * 1024 * 1024


def midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, KST)


def safe_url(value) -> str | None:
    value = str(value or "").strip()
    parsed = urlsplit(value)
    return value if parsed.scheme in {"https", "http"} and parsed.hostname else None


def parse_calendar(raw: bytes) -> Calendar:
    if len(raw) > MAX_ICS_BYTES or b"BEGIN:VCALENDAR" not in raw[:200]:
        raise ValueError("유효한 캘린더 파일이 아닙니다.")
    calendar = Calendar.from_ical(raw)
    for event in calendar.walk("VEVENT"):
        if not event.get("DTSTART") or not event.get("UID"):
            raise ValueError("일정 식별자 또는 시작 시간이 누락되었습니다.")
    return calendar


def calendar_events(raw: bytes, start: date, end: date) -> list[dict]:
    lo, hi = midnight(start), midnight(end)
    result = []
    for event in recurring_ical_events.of(parse_calendar(raw)).between(lo, hi):
        if str(event.get("STATUS", "")).upper() == "CANCELLED":
            continue
        begins = event["DTSTART"].dt
        all_day = isinstance(begins, date) and not isinstance(begins, datetime)
        finish = event.get("DTEND")
        finish = finish.dt if finish else begins + (
            event["DURATION"].dt if event.get("DURATION") else
            timedelta(days=1) if all_day else timedelta(0)
        )
        begins = midnight(begins) if all_day else (
            begins.replace(tzinfo=KST) if begins.tzinfo is None else begins.astimezone(KST)
        )
        finish = midnight(finish) if not isinstance(finish, datetime) else (
            finish.replace(tzinfo=KST) if finish.tzinfo is None else finish.astimezone(KST)
        )
        if finish < begins:
            raise ValueError("일정 종료 시간이 시작 시간보다 빠릅니다.")
        if begins >= hi or (finish <= lo and begins != finish) or begins == finish and begins < lo:
            continue
        uid = str(event["UID"])
        identity = sha256(f"{uid}|{begins.isoformat()}".encode()).hexdigest()[:24]
        result.append({
            "id": f"meeting-{identity}", "title": str(event.get("SUMMARY", "제목 없는 일정")),
            "kind": "meeting", "start": begins.isoformat(), "end": finish.isoformat(),
            "allDay": all_day, "person": None, "leaveType": None, "amount": None,
            "location": str(event.get("LOCATION", "")) or None,
            "url": safe_url(event.get("URL")), "source": "Outlook",
        })
    return list({event["id"]: event for event in result}.values())


DATE = r"\d{4}[/.-]\d{1,2}[/.-]\d{1,2}"
ROW = re.compile(
    rf"^\s*(?P<person>[가-힣A-Za-zÀ-ž][가-힣A-Za-zÀ-ž .·'-]{{0,79}}?)\s*"
    rf"(?P<start>{DATE})(?:\s*[~～–]\s*(?P<end>{DATE}))?\s*"
    r"(?P<kind>오전\s*반차|오후\s*반차|대체\s*휴가|연차|반차|공가|병가|휴가)\s*"
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<tail>.*)$"
)


def read_pdf(raw: bytes) -> str:
    if len(raw) > MAX_PDF_BYTES:
        raise ValueError("PDF 크기가 20 MB를 초과합니다.")
    reader = PdfReader(BytesIO(raw))
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError("암호화되었거나 페이지 수 제한을 초과한 PDF입니다.")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_leave_text(text: str, source: str) -> tuple[list[dict], list[str]]:
    if "근태전표" not in text or "근태일자" not in text:
        return [], ["근태전표와 근태일자 항목을 찾지 못했습니다. 스캔본 또는 다른 양식인지 확인하세요."]
    if re.search(r"취소|반려", text):
        return [], ["취소 또는 반려 표시가 있어 휴가 반영 여부를 확인해야 합니다."]
    # Only table bodies following the attendance date header are eligible.
    body = text.split("근태일자", 1)[1]
    events, issues = [], []
    for line in body.splitlines():
        if not re.search(DATE, line):
            continue
        match = ROW.match(line.replace("\u00a0", " "))
        if not match:
            issues.append("날짜가 있는 행의 이름·휴가 유형·일수를 명확히 읽지 못했습니다.")
            continue
        fields = match.groupdict()
        try:
            begin = date(*map(int, re.split(r"[/.-]", fields["start"])))
            last = date(*map(int, re.split(r"[/.-]", fields["end"]))) if fields["end"] else begin
            amount = float(fields["amount"])
            kind = re.sub(r"\s+", "", fields["kind"])
            if last < begin or (last - begin).days > 366 or amount <= 0:
                raise ValueError
            if "시간" in fields["tail"] or amount > (last - begin).days + 1:
                raise ValueError
            if "반차" in kind and amount != 0.5:
                raise ValueError
            if amount not in {0.5, 1.0} and not fields["end"]:
                raise ValueError
            person = fields["person"].strip()
            signature = f"{person}|{begin}|{last}|{kind}|{amount}"
            events.append({
                "id": "leave-" + sha256(signature.encode()).hexdigest()[:24],
                "title": f"{person} · {kind}", "kind": "leave",
                "start": midnight(begin).isoformat(), "end": midnight(last + timedelta(days=1)).isoformat(),
                "allDay": True, "person": person, "leaveType": kind, "amount": amount,
                "location": None, "url": None, "source": source,
            })
        except ValueError:
            issues.append("휴가 날짜·기간·일수의 해석이 불명확합니다. 원본을 확인하세요.")
    if not events and not issues:
        issues.append("근태전표에서 읽을 수 있는 휴가 행이 없습니다.")
    # A partly parsed document is held entirely for review, never partly accepted.
    return ([] if issues else events), list(dict.fromkeys(issues))
