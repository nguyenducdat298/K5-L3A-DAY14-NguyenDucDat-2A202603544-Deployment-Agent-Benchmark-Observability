# Mission Answers — Day 14

## Part 1: Localhost vs Production (CP1)

### 1. Các anti-pattern trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong source code** (`develop/app.py` dòng 17–18):
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`.
   - Trong `production/app.py` (dòng 24) & `production/config.py`: đọc cấu hình và secrets từ biến môi trường (`settings`), không commit `.env` thật.
2. **Không có config management, bật cứng `DEBUG = True`** (`develop/app.py` dòng 21–22):
   - Trong `production/app.py` (dòng 29): `level=logging.DEBUG if settings.debug else logging.INFO`.
3. **Dùng `print()` và log lộ secret** (`develop/app.py` dòng 33–34, 38):
   - `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` in thẳng API key ra stdout.
   - Trong `production/app.py` (dòng 28–32): dùng `logging` với định dạng JSON có cấu trúc, không log secret.
4. **Thiếu health check endpoint & graceful shutdown** (`develop/app.py` dòng 42–43):
   - Không có `/health` hay `lifespan` để xử lý tắt ứng dụng êm ái.
   - Trong `production/app.py` (dòng 39–67): dùng `@asynccontextmanager async def lifespan(app)` để quản lý startup/shutdown và cờ `is_ready`.
5. **Bind `host="localhost"`, hardcode `port=8000`, bật `reload=True`** (`develop/app.py` dòng 49–54):
   - `localhost` chỉ nhận kết nối nội bộ, không chạy được trong container; `port` cứng không nhận `PORT` env var của platform; `reload=True` gây tốn tài nguyên và không an toàn ở production.

### 2. Kết quả chạy & gọi thử bản `develop`

Chạy `.venv/bin/python 01-localhost-vs-production/develop/app.py`:

- `GET http://localhost:8000/` → `200 OK`:
  ```json
  {"message":"Hello! Agent is running on my machine :)"}
  ```
- `POST http://localhost:8000/ask?question=Hello` → `200 OK`:
  ```json
  {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
  ```
  Server log in ra: `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this`.

### 3. Bảng so sánh `develop` vs `production`

| Tiêu chí | `develop/app.py` | `production/app.py` | Giải thích |
| --- | --- | --- | --- |
| **Secrets & Config** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG = True` | Đọc từ env vars qua `config.py` (`settings`) | Tránh lộ key khi push Git; tách cấu hình khỏi code (12-factor). |
| **Logging** | `print("[DEBUG] ...")`, log cả API key | Structured JSON logging (`logging`) | Dễ parse bởi Datadog/Loki; không làm lộ thông tin nhạy cảm. |
| **Network & Port** | `host="localhost"`, `port=8000`, `reload=True` | `0.0.0.0`, port từ `PORT` env var, tắt reload | Container/cloud cần bind `0.0.0.0` và nhận `PORT` động từ platform. |
| **Health & Lifecycle** | Không có `/health`, tắt đột ngột | Có `/health`, `lifespan` + graceful shutdown | Platform biết khi nào app sống/sẵn sàng và không cắt ngang request đang xử lý. |

---

## Part 2: Docker (CP2)

### 1. Trả lời Exercise 2.1 (`02-docker/develop/Dockerfile`)

1. **Base image là gì?** `python:3.11` (full Python distribution, ~1 GB).
2. **Working directory là gì?** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` trước `COPY . .`?** Để tận dụng Docker layer cache: khi chỉ sửa code (`app.py`), layer `pip install -r requirements.txt` được cache lại và không phải cài lại dependencies từ đầu.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?** `CMD` là lệnh mặc định khi container chạy và dễ bị ghi đè khi truyền tham số lúc `docker run`; `ENTRYPOINT` cố định executable chính của container, tham số truyền thêm sẽ được nối vào sau `ENTRYPOINT`.

### 2. Kết quả chạy & gọi container `my-agent:develop` (Exercise 2.2)

- `docker run -d --rm -p 8000:8000 my-agent:develop`
- `curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d '{"question": "What is Docker?"}'`
  - Trả về `422` (`{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}`) do endpoint `/ask` trong `develop/app.py` nhận `question` qua query param.

### 3. So sánh kích thước image `develop` và `production` (Exercise 2.3)

Đo trực tiếp bằng `docker images | grep my-agent`:

| Image | Tag | Size | Disk Usage | Ghi chú |
| --- | --- | ---: | ---: | --- |
| `my-agent` | `develop` | `1.67GB` | `426MB` | Single-stage, base `python:3.11` |
| `my-agent` | `advanced` | `240MB` | `57.4MB` | Multi-stage (`builder` + `runtime` trên `python:3.11-slim`) |

- **Chênh lệch:** `my-agent:advanced` nhỏ hơn `my-agent:develop` khoảng **85.6%** (`(1670 - 240) / 1670 ≈ 85.6%`).
- **Lý do nhỏ hơn:** Stage `builder` cài `gcc` và build dependencies vào `/root/.local`; stage `runtime` chỉ dùng `python:3.11-slim`, copy `/root/.local` sang và chạy dưới user không phải root (`appuser`), loại bỏ toàn bộ compiler/build tools.

