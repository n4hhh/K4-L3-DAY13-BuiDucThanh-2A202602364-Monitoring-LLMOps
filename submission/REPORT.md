# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Bùi Đức Thành
- **MSSV:** 2A202602364
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/n4hhh/K4-L3-DAY13-BuiDucThanh-2A202602364-Monitoring-LLMOps
- **Commit SHA cuối:** xem commit SHA được nộp trên LMS/Codelabs
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602364`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Hoàn thiện correlation ID, enrichment và PII processor |
| `validate_dashboard.py` | 6/6 contract | 6/6 contract | Có dashboard runtime 6 panel |
| `pytest` | 22 passed | 24 passed | Bổ sung test CCCD và credit card |
| Số traces hợp lệ | Chưa có đầy đủ child observations | >= 10 traces đầy đủ | Có root, retrieval và generation |
| Số PII leak | 0 | 0 | Không phát hiện PII thô trong validator |
| Latency P95 / TTFT P95 | 538 ms / 50 ms | 538 ms / 50 ms ở baseline sạch | Incident làm P95 tăng tới 2653 ms |
| Retrieval success rate | Chưa có dashboard runtime | 100% ở baseline sạch | Incident vẫn success nhưng latency tăng |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ bằng `clear_contextvars()`, nhận header `x-request-id` nếu có; nếu không thì sinh ID dạng `req-<8 ký tự hex>`. ID được bind bằng `bind_contextvars()`, lưu vào request state và trả lại qua response header `x-request-id`.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, cùng các metric như `latency_ms`, `ttft_ms`, token, cost, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` được đặt trong processor chain trước `JsonlFileProcessor` và JSON renderer. Các pattern bao gồm email, số điện thoại Việt Nam, CCCD và credit card.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100; public tests và test bổ sung đều pass; log runtime cho thấy email/phone/card được thay bằng marker redacted.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Workload được chạy trực tiếp từ fork cá nhân và traces xuất hiện trong project Langfuse `day13-k4-l3b-2A202602364`.
- **Cấu trúc observations:**

    day13-agent-request
    └── lab-agent-run
        ├── retrieval
        └── generation

- **Cách nối trace với log:** `correlation_id` được propagate vào metadata của observations và cùng giá trị được ghi trong structured log.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** version 1, label `baseline`
- **Version/label candidate:** version 2, label `candidate`
- **Trace ID baseline v1:** `87e3ac666df09516466ae368ce1a61db`
- **Trace ID candidate v2:** `b95746ba25d94e48111967520366d4f0`
- **Cách promote và rollback `production`:** Label `production` được chuyển từ v1 sang v2 để promote, sau đó chuyển ngược về v1 để rollback mà không cần thay đổi application code. Trạng thái cuối là v1=`baseline, production`; v2=`candidate, latest`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard runtime đọc trực tiếp `data/logs.jsonl`, time range 60 phút, refresh 30 giây, gồm Latency/TTFT, Traffic, Errors/Retrieval success, Cost, Tokens và Quality. Mỗi panel có unit và threshold.
- **Baseline dashboard:** P50 latency 152 ms, P95 538 ms, P99 790 ms, TTFT P95 50 ms, error rate 0%, retrieval success 100%, cost khoảng $0.0208, quality proxy 0.88.
- **SLO và lý do chọn:** SLO chính yêu cầu 99.5% request trong cửa sổ 28 ngày trả thành công với latency không vượt 3000 ms. Baseline P95 khoảng 538 ms nên ngưỡng 3000 ms đủ cao để không cảnh báo dao động bình thường nhưng vẫn bắt được degradation rõ rệt.
- **Cách tính error budget:** SLO 99.5% tương ứng error budget 0.5%. Với 10,000 request trong cửa sổ, tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO.
- **Ba alert:**
  - `HighLatencyP95`: P95 > 3000 ms trong 5 phút.
  - `HighErrorRate`: error rate > 2% trong 5 phút.
  - `LowRetrievalSuccess`: retrieval success < 90% trong 5 phút.
