# dbt-gen

dbt model generator — AI-powered or fully local with templates. Describe what you need, get production-ready dbt models out.

Built for data teams where analysts know their data but don't want to hand-write every SQL file, YAML schema, and test from scratch.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## What it does

You run `python3 dbt_gen.py`, tell it what data you're working with and what you want to see at the end, and it generates a complete set of dbt files — source definitions, staging models, intermediate transformations, and final mart tables — all following [dbt Labs best practices](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview).

You can run it in two modes:

- **AI mode** — describe what you want in plain English, and a language model writes the SQL, YAML, and tests for you. Great when you want fully fleshed-out logic from a description.
- **Local mode** — no API key, no internet, no cost. You provide your column names and the tool generates properly structured dbt scaffolding from built-in templates. You fill in the join logic and final SELECTs yourself. Great for getting the boilerplate right instantly.

Every run creates a named folder inside your configured output directory. Review the files, adjust as needed, and you're good to go.

## Supported providers

| Provider | Install | Notes |
|---|---|---|
| **Local templates** | *(none)* | No AI, no API key, works offline. You provide columns, it builds scaffolding. |
| **OpenAI** | `pip install openai` | gpt-4o, gpt-4.1, etc. |
| **Groq** | `pip install openai` | Free tier available, very fast. Uses the OpenAI SDK under the hood. |
| **Anthropic** | `pip install anthropic` | Claude Sonnet, Claude Haiku |

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/jcktp/dbt-gen.git
cd dbt-gen

# 2. (Optional) Install an AI provider SDK — skip this for local mode
pip install openai        # for OpenAI or Groq
pip install anthropic     # for Claude

# 3. Run it
python3 dbt_gen.py
```

First time, it walks you through setup — pick a provider (or local templates), paste your API key if using AI, choose a model, and select your output folder. That's saved to `~/.dbt-gen.json` (permissions locked to your user only) so you don't have to do it again.

---

## How it works

```
$ python3 dbt_gen.py

  ┌─────────────────────────────────────────┐
  │         dbt-gen  ·  model generator     │
  └─────────────────────────────────────────┘

  Using local templates (no AI)
  Output → ~/analytics

  What do you want to do?

    1)  Create a full model   (the whole thing, start to finish)
    2)  Add a staging model   (clean up a raw source table)
    3)  Add a transformation  (join or reshape existing models)
    4)  Add a final table     (the output for dashboards/reports)
    5)  Set output folder     (change where files are saved)
    6)  Change settings       (switch AI provider or API key)

  Pick a number (or q to quit):
```

### Option 1: Create a full model

The one most people will use. It asks a few simple questions:

```
  What should this model be called?
  : recruiter_performance

  What system is the data in?
    1) Greenhouse
    2) Ashby
    ...
  #: 1

  Which tables from Greenhouse?
  : applications, offers, interviews, jobs

  Add another system? [y/N]: y

  What system is the data in?
  #: 3

  Which tables from Workday?
  : employees

  Add another system? [y/N]: n

  What should the final output look like?
  > Monthly breakdown per recruiter showing time to hire,
  > offer acceptance rate, and interviews per opening
  >
```

In **local mode**, the tool then asks for the column names in each table (since there's no AI to guess them):

```
  Columns in Greenhouse.applications?
  : id, candidate_id, job_id, status, applied_at, created_at

  Columns in Greenhouse.offers?
  : id, application_id, status, salary, created_at
  ...
```

It then generates everything — source YAML, staging models, intermediate joins, and the final mart — properly named and structured:

```
  ✓ models/staging/greenhouse/_sources.yml
  ✓ models/staging/greenhouse/stg_greenhouse__applications.sql
  ✓ models/staging/greenhouse/stg_greenhouse__offers.sql
  ✓ models/staging/greenhouse/stg_greenhouse__interviews.sql
  ✓ models/staging/greenhouse/stg_greenhouse__jobs.sql
  ✓ models/staging/greenhouse/_greenhouse__models.yml
  ✓ models/staging/workday/_sources.yml
  ✓ models/staging/workday/stg_workday__employees.sql
  ✓ models/staging/workday/_workday__models.yml
  ✓ models/intermediate/recruiter_performance/int_recruiter_performance_joined.sql
  ✓ models/intermediate/recruiter_performance/_recruiter_performance__models.yml
  ✓ models/marts/recruiter_performance/fct_recruiter_performance.sql
  ✓ models/marts/recruiter_performance/_recruiter_performance__models.yml

  All files saved to: ~/analytics/recruiter_performance
