# 둘이서 강원 — 자동수집 연결형

강원도 축제·공연을 API에서 가져와 `events.json`으로 모으고, 모바일 웹사이트에 표시하는 프로젝트.
**현재 ZIP 파일은 GitHub 계정/API 키/호스팅 연결 전이므로 실제 자동수집은 실행 중이지 않다.**
기본 4건은 2026-11-19에 수동 등록한 예시이며, 시간이 지나면 일정이 종료될 수 있다.

## 1. 연결되는 자료

| 자료 | 수집 경로 | 상태 |
|---|---|---|
| 축제·행사 | 한국관광공사 국문 관광정보 서비스 (TourAPI `searchFestival2`) | 키 설정 시 자동 |
| 연극·뮤지컬·콘서트 등 공연 | KOPIS 공연예술통합전산망 (`pblprfr`) | 키 설정 시 자동 |
| 전시·미술관·소규모 행사 | 문화포털 공연전시정보 API 등 | 추후 연결 필요 |
| 팝업스토어·플리마켓·야시장 | 주최기관 공식 안내 수동 등록 또는 허용된 곳만 크롤링 | 현재 수동 |

두 API로 **강원도의 모든 행사가 수집되는 것은 아님**. 누락·미등록·수정 지연이 있을 수 있다.

## 2. 시작하기 (정확히 이 순서)

1. [GitHub](https://github.com/)에서 계정 생성 후 `gangwon-date`라는 새 저장소 생성 (추천: 공개 저장소, 개인 비밀 내용 업로드 금지).
2. 이 폴더의 **모든 파일과 `.github/workflows` 폴더까지** 저장소에 업로드. `.github`는 숨김 폴더라 빠뜨리지 않도록 확인.
3. [공공데이터포털의 TourAPI 신청](https://www.data.go.kr/data/15101578/openapi.do) 후 발급된 **일반 인증키(Decoding)** 확인. 아직 활성화 안 됐다면 승인·활성화 후 테스트.
4. [KOPIS](https://kopis.or.kr/)에서 OpenAPI 사용 신청 후 키 발급 (선택, 공연 수집용).
5. GitHub 저장소 `Settings → Secrets and variables → Actions → New repository secret`에서 다음 키 등록:
   - `KTO_SERVICE_KEY` : 한국관광공사 TourAPI 키
   - `KOPIS_SERVICE_KEY` : KOPIS API 키 (선택)
   - **키를 `index.html`, `events.json`, README 또는 Git 커밋에 직접 적지 않는다.**
6. GitHub 저장소에서 `Settings → Pages → Build and deployment → Source → GitHub Actions`를 선택. **Deploy from a branch를 선택하면 자동 수집 후 재배포가 연결되지 않을 수 있음.**
7. `Actions → Update and publish Gangwon dates → Run workflow` 수동 실행. `events.json`에 행사 수가 늘어났는지 확인. **GitHub Pages가 같은 작업에서 자동 배포**되며 `https://<아이디>.github.io/gangwon-date/` 같은 주소가 생김.
8. 여자친구에게 URL을 공유하면 같은 최신 행사 목록을 볼 수 있음. **하트/찜은 아직 각자 휴대폰에만 저장됨**. KOPIS에서 시군구 미제공 시 `강원 전체`로 표시.

> GitHub Pages 또는 Cloudflare Pages 모두 가능. 이 프로젝트는 **GitHub Actions → GitHub Pages 직접 배포**로 설정돼 있으므로 `Settings → Pages → Source: GitHub Actions`를 선택해야 함. 최초 배포·GitHub Actions 활성화는 계정 소유자가 직접 해야 함.

## 3. 매일 자동으로 갱신되는 원리

- `.github/workflows/update-events.yml`이 **매일 한국시간 오전 7시 17분(UTC 22:17)** Python 실행을 요청.
- `scripts/update_events.py`가 TourAPI와 KOPIS API에 접속해 강원 행사 조회.
- **지역 판정 → 진행 중/예정 행사 확인 → 중복 제거 → events.json 저장**.
- GitHub Actions가 파일 변경을 커밋하고 **같은 작업 안에서 GitHub Pages로 직접 배포**. GITHUB_TOKEN 커밋만으로 Pages 재빌드가 자동 시작되지 않는 문제를 회피.
- API 오류 시 기존 자동수집 자료를 최대한 유지하고 `sources`에 오류 표시. 다만 인증키 오류·공급자 응답변화 시 코드를 수정해야 함.
- GitHub 예약 실행은 지연되거나 실패할 수 있음. **공개 저장소가 60일간 비활성 상태일 때 일정 실행이 중지될 수 있어** Actions 상태를 확인해야 함.

## 4. 팝업스토어 / 전시 / 야경 / 행사 수동 등록

`manual_events.json`의 기존 항목을 복사해 새 행사 객체를 추가하면 됨. 필수 항목:

```json
{
  "id": "my-event-2027",
  "title": "행사명",
  "city": "강릉",
  "category": "팝업",
  "start": "2027-01-01",
  "end": "2027-01-03",
  "place": "행사 장소",
  "address": "강원특별자치도 강릉시 ...",
  "price": "무료 / 확인 필요",
  "emoji": "🛍️",
  "theme": "christmas",
  "intro": "행사 간단 소개",
  "highlight": "데이트 추천 포인트",
  "status": "주최 측 확인",
  "sourceLabel": "주최기관",
  "sourceUrl": "https://주최기관-공식주소",
  "mapQuery": "강릉 행사 장소",
  "note": "예약 필요 여부"
}
```

변경 후 `Actions → Update and publish Gangwon dates → Run workflow`를 눌러 `events.json`에 반영. API 키가 없으면 수동 자료만 배포되므로, `manual_events.json`을 수정했다면 API 연결 후 실행하거나 로컬에서 `python scripts/update_events.py`를 실행해 `events.json`도 업로드해야 함.

## 5. 주의사항

- 타 기관 홈페이지 HTML 크롤링은 무조건 가능한 게 아님. robots.txt, 이용약관, 저작권, 접근 제한을 확인하고 허용 범위에서만 진행.
- 팝업/마켓은 통합 공식 API가 없어 자동 누락 가능. 주최 측에 API·RSS 존재 여부 문의 또는 수동 입력 권장.
- 공식 API 자료도 날짜·요금·취소 여부가 변경될 수 있음. 행사 상세 페이지 확인을 안내할 것.
- 개인정보, 비공개 로그인 정보, API 인증키를 저장소에 공개하지 말 것.
- 한국관광공사 사진은 별도 이용조건 확인 후 이용. 현재 디자인은 이미지를 자동 복제하지 않음.
- `index.html`을 PC에서 직접 열 때(file://)는 내장 예시 목록만 표시됨. 실제 자동 갱신은 호스팅 접속 시 `events.json`을 읽음.

## 파일 구조

```
index.html                       - 모바일 웹 화면/달력/필터/관심목록
manual_events.json              - 직접 등록하고 싶은 행사
 events.json                     - 사이트가 읽는 자동 생성 데이터
scripts/update_events.py        - 공식 API 수집 + 데이터 갱신
.github/workflows/update-events.yml - 매일 자동 실행 스케줄
```
