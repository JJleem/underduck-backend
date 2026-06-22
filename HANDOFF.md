# Underduck Backend — 핸드오프

> 상태(2026-06-19): **Google Sheets 13개 도메인 전부 백엔드 이전 + 엔드포인트 라이브.** 프론트 컷오버만 남음.

## 인프라
- 레포 `JJleem/underduck-backend`(private). Python 3.12 / FastAPI / SQLAlchemy / Alembic. 별도 프로세스/별도 DB.
- 서버 `ubuntu@3.36.239.214`, 코드 `/home/ubuntu/underduck-backend`, systemd `underduck-backend.service`(:8001).
- 공개: **`https://underduck-api.cosmic-hustle.ai.kr`** (nginx + Let's Encrypt TLS, HTTP→HTTPS 301).
- 인증: 모든 엔드포인트 헤더 **`X-Underduck-Secret`** == 서버 `.env`의 `UNDERDUCK_API_SECRET`. 서버사이드에서만 호출.
- 배포: `main` push → GitHub Actions(rsync+pip+`alembic upgrade head`+restart). 시크릿 LIGHTSAIL_HOST/KEY 등록됨.
- DB 시드(시트→Postgres): `scripts/import_sheets.py` (재실행 안전, truncate+insert). 서버에서:
  `cd ~/underduck-backend && GOOGLE_SHEET_ID=... GOOGLE_SHEETS_API_KEY=... .venv/bin/python -m scripts.import_sheets`

## 엔드포인트 (전부 `/api/underduck/*`, X-Underduck-Secret 필요)
| 도메인 | 메서드·경로 | 비고 |
|---|---|---|
| matches | GET `/matches`, GET `/matches/{id}`, POST `/matches`, PATCH `/matches/{id}`, POST·DELETE `/matches/{id}/photos` | match_id=시트 0-based 인덱스 보존. CSV 필드(goals/assists/attendees/photos) 원형 |
| mom-vote | GET `/mom-vote?match_id=`, POST, DELETE(body: match_id,voter_name,vote_type?) | |
| vote-comment | GET `?match_id=`, POST, DELETE `/{id}` | |
| attendance | GET `?match_id=`, POST(upsert match_id+kakao_id), POST `/{id}/finalize`, PATCH `/{id}/status` | finalize→matches.attendees+마감 |
| featured | GET, PUT(player_name, title_ids[3]) | |
| push | GET, POST(upsert endpoint), DELETE(body endpoint) | |
| roster | GET, POST | |
| stats | GET | matches(골/도움/참석 명단)+mom_vote(공/수 부문 투표)에서 **매 요청 집계**. no/pos는 roster 조인. (구 스냅샷 방식 폐기) |
| notice | GET(단일), PUT | 활성 공지 1건 |
| lineup | GET `?match_id=`, PUT(upsert match_id+quarter, 빈값이면 삭제) | players[11]/subs[5]/substitutions JSON 배열 |
| feedback | GET `?match_id=`, POST, DELETE `/{id}` | |
| users | GET, GET `/{kakao_id}`, POST(upsert) | |
| media | GET, POST, DELETE `/{id}` | |
| name-alias | GET, PUT(kakao_name, real_name), DELETE `/{kakao_name}` | 카카오 닉네임→로스터 실명 맵핑. mom_vote/vote_comment/attendance/feedback 저장 시 자동 정규화 |

응답 스키마는 `schemas.py` 참조. timestamp/joined_at 등은 ISO datetime.

## 남은 일 (프론트 컷오버, Phase 3 — `underducfc-dashboard`)
1. Vercel/`.env.local`에 `UNDERDUCK_API_BASE=https://underduck-api.cosmic-hustle.ai.kr`, `UNDERDUCK_API_SECRET`(서버 .env 값) 추가.
2. `app/lib/underduck.ts`(서버사이드 fetch 헬퍼, 이미 존재) 위에 도메인별 래퍼 작성.
3. 도메인 단위 PR로 `getSheetData`/`sheets-write.ts` 호출을 백엔드 호출로 전환 + 매번 실검증. 빅뱅 금지.
4. 전 도메인 전환 후 `google-sheets.ts`/`sheets-write.ts`/`GOOGLE_*` 제거.
5. ~~**stats**: 백엔드 집계 endpoint로 교체~~ ✅ 완료(2026-06-19). `routers/stats.py`가 matches/mom_vote에서 실시간 집계. `stats` 테이블·`import_sheets`의 stats 시드는 더 이상 사용 안 함(제거 가능). mom은 vote_type(공격/수비) 부문별 최다득표 합산이라 프론트에서 부문 분리 표기가 필요하면 `StatOut`에 필드 추가 검토.