```

In AI mode, the staging SQL includes AI-generated column logic; in local mode, it includes properly cast columns with `TODO` markers in the intermediate and mart models where you add your own logic.

### Option 2–4: Add individual pieces

If you already have part of a dbt project and just need to add a specific layer:

- **Add a staging model** — pick the system, pick the table, it creates the stg_ file + source YAML
- **Add a transformation** — describe a join or aggregation between existing models
- **Add a final table** — create the mart/output table that dashboards will read from

Each asks the same kind of simple questions: pick your system, name it, describe what should come out.

### Option 5: Set output folder

Change where generated files are saved. On first run, you're asked to pick a folder during setup — typically your dbt project root. After that, the path is saved to your config and shown in the status line every time you open the menu.

When you pick this option, the tool opens a **native OS folder picker dialog** (on macOS/Windows/Linux with a desktop). If you're on a headless server or a terminal without GUI support, it falls back to a manual path prompt where you can paste or type the path directly. If the folder doesn't exist yet, it'll offer to create it for you.

The output path is persisted in `~/.dbt-gen.json`, so it carries across sessions.

---

## AI mode vs local mode

| | AI mode | Local mode |
|---|---|---|
| **Needs API key** | Yes | No |
| **Needs internet** | Yes | No |
| **Cost** | Per-token (free tier on Groq) | Free |
| **Staging models** | AI writes full column logic | You provide columns, tool casts & structures them |
| **Intermediate models** | AI writes join/transform logic | Scaffolding with `ref()` CTEs, you write the joins |
| **Mart models** | AI writes the final SELECT | Scaffolding with config + CTEs, you write the SELECT |
| **YAML schemas** | AI fills in descriptions & tests | Structure with `TODO` placeholders |
| **Best for** | "Describe it and get working SQL" | "I know my columns, just give me the boilerplate" |

You can switch between modes at any time via option 6 (Change settings).

---

## Output structure

Each run creates a folder inside your configured output directory:

```
~/analytics/                      ← your configured output folder
├── recruiter_performance/        ← from first run
│   └── models/
│       ├── staging/
│       │   ├── greenhouse/
│       │   │   ├── _sources.yml
│       │   │   ├── _greenhouse__models.yml
│       │   │   ├── stg_greenhouse__applications.sql
│       │   │   └── stg_greenhouse__offers.sql
│       │   └── workday/
│       │       └── stg_workday__employees.sql
│       ├── intermediate/
│       │   └── recruiting/
│       │       └── int_applications_joined_with_offers.sql
│       └── marts/
│           └── recruiting/
│               ├── _recruiting__models.yml
│               └── fct_recruiter_performance_monthly.sql
├── time_to_hire/                 ← from second run
│   └── models/...
└── headcount_tracking/           ← from third run
    └── models/...
```

Since your output folder points to your project, the generated files land where they belong — no manual copying needed.

---

## Naming conventions

The tool enforces dbt naming standards automatically:

| What | Pattern | Example |
|---|---|---|
| Source definition | `_sources.yml` | `_sources.yml` |
| Staging model | `stg_<source>__<entity>.sql` | `stg_greenhouse__applications.sql` |
| Intermediate model | `int_<entity>_<verb>.sql` | `int_applications_joined_with_offers.sql` |
| Dimension table | `dim_<entity>.sql` | `dim_candidates.sql` |
| Fact table | `fct_<entity>.sql` | `fct_hires_monthly.sql` |
| Report table | `rpt_<entity>.sql` | `rpt_time_to_hire.sql` |
| Schema YAML | `_<folder>__models.yml` | `_greenhouse__models.yml` |

---

## Local mode details

When running in local mode, the template engine:

- **Infers SQL types from column names** — columns ending in `_at` or `_date` get `cast(... as timestamp)`, `_id` columns get `varchar`, `amount`/`salary`/`cost` get `numeric`, `is_`/`has_` prefixes get `boolean`, and so on.
- **Detects primary keys** — looks for `<table>_id`, `id`, or the first `_id` column and adds `unique` + `not_null` tests automatically.
- **Builds proper ref() chains** — intermediate models get a CTE for each input model using `{{ ref('...') }}`, mart models reference intermediates with `{{ config(materialized='table') }}`.
- **Marks TODOs clearly** — anywhere you need to add your own logic (join conditions, final SELECTs, column descriptions), you'll see a `TODO` comment.

This means you get the entire dbt folder structure, naming conventions, YAML boilerplate, and test scaffolding for free — you just fill in the business logic.

---

## Configuration

Config is saved to `~/.dbt-gen.json` the first time you run the tool. You can also use environment variables:

```bash
export DBT_GEN_PROVIDER=local         # local, openai, groq, or anthropic
export DBT_GEN_API_KEY=gsk-...        # your API key (not needed for local)
export DBT_GEN_MODEL=llama-3.3-70b-versatile  # optional, uses provider default
```

Environment variables override the config file. To reconfigure interactively, pick option 6 from the menu. To change just the output folder, pick option 5.

### Config file example

```json
{
  "provider": "local",
  "api_key": "",
  "model": "templates",
  "output_folder": "/Users/you/repos/analytics"
}
```

### Where to get API keys

Only needed if you choose an AI provider:

- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Groq**: [console.groq.com](https://console.groq.com) (free tier available)
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)

---

## Tips

- **Start with option 1** ("Create a full model") — it handles everything and you can always remove files you don't need
- **Try local mode first** — if you know your column names, local mode gives you instant results with zero setup
- **Point output to your dbt project** — set the output folder to your repo root so generated files land directly in the right place
- **Describe things like you'd tell a colleague** (AI mode) — "I need a table that shows how many people each recruiter hired per month, with their department" works great
- **Column names will be guesses in AI mode** — the AI uses common patterns (e.g. `id`, `created_at`, `status`) but review them against your actual schema before running
- **Each run is isolated** — you can generate several models side by side and pick what works
- **Switch any time** — option 6 lets you swap between local and AI mode whenever you want

---

## Requirements

- Python 3.9+
- No additional packages needed for local mode
- `openai` package (for OpenAI or Groq) and/or `anthropic` package (for Claude) if using AI mode
- `tkinter` (included with most Python installs) for the native folder picker — optional, falls back to manual path entry if unavailable

---

## License

MIT
