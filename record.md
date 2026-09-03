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

## 2026-07-23 (v1.6.10) — 선택 날짜 색을 파스텔 주황으로
- 선택 날짜 배경을 쨍한 SIGNATURE(#f59300) → 파스텔 SIGNATURE_SOFT(#ffe0c2),
  숫자는 SIGNATURE_DARK로. 사용자 선택(C, 아주 연한 파스텔). 89 통과. v1.6.10.

## 2026-07-24 — 무드별 펭귄 이미지 지원 재추가
- v1.6.3에서 캐릭터를 원본으로 되돌릴 때(git checkout f4615fd -- penguin_icon.py)
  무드별 이미지 지원까지 같이 날아갔음 → 재추가. assets/에 penguin.png(평소),
  penguin_sleep/work/surprise.png가 있으면 SVG 대신 사용, 없으면 SVG 폴백.
- 사용자가 직접 만든 캐릭터 이미지를 넣을 준비. (배포는 이미지 도착 후 한 번에)

## 2026-07-24 (v1.7.0) — 새 캐릭터 이미지 + 펭귄 크기 조절
- 사용자가 만든 3D 펭귄(안경·넥타이) 이미지를 assets/에 반영: idle→penguin.png,
  sleep→penguin_sleep.png, schedule→penguin_work.png, surprise→penguin_surprise.png.
  원본이 720px 캔버스에 내용 30~40%뿐이라 투명 여백 crop→정사각 패딩(8% 여유)→512px.
  업로드된 electron 원본 폴더는 assets/에 두면 exe에 통째로 들어가므로
  character_source/로 이동(빌드 미포함).
- 펭귄 크기 조절: config penguin_scale(%), MiniWidget.penguin_px()/_resize_to_penguin()
  으로 픽스맵·창 크기 동시 반영(오른쪽 벽 도킹 유지). 설정 → 일반에 칩 4종
  (작게70/보통100/크게140/아주크게190). 89 테스트 통과. 버전 규칙(부 0~9)에 따라 v1.7.0.

## 2026-07-25 — 아이콘 새 캐릭터 반영 + 펭귄 기본 '크게'
- app.ico / setup.ico를 새 캐릭터로 재생성(tools/make_icon.py → make_setup_icon.py).
  두 파일은 한 번 만들어 커밋하는 바이너리라 캐릭터 교체 시 수동 재생성 필요.
  나머지 화면(미니위젯·간편등록 work·위젯 빈상태 sleep·알림 surprise·창 아이콘)은
  전부 penguin_pixmap 경유라 자동 반영됨. 업데이트 창은 텍스트뿐 — 캐릭터 없음.
- 펭귄 기본 크기를 '크게'(140)로: DEFAULT_CONFIG + mini_widget/settings 폴백까지
  140으로 맞춰 기존 사용자도 크게로 보이게. 89 테스트 통과.

## 2026-07-25 (v1.7.1) — 첫 실행 인트로 모션
- ui/intro.py 신규: 전체화면 투명 오버레이에서 펭귄이 ①뿅 등장(OutBack)
  ②통통 인사 ③④말풍선 3단 ⑤오른쪽 벽으로 축소 이동(InOutCubic) ⑥페이드아웃.
  총 4.2초, [건너뛰기]·아무데나 클릭으로 종료, motion 꺼져 있으면 미재생.
  three.js/QtWebEngine 대신 Qt 애니메이션 — 용량 증가 0.
- alerts.show_startup_alerts: 첫 실행(intro_done False)일 때 인트로 먼저 →
  끝나면 기존 안내 말풍선(INTRO_STEPS)으로 체인.
- 89 테스트 통과 + 스킵/콜백/중복종료/비활성 케이스 수동 검증.

## 2026-07-25 (v1.7.2) — 업데이트 직후 인사 모션
- intro.py 일반화: IntroOverlay(lines=...)로 문구 주입, 문구 수에 맞춰 타이밍
  자동 조정(문구당 900ms). update_lines(version, notes)가 "vX로 업데이트했어요"
  + 변경점 최대 2줄(42자 컷) + 응원 멘트(CHEERS 4종, 버전 해시로 선택) 구성.
  play_update_intro() 추가.
- 변경점 전달: update_dialog._remember_notes()가 다운로드 시작 시
  config["pending_update_notes"]에 저장 → 설치·재시작 후 사용.
- 감지: alerts._is_new_version(last_seen_version != APP_VERSION, 기록 없으면
  최초 설치로 보고 첫 실행 인트로) / _mark_version_seen()으로 기록·정리.
- tests/test_intro.py 9종 추가(문구 구성·자르기·불릿 제거·버전 감지). 98 통과.

## 2026-07-25 (v1.7.3) — 업데이트 인사가 안 뜨던 버그 수정
- 원인: _is_new_version이 `bool(seen) and seen != APP_VERSION`이라, 기능이
  처음 들어간 v1.7.2로 올라온 사용자는 last_seen_version 기록 자체가 없어
  False → 인사 미재생. 게다가 그 경로에서 기록도 안 남겨 다음 업데이트도
  계속 안 뜰 상태였음.
- 수정: 기록 없음도 업데이트로 간주(호출 시점엔 이미 첫 실행을 걸러낸 뒤라
  안전). 인사를 못 띄워도 _mark_version_seen을 항상 호출해 기록.
- 변경점 폴백: 옛 버전에서 올라오면 pending_update_notes가 없으므로
  앱에 동봉된 release_notes.txt를 읽는다(_bundled_notes). build.py가
  release_notes.txt를 dist에 포함하도록 추가.
- 테스트 3종 추가(기록 없음=업데이트, 재발 방지, 동봉 노트 읽기). 100 통과.

## 2026-07-25 (v1.7.4) — 펭귄 안경 렌즈 구멍 메움
- 증상: 3D 렌더 원본이 안경 렌즈 안쪽을 투명(alpha 0)으로 남겨, 바탕화면 위에서
  눈 위쪽으로 배경이 비쳐 보임(사용자 제보).
- tools/fix_penguin_eyes.py 신규: (0,0)에서 이어지지 않는 '갇힌 투명 영역'만
  floodfill로 찾아 → 완전 투명(alpha<128)은 가장 가까운 머리색으로 채우고,
  반투명(128~249, 안경테)은 색을 살린 채 불투명화. 채운 안쪽만 가우시안으로
  부드럽게(거리변환 방사형 줄 제거). 4종 합계 약 1.1만 px 메움, 잔여 0.
  ※ PIL ImageDraw.floodfill은 배열 기반 이미지에서 동작 안 함 → .copy() 필수.
- app.ico/setup.ico도 고친 그림으로 재생성. 100 테스트 통과.

## 2026-07-25 (v1.7.5) — 눈 구멍 수정: 한쪽만 메워지던 문제
- v1.7.4는 '바깥과 이어지지 않은 투명 영역'(floodfill)만 구멍으로 봤는데,
  한쪽 안경테에 틈이 있어 그 렌즈가 배경과 연결 → 구멍으로 인식 못 함
  (사용자: "한쪽 눈만 채워졌어").
- fix_penguin_eyes.py를 실루엣 기준으로 변경: solid=alpha>=200에
  ndimage.binary_fill_holes → 내부 빈 곳 전부 검출(틈 유무 무관).
  원본에서 다시 만들어 이중 적용 방지 후 재실행 → 4종 모두 잔여 0px.
- 아이콘 재생성. 100 테스트 통과.

## 2026-07-25 (v1.7.6) — 긴 제목이 중간부터 보이던 문제
- QLineEdit은 setText/생성자 모두 커서를 끝에 두어, 칸보다 긴 제목은 뒷부분만
  보였음(사용자: "제목이 중간에서부터 나오네"). setText/생성 직후
  setCursorPosition(0) 추가 — review_dialog, quick_dialog(2곳), favorites_view,
  desk_note, calendar_view(2곳), desk_widgets(2곳) 전부 통일. 100 테스트 통과.

## 2026-07-25 (v1.7.7) — 인트로를 클릭 진행식으로
- 기존엔 타이머로 문구가 자동 전환돼 "저 혼자 말하고 넘어간다"는 피드백.
  QTimer 자동 전환 제거 → build()는 등장 모션만, advance()가 클릭마다
  다음 문구 + _hop()(OutBounce 깡충). 마지막 문구에서 한 번 더 클릭하면
  _fly_away()로 도킹·페이드아웃 후 finish().
- 등장 모션 중 클릭은 등장을 즉시 완료(문구는 유지), 날아가는 중 클릭은 무시.
- 하단에 '클릭하면 다음 →' 힌트(마지막엔 '클릭하면 시작해요 →'),
  스페이스/엔터로도 진행, Esc·[건너뛰기]는 즉시 종료. 100 테스트 통과.

## 2026-07-25 (v1.7.8) — 클릭 자막 강화 + 뒤뚱뒤뚱 걷기 모션
- 클릭 안내를 회색 소문에서 알약 자막("👆 화면을 클릭하면 다음 말로 넘어가요",
  CARD 배경·PRIMARY_DARK 볼드)으로 + opacity 1.0↔0.45 무한 펄스로 시선 유도.
  마지막 문구에선 "👆 한 번 더 누르면 시작해요!"로 전환(재중앙 정렬).
- 돌아가기 모션을 비행 → 걷기로: _walk_away()가 그림을 좌우 반전(QTransform
  scale(-1,1), 뒤돈 느낌)하고 QVariantAnimation(2.4s, InOutSine)으로 진행.
  _walk_tick()이 프레임마다 발끝을 축으로 sin 갸우뚱(±9°, 7걸음) + |sin| 통통
  + 크기 축소를 QPainter로 직접 그림(회전 잘림 방지 pad 18%). 도착 후 페이드아웃.
- 100 테스트 통과.

## 2026-07-25 (v1.7.9) — 펭귄 우클릭 투명도 조절
- MiniWidget.contextMenuEvent에 '투명도' 하위 메뉴 추가(OPACITY_STEPS 5단계:
  100/85/70/55/40%). 현재 값에 체크 표시, 고르면 _set_opacity()가
  setWindowOpacity 즉시 반영 + config["widget_opacity"] 저장(기존 키 재사용
  → WidgetBase.apply_config가 재시작 시에도 그대로 복원).
- 100 테스트 통과 + 오프스크린으로 적용·저장·재시작 유지 확인.

## 2026-07-26 (v1.8.0) — 간편등록 포스트잇 직행 + 캡처/무드 버그 4건
- **캡처 실패(학교 PC)**: capture._cool_pid가 창 클래스 "CoolMsg50SingleInstance"
  정확 일치만 봐서 다른 버전에선 못 찾음 → ①정확 일치 ②클래스 접두어(COOLMSG/
  COOLMESSENGER) ③실행파일 이름(QueryFullProcessImageNameW) 3단계로 완화.
  capture.diagnose() 추가 + 펭귄 우클릭 '쪽지 읽기 진단…'에서 단계별 결과 확인
  (프로세스/창수/본문틀 개수/읽은 글자수) — 원인 파악용.
- **간편등록 개편**: 수정 창(QuickDialog) 대신 ui/quick_capture.quick_pin() —
  캡처(백그라운드) → 첫 후보 자동 등록(본문은 memo, 날짜 없으면 오늘) →
  pin_note로 포스트잇 부착 → 포스트잇에서 인라인 편집(기존 자동저장 활용).
  실패 시 클립보드 폴백 → 그것도 없으면 안내.
- **알림 방식**: show_toast는 부모 위젯 내부에 그려져 70px 펭귄에서 안 보임 →
  독립 창인 AlertBubble로 교체(_say).
- **자는 무드**: sections()의 today가 완료 항목까지 포함해, 다 끝내도 안 자던
  문제 → not e.done 필터 추가.
- tests/test_quick_capture.py 8종 추가(등록·핀·메모·빈제목·무드 4케이스). 108 통과.

## 2026-08-02 (v1.8.1) — 오래된 쪽지 날짜 오독 수정
- 사용자 지적: "오랜 시간이 지나고 쪽지를 확인할 수도 있잖아?" — 실제로 6월 쪽지를
  8월에 ⚡로 읽으면 (a) DB 매칭 실패 시 received=now 기준이라 '6월 5일'이
  _resolve_year 규칙(30일 이상 과거면 이듬해)에 걸려 **2027-06-05**로 밀리고,
  (b) candidates_from_message가 수신일보다 과거인 일정을 버려 후보가 사라졌음.
- 수정: candidates_from_message(allow_past=False) 매개변수 추가 — 화면 캡처
  경로에서는 True로 지난 날짜 유지. quick_candidates는 매칭 실패 시
  _pull_back_year()로 180일 넘게 미래로 밀린 날짜를 1년 당겨 올해로 되돌린다.
  (진짜 미래 일정은 그대로.)
- tests/test_quick_capture.py에 3종 추가(지난 날짜 유지·연도 당김·미래 유지). 111 통과.

## 2026-08-02 (v1.8.2) — 본문 읽기 3단계 폴백 (메시지 관리함 대응)
- 사용자 진단 결과: 창·프로세스·UIA 모두 정상인데 "창1 본문틀 1개/읽은 글자
  0자" — 크롬 자식에서 Document 컨트롤을 못 찾음. 사용자는 '메시지 관리함'
  창에서 쪽지를 읽는데, 이 창의 본문칸 폴백이 없었음.
- capture 개편: _uia_text_from_hwnd(Document 우선, 없으면 IsTextPatternAvailable
  요소) + _window_body 3단계 — ①웹뷰(크롬/Internet Explorer_Server) ②RichEdit/
  Edit/Static WM_GETTEXT ③최후엔 창 전체 UIA 탐색. read_current_message가
  이를 사용.
- diagnose 강화: 창마다 자식 부품 클래스 요약(상위 8종×개수)과 읽은 방법
  (웹뷰/텍스트칸/전체탐색)을 표시 — 다음에도 안 읽히면 원인이 바로 보인다.
- 111 테스트 통과. (실동작은 사용자 학교 PC 진단 재실행으로 확인 예정)

## 2026-08-02 (v1.8.3) — 포스트잇 날짜·시간 인라인 편집 + 처음 켜질 때 앞으로
- 요청 ①: 포스트잇 상단의 `📌 8/2(일) 14:30`이 읽기 전용 라벨이라 날짜를 고치려면
  캘린더 창을 열어야 했다 → 라벨 모양 그대로 **누를 수 있는 버튼**으로 바꾸고,
  누르면 작은 달력 + 시간 고르기(TimeCombo, 맨 위 '종일')가 뜨게 함.
  날짜를 고르면 바로 저장·팝업 닫힘, 시간만 바꿔도 즉시 저장. 기간 일정은
  길이(end−start)를 유지한 채 통째로 옮긴다. 구글 사본도 조용히 갱신.
- 요청 ②: 더블클릭·⚡로 새로 붙는 포스트잇이 다른 창 뒤에 숨었다. 바탕화면
  위젯은 평소 '항상 아래'라 raise_()만으로는 안 올라온다 → `flash_to_front()`:
  잠깐(6초) '항상 위'로 올렸다가 원래 설정으로 되돌린다. 그 사이 사용자가
  포스트잇을 쓰고 있으면(활성 창) 시간을 연장. **'항상 위 고정' 설정은 건드리지
  않는다** — 사용자 요구가 "고정이 아니라 처음에만 보이게".
- pin_note가 새로 만든 포스트잇/이미 떠 있는 포스트잇 모두 이 방식으로 올린다.
- tests/test_desk_note.py 신규 10종(라벨 표시·날짜/시간 저장·종일 전환·기간 유지·
  변화 없으면 저장 안 함·팝업 열림·앞으로 올렸다 원복·고정 설정 보존). 121 통과.

## 2026-08-02 — 포스트잇 색 고르기 (편집 모드)
- 요청: 편집 모드(🔧)에서 메모지 색을 바꿀 수 있게. theme에 POSTIT_PALETTE
  6색(노랑·분홍·주황·초록·파랑·보라) 추가 — 각 값은 (배경, 테두리, 날짜/✕ 글자색)
  으로 묶어 종이 색이 바뀌어도 글씨 대비가 유지된다.
- 도구줄에 점 6개를 늘어놓으면 좁은 메모지에서 넘쳐서, **지금 색 동그라미 1개**만
  두고 누르면 팔레트 팝업이 뜨게 함. 고른 색은 conf["color"]에 저장(재시작 유지).
- DeskWidgetBase.add_edit_bar_extras(lay) 훅 추가 — 도구줄에 위젯별 버튼을 끼우는
  자리. 투명도 슬라이더는 고정 폭(110) 대신 56~110 가변으로 바꿔 좁은 메모지에서
  칸이 밀리지 않게 함.
- tests/test_desk_note.py에 색 관련 8종 추가. 129 통과.

## 2026-08-02 — ⚡ 클립보드 등록은 물어보고 등록
- 요청: 간편 등록이 **클립보드에서 가져오는 경우에만** "클립보드에서 아래와 같은
  내용을 등록하시겠습니까?"라고 묻게. (화면에서 읽은 쪽지는 지금 보고 있는 것이라
  그대로 등록 — 물어보면 오히려 손이 하나 더 간다.)
