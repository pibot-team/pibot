"""규칙(정규식)으로 영업시간·휴무·안내를 읽는다.

확실하지 않으면 confident=False 로 돌려준다. 규칙+LLM 방식은 이때만 LLM 에 넘긴다.
"""

import re

from app.hours.labels import span, to_time
from app.hours.model import WEEKDAYS, Closures, Hours, HoursRule, Notice, ParsedPlace

TIME = r"(\d{1,2}):(\d{2})"
RANGE = re.compile(rf"{TIME}\s*[~\-]\s*{TIME}")
LAST_ENTRY = re.compile(
    rf"(?:입장\s*마감|마지막\s*주문|주문\s*마감|라스트\s*오더|L\.?\s?O\.?)\s*:?\s*\(?{TIME}"
    rf"|{TIME}\s*\)?\s*(?:입장\s*마감|주문\s*마감)"
)
BREAK = re.compile(r"휴게|브레이크|준비\s*시간|break", re.IGNORECASE)
MONTHS = re.compile(r"(\d{1,2})월\s*[~\-]\s*(\d{1,2})월")
DAY = rf"([{WEEKDAYS}])(?:요일)?"
DAYS = re.compile(rf"{DAY}\s*[~\-]\s*{DAY}|평일|주말")
NOTICE_RULES = [
    ("날씨", re.compile(r"우천|기상|날씨|강풍|태풍")),
    ("조기 마감", re.compile(r"재료|소진|매진")),
    ("교통·예약", re.compile(r"여객선|운항|배편|예약")),
    ("변동 가능", re.compile(r"변동")),
    ("기타", re.compile(r"정상\s*운영|공연|회차")),
]
ORDINAL = {"첫째": 1, "둘째": 2, "셋째": 3, "넷째": 4, "다섯째": 5}


def split_notes(text: str | None) -> tuple[str, list[str]]:
    """※ 뒤 문장을 본문에서 떼어 낸다."""
    if not text:
        return "", []
    parts = re.split(r"※", text)
    return parts[0].strip(), [p.strip(" \n-") for p in parts[1:] if p.strip(" \n-")]


def find_notices(*texts: str | None) -> list[Notice]:
    """※ 문장과 본문에서 안내를 찾는다. 같은 유형은 한 번만."""
    sentences = []
    for text in texts:
        body, notes = split_notes(text)
        sentences += notes
        sentences += [s.strip(" -") for s in re.split(r"\n|(?<=[)\]])\s*-", body)
                      if re.search(r"공연|회차|재료|소진", s)]
    found: dict[str, Notice] = {}
    for sentence in sentences:
        for kind, pattern in NOTICE_RULES:
            if pattern.search(sentence) and kind not in found:
                found[kind] = Notice(type=kind, text=sentence)
    return list(found.values())


def _days(m: re.Match) -> list[int]:
    if m.group(0) == "평일":
        return [0, 1, 2, 3, 4]
    if m.group(0) == "주말":
        return [5, 6]
    return span(WEEKDAYS.index(m.group(1)), WEEKDAYS.index(m.group(2)), 7)


