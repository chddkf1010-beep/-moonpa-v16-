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
    "missions": [[651, 652, 653]],
    "rest": [654],
    "attack": null
  }
}
```

- `attack`을 지정할 때는 `{"zone": 39, "setup": [...]}`을 넣는다. `setup`은 기존 점령전과 같은 5개의 `{id, row, skills}`다.
- 수익 임무는 기존 경제 엔진 기준으로 팀당 3명, 최대 2팀이다. 중복 배치, 부상자 활동, 1군 20명 초과, 활동 15명 미달을 검사한다. 부상·인원 부족으로 가용 인원이 15명 미만이면 가용 인원까지만 요구한다.
- 빈 1군 자리는 가용 인원을 훈련에 자동 배치한다. 2군 훈련과 부상 회복은 주간 처리에서 계산한다.
- 점령전이 있으면 `week_pending: true`와 `battle`을 반환한다. 기존 `round` 명령으로 전투를 진행한다. 종료와 동시에 이번 주 결산을 한 번 확정한다.
- 점령전이 없으면 바로 결산하고 다음 주를 반환한다. 오래된 시즌·주차 요청과 전투 중 중복 제출은 오류로 반환한다.

## 결산 화면

`week_report`에는 정산한 `season`·`week`, `income`·`expenses`·`cash_change`, 장부 항목 `entries`, 구역별 수익 일수와 총수입 `territories`, 선수별 CA·레벨·XP·피로·부상 변동 `members`, 임무비 지급 여부 `missions`, 점령 결과 `battle`이 들어간다.

점령한 주에는 3일분 수입이 잡힌다. 점령 상태가 다음 주에도 유지되면 7일분이 잡힌다. 구역 순수입을 보여주려면 장부에서 구역 총수입과 유지비·관리비를 구분한다. 51주 결산과 함께 다음 시즌으로 넘어갈 때 자동 52주·연말 처리는 장부 항목의 주차로 구분한다.

모의전 출전은 기존 `start`의 `practice: true`를 사용한다. 모의전 종료 후에도 주차와 장부가 유지된다.

테스트는 저장소 루트에서 `PYTHONPATH=engine python -m unittest discover -s tests -v`로 실행한다.
