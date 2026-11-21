# 우리두리 먹거리 — 강릉 확장형 음식점 검색

기준일: 2026-11-21 · [먹거리 페이지](https://wlsdh8788.github.io/duri-zinoyerim/food.html)

## 현재 기능
- 음식 종류: 전체, 한식, 피자, 햄버거, 돈까스, 회, 양식, 카페, 중식, 일식, 고기·구이, 분식, 치킨, 기타
- 동네 필터, 검색어 즉시 검색, 추천 후보 우선/가나다순/내 별점순, 페이지 단위 더 보기
- `food.json`: 직접 확인해 선정한 강릉 음식점 25곳
- `food-public.json`: 행정안전부 지방행정 인허가데이터 **강릉시** 음식점·휴게음식점 영업자료를 **자동 생성**한 목록. 생성되기 전에는 추천 후보만 표시
- 네이버 지도 이동: 모든 음식점 이름을 눌러 지도에서 영업 여부·리뷰·메뉴·실제 위치 확인
- 자체 별점은 브라우저 localStorage에만 저장하며 네이버 방문자 평점이 아님

## 공식 공공데이터 자동 확장
배포 워크플로 `.github/workflows/update-events.yml`은 main에 푸시될 때와 매일 정기 실행 시 `python scripts/update_food_public.py`를 실행해 목록을 생성한다.

원천: 행정안전부 지방행정 인허가데이터(LOCALDATA)
- 일반음식점: https://file.localdata.go.kr/file/download/general_restaurants/info?orgCode=4201000
- 휴게음식점: https://file.localdata.go.kr/file/download/rest_cafes/info?orgCode=4201000
- 강릉시 인허가 코드: `4201000`
- CP949 CSV, 영업/정상만 반영, 명칭·주소가 있는 자료만 사용
- 상호/업태로 음식 종류를 **추정**하며 실제 메뉴·현재 영업시간·별점·인기순위는 제공하지 않는다
- 인허가 자료에는 일시적인 행사 업소나 영업종료 반영 지연이 있을 수 있으므로 방문 전 확인 필요
- 원천 다운로드가 실패했을 때는 이전에 성공한 `food-public.json`을 보존한다. 처음부터 실패하면 비어 있는 목록으로 배포하되 기존 25곳은 유지한다.

수동 실행: GitHub 저장소 → Actions → **Update and publish Gangwon dates** → Run workflow. 정상 실행 로그의 `Saved N unique Gangneung permitted establishments`로 건수를 확인한다. 한 번 생성된 `food-public.json`은 정기 작업에서 파일 변경이 있을 때 자동 커밋된다.

## 선택 기능: 네이버 지역 검색 실시간 연동

**네이버 API HUB 키와 서버 측 중계가 필요한 선택 기능이며, 별도 설정 전에는 비활성화돼 있다.** 사이트 내 검색과 네이버 지도 링크는 키 없이 정상 작동한다.

2026-07-31 이후 신규 검색 API 신청은 NAVER Developers가 아닌 **NAVER API HUB**에서 진행한다(기존 API는 2027-06-30 지원 종료). 네이버 공식 지역검색은 **한 번에 5건**까지만 제공하고 네이버 지도 전체 목록과 동일하지 않다. 방문자 평균 별점도 제공하지 않는다.

1. NAVER Cloud Platform **NAVER API HUB**에서 Search API 사용을 설정하고 Client ID/Secret을 발급받는다.
2. Cloudflare Workers에 `naver-food-worker.js`의 코드를 새 Worker로 배포한다.
3. Worker Secret에 `NAVER_API_CLIENT_ID`, `NAVER_API_CLIENT_SECRET`을 각각 설정한다. **이 값은 공개 GitHub 파일에 넣지 않는다.**
4. `food-config.js`의 `window.FOOD_NAVER_PROXY_URL`에 실제 Worker HTTPS 주소와 `/search` 경로를 입력한다. 예: `https://example.workers.dev/search`.
5. GitHub Pages가 재배포되면 사용자가 카테고리나 검색어를 변경했을 때 **최대 5개의 실시간 네이버 검색 결과**가 별도 목록으로 표시된다.

Worker는 허용 출처 `https://wlsdh8788.github.io`만 CORS로 허용하도록 설정돼 있다. 공개 프록시 특성상 추가적인 호출량 관리·부정 사용 방어가 필요할 수 있다. 중계 API의 이용료 및 이용약관은 직접 확인해야 한다.

네이버 검색 문서: https://api.ncloud-docs.com/docs/naver-api-hub-search-local

## 데이터 품질 정책
- **공공 인허가 목록 ≠ 맛집 추천 목록**. 공식 자료의 영업상태는 지금 문을 열었는지와 다르다.
- 개인 점수는 사용자 기기 안에만 저장되며 사이트 관리자가 확보하지 않는다.
- 네이버 리뷰·사진·별점은 허가 없이 복제하거나 영구 저장하지 않는다.
- 카테고리 분류 오류가 발견되면 `scripts/update_food_public.py`의 `category_for` 규칙을 수정한다.
- 식당의 정확한 메뉴·가격·주차·예약은 네이버 지도에서 확인한다.
