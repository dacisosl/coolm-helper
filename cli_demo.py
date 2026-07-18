# -*- coding: utf-8 -*-
"""M1 CLI 데모: 가장 최근 쪽지 N개에서 일정 후보를 추출해 마스킹 출력한다.

사용: python cli_demo.py [쪽지 개수]   (기본 10)
출력은 전부 마스킹 적용 — 본문 미리보기는 앞 20자만.
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from parser import pipeline, pii_detector


def preview(text: str, roster: set, n: int = 20) -> str:
    text = pii_detector.mask(text, roster=roster).replace("\n", " ").replace("\r", " ")
    return (text[:n] + "...") if len(text) > n else text


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    candidates, no_event, source = pipeline.collect(BASE_DIR, count)
    config = pipeline.load_config(BASE_DIR)
    roster = pipeline.build_roster(BASE_DIR, config, None)

    print(f"데이터 소스: {'쿨메신저 DB (Plan A)' if source == 'db' else '엑셀 내보내기 (Plan B)'}")
    print(f"일정 후보 {len(candidates)}건 / 일정 없는 쪽지 {len(no_event)}건\n")

    for i, c in enumerate(candidates, 1):
        when = c.start.strftime("%Y-%m-%d (%a)")
        if not c.all_day:
            when += c.start.strftime(" %H:%M")
        if c.end and c.end.date() != c.start.date():
            when += " ~ " + c.end.strftime("%Y-%m-%d")
        flags = []
        if c.all_day:
            flags.append("종일")
        if c.is_deadline:
            flags.append("마감")
        print(f"[{i}] {c.masked_title}")
        print(f"    일시: {when}  {'(' + ', '.join(flags) + ')' if flags else ''}")
        print(f"    근거: \"{c.source_text.strip()}\"")
        print(f"    쪽지: {preview(c.message.title, roster)} "
              f"(받은날 {c.message.received:%m/%d %H:%M})")
        if c.title_spans:
            kinds = ", ".join(sorted({s.kind for s in c.title_spans}))
            print(f"    ⚠ 제목에서 개인정보 탐지·마스킹됨: {kinds}")
        print()


if __name__ == "__main__":
    main()