- **Config/runbook:**
  - `../config/slo.yaml`
  - `../config/alert_rules.yaml`
  - `../docs/alerts.md`

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** khoảng 11:30 Asia/Ho_Chi_Minh ngày 30/09/2026, tương ứng khoảng `04:30 UTC`.
- **Triệu chứng từ metrics:** P95 latency tăng từ khoảng **538 ms** lên **2653 ms**, P99 tăng từ **790 ms** lên **2654 ms**. TTFT P95 vẫn 50 ms, error rate vẫn 0% và retrieval success vẫn 100%.
- **Log line liên quan:** request `req-488534f5` tại `2026-09-30T04:30:00.977604Z` có `latency_ms=2654`, `ttft_ms=50`, `tool_success=true`.
- **Trace ID:** `0529027f8d9d1d8291498a2f7e19e2a0`
- **Span gây ảnh hưởng:** `retrieval` khoảng **2.50 s**, trong khi `generation` chỉ khoảng **0.15 s** và tổng `lab-agent-run` khoảng **2.65 s**.
- **Root cause:** Retrieval latency tăng cao và chiếm gần như toàn bộ end-to-end latency. Đây là slow-success incident: request vẫn HTTP 200 và retrieval vẫn thành công, nhưng tail latency tăng mạnh.
- **Fix action:** Khôi phục retrieval path/configuration về trạng thái latency bình thường. Trong lab, incident được tắt bằng scenario `rag_slow` sau khi thu thập đủ evidence.
- **Preventive measure:** Theo dõi riêng latency của retrieval span, bổ sung cảnh báo khi retrieval duration tăng ngay cả khi `tool_success=true`, đồng thời giữ correlation ID xuyên suốt metrics/logs/traces để điều tra slow-success request.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tôi đặt `capture_input=False` và `capture_output=False` cho observations có thể chứa dữ liệu người dùng. Thay vì đưa raw prompt/response vào trace, trace chỉ giữ metadata, token, cost và correlation ID cần thiết cho observability.
- **Một lỗi/blocker đã gặp:** Kết nối tới Langfuse Japan có lúc timeout khi fetch managed prompt và export spans.
- **Cách tìm nguyên nhân và xử lý:** Tôi kiểm tra DNS bằng `Resolve-DnsName`, TCP 443 bằng `Test-NetConnection`, HTTP bằng `httpx` và `Invoke-WebRequest`. Khi xác định network path chập chờn, tôi chuyển sang hotspot điện thoại và kiểm tra lại prompt fetch trước khi chạy workload.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics dùng để phát hiện triệu chứng và thời điểm bất thường. Logs dùng để chọn một request cụ thể thông qua `correlation_id`. Trace cùng correlation ID cho biết bước nào trong request gây latency/lỗi. Root cause chỉ được kết luận sau khi ba lớp evidence nhất quán.
- **Vai trò của prompt version, token/cost, SLO và rollback:** Prompt versioning giúp biết chính xác version nào phục vụ request và rollback mà không đổi code. Token/cost giúp phát hiện tăng chi phí dù request vẫn thành công. SLO biến chất lượng vận hành thành mục tiêu đo được và error budget xác định mức degradation có thể chấp nhận.
- **Điều quan trọng nhất đã học:** HTTP 200 không đồng nghĩa hệ thống khỏe; slow-success, cost spike hoặc quality degradation chỉ thấy được khi instrument nhiều lớp observability.
- **Hạn chế:** Dashboard hiện là dashboard local đọc `data/logs.jsonl`, phù hợp lab nhưng chưa có persistent metrics backend. Trace/prompt management phụ thuộc kết nối tới Langfuse Cloud.

## 9. Checklist trước khi nộp

- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân.
- [x] Dashboard đủ 6 panel.
- [x] SLO, error budget, 3 alert và runbook đã hoàn thiện.
- [x] Challenge file không được commit.
- [x] Final tests/validators chạy trên source cuối.
- [x] Evidence `01–14` đã nằm trong repository.
- [x] Secret scan sạch.
- [ ] Commit SHA cuối đã được push và nộp trên LMS/Codelabs.