### 4. Sơ đồ stack Exercise 2.4 & kết quả test qua Nginx

```text
Client (localhost:80)
   │
   ▼
[ nginx ] (nginx:alpine — reverse proxy, expose port 80)
   │
   ▼  (internal network)
[ agent ] (my-agent:advanced, port 8000, không expose ra ngoài)
   ├──▶ [ redis ]  (redis:7-alpine, port 6379 — session cache & rate limiting)
   └──▶ [ qdrant ] (qdrant/qdrant:v1.9.0, port 6333 — vector DB cho RAG)
```

Kết quả test qua Nginx (`02-docker/production/docker-compose.yml`):

- `curl -sS http://localhost/health`:
  ```json
  {"status":"ok","uptime_seconds":5.2,"version":"2.0.0","timestamp":"2026-11-25T07:36:56.341828"}
  ```
- `curl -sS http://localhost/ask -X POST -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'`:
  ```json
  {"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
  ```

---

## Part 4: API Security (CP3)

### 1. Output `curl -i` các trường hợp `401`, `200`, `429`

- **Trường hợp `401 Unauthorized` (không có token):**
  ```http
  HTTP/1.1 401 Unauthorized
  date: Wed, 25 Nov 2026 07:49:51 GMT
  server: uvicorn
  www-authenticate: Bearer
  content-length: 76
  content-type: application/json
  x-content-type-options: nosniff
  x-frame-options: DENY
  x-xss-protection: 1; mode=block
  referrer-policy: strict-origin-when-cross-origin

  {"detail":"Authentication required. Include: Authorization: Bearer <token>"}
  ```

- **Trường hợp `200 OK` (có JWT token từ `/auth/token`, đã che token):**
  ```http
  HTTP/1.1 200 OK
  date: Wed, 25 Nov 2026 07:50:17 GMT
  server: uvicorn
  content-length: 209
  content-type: application/json
  x-content-type-options: nosniff
  x-frame-options: DENY
  x-xss-protection: 1; mode=block
  referrer-policy: strict-origin-when-cross-origin

  {"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
  ```

- **Trường hợp `429 Too Many Requests` (vòng lặp `curl` chạm ngưỡng 10 req/60s ở request #10):**
  ```http
  HTTP/1.1 429 Too Many Requests
  date: Wed, 25 Nov 2026 07:50:19 GMT
  server: uvicorn
  x-ratelimit-limit: 10
  x-ratelimit-remaining: 0
  x-ratelimit-reset: 1795593079
  retry-after: 59
  content-length: 98
  content-type: application/json
  x-content-type-options: nosniff
  x-frame-options: DENY
  x-xss-protection: 1; mode=block
  referrer-policy: strict-origin-when-cross-origin

  {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
  ```

### 2. Giải thích cách làm Cost Guard (`04-api-gateway/production/cost_guard.py`)

- **Rate limit** chỉ giới hạn số lượng request theo thời gian (bảo vệ tốc độ/server), nhưng một request LLM dài vẫn có thể tốn nhiều token và tiền.
- **Cost guard** bảo vệ ngân sách bằng cách:
  1. Đặt **ngân sách tối đa** theo user/ngày hoặc toàn hệ thống (USD).
  2. **Kiểm tra trước khi gọi LLM** (từ chối nếu đã vượt budget).
  3. **Tính chi phí thực tế sau khi gọi** dựa trên số `input_tokens` và `output_tokens` rồi cộng dồn vào bộ đếm chi phí (trả về `budget_remaining_usd` trong response).

---

## Part 5: Scaling & Reliability (CP4)

### 1. Kết quả chạy `test_stateless.py` với 3 instance (`--scale agent=3`)

Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` rồi `python test_stateless.py`:

```text
Session ID: 3d19be20-67af-450c-9fde-6af33f5eae71

Request 1: [instance-bec39d]
Request 2: [instance-272207]
Request 3: [instance-7a7212]
Request 4: [instance-bec39d]
Request 5: [instance-272207]

Total requests: 5
Instances used: {'instance-bec39d', 'instance-272207', 'instance-7a7212'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

### 2. Giải thích kết quả & Liveness vs Readiness

- **Tại sao không mất state khi chạy 3 instance?**
  Nginx load-balance 5 request luân phiên qua cả 3 container (`instance-bec39d`, `instance-272207`, `instance-7a7212`). Nhờ lịch sử hội thoại được lưu tập trung trong **Redis** (thay vì RAM cục bộ của từng container), bất kỳ instance nào nhận request tiếp theo cũng đọc/ghi được đúng session đó.
- **Liveness (`/health`) vs Readiness (`/ready`):**
  - `/health` (liveness): kiểm tra process app còn sống hay đã treo (nếu fail → restart container).
  - `/ready` (readiness): kiểm tra app đã sẵn sàng nhận traffic chưa (ví dụ: kết nối Redis thành công; nếu fail → load balancer tạm ngừng gửi request tới instance đó).
