# Benchmarks

Keep measurement workloads and reproduction instructions here. Large datasets,
generated inputs and result files stay outside tracked source; refer to accepted
datasets by version and digest. Declare dependencies on `code` or `proof` in the
root `project.json` when their changes affect a benchmark.

The supplied SHA-256 workload is a working example of the measurement interface.
It exercises deterministic input generation, correctness checking, warm-up,
repeated timing and a structured report. Its throughput is not a result about
your research. Replace it with the workload that answers your evaluation question.

From this directory:

```sh
python3 run.py --mode smoke --output results/smoke.json
python3 run.py --mode full --output results/full.json
python3 -B -m unittest discover -s . -p 'test_*.py'
```

Smoke uses 256 KiB and three measured iterations; full uses 16 MiB and fifteen.
`--bytes`, `--repetitions` and `--seed` override those settings. Each output path
must be new, preserving earlier evidence. Results include input and script
digests, individual nanosecond samples, median duration/throughput with units,
Python and machine information, and the exact invocation. Input generation and
the one warm-up iteration are excluded from timings. No absolute performance
threshold is imposed on shared CI runners.

The benchmark component is disabled in the starter until deliberately selected.
To enable this example, set `components.benchmark.enabled` to `true` and its
`profiles` to the following in `project.json`. This is component configuration,
not another repository identity file:

```json
{
  "ordinary": [{
    "name": "smoke", "kind": "benchmark",
    "argv": ["python3", "run.py", "--mode", "smoke", "--output", "results/smoke.json"],
    "timeout": 60, "outputs": ["results/smoke.json"], "result_file": "results/smoke.json"
  }],
  "full": [{
    "name": "full", "kind": "benchmark",
    "argv": ["python3", "run.py", "--mode", "full", "--output", "results/full.json"],
    "timeout": 600, "outputs": ["results/full.json"], "result_file": "results/full.json"
  }]
}
```

CI validates `component-result/v1` and adds source, configuration, resolved
runtime and run identity. A successful smoke run proves this workload executed
and produced its report; it does not validate a paper's performance claims.
Run full research measurements explicitly with declared hardware, dataset,
method, repetitions and limits. Publish the selected evidence with those facts.