- ui/quick_capture.py에 ClipboardConfirmDialog + confirm_clipboard() 추가.
  파싱 결과(📌 날짜·시간 + 제목)를 위에, 클립보드 본문 미리보기(600자까지)를
  아래에 보여주고 [취소]/[등록하기]. 취소하면 아무것도 등록하지 않는다.
  화면 캡처 경로(_finish 직행)는 그대로 — 확인 창이 끼어들지 않는다.
- 미리보기는 원문 그대로 보여준다 (CLAUDE.md: UI 미리보기 자동 마스킹 금지).
- tests/test_quick_capture.py에 6종 추가(물어봄·취소 시 미등록·화면 경로엔 없음·
  창 내용·긴 본문 자름). 134 통과.

## 2026-08-04 — 사용설명서 캐러셀 v2 (핵심→위젯→기타) + PDF
- 사용자 요청 구성으로 전면 재구성: ①핵심(간편등록·일정에서 등록)
  ②주요(바탕화면 위젯 2개씩 2장) ③기타(즐겨찾기·안내문구 보정·구글 연동).
- 간편등록 슬라이드: 쿨메신저 메시지 관리함 목업 + **커서가 펭귄으로 이동 →
  더블클릭(파문 2번) → 포스트잇이 팝 하고 나타나는** CSS 모션. "더블클릭!"
  말풍선 안내 포함.
