# 개발 기록 (record.md)

개발 과정에서 있었던 일·결정·시행착오를 시간순으로 기록한다.
새 작업을 할 때마다 아래에 이어서 적는다. (형식: 날짜 → 한 일 → 배운 점/결정)

---

## 2026-07-18 — 하루 만에 M0부터 M4까지

### M0: 사전 조사 (데이터 소스 확인)
- `%LOCALAPPDATA%\CoolMessenger\Memo`에서 .udb 2개 발견 (활성 1개 + 구버전 1개).
- 헤더 확인 결과 **암호화 없는 표준 SQLite 3** (WAL 모드) → Plan A(.udb 직접 읽기) 가능 판정.
- 받은 쪽지는 `tbl_recv`(당시 3,839행). 본문이 `MessageText`(평문)와
  `MessageBody`(zlib 압축) 두 컬럼에 있음 → **평문 쪽만 쓰면 압축 해제 불필요.**
- 날짜가 DATETIME이 아니라 문자열 `"2026/07/16 17:04:52 (목)"` → 전용 파싱 필요.
- `tbl_member`(교직원 243명)는 개인정보 탐지 사전으로 재활용하기로.
- 엑셀 내보내기(coolmsg_*.xls)도 파싱 가능 확인 → Plan B(폴백)로 확정.
- **접근 규칙 확립: udb+wal+shm을 임시 폴더에 복사 → 복사본만 읽기 전용으로 열기.**

### 기획 문서
- README.md(개요) + PRD.md(상세) 작성.
- 핵심 아키텍처: **로컬 존 / 온라인 존 분리** — 온라인으로 나가는 건
  마스킹·확인된 제목, 시작, 종료 딱 3가지.
- 사용자 제안으로 **내장 캘린더뷰를 P2 기본 기능으로** 승격 → 구글 연동은
  P3 선택 기능이 되면서 구글 OAuth 없이도 완전한 사용 가능 = 배포 문제 해결.

### M1: 파서
- db_reader / date_parser(한국어 날짜 5유형) / pii_detector(4종 규칙) / pipeline.
- 단위 테스트 28개. 실제 DB로 돌려보며 오탐 3종 발견·수정:
  1. 목록 번호 "2. 3"을 2월 3일로 오인 → `.`/`-` 구분자는 연도·요일 있을 때만 인정
  2. "1:" 조각을 1시로 오인 → `:` 시간은 분까지 있어야 인정
  3. 본문에 인용된 과거 날짜가 일정으로 등록 → 수신일 이전 일정은 제외

### M2: UI + 로컬 저장
- PyQt6 플로팅 위젯 + 미리보기 카드 + 내장 캘린더/할일 + events.json 저장소.
- offscreen 스모크 테스트로 검증.

### M3: 구글 연동 (옵트인)
- credentials 없으면 완전 비활성. 함수가 제목·시작·종료만 받도록 설계해
  원문이 넘어갈 통로를 구조적으로 차단. 설정 절차는 calendar_sync/SETUP.md.

### M4: 패키징
- PyInstaller 빌드. **배치파일 함정**: 한글 주석 + LF 줄바꿈 .bat은 cmd가
  줄 연속(^)을 못 읽고 깨짐 → 빌드 로직을 build.py로 옮기고 .bat은 한 줄 래퍼로.
- Inno Setup 스크립트(installer.iss) + 설치안내/개인정보고지 문서 작성.
- config.json 없으면 자동 생성(경로 자동 탐지) — 다른 PC 배포 대비.

### 사용 후 피드백 반영 (같은 날)
1. **"마스킹하지 말고 빨간 표시만 해줘"** — 미리보기에서 ○○○ 자동 치환 제거.
   탐지된 전화번호·이름은 빨간 글씨로만 표시하고, 지울지는 사용자가 인라인
   편집으로 결정. 합성어 오탐("위기학생"→이름 오인)도 stopword로 수정.
2. **"검은 형광펜처럼 보인다"** — 마스킹이 아니라 Windows 다크 모드가
   입력칸을 검게 칠한 것. 모든 창을 라이트 테마로 고정해 해결.
   (참고: "○1~2교시"의 ○는 보낸 분이 쓴 글머리표 — 프로그램과 무관)
3. **"공휴일 문제"** — 최근 N일 방식은 연휴에 취약 → **가장 최근 쪽지 N개**
   방식으로 전환 (기본 10, 미리보기 창에서 10/50/100 즉시 전환).
4. **치명 버그: 두 번째 실행부터 앱이 조용히 죽음** — 첫 실행 때 exe 옆에
   생기는 `store` 데이터 폴더가 내부 `store` 코드 모듈을 가림(sys.path 순서 문제).
   frozen 모드에서 BASE_DIR를 sys.path에 넣지 않는 것으로 해결.
   재발 방지로 전역 예외 훅 추가: 오류 시 안내창 + coolm_helper_error.log 기록.
