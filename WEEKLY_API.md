# 문파 주간 운영 화면 연결

기존 Web Worker에 `{path, payload}`를 보내고 `{state}` 또는 `{error}`를 받는다. 게임 시작 시 `state`를 호출해 `season`, `week`, `tier`, `rank`, `cash`, `roster`, `zones`를 읽는다. 명단의 `id`를 배치에 쓰고 `injured`가 0보다 크면 전투·임무·훈련 선택을 비활성화한다.

## 주간 배치 제출

`path: "week"`에 아래 구조를 보낸다. 화면에 보이는 현재 시즌·주차와 실제 문파원·구역 ID를 사용한다.

```json
{
  "season": 1,
  "week": 1,
  "assignment": {
    "training": [650],
    "mission_orders": [{"id": "<state.mission_board에서 받은 ID>", "members": [651, 652, 653], "approach": "balanced"}],
    "rest": [654],
    "attack": null
  }
}
```

- `attack`을 지정할 때는 `{"zone": 39, "setup": [...]}`을 넣는다. `setup`은 기존 점령전과 같은 5개의 `{id, row, skills}`다.
- 수익 임무는 현재 주차의 `state.mission_board`에서 최대 2건을 고르며, 각 임무의 `min_members`~`max_members`(2~5명) 인원을 편성한다. 같은 임무 중복 선택, 구주차 의뢰 재사용, 부상자 배치, 같은 문파원의 활동 중복 및 기존 1군 20명·최소 활동 15명을 검증한다. 구형 API `missions: [[id,id,id]]`도 호환된다.
- 임무 접근 방식은 `cautious`(신중), `balanced`(정석), `bold`(과감)이며, 성공률과 지급 보상·부상 위험에 영향을 준다. 임무는 대성공·성공·부분 성공·실패로 정산되고 취소 시 실제 현금 지급이 없다. 빈 1군 자리는 가용 인원을 훈련에 자동 배치한다. 2군 훈련과 부상 회복은 주간 처리에서 계산한다.
- 점령전이 있으면 `week_pending: true`와 `battle`을 반환한다. 기존 `round` 명령으로 전투를 진행한다. 종료와 동시에 이번 주 결산을 한 번 확정한다.
- 점령전이 없으면 바로 결산하고 다음 주를 반환한다. 오래된 시즌·주차 요청과 전투 중 중복 제출은 오류로 반환한다.

## 결산 화면

`week_report`에는 정산한 `season`·`week`, `income`·`expenses`·`cash_change`, 장부 항목 `entries`, 구역별 수익 일수와 총수입 `territories`, 선수별 CA·레벨·XP·피로·부상 변동 `members`, 제목·접근법·결말·사건 묘사·실제 보상·준비비 `missions`, 점령 결과 `battle`이 들어간다.

점령한 주에는 3일분 수입이 잡힌다. 점령 상태가 다음 주에도 유지되면 7일분이 잡힌다. 구역 순수입을 보여주려면 장부에서 구역 총수입과 유지비·관리비를 구분한다. 51주 결산과 함께 다음 시즌으로 넘어갈 때 자동 52주·연말 처리는 장부 항목의 주차로 구분한다.

모의전 출전은 기존 `start`의 `practice: true`를 사용한다. 모의전 종료 후에도 주차와 장부가 유지된다.

테스트는 저장소 루트에서 `PYTHONPATH=engine python -m unittest discover -s tests -v`로 실행한다.

추가 콘텐츠 구조와 미구현 장기/정예 임무 범위는 [`MISSIONS.md`](MISSIONS.md)를 참고한다.

## 정예 임무 (추가)

`state.elite_board`에서 이번 주 정예 의뢰를 선택하고 `assignment.elite_order = {"id":"<게시판 ID>","members":[1,2,3],"choice":"study"}`를 제출한다. 주 1회 별도 슬롯, 3~5인, 부상/파견/다른 활동 중복 배치 금지. 선택지는 `study` / `guard` / `seize`. 기연·현금·부상 결과는 `week_report.elite_missions`, 보유 비급과 인연은 `member` 상세에 제공한다. 전체 규칙은 [ELITE_KIYUN.md](ELITE_KIYUN.md) 참고.