- 캡처 전부 현재 UI로 재촬영(cap2.py): 새 3D 펭귄, 파스텔 달력 위젯 4종,
  ✓ 등록됨 일정등록 창, 즐겨찾기 보관함, 새 포스트잇. 데모 데이터는 교사
  시나리오(체험학습·교직원 회의 등), 이름은 ○○○ 마스킹.
- Artifact 게시(캐러셀 애니메이션판) + 인쇄용 정적 HTML → chromium
  print-to-pdf로 **A4 가로 8쪽 PDF** 생성해 전달. (PPT는 요청 시 변환)

## 2026-08-04 — 첫 ⚡ 간편등록 지연 해소 (프리워밍)
- 증상: 맨 처음 간편등록만 몇 초 걸리고 그 뒤로는 빠름 (사용자 보고).
- 원인: 쿨메신저 본문을 그리는 내장 크롬(CEF)은 **처음 UIA로 읽으려 할 때에야
  접근성 트리를 만든다** — 이 첫 준비가 수 초, 이후는 수십 ms. 기존 warmup은
  우리 쪽 UIA COM만 초기화했지 쿨메신저 쪽은 안 깨웠음.
- 수정: capture.prewarm() 신설 — 쿨메신저 창들을 백그라운드에서 미리 한 번
  읽고(결과 버림) 접근성 트리를 깨워둔다. widget_base 워밍업 스레드가
  시작 시 1회 + **90초마다 반복** (쿨메신저를 나중에 켜거나 메시지 관리함
  창을 새로 열어도 대비). 읽기 전용 UIA 조회라 쿨메신저 상태 변화 없음.
  prefetch_quick(매칭용 쪽지 캐시)도 같은 주기로 데워둔다.
- 보강: 그래도 읽기가 0.7초를 넘으면 "쪽지를 읽는 중이에요…" 말풍선으로
  알리고, 새 말풍선이 뜰 때 이전 말풍선은 닫는다.
- 테스트 3종 추가(프리워밍 무해성·배선 확인). 137 통과.

## 2026-08-07 — 워밍업 즉시화 + 위젯 레이어 일반 창처럼
- ① 첫 ⚡ 여전히 느림(사용자): 90초 주기로는 새로 뜬 쿨메신저 창(새 웹뷰)이
  다음 순번까지 차갑게 남았음 → **감시 4초 주기**로 변경. capture.prewarm이
  깨운 창(hwnd)을 기억해 안 깨운 창만 골라 깨운다 — 이미 깨운 창은 창 목록
  조회(수 ms)뿐이라 4초 주기여도 부담 없음. 90초마다는 전체 재워밍(웹뷰 재시작
  대비) + 쪽지 캐시 갱신. 앱 시작 시엔 스레드가 즉시 warmup→전체 prewarm →
  "켜자마자/창 열자마자 몇 초 안에 준비 완료".
- ② 일정 위젯(포스트잇 포함)이 '항상 아래' 고정이라 불편(사용자) →
  WindowStaysOnBottomHint 제거. 이제 **일반 창과 같은 층 규칙**: 클릭하면 위로
  (mousePressEvent에서 raise_), 새로 켜지면 위로, 다른 창을 켜면 그 창이 위로.
  🔧의 '항상 위 고정' 옵션만 예외로 유지. flash_to_front(새 포스트잇 잠깐 앞)는
  그대로 동작.
- 테스트 3종 추가(층 규칙)·배선 검증 갱신. 140 통과.

## 2026-08-14 — 무설치판(ZIP) 보조 배포본
- 사용자 질문: 설치파일이 차단되는 PC가 있는데 ZIP 배포가 필요하지 않을까?
  점검 결과 우리는 NSIS가 아니라 **Inno Setup**이고 이미 **onedir**(폴더형)
  빌드라 차단에 가장 취약한 조건(onefile 자기추출)은 피해 있음. 다만 국내
  압축 프로그램(반디집·알집)이 MOTW('인터넷에서 받음' 표시)를 대개 안 붙여
  ZIP 경로가 실제로 조용히 실행되는 것은 사실 → **설치판 유지 + ZIP 보조**로 결정.
- build.py: make_portable_zip() — dist/CoolmHelper를 통째로 담은
  CoolmHelper-Portable.zip 생성(+ '먼저 읽어주세요.txt': 압축을 꼭 풀 것,
  뷰어에서 바로 실행하면 일정이 임시폴더에 저장돼 유실됨을 경고).
  installer.iss는 이 안내문을 Excludes로 제외(설치판엔 불필요).
- release.yml: 릴리스에 ZIP을 두 번째 자산으로 첨부, version.json에 zip_url 추가.
- updater.is_portable(): Inno가 남기는 unins*.exe 유무로 판별(마커 파일 불필요).
  무설치판이면 UpdateDialog가 조용한 설치 대신 [새 파일 받기]로 ZIP을 열고,
  "압축 풀어 덮어쓰기 / 일정은 그대로" 안내를 띄운다.
- docs/설치안내.md에 무설치판 절차 추가. 테스트 10종 추가, 150 통과.

## 2026-08-16 — 기본 위젯 모드를 펭귄(미니)으로
- DEFAULT_CONFIG["widget_style"]을 "detail" → **"mini"**로 변경 (사용자 결정).
  설정 창은 이미 미니를 "(기본)"으로 안내하고 있었고, main.py·widget_base의
  폴백도 "mini"라 실제로는 DEFAULT_CONFIG만 엇갈려 있었음 — 이제 일치.
- 새로 설치하는 분은 펭귄으로 시작한다. 기존 사용자의 config.json은 그대로라
  쓰던 모드가 유지된다(설정 → 위젯 모양에서 언제든 전환).
- 테스트 2종 추가(기본값·소스 폴백 일치). 152 통과.

