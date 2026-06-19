# Underduck Backend

UNDERDUCK FC 대시보드의 백엔드. cosmic-hustle와 **완전히 분리된 별도 프로세스/별도 DB**.

- **별도 레포·별도 프로세스**: cosmic-hustle FastAPI(:8000)와 무관. uvicorn `:8001`.
- **별도 DB**: PostgreSQL `underduck` (전용 유저 `underduck`). cosmic_hustle DB와 섞지 않음.
- **ML/임베딩 없음**: 순수 CRUD. 린 의존성.
- **프론트**: `underducfc-dashboard`(Next.js, Vercel). 서버사이드에서 `X-Underduck-Secret` 헤더로 프록시 호출.

## 로컬 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # 값 채우기 (아래)
.venv/bin/python run.py   # http://localhost:8001
```

`.env`:

```env
UNDERDUCK_DATABASE_URL=postgresql://underduck:<PASSWORD>@localhost:5432/underduck
UNDERDUCK_API_SECRET=<openssl rand -hex 32>
```

로컬 DB 준비:

```sql
CREATE USER underduck WITH PASSWORD '<PASSWORD>';
CREATE DATABASE underduck OWNER underduck;
```

## 인증

모든 엔드포인트는 `X-Underduck-Secret` 헤더 필요(`UNDERDUCK_API_SECRET`와 상수시간 비교).

```bash
curl -H "X-Underduck-Secret: $UNDERDUCK_API_SECRET" http://localhost:8001/api/underduck/health
# {"ok": true, "db": "connected"}
```

- `GET /api/underduck/health` — DB 연결 확인
- `GET /api/underduck/_authcheck` — 인증 확인

⚠️ secret은 **평문 HTTP/공인 IP로 전송 금지**. 프로덕션은 nginx+TLS 서브도메인 경유.

## 마이그레이션 (Alembic)

```bash
.venv/bin/alembic upgrade head        # 적용
.venv/bin/alembic revision -m "..."   # 신규(Phase 1~)
```

Phase 0에는 모델·revision이 없다. `upgrade head`는 no-op.

## 테스트

```bash
.venv/bin/python -m pytest -q
```

## 배포

- 서버: Lightsail `ubuntu@3.36.239.214`, 코드 `/home/ubuntu/underduck-backend`
- 프로세스: systemd `underduck-backend.service` (`deploy/underduck-backend.service`)
- 공개: nginx + certbot TLS 서브도메인 (`deploy/nginx-underduck.conf`)
- CI: `main` push 시 `.github/workflows/deploy.yml` (rsync + pip + alembic + restart)

상세 절차는 `deploy/` 내 각 파일 주석 참고.
