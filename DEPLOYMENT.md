# Deployment Information

## Public URL
https://helpful-acceptance-production-b7fe1f20.up.railway.app

## Platform
Railway (Root Directory: `/06-lab-complete`, Dockerfile builder, Redis add-on)

## Test Commands

### Health Check
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://helpful-acceptance-production-b7fe1f20.up.railway.app/health"
# Expected: 200
```

### Readiness Check (Redis connected)
```bash
curl -sS "https://helpful-acceptance-production-b7fe1f20.up.railway.app/ready"
# Expected: {"status":"ready","redis":"ok"} (HTTP 200)
```

### API Test (Authentication)
```bash
# Missing API key -> 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  "https://helpful-acceptance-production-b7fe1f20.up.railway.app/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Valid API key -> 200
curl -sS -X POST \
  "https://helpful-acceptance-production-b7fe1f20.up.railway.app/ask" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

## Environment Variables Set
- `PORT` (`8000`)
- `REDIS_URL` (`${{Redis.REDIS_URL}}`)
- `AGENT_API_KEY` (set via Railway Variables, not committed to Git)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`5.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
