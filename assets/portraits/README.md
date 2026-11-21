# 문파 키우기: 역할별 초상화 자산

이 폴더에는 이미지 6종이 위치해야 합니다. 현재 소스 코드는 이 파일들이
없을 때 기존 역할 글자 표시를 유지하도록 작성되어 있습니다.

| 역할 ID | 역할 | 필요한 파일 |
|---|---|---|
| 0 | 수호형 | `guardian_card.webp` |
| 1 | 무인형 | `warrior_card.webp` |
| 2 | 사수형 | `archer_card.webp` |
| 3 | 주술형 | `shaman_card.webp` |
| 4 | 치유형 | `healer_card.webp` |
| 5 | 암살형 | `assassin_card.webp` |

초상화 6종 실물은 대화에서 별도 제공한 `moonpa_character_portraits_6roles_v1.zip`
안의 `assets/portraits/`에 있습니다. **WebP 이미지 바이너리는 아직 GitHub에
업로드되지 않았습니다.** ZIP에서 폴더를 추출하여 저장소에 업로드해야 이미지가 표시됩니다.

현재 이 6장은 캐릭터 개인 초상화가 아닌 **역할별 공용 초상화**입니다.
개별 문파원의 얼굴이 확정되면 `fid`를 기준으로 연결하고, 이적해도 동일한
초상화를 사용하도록 확장해야 합니다.
