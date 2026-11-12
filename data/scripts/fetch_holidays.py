"""천문연 특일 정보(공휴일)를 받아 data/holidays.json 에 저장한다.

    cd ai && python ../data/scripts/fetch_holidays.py 2026 2027

공공데이터포털에서 "한국천문연구원_특일 정보" 활용신청이 필요하다 (DATA_GO_KR_KEY).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import httpx

from app.config import settings
from app.hours.holidays import PATH

URL = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"


def fetch(year: int) -> dict[str, str]:
    res = httpx.get(URL, params={"serviceKey": settings.data_go_kr_key, "solYear": year,
                                 "numOfRows": 100, "_type": "json"}, timeout=20)
    res.raise_for_status()
    items = res.json()["response"]["body"]["items"]
    items = items["item"] if items else []
    items = items if isinstance(items, list) else [items]
    out = {}
    for it in items:
        if it.get("isHoliday") == "Y":
            d = str(it["locdate"])
            out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = it["dateName"]
    return out


def main(years: list[int]):
    data = json.loads(PATH.read_text()) if PATH.exists() else {}
    for year in years:
        got = fetch(year)
        data = {d: n for d, n in data.items() if not d.startswith(str(year))} | got
        print(f"{year}: 공휴일 {len(got)}일")
    PATH.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main([int(y) for y in sys.argv[1:]])
