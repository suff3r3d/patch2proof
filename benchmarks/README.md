# Benchmark harness

The benchmark track keeps evaluation separate from the runtime graph. Each
case runner exports one JSON record with the following minimum fields:

```json
{
  "case_id": "project-cve-1",
  "ground_truth": "confirmed",
  "claim_status": "candidate",
  "valid_differential": false,
  "simulation": false,
  "attempts": 2,
  "duration_seconds": 31.4,
  "evidence_completeness": 0.75,
  "safety_violations": 0,
  "failure_class": "reachability_failure",
  "graph_edges_total": 6,
  "graph_edges_supported": 4,
  "fcs_memory_hit": true
}
```

Use `score.py` to obtain aggregate metrics. Keep simulated adapters in a
separate input file or pass `--include-simulation` only for protocol tests.
Split cases by project/family before running the script so memory transfer and
model leakage can be measured honestly.
