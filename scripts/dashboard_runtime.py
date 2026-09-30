from __future__ import annotations

import html
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from statistics import mean

LOG_PATH = Path("data/logs.jsonl")
HOST = "127.0.0.1"
PORT = 8501
WINDOW_MINUTES = 60


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0

    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]

    pos = (len(xs) - 1) * (p / 100.0)
    lo = math.floor(pos)
    hi = math.ceil(pos)

    if lo == hi:
        return xs[lo]

    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_records() -> list[dict]:
    if not LOG_PATH.exists():
        return []

    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        try:
            record = json.loads(line)
            if "ts" in record:
                record["_dt"] = parse_ts(record["ts"])
            records.append(record)
        except (json.JSONDecodeError, ValueError):
            pass

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    return [
        r for r in records
        if r.get("_dt") is not None and r["_dt"] >= cutoff
    ]


def bucket_by_minute(records: list[dict], event: str, field: str | None = None):
    buckets: dict[str, list[float]] = defaultdict(list)

    for r in records:
        if r.get("event") != event:
            continue

        key = r["_dt"].strftime("%H:%M")

        if field is None:
            buckets[key].append(1.0)
        elif isinstance(r.get(field), (int, float)):
            buckets[key].append(float(r[field]))

    return dict(sorted(buckets.items()))