def parse_hours(text: str | None) -> tuple[Hours, bool]:
    body, _ = split_notes(text)
    if not body:
        return Hours(status="unknown"), True
    if re.search(r"입실|퇴실", body):
        return Hours(status="unknown"), True
    if re.search(r"상시\s*개방|24\s*시간", body) and not RANGE.search(body):
        return Hours(status="always"), True

    # 위치 순서대로 훑으면서 기간·요일 표시가 나오면 그 뒤 시간에 붙인다
    events = []
    for m in MONTHS.finditer(body):
        events.append((m.start(), "months", span(int(m[1]) - 1, int(m[2]) - 1, 12, base=1)))
    for m in DAYS.finditer(body):
        events.append((m.start(), "days", _days(m)))
    for m in RANGE.finditer(body):
        # "휴게시간 12:00~13:00" 이나 "14:00~17:00 준비시간" 은 빼고,
        # "09:00~18:00(휴게시간 ...)" 처럼 괄호로 뒤에 붙은 설명은 다음 시간 이야기다
        before = body[max(0, m.start() - 8):m.start()]
        after = body[m.end():m.end() + 6].lstrip()
        if BREAK.search(before) or BREAK.match(after):
            continue
        events.append((m.start(), "range", (to_time(m[1], m[2]), to_time(m[3], m[4]))))
    for m in LAST_ENTRY.finditer(body):
        h, mi = (m[1], m[2]) if m[1] else (m[3], m[4])
        events.append((m.start(), "last", to_time(h, mi)))
    events.sort(key=lambda e: e[0])

    rules: list[HoursRule] = []
    months = weekdays = None
    confident = True
    for _, kind, value in events:
        if kind == "months":
            months = value
        elif kind == "days":
            weekdays = value
        elif kind == "range":
            same = [r for r in rules if r.months == months and r.weekdays == weekdays]
            if same:
                # 같은 조건에 시간이 두 개면 구역별 시간 같은 것. 첫 번째만 쓰고 확신 없음
                confident = False
                continue
            rules.append(HoursRule(months=months, weekdays=weekdays,
                                   open=value[0], close=value[1]))
        elif kind == "last" and rules and rules[-1].last_entry is None:
            rules[-1].last_entry = value

    if not rules:
        return Hours(status="unknown"), not RANGE.search(body)
    if re.search(r"하절기|동절기|성수기|비수기", body) and not MONTHS.search(body):
        confident = False
    return Hours(status="known", rules=rules), confident


def holidays(body: str) -> set[str]:
    """설·추석은 당일인지 연휴인지 나눈다. 연휴라고 안 하면 당일, 구분 없이 명절이면 명절."""
    found = set()
    for m in re.finditer(r"(설날|설|추석)((?:\s*[·,/]\s*(?:설날|설|추석))*)\s*(연휴|당일)?", body):
        names = re.findall(r"설날|설|추석", m[0])
        kind = m[3] or "당일"
        found |= {f"{'설' if n.startswith('설') else '추석'} {kind}" for n in names}
    if not found and "명절" in body:
        found.add("명절")
    return found


def parse_closures(text: str | None) -> tuple[Closures, bool]:
    body, _ = split_notes(text)
    if not body:
        return Closures(weekly=None), True
    weekly: set[int] = set()
    other: set[str] = set()

    for m in re.finditer(r"(?:매월|매달)\s*((?:(?:첫째|둘째|셋째|넷째|다섯째|마지막)[\s,·]*)+)"
                         rf"\s*([{WEEKDAYS}])요일", body):
        nums = [str(ORDINAL.get(o, "마지막")) for o in re.findall(r"첫째|둘째|셋째|넷째|다섯째|마지막", m[1])]
        other.add(f"매달 {'·'.join(nums)}주 {m[2]}")
        body = body.replace(m[0], " ")
    for m in re.finditer(rf"매주\s*((?:[{WEEKDAYS}](?:요일)?[\s,·]*)+)", body):
        # "월요일"의 "일"을 일요일로 읽지 않게 요일까지 같이 소비한다
        weekly |= {WEEKDAYS.index(d) for d in re.findall(rf"([{WEEKDAYS}])(?:요일)?", m[1])}
    if "주말" in body:
        weekly |= {5, 6}
    other |= holidays(body)
    for m in re.finditer(r"(\d{1,2})월\s*(\d{1,2})일", body):
        other.add(f"{int(m[1])}월 {int(m[2])}일")
    if re.search(r"공휴일|국경일", body):
        other.add("법정공휴일")

    if weekly or other or "연중무휴" in body:
        return Closures(weekly=sorted(weekly), other=sorted(other)), True
    return Closures(weekly=None), False


def parse(hours_text: str | None, rest_text: str | None) -> tuple[ParsedPlace, bool]:
    hours, ok_h = parse_hours(hours_text)
    closures, ok_c = parse_closures(rest_text)
    notices = find_notices(hours_text, rest_text)
    return ParsedPlace(hours=hours, closures=closures, notices=notices), ok_h and ok_c