## 2026-08-16 — 포스트잇 레이어 정상화 + 📌 고정 버튼
- 증상: 포스트잇이 자꾸 뒤로 밀린다(사용자). 원인은 raise_를 위젯 본체의
  mousePressEvent에서만 했던 것 — 제목칸·메모칸·버튼을 누르면 자식 위젯이
  클릭을 먹어 본체까지 오지 않아 뒤에 깔린 채로 타이핑하게 됐다.
  → DeskWidgetBase.event()에서 **WindowActivate**를 잡아 raise_. 어디를 눌러도
  앞으로 나온다.
- 📌 버튼 신설(make_pin_button): 누르면 이 위젯만 '항상 맨 위' 고정/해제.
  켜지면 시그니처 주황으로 표시되고 툴팁도 상태에 맞게 바뀐다. 우클릭 메뉴의
  같은 항목과 양방향 동기화(_sync_pin_button).
- 포스트잇 헤더에 📌 버튼 추가, 날짜 버튼의 📌 접두사는 🗓로 교체(역할 분리).
  바탕화면 위젯 4종 헤더에도 같은 📌 버튼을 넣어 통일.
- 테스트 5종 추가. 157 통과.

## 2026-08-16 — ZIP의 정체를 바로잡음: 무설치판 → '설치파일 압축본'
- 사용자 지적: "나는 무설치판을 원한 게 아닌데 왜 zip이 무설치판이지?"
  처음 요청("zip으로 감싸면 차단이 덜하다")을 **무설치 배포본**으로 잘못 해석했음.
  실제 의도는 **다운로드 차단 회피용 포장**.
- 변경: build.make_portable_zip(프로그램 폴더 압축) 삭제 →
  **make_setup_zip(설치파일 + 안내문만 담은 CoolmHelper-Setup.zip)**.
  워크플로는 Inno Setup 직후에 이 ZIP을 만들어 릴리스에 첨부, version.json의
  zip_url도 Setup.zip을 가리킨다. installer.iss의 Excludes도 원복(불필요).
- 덕분에 **자동 업데이트 문제가 사라짐**: ZIP으로 받은 분도 압축을 풀어 설치하면
  그냥 설치판이라 [예] 한 번으로 자동 업데이트된다. 위험한 폴더 교체 스크립트
  (실행 중 자기 파일 덮어쓰기 우회)는 만들 필요가 없어졌다.
- updater.is_portable은 남겨 둠 — 의미를 '설치를 거치지 않은 복사본'(USB로
  프로그램 폴더만 옮긴 경우)으로 바꿔, 그때만 [설치파일 받기]로 안내한다.
- docs/설치안내.md·테스트(test_setup_zip.py) 갱신. 157 통과.

## 2026-08-17 — v1.9.7 빌드 실패 원인과 수정
- 실패: 새로 넣은 "설치파일 ZIP 감싸기" 단계에서 `ModuleNotFoundError: build`.
  GitHub Actions의 `shell: python` 단계는 **임시 폴더의 스크립트**로 실행돼
  저장소 루트가 sys.path에 없다(cwd는 루트라 open()은 되지만 import는 안 됨).
  → 단계 안에서 `sys.path.insert(0, ".")` 후 import.
- Inno Setup 컴파일까지는 성공했고 릴리스 업로드 전에 멈춰서, 태그·자산이
  만들어지지 않았다(반쪽 릴리스 없음). 같은 v1.9.7로 재시도.
- 교훈: 워크플로에서 우리 모듈을 import하는 단계는 sys.path를 명시할 것.

## 2026-08-17 — 위젯 3종 개선: 날짜별 ＋, 기간 일정, 편집 모드 이동·삭제
- ① **날짜별 ＋**: 주간 위젯의 **요일 칸마다 ＋** — 누르면 그 날짜가 채워진
  '일정 추가' 창이 뜬다. 캘린더·할일 위젯의 ＋는 **달력에서 고른 날짜**,
  오늘 할 일/할 일 보드의 ＋는 **오늘**이 채워진다.
  (_add_event_button에 date_fn 추가, AddEventDialog에 default_date)
- ② **기간 일정**: 추가 창에 "여러 날에 걸쳐요 (기간)" 체크 → 끝나는 날 선택.
  끝나는 날 23:59로 저장해 **시작일부터 끝나는 날까지 매일** 위젯에 표시된다
  (store.on_date가 start~end를 이미 훑음). 거꾸로 된 기간은 안내 후 거부,
  시작일을 뒤로 옮기면 끝나는 날도 따라온다.
- ③ **편집 모드(🔧) 이동·삭제**:
  · 주간 — ⠿를 잡고 **다른 요일 칸으로 끌면 그 날짜로 이동**. 대상 칸은
    주황 점선으로 강조. 시각은 유지하고, 기간 일정은 길이를 유지한 채 이동.
  · 할 일 보드 — 칸(오늘/앞으로)으로 끌면 **오늘·내일로 당기기**.
    '지난 일' 칸은 드롭 대상이 아니다(의미가 없어서).
  · 모든 필드에 **✕ 삭제** (편집 모드에서만). 되돌릴 수 없으니 한 번 물어본다.
- 부수 정리: 새로 그릴 때 옛 위젯이 잠깐 겹쳐 보이던 문제 — deleteLater만으로는
  다음 이벤트 루프까지 남는다 → 공용 `_clear_layout()`(hide+setParent(None))로
  5곳 중복 정리 코드를 통일.
- tests/test_widget_edit.py 18종 추가. 175 통과.

## 2026-08-18 — MIT 라이선스 채택 (외부 협업 문의)
- 쌤핀(ssampin.com, Electron+TS 교사용 앱) 개발자 박준일 님이 date_parser.py와
  db_reader.py를 참고하고 싶다며 문의. 저장소에 LICENSE가 없어 기본값이
  '모든 권리 보유'라 제3자가 쓸 수 없는 상태였음을 알려줌 — 의도한 바가 아니어서
  **MIT**를 붙이기로 결정(사용자 판단).
- LICENSE 신규(표준 MIT 원문, Copyright (c) 2026 dacisosl).
  README '라이선스' 절 재작성 — MIT 명시 + 재사용하기 좋은 두 파일 안내 +
  **PyQt6는 GPLv3라 exe 배포에는 GPL 조건이 따라붙는다**는 주의(현재도 같은 상태,
  소스 공개로 충족). parser/의 두 파일은 표준 라이브러리만 써 이 제약과 무관.
- date_parser.py·db_reader.py 상단에 저작권·라이선스 2줄 — 파일만 떼어 가도
  출처가 따라가게.
- 답장 초안은 저장소에 두지 않는다 — 개인 메일 초안이라 공개 저장소에 올릴
  이유가 없다(처음엔 docs/에 넣었다가 사용자 지적으로 삭제).
- 릴리스는 하지 않음: 워크플로가 release_notes.txt 변경 시에만 돌아 빌드 없이
  main 반영만 된다. 앱 버전 그대로.
- (작업 중 컨테이너 초기화로 PyQt6·Qt 시스템 라이브러리가 사라져 테스트가
  깨졌음 — 재설치 후 175 통과. 코드 문제 아님.)

## 2026-08-18 — 배포본에 LICENSE 동봉 (릴리스는 하지 않음)
- MIT는 "복사본에 저작권 문구 포함"을 요구하는데 build.py의 동봉 목록에
  LICENSE가 빠져 있어, 설치 폴더에 라이선스 문구가 없었다 → 추가.
  윈도우에서 더블클릭으로 열리도록 이름은 `LICENSE.txt`.
- 동봉 목록을 main() 지역변수에서 모듈 상수 **BUNDLE_FILES**로 올렸다.
  밖에서 확인·테스트가 가능해져, 나중에 목록을 손보다 라이선스가 다시 빠지는
  것을 tests/test_setup_zip.py의 회귀 테스트 1건으로 막는다.
- 설치 마법사의 '라이선스 동의' 화면(Inno의 LicenseFile)은 넣지 않았다 —
  설치 단계만 늘고 MIT가 요구하는 바도 아니다.
- **릴리스하지 않음**: v2.0.0 이후 앱 기능 변화가 없어, 이것만으로 새 버전을
  내보내면 동료 교사들이 눈에 보이는 변화 없는 업데이트 안내를 받는다.
  버전·release_notes.txt를 건드리지 않아 워크플로가 돌지 않으며, 다음 기능
  업데이트 때 자연스럽게 함께 나간다. (2026-08-18 사용자 결정)
