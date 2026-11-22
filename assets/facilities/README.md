# 문파 건축물 단계별 일러스트 v1

- **실제 시설:** 훈련소(training), 장원(estate), 의료시설(medical).
- **실제 레벨:** Lv.0~5. Lv.0은 미건설 부지, Lv.1~5는 각각 고유 이미지.
- **아트:** `facility_growth_v1.webp`, 900×540px WebP, 5열×3행의 180×180px 타일 15종. 원본은 생성형 오리지널 일러스트.
- **행 순서:** 첫째 행 훈련소(연무장), 둘째 행 장원(숙소·생활관), 셋째 행 의료시설(약방·의약당).
- **열 순서:** 좌측부터 Lv.1, Lv.2, Lv.3, Lv.4, Lv.5.
- **렌더링:** `management.js`의 `facilityStageArt(f,level)` 함수. CSS `background-size:500% 300%`와 `background-position: (level-1)*25%, row*50%`.
- **게임 규칙:** 기존 Python `campaign.facility_view`와 `campaign.upgrade`가 계산한 현재 가치, 다음 가치, 비용, 최대 레벨만 사용. 아트는 저장되지 않으며 경제·전투 로직에 영향 없음.
- **세이브:** 기존 시설 레벨을 읽기만 하므로 과거 저장 파일도 즉시 올바른 이미지 사용.
- **최고 레벨:** Lv.5에서 더 이상 업그레이드하지 않으며 현재 최종 건물 이미지와 최고레벨 안내 표시.
- **미건설 부지:** 별도의 빈 터 UI가 렌더링되어 첫 건설 전부터 상태가 구분됨.

검증: `node --test tests/test_facility_art_v1.mjs`.
