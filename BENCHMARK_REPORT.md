# Benchmark & Observability Report — Day 14

> Mọi con số dưới đây được đo trực tiếp từ các file report JSON trong `06-lab-complete/benchmark-observability/develop/reports/`.

**Họ tên:** NguyenDucDat (2A202603544 - L3A)
**Ngày chạy:** 2026-11-25
**Môi trường:** Ubuntu 26.04 LTS, Python 3.12 (`.venv`), Docker Engine 29.10.1

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | 95% request phải phản hồi dưới 0.5s để UX mượt; p95 nhạy với tail latency hơn avg. |
| Error rate `/ask` | ≤ 2.0 % | Chấp nhận lỗi ngẫu nhiên tối đa 2% từ LLM upstream (mock 1%). |
| Accuracy trên golden dataset | ≥ 85 % | Đảm bảo agent trả lời đúng tối thiểu 85% golden dataset và không có regression trước khi merge. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.32 req/s | 187.8 | 219.4 | 1697.8 | 1.00% | PASS |
| 10 | 42.58 req/s | 193.6 | 223.8 | 1696.4 | 1.00% | PASS |
| 50 | 108.90 req/s | 194.8 | 266.8 | 1708.6 | 0.00% | PASS |
| 100 | 49.71 req/s | 688.2 | 4273.5 | 4873.6 | 0.67% | FAIL (p95 > 500ms) |

**Nhận xét:** RPS không tăng tuyến tính mãi theo concurrency. Từ c=1 đến c=50, RPS tăng mạnh (4.32 → 42.58 → 108.90 req/s) nhờ xử lý bất đồng bộ (`async`). Đến c=100, single-worker uvicorn/event loop bị bão hòa hàng đợi nên RPS tụt xuống 49.71 req/s và p95 vọt lên 4273.5 ms (vi phạm SLO).

### 2.2 Tail latency (`--requests 300 --concurrency 20`)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.9 | 216.1 | 222.0 |
| 0.03 (mặc định) | 220.0 | 219.4 | 1673.0 |
| 0.1 | 331.6 | 1685.0 | 1711.7 |

**Nhận xét:** `p99` và `p95` nhạy nhất với các request chậm bất thường: khi `MOCK_SLOW_RATE` tăng từ `0` lên `0.03`, `avg` chỉ nhích nhẹ từ 189.9 ms lên 220.0 ms, nhưng `p99` nhảy vọt hơn 7.5x (222.0 ms → 1673.0 ms); lên `0.1` thì cả `p95` (1685.0 ms) cũng vượt ngưỡng SLO. Do đó SLO phải đặt theo p95/p99 chứ không theo average, vì average che giấu trải nghiệm tệ của nhóm user chậm nhất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.0 | 109.0 | 113.7 |
| Tổng cost (USD) | $0.000403 | $0.000760 | $0.000790 |
| Cost / câu đúng (USD) | $0.00040335 | $0.00003619 | $0.00003436 |
| Quality gate | FAIL | PASS (≥80%) | PASS (≥100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry về `jwt` (phân biệt API key và JWT có chữ ký số & hết hạn) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry về `hpa`, `kubernetes`, `autoscal` (scale theo CPU, memory, custom metrics) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
Agent v2 dùng retrieval (RAG) nên tốn gấp ~2x tokens/câu (`113.7` vs `57.0`) và p95 cao hơn một chút (`217.5 ms` vs `204.9 ms`), nhưng accuracy tăng vọt từ `4.3%` lên `100.0%`. Nhờ vậy **cost / câu đúng** của v2 (`$0.00003436`) rẻ hơn tới **~11.7 lần** so với v1 (`$0.00040335`). Dùng "cost / câu đúng" phản ánh giá trị thực tế tốt hơn "cost / câu" vì câu trả lời sai không mang lại giá trị.

**CI Quality Gate (`.github/workflows/eval.yml`):**
Job CI chạy `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85`. Nếu accuracy < 85% hoặc có regression, `run_eval.py` thoát với exit code `1` làm bước CI fail và chặn merge PR.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [screenshots/grafana-overview.png](screenshots/grafana-overview.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 2 alert đang **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~101 s (`for: 1m`) | Error Rate `/ask` |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`pending` từ 30s, cần `for: 2m`) | ~120 s+ | Latency p50/p95/p99 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~10–120 s (`for: 2m`) | LLM Cost / Burn Rate |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~40 s (`for: 30s`) | Requests/s theo instance / Up instances |
| E | `AGENT_VERSION=v1` | Không có alert nào | — | Accuracy trên Eval CI |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Prometheus chỉ đo được các chỉ số hạ tầng/hệ thống (latency, error rate, cost, availability), không biết câu trả lời của LLM có đúng hay không. Để phát hiện tụt chất lượng khi đổi sang `v1`, cần chạy **Eval Quality Gate** (`eval/run_eval.py` trên golden dataset trong CI/CD trước khi deploy) kết hợp theo dõi định kỳ feedback/evaluation trên tập mẫu production.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được (`agent.retrieve_context` + `chat mock-llm-small`):

- `trace_id`: `890745442172ad1cb2146268003b72b7`
- Tổng thời gian: `1700 ms` (`1.7 s` trên Jaeger UI)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1688.2 ms`, chiếm **~99.1%** tổng thời gian; `agent.retrieve_context` chỉ mất `14.7 ms`)
- Dòng log tương ứng của trace chậm và trace lỗi `26b062a554f5175f8c9c7f4d6806c493` (grep theo `trace_id` / `llm_error`):

```json
{"ts": "2026-11-25T09:26:13.209882+00:00", "level": "INFO", "service": "observable-agent", "instance": "1806df8512ec", "event": "llm_call", "trace_id": "890745442172ad1cb2146268003b72b7", "span_id": "37328239fe2fe150", "request_id": "f98597a5dcc5", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 40, "cost_usd": 3.5e-05, "llm_ms": 1688.2}
{"ts": "2026-11-25T09:26:15.044174+00:00", "level": "INFO", "service": "observable-agent", "instance": "1806df8512ec", "event": "llm_error", "trace_id": "26b062a554f5175f8c9c7f4d6806c493", "span_id": "e1447c30949371c6", "request_id": "3751c42204cc", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS (Aggregated) | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 (`scale_1_stats.csv`) | 65.29 | 190 | 390 (`POST /ask`: 430) | 1700 | 80 (1.03%) |
| 3 (`scale_3_stats.csv`) | 65.54 | 190 | 240 (`POST /ask`: 250) | 1700 | 69 (0.89%) |

**Giải thích kết quả:**
Scale từ 1 lên 3 instance **cải thiện rõ rệt p95** (giảm từ `390 ms` xuống `240 ms` toàn cục, và từ `430 ms` xuống `250 ms` riêng `/ask`) nhờ san tải đồng thời qua Nginx, giảm nghẽn event loop trên từng container. Tuy nhiên **RPS gần như giữ nguyên (~65.3–65.5 req/s)** và **p99 vẫn ở 1700 ms** vì: (1) nút thắt RPS nằm ở `wait_time` giữa các request của 100 Locust user; (2) nút thắt p99 nằm ở `MOCK_SLOW_RATE=0.03` (+1500 ms mô phỏng LLM upstream chậm) — scale số container agent không làm giảm độ trễ từ upstream LLM.