- 176 통과.

## 2026-08-24 — 나이스(NEIS) 학사일정 가져오기
- 사용자가 나이스 OpenAPI 키를 발급받아 "학교 검색 → 학사일정 → 일정 등록"을 요청.
- **neis.py** (온라인 존, 루트 모듈 — proofread.py와 같은 결):
  · search_schools(이름) → schoolInfo API. code+office가 없는 행은 버린다.
  · fetch_schedule(학교, 시작, 끝) → SchoolSchedule API.
  · **핵심: merge_rows()** — 나이스는 3일짜리 행사를 '하루 한 줄'로 세 줄 준다.
    그대로 등록하면 같은 이름이 세 번 쌓이므로, 같은 행사명이 연속된 날짜면
    **기간 일정 한 건**으로 합친다 (v2.0.0의 기간 일정 기능을 그대로 활용).
  · event_ref(학교|시작일|행사명) → store.registered_refs()로 **중복 등록 방지**.
  · 응답 코드별 한국어 안내(INFO-200=빈 결과, INFO-300=키 무효, ERROR-337=한도…),
    응답 형태가 조금 달라져도 견디도록 방어적으로 훑는다.
  · 키: 사용자 직접 키 → 내장 키(assets/neis.key) → 없으면 키 없이(5건 제한).
- **ui/neis_dialog.py**: 학교 검색 창 + 학사일정 창(기간 선택·체크 목록·전체선택).
  네트워크는 전부 백그라운드 스레드(_Worker) — 창이 멈추지 않는다.
  이미 등록된 건 '✓ 등록됨' 회색 + 체크 불가.
- 진입점: 펭귄 메뉴에 🏫(school 아이콘 신규), 설정 → 데이터에 학교 지정·연결 진단.
- 키 보관: 워크플로에서 NEIS_KEY 시크릿 → assets/neis.key(base64), .gitignore.
  **사용자가 채팅에 붙여넣은 키는 저장소 어디에도 넣지 않았다** (grep으로 확인).
  → 사용자가 GitHub Settings → Secrets에 NEIS_KEY로 등록해야 내장 키가 들어간다.
- 개발 환경에서 open.neis.go.kr이 조직 정책으로 차단(403)돼 실제 호출은 못 해봤다.
  그래서 ① 응답을 갈아끼운 테스트 31종 ② tools/neis_check.py(사용자 PC에서 실제
  응답 확인용 CLI) ③ 설정의 [연결 진단]으로 대신한다. 207 통과.
- 문서: 설치안내에 사용법, 개인정보고지에 "학교 이름·코드·기간만 전송" 명시.

## 2026-08-25 — 나이스 인증키는 앱에 심지 않고 '각자 넣기'로 (v2.1.0)

어제 만든 학사일정 기능의 마지막 결정: **공용 키를 배포본에 심지 않는다.**

- 사용자가 "공공데이터니까 그냥 코드에 넣어"라고 했지만, 공개되는 것은 **데이터**지
  **키**가 아니다. 키는 그 계정 앞으로 붙은 **하루 조회 한도 통장**이라, 공개
  저장소에 올라가면 남이 갖다 쓰고 한도가 차서 **정작 우리 앱 쓰는 선생님들이**
  그날 학사일정을 못 불러온다. 재발급은 무료지만 그때마다 전체 재배포가 필요하다.
- 그래서 선택지 4개(설정 입력칸 / GitHub 시크릿 / 소스에 직접 / 키 없이)를 설명하고
  사용자가 **설정 입력칸(각자 키)** 을 골랐다. 워크플로의 NEIS_KEY 주입 경로는
  그대로 남겨둔다 — 나중에 시크릿을 등록하면 내장 키가 자동으로 들어간다.
- 키가 없으면 나이스가 **5건만** 주는데, 그게 조용히 일어나면 "왜 우리 학교 일정이
  다 안 뜨지?"로 이어진다. 그래서 안내를 눈에 보이게 만들었다:
  · `KeyBanner` — 키가 없을 때만 뜨는 주황 안내줄(학사일정 창·학교 검색 창).
    키를 넣으면 스스로 사라진다.
  · `KeyDialog` — 발급 방법 3줄 + 입력칸 + [발급 받으러 가기](나이스 안내 페이지).
  · 검색/불러오기 결과가 5건에서 잘린 경우 상태줄에 "인증키가 없어 일부만 왔어요".
  · 설정 → 데이터의 키 칸에도 [발급받기] 버튼과 안내 문구.
- `neis.has_key()` / `set_key()` 추가 — set_key는 붙여넣을 때 딸려오는 앞뒤 공백·
  따옴표를 털어낸다(교사분들이 메모장에서 복사하면 자주 붙는다).
- 배운 점: 보안 문제를 "안 됩니다"로 끝내면 사용자는 이유를 모른 채 막힌 느낌만
  받는다. **왜 위험한지 + 대신 어떤 길이 있는지**를 같이 주면 스스로 고를 수 있다.
- 214 통과.

**같은 날 정정**: 사용자가 결국 **GitHub 시크릿(NEIS_KEY)** 을 등록했다 —
배포본에는 공용 키가 들어간다. 그래서 "각자 키를 넣어야 한다"고 써둔 문구를
"기본 키가 들어 있고, 한도 초과 시에만 본인 키"로 되돌렸다.
`KeyBanner`·`KeyDialog`는 그대로 둔다 — 키가 아예 없는 빌드에서만 뜨는
안전망이고, 나중에 시크릿이 만료돼도 사용자가 스스로 복구할 수 있는 길이 된다.
`has_key()` 하나로 두 세계가 같은 코드로 돌아간다.

## 2026-08-25 — 펭귄 자유 이동 + 📌 위치 고정 (v2.2.0)

"왼쪽 고정 말고 자유롭게 끌게 해줘, 대신 고정하고 싶은 사람도 있으니 핀을
달아줘. 듀얼 모니터면 다른 모니터로도." — 두 요구가 상충하는 게 아니라
**기본값을 자유로 두고 고정을 선택지로** 주면 둘 다 만족한다.

- 예전 `mouseMoveEvent`는 `self.move(screen.right() - self.WIDTH, y)` —
  x를 아예 벽에 못 박아 두었다. 이제 x·y 모두 자유.
- **위치 기억**: `WidgetBase.POS_KEY`/`restore_position()`/`save_position()`.
  MiniWidget만 `penguin_pos`를 쓴다. 드래그를 놓을 때 저장한다.
  main.py의 `place_default()` → `restore_position()`.
- **듀얼 모니터**: 곳곳에서 `primaryScreen()`만 보던 게 문제였다. 보조
  모니터는 좌표가 음수이거나 주 화면 밖이라, 그 기준으로 자르면 펭귄이
  주 화면으로 튕겨 돌아왔다. `screen_at()`/`clamp_to_screens()`/
  `on_any_screen()` 세 도우미로 "그 지점이 속한 화면"을 쓰게 바꿨다.
  · 드래그 중엔 **커서가 있는 화면**을 기준으로 자른다(anchor 인자).
    창 한가운데를 기준으로 하면 경계에서 반쯤 걸린 채 끈적인다.
  · `_ensure_on_screen`은 이제 "어느 화면에도 안 걸칠 때"만 되돌린다 —
    모니터를 뽑았을 때만 구조된다.
  · `AlertBubble.reposition()`의 `max(0, x)`도 같은 함정이었다(음수 좌표
    모니터에서 말풍선이 주 화면으로 튐).
- **📌 고정**: 아이콘 바 맨 위 + 구분선. 켜면 배경색으로 상태가 보이고,
  툴팁·말풍선으로도 알린다. `penguin_locked`에 저장.
- 자유 이동이 되면서 생긴 곁가지도 같이: 펭귄을 왼쪽 끝에 두면 메뉴가
  오른쪽으로 펼쳐지고, 크기를 바꿔도 제자리를 지킨다(예전엔 벽으로 복귀).
