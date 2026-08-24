# -*- coding: utf-8 -*-
"""나이스 연결 확인 — 학교 검색과 학사일정이 실제로 오는지 눈으로 본다.

쓰는 법 (설치 폴더나 소스 폴더에서):
    python tools/neis_check.py 가온초
    python tools/neis_check.py 가온초 --key 발급받은키

개발용 도구다. 앱은 이 파일 없이도 동작한다.
"""
import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import neis


def main() -> int:
    ap = argparse.ArgumentParser(description="나이스 연결 확인")
    ap.add_argument("name", help="찾을 학교 이름 (두 글자 이상)")
    ap.add_argument("--key", default="", help="인증키 (없으면 내장 키/키 없이)")
    ap.add_argument("--days", type=int, default=90, help="며칠치 학사일정")
    args = ap.parse_args()

    config = {"neis_api_key": args.key}
    key = neis.api_key(config)
    print(f"인증키: {'…' + key[-4:] if key else '없음 (5건만 옵니다)'}")

    try:
        schools = neis.search_schools(args.name, config)
    except neis.NeisError as e:
        print(f"✗ 학교 검색 실패: {e}")
        return 1
    if not schools:
        print("✗ 그 이름의 학교를 찾지 못했습니다.")
        return 1
    print(f"\n✔ 학교 {len(schools)}곳:")
    for i, s in enumerate(schools[:10], 1):
        print(f"  {i}. {s.label()}  [{s.office_name}] {s.address}")

    school = schools[0]
    start = date.today()
    end = start + timedelta(days=args.days)
    print(f"\n'{school.name}'의 {start} ~ {end} 학사일정:")
    try:
        events = neis.fetch_schedule(school, start, end, config)
    except neis.NeisError as e:
        print(f"✗ 학사일정 조회 실패: {e}")
        return 1
    if not events:
        print("  (그 기간에 올라온 일정이 없습니다)")
    for e in events:
        memo = f"  — {e.memo[:20]}" if e.memo else ""
        print(f"  · {e.when_text():12} {e.title}{memo}")
    print(f"\n총 {len(events)}건.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
