# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000 ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn đáng kể so với baseline trước khi nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency để xác nhận P95/P99 tăng và xác định khoảng thời gian bắt đầu bất thường.
  2. Lọc `data/logs.jsonl` trong khoảng thời gian đó, chọn một `response_sent` có `latency_ms` cao và lấy `correlation_id`.
  3. Mở trace có cùng `correlation_id` trên Langfuse, so sánh thời gian của `retrieval` và `generation` để xác định bước gây chậm.
- Mitigation tạm thời: rollback prompt/config gần nhất nếu evidence cho thấy regression; tắt incident practice nếu đang bật; giảm tải tạm thời nếu latency tăng do traffic.
- Owner: `student-2A202602364`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate của request API
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` trong 5 phút
- Ảnh hưởng tới người dùng: một phần request không nhận được câu trả lời thành công.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors để xác nhận error rate tăng và xem khoảng thời gian xảy ra.
  2. Lọc các event `request_failed` trong `data/logs.jsonl`, xem `error_type`, `tool_success` và lấy một `correlation_id` đại diện.
  3. Mở trace cùng `correlation_id` trên Langfuse để xác định observation nào lỗi hoặc không hoàn tất.
- Mitigation tạm thời: rollback thay đổi gần nhất nếu có tương quan thời gian; khôi phục dependency/config gây lỗi; tắt scenario practice khi demo nếu đó là nguồn sự cố.
- Owner: `student-2A202602364`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: retrieval success rate
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` trong 5 phút
- Ảnh hưởng tới người dùng: hệ thống có thể không lấy được context cần thiết, làm request thất bại hoặc làm chất lượng câu trả lời giảm.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors để xác nhận retrieval success giảm dưới 90%.
  2. Lọc log có `tool_name="retrieval"` và `tool_success=false`, sau đó lấy `correlation_id` của request bị ảnh hưởng.
  3. Mở trace cùng `correlation_id` và kiểm tra observation `retrieval` để xác định lỗi hoặc latency bất thường.
- Mitigation tạm thời: khôi phục dependency retrieval, rollback cấu hình liên quan hoặc dùng fallback an toàn nếu có; không kết luận root cause trước khi đối chiếu trace.
- Owner: `student-2A202602364`