def line_svg(values: list[float], threshold: float, ymax: float | None = None) -> str:
    width = 620
    height = 150
    pad = 18

    vals = values or [0.0]
    upper = ymax or max(max(vals), threshold, 1.0)
    upper *= 1.10

    def y(v: float) -> float:
        return height - pad - ((v / upper) * (height - 2 * pad))

    if len(vals) == 1:
        xs = [width / 2]
    else:
        xs = [
            pad + i * ((width - 2 * pad) / (len(vals) - 1))
            for i in range(len(vals))
        ]

    points = " ".join(f"{x:.1f},{y(v):.1f}" for x, v in zip(xs, vals))
    threshold_y = y(threshold)

    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y(v):.1f}" r="3.5" fill="currentColor"/>'
        for x, v in zip(xs, vals)
    )

    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart">
      <line x1="{pad}" x2="{width-pad}" y1="{height-pad}" y2="{height-pad}"
            stroke="#d8d8df" stroke-width="1"/>
      <line x1="{pad}" x2="{width-pad}" y1="{threshold_y:.1f}" y2="{threshold_y:.1f}"
            stroke="#d44" stroke-width="2" stroke-dasharray="8 6"/>
      <polyline points="{points}" fill="none" stroke="currentColor"
                stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
      {circles}
    </svg>
    """


def render_dashboard() -> str:
    records = load_records()

    received = [r for r in records if r.get("event") == "request_received"]
    responses = [r for r in records if r.get("event") == "response_sent"]
    failures = [r for r in records if r.get("event") == "request_failed"]

    latencies = [float(r["latency_ms"]) for r in responses if "latency_ms" in r]
    ttfts = [float(r["ttft_ms"]) for r in responses if "ttft_ms" in r]

    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    ttft_p95 = percentile(ttfts, 95)

    traffic_buckets = bucket_by_minute(records, "request_received")
    traffic_values = [sum(v) for v in traffic_buckets.values()]

    error_rate = (len(failures) / len(received) * 100.0) if received else 0.0

    tool_records = [r for r in records if r.get("tool_success") is not None]
    retrieval_success = (
        sum(1 for r in tool_records if r.get("tool_success") is True)
        / len(tool_records)
        * 100.0
        if tool_records else 0.0
    )

    error_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"requests": 0, "errors": 0}
    )
    for r in received:
        error_buckets[r["_dt"].strftime("%H:%M")]["requests"] += 1
    for r in failures:
        error_buckets[r["_dt"].strftime("%H:%M")]["errors"] += 1

    error_values = []
    for key in sorted(error_buckets):
        item = error_buckets[key]
        rate = (
            item["errors"] / item["requests"] * 100.0
            if item["requests"] else 0.0
        )
        error_values.append(rate)

    cost_total = sum(float(r.get("cost_usd", 0.0)) for r in responses)

    cost_buckets = bucket_by_minute(records, "response_sent", "cost_usd")
    cost_values = [sum(v) for v in cost_buckets.values()]

    tokens_in = sum(int(r.get("tokens_in", 0)) for r in responses)
    tokens_out = sum(int(r.get("tokens_out", 0)) for r in responses)

    quality_values = [
        float(r["quality_score"])
        for r in responses
        if isinstance(r.get("quality_score"), (int, float))
    ]
    quality_mean = mean(quality_values) if quality_values else 0.0

    latency_series = [
        mean(v)
        for v in bucket_by_minute(records, "response_sent", "latency_ms").values()
    ]

    quality_series = [
        mean(v)
        for v in bucket_by_minute(records, "response_sent", "quality_score").values()
    ]

    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>K4-L3B Day13 Dashboard</title>
<style>
body {{
    margin: 0;
    padding: 28px;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    background: #f6f6fa;
    color: #252532;
}}
.header {{
    display: flex;
    justify-content: space-between;
    align-items: end;
    margin-bottom: 22px;
}}
h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
.sub {{ color: #6d6d7b; font-size: 14px; }}
.grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
}}
.card {{
    background: white;
    border: 1px solid #e4e4ec;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 5px 18px rgba(0,0,0,.045);
}}
.card h2 {{
    margin: 0 0 4px 0;
    font-size: 19px;
}}
.meta {{
    font-size: 12px;
    color: #777785;
    margin-bottom: 13px;
}}
.metrics {{
    display: flex;
    gap: 22px;
    flex-wrap: wrap;
    margin-bottom: 4px;
}}
.metric strong {{
    display: block;
    font-size: 25px;
}}
.metric span {{
    color: #777785;
    font-size: 12px;
}}
.threshold {{
    margin-top: 8px;
    font-size: 12px;
    color: #b33;
}}
.chart {{
    width: 100%;
    height: 125px;
    color: #6d55b3;
}}
.good {{ color: #208558; }}
.bad {{ color: #c0392b; }}
.footer {{
    margin-top: 18px;
    font-size: 12px;
    color: #777785;
}}
</style>
</head>

<body>
<div class="header">
  <div>
    <h1>K4-L3B Day 13 — Monitoring & LLMOps</h1>
    <div class="sub">
      Source: data/logs.jsonl · Time range: last 60 minutes · Auto refresh: 30 seconds
    </div>
  </div>
  <div class="sub">
    Generated: {html.escape(generated_at)}<br>
    Requests in window: {len(received)}
  </div>
</div>

<div class="grid">

<section class="card">
  <h2>1. Latency</h2>
  <div class="meta">Unit: ms · response_sent.latency_ms / ttft_ms</div>
  <div class="metrics">
    <div class="metric"><strong>{p50:.0f}</strong><span>P50 latency</span></div>
    <div class="metric"><strong>{p95:.0f}</strong><span>P95 latency</span></div>
    <div class="metric"><strong>{p99:.0f}</strong><span>P99 latency</span></div>
    <div class="metric"><strong>{ttft_p95:.0f}</strong><span>TTFT P95</span></div>
  </div>
  {line_svg(latency_series, 3000, ymax=max(3500, max(latency_series or [0])))}
  <div class="threshold">Threshold line: P95 latency ≤ 3000 ms</div>
</section>

<section class="card">
  <h2>2. Traffic</h2>
  <div class="meta">Unit: requests/minute · request_received</div>
  <div class="metrics">
    <div class="metric">
      <strong>{len(received)}</strong>
      <span>Total requests</span>
    </div>
    <div class="metric">
      <strong>{max(traffic_values or [0]):.0f}</strong>
      <span>Peak req/min</span>
    </div>
  </div>
  {line_svg(traffic_values, 1, ymax=max(2, max(traffic_values or [0])))}
  <div class="threshold">Threshold line: traffic ≥ 1 request/minute</div>
</section>

<section class="card">
  <h2>3. Errors</h2>
  <div class="meta">Unit: percent · request_failed + tool_success</div>
  <div class="metrics">
    <div class="metric">
      <strong class="{"good" if error_rate <= 2 else "bad"}">{error_rate:.1f}%</strong>
      <span>Error rate</span>
    </div>
    <div class="metric">
      <strong class="{"good" if retrieval_success >= 90 else "bad"}">{retrieval_success:.1f}%</strong>
      <span>Retrieval success</span>
    </div>
  </div>
  {line_svg(error_values, 2, ymax=max(5, max(error_values or [0])))}
  <div class="threshold">Threshold line: error rate ≤ 2% · Guardrail: retrieval success ≥ 90%</div>
</section>

<section class="card">
  <h2>4. Cost</h2>
  <div class="meta">Unit: USD · response_sent.cost_usd</div>
  <div class="metrics">
    <div class="metric">
      <strong>${cost_total:.4f}</strong>
      <span>Total cost</span>
    </div>
  </div>
  {line_svg(cost_values, 2.5, ymax=2.75)}
  <div class="threshold">Threshold line: total cost ≤ $2.50</div>
</section>

<section class="card">
  <h2>5. Tokens</h2>
  <div class="meta">Unit: tokens · response_sent.tokens_in / tokens_out</div>
  <div class="metrics">
    <div class="metric"><strong>{tokens_in}</strong><span>Input tokens</span></div>
    <div class="metric"><strong>{tokens_out}</strong><span>Output tokens</span></div>
  </div>
  {line_svg([tokens_in, tokens_out], 50000, ymax=55000)}
  <div class="threshold">Threshold line: token sum by field ≤ 50,000</div>
</section>

<section class="card">
  <h2>6. Quality</h2>
  <div class="meta">Unit: score 0–1 · response_sent.quality_score</div>
  <div class="metrics">
    <div class="metric">
      <strong class="{"good" if quality_mean >= .75 else "bad"}">{quality_mean:.2f}</strong>
      <span>Mean quality proxy</span>
    </div>
  </div>
  {line_svg(quality_series, .75, ymax=1.0)}
  <div class="threshold">Threshold line: mean quality ≥ 0.75</div>
</section>

</div>

<div class="footer">
Metrics → Logs → Traces → Root cause
</div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = render_dashboard().encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    print(f"Dashboard: http://{HOST}:{PORT}")
    print("Reading data/logs.jsonl | range=60m | refresh=30s")
    HTTPServer((HOST, PORT), Handler).serve_forever()