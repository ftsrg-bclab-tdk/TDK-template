# The demonstration

Recorded programmatically, never by hand, so it is reproducible, it cannot drift from the code,
and CI publishes a fresh recording on every push (`.github/workflows/demo.yml`).

- A web UI: a Playwright script in `demo/web/` that drives the real flow, with captions drawn
  into the recording at each step (what the viewer should notice, not what is being clicked),
  saved as video and as a trace.
- A backend, a CLI, a prover (Tamarin, Lean, a model checker): an asciinema cast recorded by
  `demo/record.sh` from a scripted session, with captions as comment lines, rendered to SVG or
  GIF with `agg` or `svg-term`; or an HTML page that embeds the cast and the verdicts.

Captions carry the insight: the invariant that holds, the attack that is rejected, the number
that appears. `just demo` runs it; the output goes to `out/demo/`.