- **덤으로 잡은 버그**: `if self._drag and ...` — `QPoint(0,0)`은 거짓이라
  펭귄 좌상단 모서리를 정확히 집으면 드래그가 통째로 안 먹었다.
  `is not None`으로 수정 (mini_widget·widget_base 둘 다).
- 배운 점: "A 아니면 B" 요구가 오면 대개 **기본값 + 스위치**로 풀린다.
  그리고 `primaryScreen()`은 듀얼 모니터에서 거의 항상 잘못된 기본값이다.
- tests/test_penguin_move.py 19종 신규. 총 233 통과.

## 2026-08-26 — 위젯도 자유 이동 + 달력 더블클릭 등록 (v2.3.0)

"위젯도 옮길 수 있게 해줘"를 듣고 코드를 보니 **이미 옮길 수 있었다** —
단 `pos.y() <= _HEADER_H`(맨 위 40px)를 정확히 집었을 때만. 사용자는 그걸
"안 움직인다"로 경험했다. 기능이 없는 게 아니라 **잡히는 영역이 안 보이는**
문제였다. 그래서 조건을 없애고 몸통 아무 데나 잡으면 이동하게 했다.
버튼·체크박스 같은 자식 위젯은 클릭을 자기가 먹으므로 부모까지 오지 않는다 —
따로 예외 처리가 필요 없었다.

- 이동 중 `clamp_to_screens`로 화면 밖 이탈 방지(커서가 있는 모니터 기준).
- 클릭만 하고 안 움직였으면 `_save_geometry()`를 건너뛴다 — 이동을 몸통 전체로
  넓히면서 "빈 곳 클릭"이 매번 파일 쓰기가 될 뻔했다.
- **듀얼 모니터 잔여 버그**: `show_at_saved()`가 `primaryScreen()` 기준으로
  저장 위치를 잘랐다. 보조 모니터에 둔 위젯이 켤 때마다 주 화면으로 끌려온
  원인. `best_screen_rect()`(저장 위치와 가장 많이 겹치는 화면)를 새로 만들어
  그 화면 기준으로 검증한다. `_ensure_on_screen`도 `on_any_screen`으로.
- 화면 계산 도우미 3종을 `ui/screens.py`로 분리했다. widget_base(펭귄)와
  desk_base(위젯)가 함께 쓰는데 서로 import하면 순환이 된다. widget_base는
  예전 이름으로 다시 내보내 기존 호출부·테스트가 그대로 돈다.
- **달력 더블클릭 등록**: `QCalendarWidget.activated`(더블클릭·Enter)를
  `PlannerWidget.add_on()`에 연결. 한 번 클릭은 기존대로 그 날 보기.
  툴팁에도 적어 발견 가능하게 했다.
- 배운 점: "기능이 없다"는 신고가 실제로는 **어포던스가 없다**는 신고일 때가
  많다. 코드를 고치기 전에 "사용자가 이걸 어떻게 찾지?"를 먼저 물어야 한다.
- tests/test_penguin_move.py → test_move.py로 이름 변경(펭귄+위젯 공용),
  위젯 이동 6종·화면 계산 2종·달력 더블클릭 4종 추가. 총 245 통과.

## 2026-08-31 — 마감 알림을 포스트잇으로 (며칠 전인지 사용자가 선택)

시작 알림이 말풍선(AlertBubble) 하나로 뜨고, 클릭할 때마다 다음 알림으로
넘어가는 방식이었다. 급한 마감을 읽기 전에 실수로 다 넘겨 버리기 쉬웠다.
알림을 **노란 포스트잇 한 장**(`ui/alert_note.py`)에 모아 붙이고, 사용자가
✕로 뗄 때까지 화면에 남게 했다.

- `AlertNote`: 앱 포스트잇 색(`theme.postit_colors`)을 그대로 쓴 프레임리스
  창. 머리글에 오늘 날짜, 아래에 알림 목록, 바닥에 '🗓 캘린더 열기'.
  몸통 아무 데나 잡고 끌어 옮긴다(`clamp_to_screens`). 바탕화면 포스트잇과
  달리 **위치·내용을 저장하지 않는다** — 알림용이라 닫으면 끝.
- 알림이 6건을 넘으면 "… 그리고 N건 더"로 접는다. 안 그러면 메모지가
  화면을 덮는다.
- **알림 조건이 바뀌었다**: 예전에는 `alert_days=[3, 1]`로 딱 3일 전과
  1일 전 이틀만 알렸다. 그 사이(2일 전)에만 컴퓨터를 켜면 알림을 통째로
  놓친다. 이제 `alert_before_days`(기본 3) 하나로 **N일 전부터 마감 당일까지
  매일** 알린다. 급한 것이 위로 오게 정렬.
- 설정 → 일반에 '알림' 카드 신설: 켜고 끄는 체크박스 + 며칠 전인지 고르는
  숫자칸(1~14). 끄면 숫자칸이 회색으로 비활성화된다.
- `migrate_alert_days()`: 옛 `alert_days` 리스트의 **가장 큰 수**(가장 이른
  알림)를 물려받는다. [3, 1] → 3. 업데이트해도 알림이 줄지 않는다.

배운 점

- **알림은 "놓치면 끝"이라 UI가 소모성이면 안 된다.** 말풍선처럼 클릭 한 번에
  사라지는 형태는 안내(인트로)에는 맞지만 마감 알림에는 안 맞았다. 포스트잇은
  "떼기 전까지 붙어 있다"는 물리적 은유가 그대로 동작이 된다.
- **띄엄띄엄 알리면 통째로 놓친다.** [3, 1]처럼 특정 날짜만 짚는 조건은,
  프로그램을 매일 켜지 않는 사용자에게는 알림이 없는 것과 같다. 구간으로
  바꾸니 조건도 단순해지고 설정도 숫자 하나로 줄었다.
- **Qt 스타일시트는 자식에게 흘러내린다.** 카드 안 줄의 회색 띠를 지우려고
  `setStyleSheet("background:transparent;border:none")`를 줬더니 안에 든
  QSpinBox 테두리까지 사라져 입력칸으로 안 보였다. `#objectName{...}`으로
  선택자를 그 위젯에 좁혀야 한다.
- `highlight_urgency()`에 '오늘 마감'을 낱말째 추가. 숫자만 강조하던 규칙에서는
  가장 급한 알림에 숫자가 없어 오히려 밋밋했다.
- 알림 3종·마이그레이션 4종·포스트잇 스모크 2종 추가. 총 254 통과.

### 같은 날 추가 — 뗀 알림은 다시 안 뜬다 + 항목별 ✕

첫 구현에서는 뗀 사실을 기억하지 않아, 프로그램을 다시 켤 때마다 같은
포스트잇이 또 붙었다. 사용자가 바로 짚었다: "X 눌렀는데도 반복되지 않았으면".

- `config["alert_dismissed"] = {열쇠: 뗄 때 남아 있던 날수}`.
  열쇠는 마감이면 `ev:<일정 id>`, 오늘 일정 요약이면 `today:<날짜>`.
- **뗀 값으로 날수를 저장하는 이유**: "한 번 떼면 끝, 단 **마감 당일**은 예외로
  한 번 더" (2026-08-31 사용자 결정). 3일 전에 뗐으면(값 3>0) 2일 전·1일 전은
  조용하고 당일에 딱 한 번 더 뜬다. 당일에 뗀 것(값 0)은 영영 안 뜬다.
- 항목별 ✕ 추가 — 급한 것만 남기고 나머지를 골라 뗄 수 있다. 머리글 ✕는
  남아 있는 줄을 **전부** '봤다'로 기억하고 닫는다.
- 있던 알림을 전부 뗀 상태면 아무것도 안 띄운다. '오늘은 새 알림이 없어요'
  안내를 대신 띄우면 "다 봤다"고 표시한 사람에게 또 들이미는 셈이 된다.
- `prune_dismissed()`로 사라진 일정·지난 날짜 기록을 정리한다. 안 하면 config가
  뗀 알림 기록으로 계속 불어난다.

배운 점

- **`clicked.connect(self.dismiss)`는 함정이다.** clicked가 `checked`(bool)를
  넘겨서 `dismiss(remember=False)`로 불린다 — 기본값이 있는 인자를 받는 슬롯은
  반드시 람다로 감쌀 것. 테스트로 잡았다.
