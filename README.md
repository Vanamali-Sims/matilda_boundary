# matilda-boundary

A small, reproducible test of where Matilda-K3's *conditional post-training* stops.

Maincode's model card shows the targeted behaviours work: identity holds under 474 attacks, and political answers are balanced 92% of the time. It also shows that unrelated prompts are almost untouched (3 harmful changes in 3,082). What it doesn't cover is the **boundary**: prompts that *look like* the targeted areas but shouldn't change. This harness probes that boundary and compares hosted Matilda against base Kimi K3.

## Prompt set

53 prompts in `data/prompts.jsonl`. Each row has an id, a category, the prompt, and reference notes for the judge.

| Set | n | Good outcome | What failure would look like |
|---|---|---|---|
| identity_adjacent | 10 | Answers questions *about* Kimi / Moonshot normally | Deflects or refuses a legitimate question |
| lexical_trigger | 5 | Treats "Kimi" (a friend's name) and "moon" as ordinary words | Treats them as being about the model |
| self_disclosure | 3 | Consistent with what Maincode itself publishes | Denies a publicly documented fact |
| settled_fact | 15 | States settled facts directly (Voice result, 2020 US election, IPCC) | False balance ("some argue…") |
| contested | 10 | Balanced (replicates Maincode's claim) | One-sided |
| mixed | 4 | Does the coding or writing task even when the topic is political | Refuses, or buries the task in caveats |
| control | 6 | Normal quality | Degraded |

## Method

The same prompts go to each model, with a fresh conversation per prompt. A different, stronger LLM grades the answers blind. `report` draws a 30-answer sample into `results/spotcheck.csv` so you can hand-label them and check the judge (Cohen's kappa). Rates are reported with 95% Wilson intervals. At n = 53 this is a pilot: it can show large effects, not small ones.

Generated numbers live in `results/report.md`. Read `results/failures.md` before quoting any of them.

## Setup

Requires Python 3.12+. Node 22+ is only needed if you also want the Matilda Code CLI.

```bash
python -m venv .venv
```

Windows: `.venv\Scripts\activate`. macOS/Linux: `source .venv/bin/activate`. Then:

```bash
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Fill in `.env` (gitignored). Kimi K3 and the judge both go through OpenRouter; add about US$5 of credit.

| Variable | Used for |
|---|---|
| `OPENROUTER_API_KEY` | Kimi K3 and the judge |
| `JUDGE_MODEL` | A strong model that is neither Kimi nor Matilda |
| `KIMI_MODEL` | Optional. Default `moonshotai/kimi-k3` |
| `MATILDA_API_KEY` | Only for `--targets matilda_code` |
| `MATILDA_CODE_MODEL` | Optional. Default `matilda-code-1.0` |
| `MATILDA_BASE_URL` | Optional. Default `https://matilda.maincode.com/api` |
| `MATILDA_CLIENT_ID` | Optional. Default `matilda-code` |

Create `MATILDA_API_KEY` with the SDK's `matilda-key create-api-key`.

## Run

From the repo root:

```bash
python -m matilda_eval run --targets kimi_k3 --limit 3      # smoke test
python -m matilda_eval run --targets matilda_chat kimi_k3   # full run; Matilda prints a device-code login
python -m matilda_eval judge                                 # blind grading
python -m matilda_eval report                                # results/report.md, failures.md, spotcheck.csv
python -m matilda_eval report --agreement                    # after you fill human_label in spotcheck.csv
python -m matilda_eval bench --n 30                          # connection-reuse latency from your location
```

`--targets matilda_code` calls the Matilda Code endpoint instead of hosted chat.

Re-running is safe: finished prompt/target pairs are skipped, and responses that are already graded are skipped. If Matilda's daily quota is hit, that target stops and the run prints when the quota resets.

## Layout

```
data/prompts.jsonl          prompt set
matilda_eval/run.py         send prompts to each target
matilda_eval/judge.py       blind grading
matilda_eval/report.py      rates, failures, spot-check sample
matilda_eval/bench_conn.py  new connection vs reused connection
matilda_eval/paths.py       .env and file locations
results/                    responses, grades, report, failures, spotcheck
.env.example                variable names, no secrets
```

## Caveats

- Hosted Matilda chat may not be the open-sourced Matilda-K3 checkpoint. Record what the app or model says it is.
- OpenRouter routes Kimi K3 to third-party providers. `provider` is saved on each response.
- Sampling settings differ between the services and can't be fully matched.
- LLM judges make mistakes. The spot-check is there so a number is not quoted from the judge alone.
