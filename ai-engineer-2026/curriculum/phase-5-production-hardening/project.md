# Phase 5 Project — The Operational Runbook

> **Ship this:** an **operational runbook** for your capstone agent — the document an
> on-call engineer (maybe future-you at 2am) uses to understand, monitor, and recover the
> system. Phase 5 isn't a feature you build once; it's a practice, and the runbook is its
> artifact.

## Why a runbook is the deliverable

The original roadmap calls Phase 5 "Forever." You can't "finish" production hardening — but
you *can* prove you operate like a professional by producing the document that makes the
system operable by someone other than its author. A runbook is also the clearest interview
signal that you've actually run an agent in production, not just demoed one.

## What the runbook must contain

### 1. System overview
- [ ] Architecture diagram (reuse your capstone's).
- [ ] The model(s) used and the **routing policy** (which model for which difficulty).
- [ ] External dependencies and what happens when each is down.

### 2. Cost budget & controls (Lesson 00)
- [ ] Target **cost per request** and monthly budget.
- [ ] Prompt-caching status (what's cached; expected savings).
- [ ] Routing thresholds; Batch-API usage for non-realtime work.
- [ ] Multi-agent policy: when it's allowed (the 15× justification).

### 3. Latency budget (Lesson 01)
- [ ] Target **p95 latency**; what's parallelized; what's streamed.
- [ ] Fan-out policy and its cost trade.

### 4. Safety checklist (Lesson 02)
- [ ] Tool allow-list (no god-tools); arg validation confirmed.
- [ ] Sandbox config for any code execution (limits, network, ephemerality).
- [ ] Auth-brokering + redaction verified (secret never in context/logs/spans).
- [ ] HITL gates on every irreversible action; audit log for sensitive workflows.

### 5. Monitoring & alerts (Lesson 03)
- [ ] Dashboards for cost/request, tool-failure rate, judge score, p95 latency.
- [ ] **Alert thresholds** for each (and trend alerts, not just static).
- [ ] On-call response: what each alert means and the first action to take.

### 6. The model-upgrade re-baseline procedure (Lesson 03)
- [ ] The 5-step checklist: run golden set → re-calibrate judge → re-check
      guardrails/prompts → re-tune cost levers → update baseline under review.

### 7. Resilience (Lesson 04)
- [ ] Durable-execution setup; checkpoint frequency; resume procedure.
- [ ] Idempotency notes for any send/charge/write step.
- [ ] Circuit-breaker / retry/backoff policy for dependencies.
- [ ] **Recovery drill:** documented steps to resume a killed run by `run_id`/`thread_id`.

## Architecture of the operational loop

```mermaid
flowchart TD
    Prod["capstone in production"] --> Spans["spans (Phase 3)"]
    Spans --> Dash["dashboards + alerts (Lesson 03)"]
    Prod -->|1% sample (Phase 4)| Eval["auto-grade → drift trend"]
    Eval --> Golden["golden set grows"]
    Up["model upgrade"] --> Rebase["re-baseline procedure"]
    Rebase --> Gate["Phase-4 CI gate"]
    Gate --> Prod
    Dash -->|alert fires| OnCall["runbook → first action"]
```

## How it's evaluated

| Criterion | Pass bar |
|-----------|----------|
| Operability | A peer could operate your agent from the runbook alone |
| Cost | Caching + routing in place; budget and per-request target stated |
| Latency | p95 target; parallel + streaming in place |
| Safety | Full checklist satisfied; injection war story documented |
| Monitoring | 4 alerts wired with thresholds + on-call actions |
| Re-baseline | A written, tested model-upgrade procedure |
| Resilience | Resume-after-kill demonstrated; idempotency addressed |

## Stretch goals

- Run a real **game day**: kill the process mid-run, trip a circuit breaker, and simulate
  a model upgrade — and follow your own runbook to recover. Note where the runbook was
  wrong and fix it.
- Build a one-page **live dashboard** from your spans.
- Add automated **anomaly detection** on the cost/latency/judge trends.

## Exit criteria for Phase 5 (and the course)

- [ ] Runbook complete and exercised at least once (a game day).
- [ ] Cost and latency measured against stated targets.
- [ ] Safety checklist fully satisfied.
- [ ] Alerts live; model-upgrade re-baseline procedure written and tested.
- [ ] Resume-after-kill demonstrated on the capstone.

🎉 **You've completed the roadmap.** You can now build *and operate* agent systems that
survive production traffic — the thing companies are paying for. Keep one
[capstone project](../../projects/) live, keep the evals green, and build in public.

➡️ Back to: [the roadmap](../../ROADMAP.md) · [the projects](../../projects/) ·
[the reference shelf](../../reference/)