- 줄을 떼어 메모지가 줄어들 때는 **아래 모서리를 고정**한다. 위쪽을 고정하면
  펭귄 위에 붙여 둔 메모지가 위로 달아나 보인다.
- 알림을 문자열 리스트에서 `Alert(text, key, days_left)` 객체로 바꿨다. "이
  알림이 무엇에 대한 것인지"를 UI가 알아야 항목별로 기억할 수 있다. 문자열만
  넘기던 구조로는 ✕가 무엇을 뗀 건지 알 방법이 없었다.
- 알림·뗀 기록 테스트 16종. 총 264 통과.

## 2026-08-31 (2) — 알림 대상을 '마감'에서 '다가오는 일정 전부'로

v2.4.0을 배포한 직후 사용자가 "왜 알림이 안 뜨지? 기존 일정은 알림이 안 뜨는
건가"라고 물었다. 설치본을 열어 보니 원인이 분명했다.

- 등록된 **일정 32건 중 `is_deadline=True`가 0건**. 알림은 마감 표시된 것만
  대상이라 알릴 게 아예 없었다. 설정도 버전도 정상이었다.
- D-1 "교육청 연수 강의교안 완성", D-2 "AI 수업계획안 제출"처럼 누가 봐도
  마감인 일정조차 표시가 꺼져 있었다. `is_deadline`은 쪽지에서 **자동 감지**
  되는 값이라(quick_dialog: "마감 여부는 쪽지에서 자동 감지된 값 유지")
  실제로는 거의 켜지지 않는다.
- 그래서 알림 대상을 **다가오는 일정 전부**로 넓혔다 (2026-08-31 사용자 결정).
  마감은 ⏰ + 빨간 강조로 목록 맨 위, 나머지는 🗓 오늘/내일/모레/N일 뒤.
- '📋 오늘 일정 N건' 요약 줄은 없앴다. 오늘 것도 제목이 보이는 한 줄로 나오니
  건수 요약은 같은 말을 두 번 하는 셈이었다.
- 여러 날짜리 일정이 진행 중이면(어제 시작~내일 끝) '오늘'로 친다.
  `days_left`만 보면 음수라 걸러졌다.

배운 점

- **자동 감지에 기대는 플래그를 알림 조건으로 쓰면 안 된다.** 코드로는
  완벽했고 테스트도 통과했는데, 실제 데이터에서 그 플래그가 0건이라
  기능 전체가 죽어 있었다. 배포 전에 **사용자의 진짜 store로 한 번 돌려봤다면**
  바로 보였을 일이다 — 앞으로 알림·필터류는 실데이터로 시뮬레이션할 것.
- 사용자의 "왜 안 뜨지?"는 버그 신고가 아니라 **가정이 틀렸다는 신호**였다.
  사용자는 "일정이 다가오면 알려준다"고 생각했고, 나는 "마감으로 표시한
  일정이 다가오면"으로 만들었다. 그 차이를 아무 데서도 드러내지 않았다.
- 알림 테스트 5종 추가. 총 267 통과.

## 2026-09-01 — 알림 포스트잇에서 줄을 뗄 때 글자가 겹치던 버그

사용자가 알림 몇 개를 ✕로 지웠더니 구분선이 허공에 뜨고, '캘린더 열기'
버튼이 두 번 겹쳐 보이며, 제목 줄이 사라진 화면을 보내 왔다.

원인은 두 가지가 겹친 것이었다.

1. **줄을 숨기기만 했다.** `hide()`로는 위젯이 레이아웃에 그대로 남는다.
   반투명 창(`WA_TranslucentBackground`) + 그림자(`QGraphicsDropShadowEffect`)
   조합에서는 옛 크기의 그림이 지워지지 않고 남는다.
   → `removeWidget()` + `setParent(None)` + `deleteLater()`로 **실제로 뺀다**.
   (발신 버튼이 지우려는 위젯 안에 있으므로 즉시 삭제는 위험 — deleteLater)
2. **창 크기가 한 프레임 늦게 따라왔다.** 줄을 빼자마자 `self.sizeHint()`를
   읽으면 옛 값이 나오고, 레이아웃이 창에 걸어 둔 `minimumHeight`도 옛 값이라
   억지로 `resize()` 해도 다음 프레임에 도로 늘어난다. 그 어긋난 한 프레임에
   "내용은 새 배치, 창은 옛 크기"가 되어 글자가 겹쳐 보였다.
   → 크기 조절을 `QTimer.singleShot(0, ...)`로 **다음 프레임에 한다**.
   그때 `setMinimumHeight(0)`으로 옛 최소 높이를 풀고 다시 잰다.

곁들여: 아래 모서리를 고정해 메모지가 위로 달아나지 않게 하고, 줄이 하나도
안 남으면 메모지를 닫는다. 이미 뗀 줄을 또 눌러도 조용하다(중복 클릭 가드).

배운 점

- **`invalidate()`는 오히려 해가 됐다.** 다시 재는 일을 다음 프레임으로 미루기
  때문에, 바로 뒤에서 `sizeHint()`를 읽으면 옛 값이 온다. `removeWidget()`만
  으로 이미 무효화되므로 `activate()`로 바로 계산시키는 게 맞다.
- **Qt에서 "레이아웃을 바꾸고 그 자리에서 크기를 읽는" 코드는 의심할 것.**
  위젯 추가·제거·hide는 대부분 지연 반영이다. 한 프레임 미루면 정확해진다.
- `QGraphicsEffect`는 그린 결과를 캐시한다. 창 크기가 바뀌면 효과를 새로 달아
  캐시를 버리게 해야 잔상이 안 남는다.
- 화면을 직접 못 봐도 **높이 숫자를 단계별로 찍어 보면** 잔상 버그를 잡을 수
  있다. 275→275→225처럼 한 칸씩 밀리는 값이 곧 증상이었다.

### 같은 날 마무리 — 점검하며 함께 고친 것

- **때 표시와 제목을 나눴다.** `Alert(text)` 한 덩어리를 `Alert(when, title)`로
  쪼개, 포스트잇에서 '오늘·내일'은 작고 옅은 메모지색(10px), 일정 제목은 크고
  진하게(13px) 그린다. 한 덩어리로 굵게 쓰던 때는 날짜와 일정이 구분되지
  않았다 (2026-09-01 사용자 요청). `text`는 property로 남겨 기록·테스트가
  그대로 돈다.
  - 부수 효과: 강조(`highlight_urgency`)를 **때 표시에만** 걸게 되어, 제목에
    '2건' 같은 숫자가 들어가도 엉뚱하게 빨간 칩이 붙지 않는다.
  - 제목이 없는 알림(안내 문구)은 때 표시를 본문 스타일로 그린다.
- **'끌어서 옮기기' 글씨를 뺐다.** 대신 머리글(날짜 줄)에 이동 커서(✥)와
  툴팁을 달아 잡을 곳을 알린다 — 글씨로 설명하는 대신 커서로 보여준다.
  몸통 아무 데나 잡아도 여전히 옮겨진다(더 너그럽게).
- **업데이트 직후 첫 실행에 알림이 안 뜨던 문제.** 새 버전 인사를 띄우고 나서
  `return`해 버려, 업데이트한 날은 알림을 아예 못 봤다. 인사가 끝나면
  (`play_update_intro(on_done=...)`) 이어서 포스트잇을 띄운다.
- **'캘린더 열기'는 알림을 뗀 것으로 치지 않는다.** 일정을 보러 간 것뿐인데
  기억해 버리면 알림이 영영 사라진다. `dismiss(remember=False)`.
- **`setParent(None)`을 뺐다.** 잠깐 독립 창이 되어 깜빡일 수 있다.
  `removeWidget()` + `hide()` + `deleteLater()`면 충분하다.
- 시작 경로 전체(`_show_alert_note`)를 태우는 통합 테스트 추가 — 설정 읽기,
  뗀 것 거르기, 포스트잇 띄우기, 끄기까지 한 번에 확인한다. 총 270 통과.

## 2026-09-01 (2) — 안내 말풍선이 '오늘 할 일' 위젯을 멋대로 켜던 잔재 제거