5. **디자인 개편** — 쿨메신저 블루(#1e88e5) + 화이트 라이트 테마로 전면 교체
   (ui/theme.py로 공용화). 플로팅 위젯은 라운드 카드 + 그림자.

### 오늘의 교훈
- 정규식 날짜 파서는 **실제 데이터로 돌려봐야** 오탐이 보인다 (테스트만으론 부족).
- PyInstaller onedir 배포에서 **데이터 폴더와 파이썬 패키지 이름을 겹치게 하지 말 것.**
- GUI 앱은 조용히 죽으면 디버깅 불가 — **예외 훅 + 로그 파일은 처음부터 넣자.**
- 다크 모드 사용자가 있다 — 테마를 명시적으로 고정하지 않으면 OS가 덮어쓴다.
- 빌드가 dist를 갈아엎으므로 **사용자 데이터(events.json)는 빌드 전 백업 필수.**

---

## 2026-07-18 (저녁) — P2.5 대규모 업데이트 (v0.2.0)

### 선택제 저장
- 설정에서 **로컬 모드(기본) / 구글 연동 모드(옵트인)** 전환.
  모바일에서 일정을 보고 싶은 사람만 구글 모드를 켠다.
- 구글 모드에선 등록 카드의 [구글에도 등록] 체크박스가 기본 켜짐.

### 설정 모달 (⚙)
- 플로팅 위젯에 톱니 아이콘 추가. 계정/데이터/개인정보/위젯 4개 탭.
- 데이터 탭에서 기본 쪽지 개수·데이터 폴더·버전·업데이트 확인 관리.
- 위젯 탭: 항상 위 표시, 투명도 조절.

### 캘린더 전면 리디자인
- 테두리 없는 플랫 달력, 날짜 아래 **일정 개수 배지**만 표시.
- 날짜 클릭 → 우측에 투두리스트: [중요도 칩] + 제목. 할일 탭 삭제.
- 항목 클릭 → 아코디언 상세보기(제목/일시/종일/중요도/메모 인라인 편집 + 저장/삭제).
- Event 모델에 priority(높음/보통/낮음), memo 필드 추가 — 기존 events.json과 호환.

### 자동 업데이트 (요청 기능)
- 시작 2초 후 백그라운드로 update_url(version.json) 확인 →
  새 버전이면 "업데이트 후 재시작하시겠습니까?" → 설치파일 다운로드 →
  /SILENT 설치 → 자동 재실행 (installer.iss의 지금실행 Run에서 skipifsilent 제거).
- 아직 배포 서버(update_url)가 없어 대기 상태. GitHub Releases + version.json
  연결만 하면 활성화됨 (updater.py 상단 주석에 절차 기록).
- 버전 관리 시작: version.py = 0.2.0 (installer.iss와 동기화 필요).

### 교훈
- Qt QSS는 #RRGGBBAA 색을 지원하지 않는다 — rgba() 또는 별도 연한 색을 쓸 것.
- 스레드에서 UI를 직접 만지지 말 것 — pyqtSignal로 메인 스레드에 전달(업데이트 체커).

---

## 2026-07-18 (밤) — GitHub 배포 + 자동 업데이트 실제 연결

- GitHub 계정(dacisosl) 연결, 공개 저장소 생성: https://github.com/dacisosl/coolm-helper
  (저장소 생성은 보안 정책상 사용자가 웹에서 직접, 나머지는 자동)
- winget으로 GitHub CLI + Inno Setup 설치. Inno로 CoolmHelper-Setup.exe 컴파일 성공.
- Releases에 v0.2.0 설치파일 업로드, version.json을 main 브랜치에 커밋.
- update_url 기본값을 raw.githubusercontent.com의 version.json으로 연결 →
  전체 체인 검증 완료 (버전 조회 200 / 동일 버전 판정 / 설치파일 다운로드 200).
- 시행착오: git push가 자격증명 GUI를 기다리며 무한 대기 → 저장소에
  gh를 credential.helper로 지정해 해결. 로컬 브랜치 rename 잠금 오류는
  `push master:main`으로 우회 후 정리.

### 다음 버전 배포 절차 (요약)
1. version.py와 installer.iss의 버전을 올린다 (예: 0.3.0)
2. `python build.py` → ISCC로 installer.iss 컴파일
3. `gh release create v0.3.0 Output\CoolmHelper-Setup.exe --title ... --notes ...`
4. version.json의 version/url/notes 갱신 → commit & push
5. 사용자들은 다음 실행 때 "업데이트 후 재시작하시겠습니까?" 안내를 받는다

---

## 2026-07-19 — v0.3.0: 데모 모드

- **데모 모드**: 내장된 가짜 학교 쪽지 8건(parser/demo_data.py)으로 쿨메신저가
  없는 PC에서도 전체 기능 체험 가능. 날짜는 실행 시점 기준으로 생성되어
  항상 미래 일정으로 파싱된다. 가짜 전화번호·가상 명단으로 빨간 표시도 체험됨.
- 켜는 방법 2가지: ① 설정 → 데이터 → 데모 모드 체크
  ② 쿨메신저를 못 찾는 PC에서 [일정 등록] 클릭 시 자동으로 "데모로 체험?" 제안.
- 데모로 등록한 일정에는 demo 표식이 붙고, 설정의
  **[데모로 등록한 일정 모두 삭제]** 버튼으로 일괄 정리 (실제 일정은 안 건드림).
- 테스트 32개로 확대 (데모 데이터 파싱·PII·삭제 검증).
- 배운 점: "김민준 학생"처럼 호칭이 붙으면 명단 규칙보다 호칭 규칙이 먼저
  잡는다(스팬 병합 순서) — 테스트 데이터 만들 때 호칭 없는 이름도 섞을 것.

---

## 2026-07-19 — v0.4.0: 대규모 UI 개편 1단계

큰 업데이트를 3단계(v0.4/0.5/0.6)로 나눠 진행하기로 결정. 이번은 1단계.

- **미니 위젯 (기본값)**: 오른쪽 벽에 도킹된 펭귄. 클릭 → 세로 아이콘 바
  (➕등록/🗓캘린더/⚙설정, 안내보정 💬은 기능 켜지면 표시). 바깥 클릭 시 자동
  접힘(Popup), 위아래로만 드래그. 우클릭으로 상세형↔미니 즉시 전환.
  펭귄은 내장 SVG이며 assets\penguin.png를 넣으면 자동 교체.
- **일정 등록 창 2분할**: 왼쪽 후보 목록 / 오른쪽 상세(제목·일시·마감 +
  원문 빨간표시 + 메모 인라인 편집 + 등록 버튼).
- **등록 표시 영속화**: Event에 source_ref("쪽지key|시작일시") 저장 →
  목록에서 등록된 항목 연두 배경, 재시작 후에도 유지, 캘린더에서 삭제하면
  실시간 원복 (EventStore subscribe 알림).
- **구조 리팩터링**: ui/widget_base.py로 공통 로직 분리 (미니/상세 공유).
- 설정 재편: 일반 탭(위젯 스타일·동작·기능 안내) 신설.
- 남은 단계: v0.5(캘린더 리뉴얼+즐겨찾기 보관함), v0.6(바탕화면 캘린더
  위젯+안내문구 보정 Gemini). 즐겨찾기는 '단순 보관함' 용도로 확정됨.

---

## 2026-07-19 — v0.4.1: 등록 표시 버그 수정 + 피드백 반영

- **버그**: 등록 시 목록 배경이 안 바뀌던 문제 — QListWidget 스타일시트가
  항목 BackgroundRole을 덮어버려서였음. **행을 커스텀 위젯(CandRow)으로
  교체**해 배경·선택·등록 상태를 직접 그리는 방식으로 해결.
  교훈: QSS를 쓴 리스트에서 item.setBackground는 믿지 말 것.
- 등록 표시 = 연두 배경 + "✓ 등록됨" 초록 마크 (색+글자 이중 표시).
- 요일 한글화: 7/21(화). offscreen 테스트에서 isVisible()은 항상 False —
  isHidden()으로 검증할 것.
- 날짜·시간 피커 현대화: 달력 팝업 버튼(DatePickerButton) + 30분 단위
  시간 드롭다운(TimeCombo, 직접 입력 가능). 종일 체크 시 시간 비활성.
- **상세내용 인라인 편집**: 별도 메모칸 제거. 원문(빨간 표시)이 채워진
  QTextEdit을 그 자리에서 수정하면 일정 memo로 저장되는 방식으로 통합.
- 안읽은 쪽지에 ● 표시 (IsUnRead 읽기만 함 — 복사본이라 원본 상태 불변).
  사용자 질문으로 확인: 가져오기는 읽음/안읽음 무관하게 최신 N개.

---

## 2026-07-19 — v0.5.0: 등록 취소 + 캘린더 리뉴얼 + 즐겨찾기 (2단계)

- **등록 취소**: 등록된 후보에서 버튼이 "등록 취소"(빨간 외곽선)로 바뀌고,
  누르면 해당 일정 삭제. 구글에 올린 사본도 delete_event로 삭제 시도
  (실패 시 직접 삭제 안내).
- **캘린더 창 리뉴얼**: FramelessWindowHint + 커스텀 타이틀바(– / ✕),
  둥근 카드 + 그림자. 타이틀바 영역 드래그로 이동.
- **빨간 배지**: 그날 일정 중 중요도 '높음'이 하나라도 있으면 날짜 배지가
  빨간색 (개수는 전체 개수).
- **즐겨찾기 보관함** (기본 꺼짐, 설정→일반에서 켬):
  - store/favorites.json + FavStore (변경 알림 지원)
  - 일정 등록 창 ☆ 버튼 → 제목+상세내용 저장 ("★ 저장됨" 피드백)
  - 캘린더 창 ★ 탭: 2분할(목록/상세), 제목·내용 인라인 편집·삭제
  - 용도는 '단순 보관함'으로 확정 (중요·반복 내용 계속 보기)
- 설정 저장 후 캘린더 창을 재생성해 탭 구성 변경을 반영.

---

## 2026-07-19 — v0.6.0: 바탕화면 캘린더 + 안내문구 보정 (3단계 완료)

- **바탕화면 캘린더 위젯** (기본 꺼짐, 설정→일반): 화면 오른쪽 반절,
  WindowStaysOnBottomHint로 항상 다른 창 아래("진짜 바탕화면 박기"는
  비표준이라 이 방식 채택). 상단 주간 보기(월~금 5열 + 토·일 접이식 얇은 열,
  ◀오늘▶ 주 이동), 하단 월간 달력(개수·빨간 배지). 날짜 클릭 →
  DayDetailDialog(아코디언 카드, 편집·삭제 가능, 항상 위). 투명도 40~100%.
- **안내문구 보정** (기본 꺼짐): proofread.py — parser를 import하지 않는
  격리 모듈(스모크 테스트로 격리 검증). 입력창에 붙여넣은 글만 Gemini로
  전송, 결과 복사 버튼. 공급자 함수 테이블(_PROVIDERS)로 Groq 교체 대비.
  API 키는 설정→계정에서 입력(마스킹), config.json(로컬 전용)에 저장.
  키 발급 페이지 버튼 포함. 유출된 옛 키 재사용 금지 안내.
- **저장소 싱글턴화**: EventStore/FavStore를 QApplication 수준에서 공유 —
  위젯 스타일 전환·바탕화면 위젯이 생겨도 모든 창이 같은 저장소를 구독,
  실시간 동기화 유지. (인스턴스가 갈라지면 알림이 끊기는 문제 예방)
- 이로써 7/19 계획한 대규모 개편 3단계(v0.4→v0.6) 완료.

---

## 2026-07-19 — v0.7.0: 시작 알림 말풍선 + 자동 시작

- **시작 알림** (ui/alerts.py): 켠 뒤 2.5초에 말풍선 1개로 순차 표시 —
  ①마감 3일 전 ②마감 1일 전(완료 체크된 건 제외) ③오늘 일정 N건.
  클릭하면 다음, 마지막 클릭에 닫힘. **세션당 1회**는 QApplication 수준
  플래그로 보장(스타일 전환으로 위젯이 재생성돼도 재발화 없음).
- 말풍선 위치: 미니=펭귄 머리 위(드래그 시 따라옴), 상세=위젯 카드 위.
- **Windows 자동 시작** (autostart.py): HKCU Run 키 등록/해제 (관리자 불필요).
  설정→일반 "Windows 시작 시 자동 실행" 체크박스. frozen이면 exe 경로,
  개발 모드면 pythonw+main.py 명령 등록.
- 테스트 37개로 확대 (알림 규칙 5종 + 말풍선 진행 + autostart 왕복).

---

## 2026-07-19 — v0.7.1: 안읽은 쪽지 전부 가져오기

- 사용자 시나리오: 안읽음이 15개 쌓인 날, 12번째쯤 읽다가 등록하려는데
  "최근 10개" 창에 그 쪽지가 없음. 후보 해법 ①읽은 것 기준 ②20개+마지막
  읽은 지점 중, **제3안 채택: 안읽음은 개수 제한 없이 전부(상한 200) +
  읽은 쪽지 최근 N개**. 안읽음 = 아직 처리 안 한 쪽지라 몇 개가 쌓여도
  항상 목록에 있고, 평소에는 기존과 동일하게 동작.
- 일정 등록 창 상단에 "● 안읽은 쪽지 N건 전부 포함" 표시.
- 가짜 DB를 만들어 검증하는 tests/test_db_reader.py 추가 (테스트 40개).

---

## 2026-07-19 — v0.8.0: ⚡ 간편 등록 (핵심 UX 완성)

- 사용자의 원래 꿈이던 흐름 구현: **쪽지를 보다가 ⚡ 누르면 그 쪽지가
  채워진 등록 모달**. "방금 읽은 것" 추측(A안)으로 계획했다가,
  실기기 실험으로 **UI 자동화(UIA)가 쿨메신저 창을 직접 읽을 수 있음**을
  확인하고 "지금 보고 있는 것"으로 업그레이드.
- 실험 과정: 창 클래스 열거(MFC 앱 확인) → 메인 창 UIA 텍스트 102개 확인
  → 쪽지 창에서 본문 Document(343자)·제목 Edit 완독 확인 → 실캡처→DB 매칭
  →후보 생성까지 엔드투엔드 검증.
- capture.py: 읽기 전용 UIA, 포커스 창 우선. 쿨메신저 상태 불변.
- match_captured: 공백 무시 대조. **버그 발견·수정**: 본문이 빈/짧은 쪽지가
  아무 텍스트와나 매칭됨 → 최소 길이(20자) 가드 + 재발 방지 테스트.
- QuickDialog: 자동 채움(제목·일시·상세), 다중 일정 콤보, 클립보드 폴백,
  전체 목록 열기, DB 매칭 시 등록 표시(source_ref) 연동.
- 미니 위젯 메뉴 맨 위에 ⚡, 상세 위젯도 ⚡ 주버튼으로. 의존성 pywinauto 추가.
- 테스트 45개.

### 속도 최적화 (사용자: "빨리 읽어줘야 의미가 있어")
- 문제: 초기 구현이 클릭당 5초+ (UIA 전체 순회 3.3초 + DB 복사 2.3초).
- 원인 분석: ①쪽지 본문이 내장 크롬(CEF)에 그려져서 창 전체 UIA 순회가
  MFC 브리지를 타며 수초 소요 ②278MB udb를 매번 복사.
- 해결: ①제목은 Edit 컨트롤 WM_GETTEXT(1ms), 본문은
  Chrome_RenderWidgetHostHWND만 콕 집어 UIA TextPattern(워밍업 후 ~40ms)
  ②간편 등록 한정, 복사 없는 WAL 직접 읽기 전용 연결(실패 시 복사 폴백)
  ③앱 시작 시 UIA 워밍업 스레드 ④모달 즉시 표시 + 내용 백그라운드 채움.
- 결과: 클릭 → 완성까지 5.6초 → **체감 즉시(내용 ~0.7초)**.
- 교훈: UIA는 스코프를 좁혀야 한다(창 전체 순회 금지). CEF 본문은
  TextPattern. "복사 후 읽기" 원칙은 대량 조회용으로 유지하되, 속도가
  생명인 경로는 WAL 동시 읽기(mode=ro)가 안전한 대안.

---

## 2026-07-19 — v0.8.1: 간편 등록 추가 최적화 (0.7초 → 0.05초)

- 프로파일링 결과 남은 병목은 "쪽지 50개 본문 전체 조회"(콜드 4.4초).
  매칭에는 앞부분만 필요 → **substr 600자 축약 조회**(콜드 0.44초)로 교체,
  매칭 성공 시 해당 쪽지 한 건만 전문 재조회.
- **캐시**: 축약 쪽지+명단을 모듈 캐시에 보관, 원본 udb 수정시각·WAL 크기
  스탬프로 무효화 (TTL 120초).
- **프리페치**: 펭귄 메뉴가 열리는 순간 백그라운드로 캐시를 데움(482ms) →
  ⚡ 클릭 시 매칭+파싱 3ms. 캡처 40ms 포함 총 ~50ms.
- 교훈: "본문 전체를 N개" 읽는 쿼리가 진짜 비용. 필요한 만큼만(substr) +
  캐시 + 사용자 의도가 보이는 순간(메뉴 열림) 프리페치 조합이 정답.

---

## 2026-07-19 — v0.9.0: 전체 점검 후 종합 개선 (13개 항목)

프로젝트 전체 점검(보안·UX·직관성·디자인) 후 사용자가 승인한 항목 일괄 반영.

- **디자인**: 이모지 → SVG 아이콘 세트(ui/icons.py, Material 기반)로 통일.
  펭귄 앱 아이콘(.ico) 생성(tools/make_icon.py) — exe·설치파일·작업표시줄 적용.
- **직관성**: 버튼명 키워드 중심("바로 등록/쪽지 목록/캘린더/문구 보정"),
  등록 취소 → 토스트+[되돌리기](ui/toast.py), 마감 체크 툴팁,
  데모 모드 뱃지(펭귄 D/상세 제목), 첫 실행 인트로 말풍선 3장(intro_done).
- **편의**: 구글 사본 수정·삭제 동기화(update_event/patch),
  마감 알림 일수 설정(7/3/1일 전 선택), 지난 일정 자동 보관
  (events_archive.json, 기본 90일), 펭귄 더블클릭=⚡(클릭 타이머로 구분),
  주말 열에 일정 있으면 주황 강조.
- **기술 정리**: .gitattributes(줄바꿈 경고 해결), release.py(릴리스 자동화 —
  버전→테스트→빌드→설치파일→GitHub→version.json→push 원커맨드).
- 보안 점검 결과: 공개 저장소 위생 OK, OneDrive 미동기화 확인, 남은 과제는
  GitHub 2FA(사용자 직접), API 키 DPAPI 암호화(추후).

---

## 2026-07-19 — v0.9.1: 캐러셀 사용설명서 (실제 화면 캡처 포함)

- docs/사용설명서.html: 8장 캐러셀(표지→핵심기능→캘린더→알림→개인정보→
  부가기능→설정→문제해결), 사용자가 정한 구성·문구. 화살표·점·키보드·스와이프.
- **실제 화면 캡처 자동 삽입**(tools/make_screenshots.py): 각 창을 show()
  없이 데모 데이터로 렌더링해 grab() → base64로 템플릿 {{SHOT:이름}}에 삽입
  → 이미지 포함 단일 파일(269KB). 실제 쪽지는 캡처에 절대 안 들어가게
  capture를 차단하고 데모만 사용.
- 시행착오 3가지: ①offscreen 플랫폼은 한글 폰트를 못 찾아 □ 렌더링 →
  일반 플랫폼 + show() 없이 grab ②grab 전 adjustSize()가 지정 크기를 되돌림
  ③deleteLater된 옛 위젯이 잔상으로 찍힘 → sendPostedEvents(DeferredDelete)
  로 정리 후 캡처.
- 원본은 사용설명서.template.html — 내용 수정은 템플릿에서, 스크린샷 갱신은
  스크립트 재실행. 설치파일에 동봉(build.py).
- 배포 안내 확정: 동료에게는 설치파일(또는 releases/latest 링크) 하나면 됨.

---

## 2026-07-21 — v0.10.0: 바탕화면 위젯 4종 개편 (반절 캘린더 대체)

- 사용자 피드백: "등록만 하면 끝이 아니라 **일정이 눈앞에 보여야** 의미가
  있다. 기존 반절 캘린더는 너무 크고 크기 조절·이동이 안 됨." → 위젯을
  4종으로 쪼개고 자유 배치 체계로 전면 개편.
- **위젯 4종** (여러 개 동시 사용): ①할일 간단판(밀린 일/오늘/앞으로)
  ②주간 일정 ③월간 달력 ④포스트잇(일정 1건=메모지 1장, 캘린더 📌로 붙임).
- **공통 동작**(ui/desk_base.py DeskWidgetBase): 상단 드래그 이동 +
  가장자리 8방향 크기 조절, 위치·크기·투명도·항상위를 config
  `desk_widgets`에 저장 → 재실행 복원. 기본은 '항상 맨 뒤'(바탕화면
  붙박이), 우클릭 메뉴로 위젯별 항상 위/투명도/끄기.
- **편집**: ①②③은 그 자리 편집 — 간단판은 ✎→EditPopup(EventItemCard
  재사용, 좁은 폭에서 입력칸 깨짐 방지로 팝오버 선택), 주간/월간은 날짜
  클릭→DayDetailDialog(기존 아코디언 카드). ④는 제목·메모 즉석 타이핑
  → 1.2초 디바운스 저장, 다른 창과 실시간 동기(subscribe), 편집 중 필드는
  안 덮어쓰는 재진입 가드. 일정 삭제 시 포스트잇 자동 소멸, ✕는 메모지만 내림.
- **관리 입구**: 펭귄 아이콘 바 ▦ 위젯 메뉴(체크 토글) + 설정 창 체크박스 3개.
- **마이그레이션**: `migrate_desk_config` — 반절 캘린더를 켜두었던 사용자는
  주간+월간이 자동으로 켜지고 투명도 승계, 최초 1회 안내 말풍선.
  desktop_calendar.py 삭제, `desktop_widget_*` 키 제거.
- 해상도 변경 대비 `clamp_geometry`(화면 밖이면 기본 배치 폴백),
  삭제된 일정의 포스트잇 항목은 `prune_notes`로 시작 시 정리.
- 테스트 63개(신규 18: 마이그레이션·클램프·prune·sections). 순수 로직은
  전부 pipeline/store에 둬서 Qt 없이 테스트 — 기존 관행 유지.
- 배운 점: frameless 리사이즈는 `startSystemResize`보다 수동 마우스
  이벤트가 낫다(놓는 순간 geometry 저장 타이밍을 잡을 수 있음). 위젯
  콘텐츠 카드 밖에 8px 투명 여백을 두면 가장자리 이벤트가 자식에게
  안 먹히고 최상위 위젯에 온다.

---

## 2026-07-21 — 릴리스 자동화 클라우드 이전 (GitHub Actions)

- 배경: 사용자가 "내 컴퓨터에서 자동으로 되게 해달라" — 로컬 release.py
  대신 **GitHub Actions(windows-latest)** 가 빌드·설치파일·릴리스·
  version.json 갱신까지 수행하도록 이전 (.github/workflows/release.yml).
- 실행 방법: version.py의 APP_VERSION 올리고 **release_notes.txt**(첫 줄=
  제목, 나머지=안내문) 수정해 main에 push → 자동 릴리스. 사용자 앱은
  다음 실행 때 업데이트 안내를 받는다.
- 시행착오: ①이 환경(원격 세션)은 workflow_dispatch 403·태그 push 403
  → **release_notes.txt paths 트리거**로 우회 ②Korean.isl 다운로드 404
  → 러너의 Inno Setup 6에 이미 내장돼 있었음(다중 폴백 로직은 유지)
  ③Windows 러너 콘솔은 cp1252라 한글 print가 UnicodeEncodeError →
  워크플로 전역 `PYTHONUTF8=1`.
- v0.10.0을 이 경로로 첫 릴리스 완료 (Setup 32MB, version.json 갱신 확인).
- 함께 추가: 업데이트.bat — 소스로 쓰는 PC에서 더블클릭 한 번으로
  pull→일정 백업→재빌드→복원.

---

## 2026-07-21 — v0.10.1~2: 업데이트 오류 수정 + 위젯 편집 모드

- **v0.10.1(긴급)**: 클라우드 빌드(3.12)와 기존 로컬 빌드(3.13) 부품이 설치
  폴더에 겹쳐 "python313.dll conflicts"로 앱이 안 켜지던 문제. installer.iss에
  `[InstallDelete]`(_internal·python*.dll·*.pyd 정리) + 빌드 파이썬 3.13 통일.
  교훈: Inno는 옛 파일을 안 지운다 — 파이썬 버전이 바뀌는 업데이트는 반드시
  설치 전 정리가 필요.
- **v0.10.2**: 사용자 요청 6건 — ①위젯마다 🔧 편집 모드 ②편집 모드에서
  변·꼭지점 8곳 파란 잡기 포인트 표시(paintEvent) ③상단 도구줄: 투명도
  슬라이더(즉시 미리보기, 놓으면 저장)+글씨 A−/A＋(위젯별 font_scale 70~150%,
  config 저장) ④할일 간단판: 전 항목 체크박스(투두리스트) + 편집 모드에서
  제목 인라인 수정(QLineEdit→store.update) ⑤월간 달력 반응형 글씨
  (높이 비례 pointSize×배율) ⑥일정 개수 배지를 가운데 아래→오른쪽 아래로,
  셀 크기에 비례 축소, 아주 작은 셀은 점만 — 날짜 숫자와 겹침 해소.
- font_px(base) 헬퍼로 위젯 내 모든 px 크기가 배율을 따라감. 편집 모드
  토글 시 refresh()로 인라인 입력칸 전환.

---

## 2026-07-21 — v0.10.3: 편집 버튼 가시성 (이모지 → SVG)

- 사용자 화면에서 🔧 버튼이 안 보인다는 보고. 이모지 렌더링은 PC·폰트에
  따라 빈칸이 될 수 있어 **내장 SVG 렌치 아이콘 + 테두리**로 교체
  (v0.9.0에서 이모지→SVG 전환한 것과 같은 이유 — 위젯 헤더에 남아있던
  이모지 버튼이 문제였다).
- 백업 진입로: 위젯 우클릭 메뉴 맨 위에 "편집 모드" 체크 항목 추가.
- 발견성: 평소에도 우하단에 은은한 대각 점 그립을 그려 "잡으면 크기 조절"
  힌트 제공. 포스트잇 최소 크기 180×140 → 140×110.

---

## 2026-07-21 — v0.11.0: 캘린더·할일 위젯 + 설정 일원화

- **PlannerWidget(캘린더·할일)**: 내 캘린더 창의 달력+그날 일정 목록을
  다섯 번째 바탕화면 위젯으로. EventItemCard 재사용이라 인라인 편집·📌
  그대로. `ensure_planner` 마이그레이션으로 기존 사용자에게 최초 1회 자동
  켬 (빠른메뉴 캘린더 아이콘을 대신하므로).
- **빠른메뉴 축소**: 캘린더·▦(위젯) 아이콘 제거 → ⚡·쪽지 목록·(문구 보정)·
  설정만. 위젯 관리는 설정 → 위젯 체크박스로 일원화, **체크 즉시 실시간
  적용**(apply_desk_widget — 저장 버튼 불필요).
- **할 일 보드 재설계**: 사용자 의도는 세로 목록이 아니라 주간 일정표형
  3열(지난 일|오늘|앞으로) 보드. 열마다 스크롤, 오늘 열은 파란 배경.
- **일정 표시 규칙 확정**: 시간 있으면 '시간 ↵ 제목' 두 줄, 종일이면 제목
  한 줄 — EventItemCard·할일 보드·주간 열 모두 통일. 제목이 옆 시간
  라벨에 잘리던 문제 해소.
- 알림 설정(7/3/1일 선택) 제거 — 기본값 [3,1] 고정.
- 교훈: "간단버전" 같은 요구는 레이아웃 그림까지 확인할 것 — 목록형으로
  만들었다가 3열 보드로 재작업.

---

## 2026-07-21 — v0.11.1: 일정 필드화 + ⠿ 순서 조정 + 자잘한 UX

- **일정 필드화**: 주간 열·할 일 보드의 일정을 공용 `_DragField` 기반
  필드로 — '시간 ↵ 제목' 완전 표시(줄바꿈, 잘림 없음), 맨 앞 ⠿ 그립을
  잡고 위아래로 끌면 순서 변경. `Event.order` 필드 신설,
  `EventStore.set_orders()`(일괄 저장 1회), 정렬은 `day_sort_key`
  (순서→중요도→시간)로 전 화면 통일.
- **달력 글씨 조절 버그**: CALENDAR_QSS가 font-size를 px로 고정해
  setFont가 무시됨 → 달력 자체 스타일시트로 덮어쓰는 `_scale_calendar`.
  교훈: QSS font-size는 위젯 폰트보다 우선한다.
- **펭귄 메뉴 딜레이 제거**: 더블클릭 구분용 대기(doubleClickInterval
  ~0.5초)가 원인 → 즉시 열고, 빠른 재요청은 ⚡로 해석하는 방식으로 전환.
- 알림 문구 "오늘 일정 N건"으로 축약 + 숫자를 빨간 배경 흰 글씨로 강조
  (표시 시점에 rich text 변환 — build_alerts는 평문 유지로 테스트 불변).
- 위젯 우클릭 메뉴에서 투명도 제거(🔧 슬라이더로 일원화), 기본 글씨
  반 단계 축소. 편집 도구줄에 📌 항상 위 고정(토글)·✕ 위젯 끄기 아이콘
  추가 (SVG — 이모지 렌더링 이슈 재발 방지).

---

## 2026-07-21 — v0.12.0: 달력 통일·한 줄 등록 바·자동 종일/마감

- **달력 위젯 통일**: MonthlyWidget 삭제 → PlannerWidget(캘린더·할일)
  하나로. `drop_monthly` 마이그레이션(월간 켰던 사용자는 planner로),
  편집 도구줄에 "상세보기" 체크(conf `show_detail`) — 끄면 순수 달력.
- **등록 UI 한 줄 바**: 제목|날짜|시간. 종일·마감 체크박스 삭제 —
  TimeCombo 첫 항목 '종일'(선택=종일), 마감 여부는 파서 자동 감지값을
  숨김 상태(`_is_deadline`)로 유지. EventItemCard도 종일 체크 제거,
  00:00 = 종일 규칙.
- ReviewDialog에 📌 포스트잇(미등록이면 등록부터) + 토스트.
- 할 일 보드 글씨 잘림: 가로 스크롤 금지 + QLabel minimumWidth(10)로
  열 너비 안 줄바꿈 강제. 교훈: wordWrap QLabel도 minimumSizeHint가
  넓으면 스크롤영역을 밀어낸다.
- 문구 보정 경고 문단 → ℹ 한 줄 + 툴팁.

---

## 2026-07-21 — v0.13.0: 설정 창·문구 보정 창 리마스터

- **설정 창**: 탭 → 사이드바(QListWidget)+QStackedWidget, 섹션은 카드
  (QFrame[scard]) 스타일. 메뉴: 일반 / 구글 연동(구 계정) / 데이터 /
  업데이트(신설, 데이터에서 분리). 개인정보 탭 삭제(사용자 결정 —
  탐지 정책·명단은 코드 그대로, UI만 제거).
- 원칙 확립: **제목 + ? 아이콘(툴팁)** — 제목 옆 긴 설명 문장 금지.
  `_help_dot`/`_card`/`_check` 헬퍼.
- 일반 탭 정리: '위젯 동작'(항상 위·투명도 — 위젯별 🔧과 중복) 삭제,
  '일정 등록(기본 기능)' 표시용 체크 삭제. 보정 체크 시에만 API 키 영역
  표시, **Gemini/OpenRouter 선택**(proof_provider) — proofread.py에
  _openrouter(OpenAI 호환 chat/completions) 추가.
- **문구 보정 창**: 원문|다듬은 글 2단 비교 + 글자 수 카운터 + 카드형
  편집기. 경고 문단은 ? 툴팁으로.
- autostart(winreg) import를 try로 감싸 비Windows(테스트)에서도 생성 가능.

---

## 2026-07-21 — v0.14.0: 전 화면 리디자인 (emil-design-eng 스킬 기준)

emilkowalski/skills 설치 후 그 기준으로 전 UI 감사·리디자인. 4단계로 나눠
단계별 커밋 (동작·레이아웃 불변, 겉감각만 개선).

- **1단계 토큰**: theme.py에 RADIUS 3단·FONT 5단·SPACE 4배수·색 상수 20+개·
  make_shadow(level) 1함수. ui/ 전체 하드코딩 hex 0건으로 치환(grep 게이트).
  QToolTip 스타일 통일, 포커스 링 2px→1px(입력칸 덜컹 제거).
- **2단계 눌림**: 모든 버튼 :pressed (배경 어둡게 + 1px 하강, 레이아웃 시프트
  없음). QSS는 scale 불가 → 이 절충. apple "pointer-down 즉각 피드백".
- **3단계 모션**: ui/motion.py(스프링 없이 QEasingCurve). fade_in/pop_in/
  fade_out_close/slide_fade_in + FadeInMixin. OutCubic, opacity 1.0 보장,
  enter<300ms·exit 더 빠르게. **빈도 기반 판단**: 펭귄 _IconBar·⚡ QuickDialog는
  무애니메이션(하루 수십 회 — Raycast 원칙). Toast는 아래서 페이드인 +
  마우스 올리면 타이머 정지. config animations_enabled + 설정 토글.
- **4단계 디테일**: DIALOG_HEADER 공유, 커서 정리.
- 교훈: PyQt는 CSS transition이 없어 모션을 QPropertyAnimation(windowOpacity/
  pos)으로 구현. QGraphicsEffect는 위젯당 1개라 그림자 있는 창엔 opacity 효과
  대신 windowOpacity를 쓴다. 자주 보는 UI에 모션을 넣지 않는 절제가 핵심.
- 테스트 77개(신규 test_motion.py 7: on/off 즉시성·토스트 호버·핫패스 무모션).

---

## 2026-07-21 — v0.14.1: QTextEdit 흰 배경 + 상세보기 단순화

- BASE_QSS에 QTextEdit 규칙 추가(CARD 흰 배경+테두리) — 상세내용 칸이
  페이지 배경색과 같아 보이던 문제 해결. postit·proof는 자체 스타일 유지.
- **EventItemCard `full` 플래그**: 기본(full=False)은 상세보기에 **메모만**,
  중요도는 접힌 줄의 칩을 눌러 QMenu로 변경(즉시 저장). EditPopup(할 일 보드
  ✎)만 full=True로 제목·일시·중요도 편집 유지. 캘린더·planner·DayDetail은
  기본 모드라 가벼워짐. compact _save는 메모만 갱신.

---

## 2026-07-21 — v0.14.2: 안내문구 보정 Gemini 홈 스타일 리디자인

- 사용자 요청(예약 실행): ProofDialog를 Gemini 홈 화면처럼 — 가운데 인사
  문구 + 둥근(radius 24) 입력창(pill). 2단 비교 뷰 → 단일 흐름으로 전환.
- **_PromptEdit**: Enter=보내기, Shift+Enter=줄바꿈. 입력창 하단에 공급자
  칩(Gemini/OpenRouter)·글자 수·✨다듬기 버튼.
- **로딩 표시**: 불확정 QProgressBar(setRange(0,0)) + "다듬고 있어요…" 라벨,
  보정 중 입력·버튼 잠금. 완료 시 숨김.
- **결과 등장**: motion.fade_in_widget(신규 — 레이아웃 안전 opacity 페이드,
  끝나면 효과 제거) 220ms OutCubic. 결과는 편집 가능 + 📋 복사.
- 개인정보 경계·툴팁 유지. 테스트 77개 + 보정 흐름 스모크(로딩/결과/Enter/
  Shift+Enter/실패/양 공급자) 통과.

---

## 2026-07-21 — v0.14.3: Gemini 모델 교체(404 수정) + 보정 창 미니멀 v2

- **장애**: 구글이 gemini-2.0-flash를 내려 보정이 404. DEFAULT_MODEL을
  gemini-3.5-flash로 올리고, `_RETIRED_MODELS` 집합으로 옛 config 값도
  호출 직전에 대체(설정 파일 마이그레이션 없이 안전). OpenRouter 기본도
  google/gemini-3.5-flash로. 교훈: 외부 모델명은 언젠가 은퇴한다 —
  기본값 하나 바꾸면 끝나도록 폴백을 코드에 둘 것.
- **디자인 v2(미니멀)**: 사용자 피드백 "세련+미니멀 아님, 창이 갑자기
  와이드". ① 내용을 가운데 열(최대 680px)에 고정 — 창을 늘려도 중앙 유지,
  창 자체도 setMaximumSize(960,900)로 제한 ② 파란 사각 버튼 → 원형 ↑
  보내기(38px) ③ Gemini 칩 → 연한 글씨 모델명 ④ 하단 닫기 줄 제거(OS
  타이틀바 X) ⑤ 로딩은 얇은 3px 진행선 ⑥ 결과 카드는 테두리 없는 본문.

---

## 2026-07-21 — v0.15.0: 보정 창 'Reword' 레퍼런스 리디자인 + 톤 선택

- 사용자가 HTML 목업(Reword)을 레퍼런스로 제공 → PyQt 번역:
  ① 2화면 QStackedWidget(입력↔결과) ② 그라데이션 헤드라인(글자별 색 보간
  `_gradient_html` — QLabel은 background-clip 미지원) ③ 유리 카드 입력 +
  ✕ 지우기 ④ **톤 칩 4종**(체크 시 검정 배경) ⑤ 검정 풀폭 CTA
  ⑥ 결과: ← 다시 작성/원본 요약/제안 카드 **타이핑 효과**(QTimer,
  전체 ~3초 내 완료, 2000자 초과·애니메이션 off면 즉시)/🔄 다른 버전
  ⑦ 복사 토스트.
- **proofread 톤 파라미터**: TONES 4종을 PROMPT의 {style}로 주입,
  provider 함수는 완성된 프롬프트를 받도록 시그니처 정리.
- 타이핑 중 복사 대비: _copy가 타이핑을 멈추고 전문으로 채운 뒤 복사.
- v0.14.3(직전): gemini-3.5-flash 교체 + _RETIRED_MODELS 폴백, 중앙 열
  고정·창 최대 크기 제한. 스모크: 톤→프롬프트 캡처 검증, 2화면 전환,
  타이핑 완주, 실패 경로. 테스트 77개 유지.

---

## 2026-07-21 — v0.15.1: 톤 선택 제거 (격식·명확 고정)

- 사용자 결정: 분위기 선택 칩 제거, "격식있고 명확하게" 단일 톤.
  proofread 기본 tone="formal", 다이얼로그는 칩 없이 바로 CTA.
  결과 헤더 "✨ 다듬은 글" 고정. TONES 자체는 남겨둠(추후 재활성 가능).

---

## 2026-07-21 — v0.15.2: 체크박스·라디오 커스텀 인디케이터 + 형광펜 버그

- 사용자 스크린샷 버그 2건: ①설정 항목 뒤 파란 띠 — 전역
  `QWidget{background:BG}`가 흰 카드 위 row 래퍼·QRadioButton에 BG를 칠함
  → row/proof_area transparent + QRadioButton 전역 transparent
  ②체크·라디오 인디케이터 소실 — 전역 QSS가 걸리면 Qt가 네이티브
  인디케이터를 못 그림 → **::indicator 직접 정의**: 체크박스 18px 둥근
  사각(체크 시 PRIMARY 배경+흰 ✓ SVG — QSS가 data: URI를 못 받아 임시
  폴더에 svg 파일 생성 `_check_icon_path`), 라디오는 checked에
  qradialgradient로 링+점.
- 교훈: 전역 스타일시트를 쓰는 앱은 체크박스·라디오 인디케이터를 반드시
  직접 정의해야 한다(half-styled 상태가 제일 못생김).

---

## (다음 기록은 여기에 이어서)

## 2026-07-21 (v0.16.0) — 위젯 통일·＋추가·전면 감사
- **사용자 요청 4건**: ① 일정 카드 아래 칸을 '메모'가 아닌 등록 때 저장한 **상세내용**으로
  (명칭 통일 + 등록 창 열 때 옛 일정의 빈 상세내용에 쪽지 원문 자동 채움),
  ② 할 일 보드를 주간 위젯과 같은 스타일로(중요도색 알약 필드·이모지 제거·열 규격 통일),
  ③ 일정 수정 모달 제목·일시·중요도 **한 줄 바**, ④ 주간·할일 위젯 헤더 **＋ 버튼** →
  AddEventDialog(한 줄 바+중요도+할 일 체크+상세내용, 로컬 전용).
- **전면 감사(에이전트 3방향: 죽은 코드/실시간 연동/UX 통일성)** 후 일괄 수정:
  - 연동: CalendarWindow·FloatingWidget subscribe 누수 수정(닫힐 때 unsubscribe,
    캘린더 창은 다시 열 때 재구독+refresh). 나머지 화면은 모두 정상 확인.
  - 안전: 일정 삭제에 '되돌리기' 토스트(등록 취소와 같은 규약), 데모 일정 일괄 삭제에 확인창.
  - 문구: 간편 등록→'바로 등록'으로 창 제목 통일, 신규 일정 버튼은 전부 '일정 등록',
    '할일'→'할 일' 띄어쓰기 통일.
  - 스타일: 제목 입력칸(TITLE_EDIT)·경고 라벨(WARN_LABEL) theme 공용화(3곳 중복 제거),
    등록 창 헤더 DIALOG_HEADER 적용, 바깥 카드 radius 16px→RADIUS_LG 토큰,
    ⠿ 그립 fpx(9)→fpx(11), 편집 모드 첫 진입 안내 토스트(세션 1회).
  - 죽은 코드: EventStore.set_google_id/todos, PRIMARY_TINT, 미사용 import 4건,
    DEFAULT_CONFIG의 문서용 4키(udb_select_rule 등) 제거. FONT_XL·SPACE_* 등
    토큰 스케일은 설계상 유지.
- EventStore.add에 priority 인자 추가. 테스트 77개 전부 통과 + 전 창 스모크
  (재구독 사이클·삭제 되돌리기 경로 포함).
- 배운 점: subscribe하는 창은 반드시 해제 시점을 짝으로 설계할 것 —
  `lambda: singleShot(0, refresh)` 콜백은 _notify의 RuntimeError 자동 정리에
  안 걸리므로(예약만 하고 리턴) 누수가 조용히 쌓인다.

## 2026-07-21 (v0.17.0) — 업데이트 화면 리디자인·설치 아이콘 구분·버튼 아이콘화
- **업데이트 안내·진행 창**(ui/update_dialog.py 신설): 클로드 앱 무드(크림 배경·
  세리프 헤드라인·테라코타 CTA) 2화면 — 안내(버전 알약+변경사항 카드) →
  진행(백그라운드 다운로드 + MB/% 게이지). 기존 QMessageBox+멈춘 커서 방식 대체.
  updater.download_installer에 progress 콜백 추가(기존 호출 호환).
- **설치파일 아이콘 구분**: tools/make_setup_icon.py — app.ico에 초록 ↓ 배지를
  얹은 assets/setup.ico 생성(커밋), installer.iss SetupIconFile 교체.
  16px에서도 보이도록 작은 크기일수록 배지 비율을 키움.
- **할 일 체크박스**: 전역 18px 고정이 좁은 열에 너무 컸음 — _TodoRow에서
  indicator를 fpx(13) 기준으로 재정의해 A−/A＋ 배율을 따라가게.
- **A−/A＋ 버튼**: 'A−' 같은 조합 글자가 PC에 따라 빈 상자로 보이는 문제
  (전에 🔧 이모지와 같은 원인) — icons.py에 stroke 기반 font_minus/font_plus
  SVG를 그려 아이콘 버튼으로 교체.
- 배운 점: 사용자 PC 글꼴에 기대는 특수문자·이모지는 전부 SVG로 —
  세 번째 같은 유형(🔧, ⚿? 아님, A−) 문제. 앞으로 버튼 글리프는 icons.py 원칙.

## 2026-07-22 (v0.17.1) — 일정 수정 창 일시 입력 통일
- EventItemCard(full)의 QDateTimeEdit(기본 Qt 달력)를 등록 창들과 같은
  DatePickerButton + TimeCombo로 교체 — 앱의 날짜·시간 입력이 한 부품으로 통일.
  '00:00=종일 자동 판단' 대신 시간 콤보의 '종일' 항목으로 명시 선택.
- 저장 왕복 테스트(시간 변경·종일 전환) 통과.

## 2026-07-22 (v0.18.0) — ? 도움말 클릭 말풍선 + ⠿ 드래그 들어올리기 모션
- ui/help_dot.py 신설: HelpDot(QPushButton) — 클릭 시 Popup 말풍선(어두운 카드,
  화면 경계 클램프), 호버 툴팁 겸용. 설정 창 _help_dot 3곳·보정 창 ? 교체.
  이유: 호버 툴팁은 사용자 PC에서 잘 발견되지 않음("눌렀는데 안 나와").
- _DragField에 _lift/_drop: 그립을 잡는 순간 PRIMARY_DARK 반투명 그림자가
  OutCubic 140ms로 퍼지며(blurRadius 0→16) 떠오르고, 커서가 쥔 손으로.
  놓으면 효과 제거. motion 꺼짐이면 그림자 즉시 적용(피드백은 항상).
  그립 기본 커서 SizeVer→OpenHand.
- 배운 점: 발견성 장치는 '기다리면 나온다'(툴팁)보다 '누르면 나온다'(클릭)가
  비전문가에게 훨씬 확실하다.

## 2026-07-22 (v0.18.1) — 인라인 편집 확대·편집바 정리
- _WeekField에 owner(edit_mode) 전달 — 주간 위젯도 편집 모드에서 제목 인라인
  수정 (_TodoRow와 동일 패턴·스타일).
- EventItemCard(compact)에 title_edit 추가: 상세보기에서 제목+상세내용 저장,
  구글 사본 제목도 갱신 시도. detail 영역을 흰 패널(#editzone, 테두리+radius)로
  감싸 '수정 중' 상태를 시각화.
- 편집바 투명도 슬라이더 stretch → 고정 110px, 📌·✕는 오른쪽 정렬.

## 2026-07-22 (v1.0.0) — 구글 연동 칩 버튼 + 버전 규칙 개편
- 설정 구글 연동 페이지: 라디오(로컬/구글 모드) → 칩 버튼 하나로 재설계
  (사용자 제안 흐름). 누르면 _GoogleLoginWorker(스레드)가 OAuth 브라우저
  로그인을 진행, 성공 시 google_sync_enabled 즉시 저장 + 초록 [✓ 연동됨] 칩.
  다시 누르면 확인 후 token 삭제·해제. 열쇠 파일 없으면 안내 문서를 바로 연다.
  google_sync.ensure_login() 추가 (로그인만 수행).
- 버전 규칙(CLAUDE.md): 부 버전 0~9 제한, 10 차례면 주 버전 상승 —
  0.18.1 다음 기능 릴리스라 v1.0.0.

## 2026-07-22 (v1.1.0) — COOL-비서 개명 + MD3 딥 네이비 전면 리디자인
- 사용자 제공 HTML 시안(MD3 토큰: primary #006699/#004d75, bg #f9f9fc,
  tertiary 보라 #571ac0) 기반 전면 재스킨. v0.14 토큰 체계 덕에 theme.py
  팔레트·radius(6/10/14→4/8/12) 교체만으로 전 화면이 일괄 전환됨 — 토큰
  투자 회수 완료.
- 시그니처 요소: EventItemCard 왼쪽 3px 중요도색 막대(_apply_card_style,
  중요도 변경 시 재적용), DIALOG_HEADER 밑줄형, SECTION_LABEL 신설,
  ACCENT 노랑→보라(터셔리), make_shadow 네이비.
- update_dialog: 크림·테라코타(클로드 무드) → theme 토큰 매핑으로 전환
  (모듈 구조 유지, 팔레트 상수만 재정의).
- 앱 이름 'COOL-비서' 전면 교체(창 제목·위젯·툴팁·installer AppName·문서).
  실행파일·설치 폴더(CoolmHelper)는 유지해 자동 업데이트 연속성 보장,
  installer [InstallDelete]로 옛 이름 바로가기 정리.
- 전 창 오프스크린 렌더 확인(캘린더/설정/업데이트/할일/날상세) + 테스트 77개.

## 2026-07-22 (v1.2.0) — 쿨쿠리 캐릭터 시스템 + 시그니처 오렌지 + 점 칩
- **쿨쿠리 무드**(penguin_icon.py 확장, 전부 내장 SVG): base/sleep/work/surprise.
  적용: 미니 위젯 펭귄(오늘 일정·밀린 일 없으면 sleep, store 구독으로 실시간,
  closeEvent unsubscribe), 간편등록 상태줄 옆 work, 알림 말풍선 surprise,
  할 일 보드 오늘 빈칸 sleep+"오늘은 한가해요". config character_mode(기본 켬).
- **시그니처 색 결정**: 쿨쿠리 부리색 오렌지(#f59300, SIGNATURE/-_BG/_DARK) —
  네이비 본체의 보색 포인트. '오늘'(할일 보드 오늘 열·주간 오늘 열)에만 사용.
- **중요도 점 칩**: 왼쪽 색 막대(사용자: "요즘 너무 많아 스트레스") 제거 →
  중립 알약 + 색 점(icons.dot_icon / 라벨은 리치텍스트 ●). priority_chip 개편.
- **설정 일반 재구성**: 미니/상세 라디오 → 칩 버튼(_pick_style), 자동실행·
  애니메이션·캐릭터 모드를 '기능' 카드로 통합.
- 렌더 검증: 무드 4종·할일보드·간편등록·설정. 테스트 77개 통과.

## 2026-07-22 (v1.2.1) — 잠자는 쿨쿠리 리터치
- 사용자 피드백("너무 구려, 잠만보 느낌으로") — SLEEP_SVG 재작도:
  벌러덩 등누움 + 배 위 손 + ︶︶ 감은 눈 + 볼터치 + 위로 뜬 발.
  오프스크린 렌더 2회 반복으로 비례 다듬음.

## 2026-07-22 (v1.3.0) — 프리미엄 신뢰 무드 전면 리디자인 (전 화면 통일)
- 사용자 시안(Apple/Linear/Notion/Stripe 급 절제 UI) 기준 전 화면 통일.
  theme.py 토큰 허브 덕에 대부분 자동 전파.
- theme: RADIUS 6/10/16 + 신설 RADIUS_XL=20, make_shadow 완화(옅고 큰 확산,
  파란 글로우 제거), ACCENT 보라→중립 슬레이트(보라 리터럴 폐기), BORDER_SUBTLE,
  FONT_XXL/HERO 신설, DIALOG_HEADER 밑줄 제거, SYSTEM_QSS(QMessageBox·QMenu
  스코프 전역 — main.py app.setStyleSheet, 반투명 위젯 회귀 방지).
- 카드 무테+그림자 스윕: floating/mini/desk/calendar/alerts/update/proof.
- proof_dialog 대수술: _gradient_html 삭제(단색 네이비 헤드라인), 검정 CTA→
  PRIMARY 네이비, 유리카드 24px→RADIUS_XL 무테.
- update_dialog: CORAL→ACCENT 별칭 정리, radius/폰트 토큰화, docstring 갱신.
- 보라 제거: 주간 주말강조 PRIMARY_LIGHT, 데모뱃지 PRIMARY. '오늘'만 시그니처
  오렌지(floating today_label 포함). favorites TITLE_EDIT 재사용.
- 검증: 77 테스트 + 8화면 오프스크린 렌더 확인. 보라 리터럴 0.

## 2026-07-22 (v1.3.1) — 시작 크래시 긴급 수정
- v1.3.0의 alerts.py가 쿨쿠리 추가 시 QHBoxLayout을 import 없이 사용 →
  시작 알림 말풍선 생성에서 NameError로 앱이 시작하자마자 죽음(위치 무관).
  오프스크린 렌더 스모크에 AlertBubble이 빠져 있어 못 잡았음.
- import 추가로 수정 + tests/test_widgets_smoke.py 신설(모든 상위 위젯을
  실제 생성 — AlertBubble 포함, 79개). 이 유형 회귀 차단.

## 2026-07-22 (v1.4.0) — 구글 연동 원클릭화 + 시작 가시성 + 소소한 정리
- **구글 연동 대개편**: requirements에 google-api-python-client/google-auth-oauthlib
  포함(이전 버전 exe에는 라이브러리가 아예 없어 연동 불가!) + build.py hidden-import.
  discovery 뭉치는 동봉 대신 static_discovery=False. credentials/token을 exe 옆
  calendar_sync/로 이동(업데이트 [InstallDelete]에 안 지워짐 — 로그인 유지),
  credentials_path()/token_path()/install_credentials() 신설.
  설정: '설정 안내 열기'(MD 열림) 삭제 → 앱 내 준비 마법사(콘솔 링크 2개 +
  QFileDialog로 열쇠 JSON 가져오기 → 자동 복사 → 즉시 로그인 이어짐).
- **실행 가시성**: main.py QLockFile 단일 실행 가드(중복 실행 시 안내 후 종료),
  시작 알림이 없어도 "켜졌어요" 말풍선 1회 표시.
- 위젯 📌 고정을 편집바에서 헤더(편집 버튼 옆)로 이동 — make_pin_button().
- 글다듬기 placeholder "안내할 내용을 간략하게 적어주세요.", 설정의
  화면 전환 애니메이션 항목 삭제(기본 켬 고정).
- 배운 점: '기능이 어렵다'는 불만의 반은 기능이 아예 빠져 있던 것(라이브러리
  미동봉). 배포물 기준으로 기능을 검증할 것.

## 2026-07-22 (v1.4.0 추가) — 공용 구글 클라이언트 내장 + CI 멈춤 수정
- 사용자가 발급한 OAuth 클라이언트를 calendar_sync/app_client.py로 내장 —
  이제 열쇠 파일 없이 [연동하기]→로그인만으로 끝. 개인 credentials.json이
  있으면 그쪽 우선. 준비 마법사 삭제(더 이상 불필요).
- libs_available()가 BaseException까지 잡음 — 손상된 설치의 rust 패닉 대응.
- v1.3.1 빌드가 테스트 단계에서 무한 대기: 새 위젯 스모크가 Windows 러너에서
  pywinauto/UIA 캡처를 실제 실행(리눅스에선 import 실패로 조용). COOLM_NO_CAPTURE
  가드(warmup·⚡ 캡처)+테스트에서 설정, 워크플로 timeout-minutes:30 추가.
  (멈춘 러너는 취소 권한이 없어 자연 타임아웃에 맡김 — 늦게 성공해도
  version.json 푸시는 non-FF로 실패해 새 버전을 덮지 않음)

## 2026-07-22 (v1.4.1) — 시간 선택 UX·글다듬기 편의
- TimeCombo: 편집형 → 순수 선택형. 기본값 = 지금을 30분 단위로 올린 시각
  (종일 기본 폐지 — 사용자 결정), 종일은 첫 항목 유지, 감지된 임의 시각
  (14:05)은 목록에 삽입. 열면 현재 선택 근처가 보여 스크롤 피로 최소.
- ProofDialog: 헤드라인 2줄 제거 → 부제 하나를 메인으로. API 키 없으면
  _ask_api_key 모달(공급자 선택+키 입력+발급 페이지 링크)이 그 자리에서
  받고 config에 저장.

## 2026-07-22 (v1.4.2) — 복사 버튼 강조
- proof 결과 카드의 '복사'(텍스트 버튼) → copy SVG 아이콘 + 채운 네이비
  [복사하기] — 결과 화면의 주 행동으로 승격. icons.py에 "copy" 추가.

## 2026-07-22 (v1.5.0) — 오늘 할 일 위젯 + 플래너 3주 보기
- TodayTodoWidget(kind="today"): 오늘 일정만 _TodoRow로 나열, 시그니처
  오렌지 헤더, 빈 상태 잠자는 쿨쿠리, ＋버튼. DEFAULT_CONFIG·DESK_KINDS·
  _widget_class·설정 목록 등록 (desk_conf가 구 config에 자동 보충).
- AlertBubble 클릭 → today 위젯 1회 자동 켬(apply_desk_widget, 실패 무해).
- PlannerWidget 상세보기: 선택 날짜 하루 → 선택 날짜부터 3주(RANGE_DAYS=21)
  날짜별 소제목 그룹, 오늘은 SIGNATURE_DARK.
- 그립 힌트: paintEvent(카드 아래 깔려 배경따라 안 보임) → _GripHint 오버레이
  (카드 위, 마우스 통과)로 전 위젯 가시화 + 우하단 24×24 코너 리사이즈 판정.
- HelpDot: Popup 말풍선 → [확인] 모달(놓치지 않고 읽게).

## 2026-07-22 (v1.5.1) — 쪽지 목록 아이콘 교체
- 간편 메뉴·상세 위젯의 쪽지 목록 아이콘 inbox → mail(편지 봉투, 네이비).
  icons.py의 inbox 정의 삭제(사용처 0).

## 2026-07-22 (v1.5.2) — 그립 실제 동작 수정 + 휠 월넘김 차단 + 메뉴 크기
- _GripHint가 WA_TransparentForMouseEvents라 아래 스크롤 영역이 클릭을
  삼켜 리사이즈가 시작되지 않던 버그 — 그립이 마우스를 직접 받아 부모의
  코너 리사이즈로 위임(press에서 _mode/_edges 설정, move/release 전달).
  드래그 시뮬레이션 테스트로 크기 변화·geometry 저장 확인.
- EventCalendar: qt_calendar_calendarview에 eventFilter로 Wheel 차단
  (월 이동은 ◀▶만 — 플래너·캘린더 창·날짜 피커 공통).
- 펭귄 메뉴 크기 설정(menu_scale 100/135) — _IconBar 버튼·아이콘 스케일,
  설정 일반 '메뉴 크기' 칩. 배운 점: 어포던스(점점)를 옮기면 히트 영역도
  같이 옮겨야 한다 — 보이는 곳과 잡히는 곳이 달라지면 고장으로 느껴진다.

## 2026-07-22 (v1.5.3) — 플래너 상세보기 헤더 토글 + 핀 정리
- make_pin_button 제거(사용자: 헤더에 굳이 필요 없음 — 우클릭 메뉴로 충분)
  → 범용 make_header_toggle로 대체. 플래너 상세보기를 편집바 체크박스에서
  헤더 ☰ 토글(icons "list")로 이동 — 편집 모드 없이 바로 접고 편다.

## 2026-07-22 (v1.6.0) — 크기 연동 글씨·해상도 가드·트레이 아이콘
- 글씨 자동 배율: auto_font_factor(h/BASE_H → 0.85/1.0/1.15/1.3 스냅) ×
  사용자 A± %. resizeEvent 단일 경로에서 단계 변화 시에만 refresh —
  드래그 중 실시간(사용자 결정)이지만 계단식이라 출렁임 없음. 생성 시점
  배율을 _last_font_step에 기록해 첫 배치에서도 정확. BASE_H: simple 250 /
  today 300 / weekly 240 / planner 520. 단위 테스트 추가(80개).
- 해상도 변경 가드: primaryScreenChanged + availableGeometryChanged →
  500~600ms 뒤 _ensure_on_screen. WidgetBase는 기본 복귀, MiniWidget은
  오른쪽 벽 재도킹(+y 클램프), DeskWidgetBase는 place_default 복귀
  (닫힌 위젯 지연 호출 RuntimeError 가드).
- 트레이 아이콘(main.py, isSystemTrayAvailable 가드): 클릭=펭귄 복귀,
  메뉴 = 펭귄 보이기/캘린더/설정/종료. SYSTEM_QSS로 메뉴 스타일 통일.
- 배포는 사용자 요청으로 2시간 뒤 실행 예약.

## 2026-07-22 (v1.6.1) — 트레이로 보내기
- v1.6.0은 '꺼내기'만 있었음(사용자: "어떻게 보내지?") — WidgetBase.
  send_to_tray(hide + 1회 안내 풍선) + 미니/상세 우클릭 메뉴 '트레이로 보내기'.
- _in_tray 플래그: 트레이로 보낸 상태는 해상도 가드가 다시 꺼내지 않게,
  showEvent에서 자동 해제(트레이 클릭 복귀와 자연 연동).

## 2026-07-22 (v1.6.2 준비 — 배포 보류) — 트레이 왕복 (개별 최소화)
- 위젯 헤더 – (make_tray_button, icons "minimize") = **그 위젯 하나만**
  최소화(_minimize_to_tray: self.hide + 세션1회 안내 풍선 show_tray_tip).
  펭귄 우클릭 '트레이로 보내기' = 펭귄만. **트레이 아이콘 클릭 = 전부 복귀**
  (main bring_back: _in_tray 표시된 데스크 위젯 전원 + 펭귄은 숨김/화면밖일
  때만 재배치 — 위젯만 최소화 시 펭귄이 안 튀게). _desk_widgets_flat로
  notes dict 평탄화, WidgetBase가 app._coolm_widget 등록.
- **릴리스 규칙 변경(CLAUDE.md)**: 사용자가 "한번에 해줘"라고 할 때만
  main 병합·배포. 이 커밋부터 브랜치에만 쌓는다.

## 2026-07-23 (v1.6.3) — 달력 휠 잠금 + 선택 날짜 주황
- **휠 월 넘김 완전 차단**(calendar_view.py): 기존 필터가 내부 뷰에만 붙어
  실제 휠은 QAbstractItemView의 viewport로 가 안 막혔음 — view.viewport()에도
  installEventFilter + 방어적 wheelEvent no-op. 오프스크린 테스트로 6회 휠 후
  monthShown/yearShown 불변 확인. (월 이동은 ◀▶ 버튼만)
- **선택 날짜 배경 시그니처 주황**(theme.py CALENDAR_QSS): QAbstractItemView
  selection-background-color PRIMARY→SIGNATURE(흰 글자 유지). 리스트/테이블
  파랑 선택색은 그대로.
- 캐릭터(펭귄 SVG)는 이번 세션에서 정장 리디자인을 시도했으나, 사용자가 직접
  이미지를 올리기로 해 **대화 시작 시점(v1.6.2) 원본으로 되돌림**. (base는
  기존대로 assets/penguin.png가 있으면 우선 사용.)
- 80 테스트 통과.

## 2026-07-23 (v1.6.4) — 플래너 달력 선택 주황 실동작 + 설치 기본값 6종
- **버그 수정**: 플래너 위젯 달력의 선택 날짜가 v1.6.3에서도 회색이던 문제 —
  desk_widgets._scale_calendar가 글씨 크기 stylesheet를 달력 본체에 직접 걸며
  조상(CALENDAR_QSS)의 선택색을 덮어썼음. _scale_calendar에도
  selection-background-color:SIGNATURE·selection-color:white 명시. 렌더로 확인.
- **처음 설치 기본값(DEFAULT_CONFIG, 사용자 결정 2026-07-23)**:
  펭귄 위젯=상세(widget_style="detail"), 메뉴크기=보통(100, 유지),
  캐릭터 변환모드=켬(유지), 즐겨찾기·안내문구 보정=끔(유지),
  바탕화면 위젯=주간 하나만(planner off·weekly on),
  Windows 시작 자동실행=처음 설치 시 켬(load_config 새 config 생성 시
  autostart.enable, winreg 없는 OS/테스트는 조용히 skip).
- test_default_config_not_polluted를 새 기본값(weekly on)으로 갱신. 80 통과.

## 2026-07-23 (배포 대기 — 시크릿 등록 후) — 안내문구 보정: 내장 키 + 폴백
- proofread.py: 사용자 본인 키 우선 → 없으면 **내장 공용 OpenRouter 키**로 동작.
  `embedded_openrouter_key()`가 assets/proof.key(base64) 읽음(없으면 무시).
  모델은 값싼 Flash 기본(google/gemini-2.0-flash-001) + 폴백(gemini-flash-1.5,
  gpt-4o-mini). 400/404=모델문제→다음 후보, 401=키, 402=크레딧 안내, 429=과다.
  권장 헤더(HTTP-Referer/X-Title) 추가. (기존 버그: 설정이 모델키를 저장 안 해
  죽은 기본모델 고정 → 해소.)
- settings_dialog: 'AI 모델(비워두면 기본값)' 입력칸 + "키 비워도 기본 제공 키로
  동작" 안내. 모델은 provider별 키로 저장.
- 보안: 공개 repo라 키는 소스에 안 넣고 릴리스 워크플로가 시크릿
  OPENROUTER_KEY → assets/proof.key로 빌드 때만 주입. .gitignore에 proof.key 추가.
- 테스트 7종 추가(tests/test_proofread.py, urlopen mock). 전체 87 통과.
- 배포 전 준비: OpenRouter 키 발급+한도 → GitHub repo secret OPENROUTER_KEY 등록.

## 2026-07-23 (v1.6.5) — 안내문구 보정: 키 입력 UI 제거(내장 키 전용화)
- 설정에서 API 키/공급자/모델 입력칸을 모두 제거 — '안내문구 보정(AI)' 체크 하나로.
  내장 공용 키(assets/proof.key)로 동작하므로 동료는 키 없이 켜기만 하면 됨.
  (기존에 본인 키를 config에 저장한 사용자는 proofread가 그 키를 계속 우선 사용.)
- _sync_proof_area/_open_key_page 제거, _save에서 proof 키 저장 라인 제거.
- 배포 v1.6.5. (내장 키는 repo secret OPENROUTER_KEY 있을 때만 빌드에 포함.)

## 2026-07-23 (v1.6.6) — 글 다듬기 헤더 인코딩 버그 핫픽스
- OpenRouter 요청의 X-Title 헤더에 한글("COOL-비서")이 들어가 HTTP 헤더
  latin-1 인코딩 실패("'latin-1' codec can't encode…")로 요청이 안 나갔음.
  → X-Title을 영문("COOL Helper")으로. 헤더 latin-1 안전성/한글 본문 통과
  테스트 2종 추가(test_proofread.py). 89 통과.

## 2026-07-23 (v1.6.7) — 글 다듬기 프롬프트 개선 + Enter 실행 제거
- proofread.PROMPT를 소극적('맞춤법만')에서 적극적 윤문(구어체→공지문, 문장 분리·
  재배열, 존댓말 통일) + 예시 1개 few-shot으로 교체. TONES도 지시형으로.
  사실(날짜·숫자·이름·링크·의미)·없는 인사말/서명 금지 제약 유지.
- proof_dialog: _PromptEdit(Enter=보내기) 제거 → 일반 QTextEdit(Enter=줄바꿈).
  '글 다듬기'는 버튼 클릭으로만 실행(실수 방지). 버튼 툴팁·submitted 연결 정리.
- 89 테스트 통과. 배포 v1.6.7.

## 2026-07-23 (v1.6.8) — 글 다듬기 기본 모델 Gemini 3.6 Flash
- OPENROUTER_MODEL을 google/gemini-3.6-flash로. 폴백은 2.5-flash → 2.0-flash-001
  → gpt-4o-mini(슬러그 안 맞으면 자동 강등). 모델 못 찾음 메시지도 정리.
- 89 테스트 통과. 배포 v1.6.8.

## 2026-07-23 (v1.6.9) — 선택 날짜 주황: 포커스 잃어도 유지 (직접 그리기)
- 증상: 플래너 위젯에서 선택 날짜가 여전히 회색. 원인은 Qt가 창이 비활성일 때
  선택색을 회색(inactive highlight)으로 바꿔 스타일시트 주황을 덮어씀.
- 해결: EventCalendar.paintCell에서 선택 셀 배경을 시그니처 주황 둥근사각형으로
  '직접' 그리고 숫자는 흰색 볼드. 포커스 유무·QSS·팔레트와 무관하게 항상 주황.
  (CalendarWindow에도 동일 적용.) 89 테스트 통과. 배포 v1.6.9.
