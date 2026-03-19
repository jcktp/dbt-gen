# dbt-gen

AI-powered dbt model generator. Describe what you need in plain English, get production-ready dbt models out.

Built for data teams where analysts know their data but don't want to hand-write every SQL file, YAML schema, and test from scratch.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## What it does

You run `python3 dbt_gen.py`, tell it what data you're working with and what you want to see at the end, and it generates a complete set of dbt files — source definitions, staging models, intermediate transformations, and final mart tables — all following [dbt Labs best practices](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview).

Every run creates a named folder in your current directory. Review the files, adjust column names to match your warehouse, and copy them into your dbt project.

## Supported providers

| Provider | Install | Notes |
|---|---|---|
| **OpenAI** | `pip install openai` | gpt-4o, gpt-4.1, etc. |
| **Groq** | `pip install openai` | Free tier available, very fast. Uses the OpenAI SDK under the hood. |
| **Anthropic** | `pip install anthropic` | Claude Sonnet, Claude Haiku |

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/jcktp/dbt-gen.git
cd dbt-gen

# 2. Install the SDK for your provider (pick one)
pip install openai        # for OpenAI or Groq
pip install anthropic     # for Claude

# 3. Run it
python3 dbt_gen.py
```

First time, it walks you through setup — pick a provider, paste your API key, choose a model. That's saved to `~/.dbt-gen.json` (permissions locked to your user only) so you don't have to do it again.

---

## How it works

```
$ python3 dbt_gen.py

  ┌─────────────────────────────────────────┐
  │         dbt-gen  ·  model generator     │
  └─────────────────────────────────────────┘

  Using Groq (llama-3.3-70b-versatile)

  What do you want to do?

    1)  Create a full model   (the whole thing, start to finish)
    2)  Add a staging model   (clean up a raw source table)
    3)  Add a transformation  (join or reshape existing models)
    4)  Add a final table     (the output for dashboards/reports)
    5)  Change settings       (switch AI provider or API key)

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
    3) Workday
    4) BambooHR
    5) SAP SuccessFactors
    6) Lever
    7) Gem
    8) GoodTime
    9) BrightHire
    10) Salesforce
    11) HubSpot
    12) Snowflake (custom tables)
    13) Other (type your own)
  #: 2

  Which tables from Ashby?
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

It then generates everything — source YAML, staging models, intermediate joins, and the final mart — properly named, tested, and documented:

```
  ✓ models/staging/greenhouse/_sources.yml
  ✓ models/staging/greenhouse/stg_greenhouse__applications.sql
  ✓ models/staging/greenhouse/stg_greenhouse__offers.sql
  ✓ models/staging/greenhouse/stg_greenhouse__interviews.sql
  ✓ models/staging/greenhouse/stg_greenhouse__jobs.sql
  ✓ models/staging/workday/_sources.yml
  ✓ models/staging/workday/stg_workday__employees.sql
  ✓ models/intermediate/recruiting/int_applications_joined_with_offers.sql
  ✓ models/marts/recruiting/fct_recruiter_performance_monthly.sql
  ✓ models/marts/recruiting/_recruiting__models.yml

  All files saved to: ~/analytics/recruiter_performance
```

### Option 2–4: Add individual pieces

If you already have part of a dbt project and just need to add a specific layer:

- **Add a staging model** — pick the system, pick the table, it creates the stg_ file + source YAML
- **Add a transformation** — describe a join or aggregation between existing models
- **Add a final table** — create the mart/output table that dashboards will read from

Each asks the same kind of simple questions: pick your system, name it, describe what should come out.

---

## Output structure

Each run creates a folder in your current directory:

```
your-working-directory/
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

When you're happy with a batch, copy the `models/` folder into your dbt project repo.

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

## Configuration

Config is saved to `~/.dbt-gen.json` the first time you run the tool. You can also use environment variables:

```bash
export DBT_GEN_PROVIDER=groq          # openai, groq, or anthropic
export DBT_GEN_API_KEY=gsk-...        # your API key
export DBT_GEN_MODEL=llama-3.3-70b-versatile  # optional, uses provider default
```

Environment variables override the config file. To reconfigure interactively, pick option 5 from the menu.

### Where to get API keys

- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Groq**: [console.groq.com](https://console.groq.com) (free tier available)
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)

---

## Tips

- **Start with option 1** ("Create a full model") — it handles everything and you can always remove files you don't need
- **Describe things like you'd tell a colleague** — "I need a table that shows how many people each recruiter hired per month, with their department" works great
- **Column names will be guesses** — the AI uses common patterns (e.g. `id`, `created_at`, `status`) but review them against your actual schema before running
- **Each run is isolated** — you can generate several models side by side and pick what works
- **Groq is fast and free** — good default for trying things out; switch to GPT-4o or Claude for more complex models if needed

---

## Requirements

- Python 3.9+
- `openai` package (for OpenAI or Groq) and/or `anthropic` package (for Claude)

---

## License

MIT