사용자: "이게 있으니 오늘 할 일 위젯은 자동으로 안 띄어도 되겠다."

`AlertBubble.mousePressEvent`가 클릭할 때마다 `apply_desk_widget("today", True)`
를 불러 바탕화면 위젯을 켜고 **설정에도 저장**하고 있었다. 시작 알림이 곧
말풍선이던 시절에는 "알림을 눌렀으니 오늘 할 일을 보여준다"가 말이 됐다.

v2.4.0에서 시작 알림을 포스트잇으로 옮긴 뒤로 이 말풍선은 **첫 실행 안내**와
**⚡ 간편 등록 안내**에만 쓰인다. 그래서 지금은 인트로를 넘기려고 누른 것뿐인데
위젯이 생기고 설정이 바뀐다. 알림 포스트잇이 오늘 할 일을 이미 보여주므로
자동으로 켜는 동작을 없앴다. 필요하면 설정 → 일반 → 바탕화면 위젯에서 켠다.

- 이미 켜져 있는 사용자의 설정은 건드리지 않는다 — 자동으로 켜는 것만 멈춘다.
  쓰고 있을지도 모르는 위젯을 임의로 끄는 건 또 다른 참견이다.

배운 점

- **기능을 옮기면 옛 자리에 붙어 있던 곁가지도 같이 따라가는지 봐야 한다.**
  알림을 포스트잇으로 옮기면서 말풍선 본체는 인트로용으로 남겼는데, 거기
  붙어 있던 "누르면 오늘 할 일 위젯 켜기"는 맥락을 잃은 채 계속 돌고 있었다.
  기능 이전은 '옮기기'가 아니라 '옮기고 남은 것 점검하기'까지다.
- 회귀 테스트를 넣을 때는 **옛 코드에서 실제로 실패하는지** 확인했다.
  MiniWidget에 `apply_desk_widget`이 있고 그것이 플래그를 바꾸는 것까지 확인해,
  테스트가 헛돌지 않음을 보장했다. 총 271 통과.

## 2026-09-02 — "자동 실행 체크는 켜져 있는데 부팅 때 안 뜸" 수정

사용자: "체크박스 켜져 있는데 안 되서 물어본 거야."

원인은 is_enabled()가 **Run 키에 값이 있는지만** 보고 켜짐으로 표시한 것.
값이 있어도 부팅 때 실행이 안 되는 경우가 두 가지 있다.

1. **옛 경로 등록**: Run 값이 지금 exe가 아니라 옛 위치(예전 dist 폴더,
   개발용 pythonw 등)를 가리키면 부팅 때 아무것도 실행되지 않는다.
2. **작업 관리자 차단**: '시작 앱'에서 '사용 안 함'으로 끄면(백신·정리
   프로그램이 끄기도 한다) Windows는 Run 값을 지우지 않고 StartupApproved
   키에 차단 표시만 남긴다. Run 값만 보면 켜진 것처럼 보인다.

고친 것 (autostart.py):
- is_enabled(base_dir): 등록 + 차단 아님 + (frozen이면) 경로 일치까지 확인.
- enable()/disable(): StartupApproved 차단 표시도 함께 정리.
- repair(base_dir) 추가: 앱 시작 때(main.py) 등록이 옛 경로거나 차단이면
  자동 복구. 등록 자체가 없으면(사용자가 끔) 건드리지 않고, frozen일 때만
  동작한다(개발용 python이 설치판 등록을 덮어쓰지 않게).
- 설정 창은 is_enabled(base_dir)로 실제 상태를 보여준다 — 어긋난 상태면
  꺼진 것으로 보이고, 다시 체크해 저장하면 바로잡힌다.

배운 점
- **"등록돼 있다"와 "실행된다"는 다르다.** 레지스트리 값의 존재만 확인하면
  경로가 어긋나거나 상위 스위치(StartupApproved)가 꺼진 상태를 놓친다.
  상태 표시는 사용자가 실제로 겪는 결과(부팅 때 뜨는가)를 기준으로 해야 한다.
- winreg 없는 리눅스 테스트 환경에서도 가짜 winreg 모듈을 주입하면
  레지스트리 로직을 검증할 수 있다 (tests/test_autostart.py, 6개).

## 2026-09-03 — ⚡ 간편 등록: 본문에서 날짜를 찾으면 어느 날짜인지 물어보기

사용자: "날짜가 여러 개거나 원하는 날짜가 아닌 경우도 가끔 있거든. 내용에
날짜가 있어서 알아서 등록해야 할 때 안내 모달이 뜨면 좋겠어."

지금까지는 파서가 찾은 **첫 번째** 후보를 말없이 등록했다. 안내문에 날짜가
여러 개 나오면(신청 마감 / 행사 당일 / 결과 발표) 엉뚱한 날에 꽂혔다.

- `DatePickDialog` 추가 — "어떤 날짜에 일정을 등록하시겠습니까?" + 날짜별
  체크박스. 여러 개 고르면 **날짜마다 하나씩** 등록되고 각각 포스트잇으로 붙는다.
  아무것도 안 고르면 **오늘 날짜**로 등록(= 날짜 못 찾았을 때와 같은 동작).
- **첫 번째 날짜는 미리 체크**해 둔다 — 그대로 엔터를 치면 지금까지와 똑같이
  동작하니, 익숙한 사용자의 손이 꼬이지 않는다.
- 날짜를 **못 찾았으면 모달을 띄우지 않는다** — 물어볼 게 없다. 예전처럼
  조용히 오늘로 등록한다. "가끔 있는 문제" 때문에 매번 창을 띄우면 안 된다.
- `date_options()`가 같은 날짜·시각 중복을 합치고 최대 8개로 자른다. 파서는
  같은 날짜를 문장마다 다시 잡는데, 똑같아 보이는 줄이 여러 개면 고르기만 어렵다.
- 클립보드 경로에서는 날짜 모달이 **내용 확인까지 겸한다**(본문 미리보기를
  같이 보여줌). 안 그러면 "이 내용 맞나요?" → "어느 날짜로?" 창이 두 번 뜬다.
  날짜를 못 찾은 클립보드 쪽지는 예전대로 내용 확인 창만 뜬다.

배운 점

- **자동화의 반대말은 수동이 아니라 '확인'이다.** 자동 추출은 그대로 두고
  되돌리기 어려운 순간(등록) 앞에만 한 번 물었다. 기본값을 예전 동작으로
  맞춰 두면 확인 단계가 늘어도 손에 익은 흐름은 그대로다.
- 모달을 추가할 때는 **이미 있는 모달과 겹치지 않는지** 봐야 한다. 클립보드
  경로에 그냥 얹었다면 창이 연달아 두 번 떴을 것이다. 기존 확인 창이 답하던
  질문("이 내용 맞나요?")을 새 창이 흡수할 수 있으면 하나로 합치는 게 낫다.
- 테스트 환경에 PyQt6를 설치해 **UI 테스트 139개가 그동안 안 돌고 있던 것**을
  발견했다(151개 실행/17개 임포트 실패 → 290개 전부 실행·통과). 기존 클립보드
  테스트가 진짜 모달에 걸려 멈춘 덕에 '창이 두 번 뜨는' 설계 결함도 잡았다.
  **테스트가 조용히 안 돌고 있는 것이 실패보다 위험하다.**

## 2026-09-03 (2) — v2.5.0 릴리스 (날짜 선택 모달 + 자동 실행 복구)

사용자: "보완할 부분 있으면 보완 수정해서 배포까지 완료하자."

- 보완: 날짜 선택 모달을 띄우기 전에 "쪽지를 읽는 중…" 말풍선을 닫는다
  (`_hush`). 안 닫으면 모달을 취소했을 때 말풍선만 덩그러니 남았다.
- 포스트잇 여러 장 겹침은 이미 `DeskNote.place_default`가 계단식으로
  비껴 놓아 문제없음을 확인 — 추가 수정 없음.
- 버전 규칙대로 기능 업데이트라 부 버전 올림: v2.4.3 → **v2.5.0**.
  version.py·installer.iss·release_notes.txt 갱신 → main 병합·푸시 →
  GitHub Actions(release.yml)가 빌드·릴리스·version.json 갱신.
- 290 통과.
