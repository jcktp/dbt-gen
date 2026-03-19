#!/usr/bin/env python3
"""
dbt-gen: AI-powered dbt model generator.
Just run: python3 dbt_gen.py
"""

import json
import os
import sys
import textwrap
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".dbt-gen.json"

PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini"],
        "default_model": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
    },
    "groq": {
        "name": "Groq",
        "models": [
            "llama-3.3-70b-versatile",
            "openai/gpt-oss-120b",
            "qwen/qwen3-32b",
            "llama-3.1-8b-instant",
            "moonshotai/kimi-k2-instruct-0905",
        ],
        "default_model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        "default_model": "claude-sonnet-4-20250514",
        "env_key": "ANTHROPIC_API_KEY",
    },
}

MAX_TOKENS = 4096

SYSTEM_PROMPT = """\
You are an expert dbt developer who generates production-quality dbt models following \
official dbt Labs best practices (staging → intermediate → marts pattern).

RULES YOU ALWAYS FOLLOW:
1. Staging models:
   - Named: stg_<source>__<entity>.sql
   - Materialized as views
   - Only rename columns, cast types, basic computations — NO joins, NO aggregations
   - Always use {{ source('source_name', 'table_name') }} references
   - Use CTEs: `source` CTE first, then `renamed`/`cleaned`, then final select

2. Intermediate models:
   - Named: int_<entity>_<verb>.sql (e.g. int_payments_pivoted_to_orders.sql)
   - Reference staging models with {{ ref('stg_...') }}
   - Handle joins, filters, window functions, re-graining, pivots
   - Subdirectories by business domain (not source system)

3. Mart models:
   - Named: dim_<entity>.sql or fct_<entity>.sql or <entity>.sql
   - Materialized as tables
   - Reference intermediate or staging models with {{ ref() }}
   - Business-ready, final entities at their correct grain
   - Denormalized for direct consumption by BI tools

4. Schema YAML:
   - Use _<folder>__models.yml naming (e.g. _staging__models.yml)
   - Include: model name, description, columns with descriptions
   - Add tests: unique, not_null on primary keys; accepted_values where relevant
   - Add meta tags where useful

5. Source YAML:
   - Define in _sources.yml inside the staging/<source_system>/ folder
   - Include: source name, database, schema, tables with descriptions
   - Add freshness checks where applicable

OUTPUT FORMAT:
Return ONLY valid JSON with this structure (no markdown fences, no preamble):
{
  "files": [
    {
      "path": "models/staging/workday/stg_workday__employees.sql",
      "content": "-- the SQL content",
      "description": "Brief description of what this file does"
    }
  ],
  "summary": "Brief explanation of what was generated and why",
  "next_steps": ["Suggestion 1", "Suggestion 2"]
}
"""

# ──────────────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────────────

class C:
    BOLD  = "\033[1m"
    DIM   = "\033[2m"
    CYAN  = "\033[36m"
    GREEN = "\033[32m"
    YELLOW= "\033[33m"
    RED   = "\033[31m"
    RESET = "\033[0m"

BANNER = f"""\
{C.CYAN}{C.BOLD}
  ┌─────────────────────────────────────────┐
  │         dbt-gen  ·  model generator     │
  └─────────────────────────────────────────┘{C.RESET}
"""

def heading(text):
    print(f"\n{C.BOLD}{C.CYAN}  {'─' * 56}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  {text}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  {'─' * 56}{C.RESET}\n")

def ok(text):
    print(f"  {C.GREEN}✓{C.RESET} {text}")

def dim(text):
    print(f"  {C.DIM}{text}{C.RESET}")

def warn(text):
    print(f"  {C.YELLOW}!{C.RESET} {text}")

def err(text):
    print(f"  {C.RED}✗{C.RESET} {text}")

def ask(label, required=True, multiline=False, secret=False):
    """Ask a question. Simple."""
    if multiline:
        print(f"  {C.BOLD}{label}{C.RESET}")
        dim("(type as many lines as you want, then press Enter on an empty line)")
        lines = []
        while True:
            line = input(f"  {C.DIM}>{C.RESET} ")
            if line == "":
                break
            lines.append(line)
        value = "\n".join(lines)
    elif secret:
        import getpass
        value = getpass.getpass(f"  {C.BOLD}{label}{C.RESET}: ")
    else:
        value = input(f"  {C.BOLD}{label}{C.RESET}: ")

    if not value.strip() and required:
        err("This field is required.")
        return ask(label, required, multiline, secret)
    return value.strip()

def pick(label, options):
    """Pick from a numbered list."""
    print(f"  {C.BOLD}{label}{C.RESET}")
    for i, opt in enumerate(options, 1):
        print(f"    {C.CYAN}{i}{C.RESET}) {opt}")
    while True:
        raw = input(f"  {C.DIM}#{C.RESET}: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx, options[idx]
        except ValueError:
            pass
        err(f"Enter a number from 1 to {len(options)}")

def yesno(label, default_yes=True):
    """Simple yes/no prompt."""
    hint = "Y/n" if default_yes else "y/N"
    raw = input(f"  {C.BOLD}{label}{C.RESET} [{hint}]: ").strip().lower()
    if raw == "":
        return default_yes
    return raw in ("y", "yes")


def pick_folder(label="Select the destination folder", current=None):
    """Open a native OS folder picker, or fall back to manual path entry."""
    if current:
        dim(f"Current: {current}")
        print()

    # Try native folder picker first
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()            # hide the root window
        root.attributes("-topmost", True)
        root.update()

        dim("Opening folder picker...")
        chosen = filedialog.askdirectory(
            title=label,
            initialdir=current or str(Path.home()),
            mustexist=True,
        )
        root.destroy()

        if chosen:
            return str(Path(chosen).resolve())
        # User cancelled the dialog — fall through to manual entry
        warn("Folder picker was cancelled.")
        print()
    except Exception:
        # tkinter not available (headless server, WSL without display, etc.)
        dim("(No graphical folder picker available — type the path instead)")
        print()

    # Fallback: manual path entry with tab-completion hint
    while True:
        raw = ask(f"{label}\n  Paste or type the full path")
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            return str(p)
        if p.parent.is_dir():
            if yesno(f"  '{p}' doesn't exist yet. Create it?"):
                p.mkdir(parents=True, exist_ok=True)
                ok(f"Created {p}")
                return str(p)
        err(f"'{raw}' is not a valid directory. Try again.")


# ──────────────────────────────────────────────────────────────────────────────
# Config management
# ──────────────────────────────────────────────────────────────────────────────

def load_config():
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    # Env vars override file
    for env, key in [("DBT_GEN_PROVIDER", "provider"), ("DBT_GEN_API_KEY", "api_key"), ("DBT_GEN_MODEL", "model")]:
        val = os.environ.get(env)
        if val:
            config[key] = val.lower() if key == "provider" else val
    # Fallback to provider-specific env var
    if "api_key" not in config:
        p = config.get("provider", "")
        if p in PROVIDERS:
            val = os.environ.get(PROVIDERS[p]["env_key"])
            if val:
                config["api_key"] = val
    return config

def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
    CONFIG_PATH.chmod(0o600)

def setup_api():
    """Interactive API setup. Returns config dict."""
    heading("First-time setup")

    idx, _ = pick("Which AI provider do you want to use?", ["OpenAI", "Groq  (free tier available, very fast)", "Anthropic (Claude)"])
    provider_key = ["openai", "groq", "anthropic"][idx]
    prov = PROVIDERS[provider_key]

    print()
    dim(f"Get your key from the {prov['name']} dashboard.")
    dim(f"It will be saved locally to {CONFIG_PATH}")
    print()
    api_key = ask("Paste your API key", secret=True)

    print()
    _, model = pick(f"Which model? (recommended: {prov['default_model']})", prov["models"])

    # Ask for output folder during first-time setup
    print()
    heading("Output folder")
    dim("Where should generated dbt models be saved?")
    dim("Pick your dbt project's root, e.g. ~/my_dbt_project/")
    dim("(model files will be written into models/ inside it)")
    print()
    output_folder = pick_folder("Select your dbt project folder")

    config = {"provider": provider_key, "api_key": api_key, "model": model,
              "output_folder": output_folder}
    save_config(config)
    print()
    ok(f"Saved! Using {prov['name']} ({model})")
    ok(f"Output folder: {output_folder}")
    return config


def setup_output_folder(config):
    """Change the output folder interactively."""
    heading("Set output folder")
    dim("Where should generated dbt models be saved?")
    dim("Pick your dbt project's root or any folder you like.")
    print()
    folder = pick_folder(
        label="Select the destination folder",
        current=config.get("output_folder"),
    )
    config["output_folder"] = folder
    save_config(config)
    print()
    ok(f"Output folder set to: {C.BOLD}{folder}{C.RESET}")
    return config

def get_config():
    """Load config or run setup if missing."""
    config = load_config()
    if config.get("provider") and config.get("api_key"):
        if "model" not in config:
            config["model"] = PROVIDERS[config["provider"]]["default_model"]
        # Prompt for output folder if not yet configured
        if not config.get("output_folder"):
            print()
            heading("One more thing — set your output folder")
            dim("Where should generated dbt models be saved?")
            dim("Pick your dbt project's root or any folder you like.")
            print()
            config["output_folder"] = pick_folder("Select the destination folder")
            save_config(config)
            ok(f"Output folder: {config['output_folder']}")
        return config
    return setup_api()

# ──────────────────────────────────────────────────────────────────────────────
# API calls
# ──────────────────────────────────────────────────────────────────────────────

def call_llm(prompt, config):
    provider = config["provider"]
    api_key = config["api_key"]
    model = config["model"]

    print()
    dim(f"Generating with {PROVIDERS[provider]['name']} ({model})...")

    if provider == "anthropic":
        raw = _anthropic(prompt, api_key, model)
    elif provider == "openai":
        raw = _openai(prompt, api_key, model)
    elif provider == "groq":
        raw = _groq(prompt, api_key, model)
    else:
        err(f"Unknown provider: {provider}")
        sys.exit(1)

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        err("Failed to parse AI response. Raw output:")
        print(raw[:2000])
        return None

def _anthropic(prompt, key, model):
    try:
        import anthropic
    except ImportError:
        err("Run: pip install anthropic"); sys.exit(1)
    client = anthropic.Anthropic(api_key=key)
    r = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
                               messages=[{"role": "user", "content": prompt}])
    return r.content[0].text

def _openai(prompt, key, model):
    try:
        from openai import OpenAI
    except ImportError:
        err("Run: pip install openai"); sys.exit(1)
    client = OpenAI(api_key=key)
    r = client.chat.completions.create(model=model, max_tokens=MAX_TOKENS, temperature=0.2,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
    return r.choices[0].message.content

def _groq(prompt, key, model):
    try:
        from openai import OpenAI
    except ImportError:
        err("Run: pip install openai"); sys.exit(1)
    client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
    r = client.chat.completions.create(model=model, max_tokens=MAX_TOKENS, temperature=0.2,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}])
    return r.choices[0].message.content

# ──────────────────────────────────────────────────────────────────────────────
# File writing
# ──────────────────────────────────────────────────────────────────────────────

def write_output(result, folder_name, output_folder=None):
    if not result or not result.get("files"):
        warn("Nothing was generated. Try describing it differently.")
        return

    if output_folder:
        base = Path(output_folder) / folder_name
    else:
        base = Path.cwd() / folder_name
    heading("Created files")

    for f in result["files"]:
        path = base / f["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f["content"])
        ok(f["path"])
        if f.get("description"):
            dim(f"  └─ {f['description']}")

    summary = result.get("summary", "")
    if summary:
        print()
        for line in textwrap.wrap(summary, 56):
            dim(line)

    tips = result.get("next_steps", [])
    if tips:
        print()
        for i, tip in enumerate(tips, 1):
            print(f"  {C.YELLOW}{i}.{C.RESET} {tip}")

    print()
    ok(f"All files saved to: {C.BOLD}{base.resolve()}{C.RESET}")

# ──────────────────────────────────────────────────────────────────────────────
# Source system picker
# ──────────────────────────────────────────────────────────────────────────────

COMMON_SYSTEMS = [
    "Greenhouse",
    "Ashby",
    "Workday",
    "BambooHR",
    "SAP SuccessFactors",
    "Lever",
    "Gem",
    "GoodTime",
    "BrightHire",
    "Salesforce",
    "HubSpot",
    "Snowflake (custom tables)",
    "Other (type your own)",
]

def ask_system():
    """Pick a source system or type a custom one. Returns the system name."""
    idx, chosen = pick("What system is the data in?", COMMON_SYSTEMS)
    if "Other" in chosen:
        return ask("Type the system name")
    return chosen

def ask_sources():
    """Ask for one or more source systems + their tables. Returns a formatted string."""
    systems = []

    system = ask_system()
    print()
    tables = ask(f"Which tables from {system}?\n  (comma-separated, e.g. applications, offers, jobs)")
    systems.append(f"{system}: {tables}")

    while True:
        print()
        if not yesno("Add another system?", default_yes=False):
            break
        print()
        system = ask_system()
        print()
        tables = ask(f"Which tables from {system}?\n  (comma-separated)")
        systems.append(f"{system}: {tables}")

    return "\n".join(systems)

def ask_single_source():
    """Ask for one system + one table. Returns (system, table) as strings."""
    system = ask_system()
    print()
    table = ask(f"Which table from {system}? (e.g. applications, employees)")
    return system, table


# ──────────────────────────────────────────────────────────────────────────────
# The actual generation flows
# ──────────────────────────────────────────────────────────────────────────────

def generate_full_model(config):
    """Full model: source → staging → intermediate → mart. The main one most people will use."""
    heading("Create a full model")

    dim("I'll generate everything: source definition, staging,")
    dim("intermediate transformations, and the final output table.")
    print()

    name = ask("What should this model be called?\n  (this becomes your folder name, e.g. recruiter_performance)")
    folder = _safe_name(name)

    print()
    sources = ask_sources()

    print()
    description = ask("What should the final output look like? Describe it like\n  you'd explain it to a colleague", multiline=True)

    prompt = f"""\
Generate a COMPLETE dbt model chain based on this analyst's request.

MODEL NAME: {name}
DATA SOURCES:
{sources}
WHAT IT SHOULD DO: {description}

Determine the right structure:
1. Which source tables are needed? Create source YAML for each system.
2. Create a staging model for each source table (clean, rename, cast).
3. If data from multiple tables needs to be joined or transformed, create intermediate models.
4. Create the final mart model(s) — the table(s) the analyst actually wants.

Generate ALL files with proper dbt naming, structure, YAML schemas, and tests.
Use sensible column names based on common data patterns. Note any assumptions.
"""
    result = call_llm(prompt, config)
    write_output(result, folder, config.get("output_folder"))
    return folder


def generate_staging(config):
    """Just a staging model — for when you need to add a new source table."""
    heading("Create a staging model")

    dim("A staging model cleans up a raw source table —")
    dim("renaming columns, fixing types, nothing complex.")
    print()

    system, table = ask_single_source()

    default_name = f"{_safe_name(system)}_{_safe_name(table)}"
    print()
    name = ask(f"Folder name for the output? [{default_name}]", required=False) or default_name
    folder = _safe_name(name)

    print()
    columns = ask("What columns does this table have? (or just describe\n  the table and I'll make reasonable guesses)", multiline=True)

    print()
    notes = ask("Anything special to do? (e.g. rename id to application_id,\n  cast dates, filter out deleted rows)\n  Leave blank if standard cleanup is fine",
                required=False)

    prompt = f"""\
Generate a dbt STAGING model.

SOURCE SYSTEM: {system}
TABLE: {table}
COLUMNS / TABLE DESCRIPTION: {columns}
SPECIAL REQUIREMENTS: {notes if notes else 'Standard cleanup — rename, cast types, clean up'}

Generate:
1. Source YAML (_sources.yml)
2. Staging SQL model (stg_<source>__<entity>.sql)
3. Schema YAML with tests and descriptions
"""
    result = call_llm(prompt, config)
    write_output(result, folder, config.get("output_folder"))
    return folder


def generate_transformation(config):
    """An intermediate model — for when you need to join or reshape data."""
    heading("Create a transformation")

    dim("A transformation joins, aggregates, or reshapes data")
    dim("from your existing staging models into something new.")
    print()

    name = ask("What should this be called? (e.g. applications_with_offers)")
    folder = _safe_name(name)

    print()
    inputs = ask("What existing models or tables does it pull from?", multiline=True)

    print()
    description = ask("What should it do? Describe it plainly", multiline=True)

    prompt = f"""\
Generate a dbt INTERMEDIATE model.

NAME: {name}
INPUT MODELS: {inputs}
WHAT IT SHOULD DO: {description}

Generate:
1. Intermediate SQL model (int_<entity>_<verb>.sql)
2. Schema YAML with tests and column descriptions
"""
    result = call_llm(prompt, config)
    write_output(result, folder, config.get("output_folder"))
    return folder


def generate_final_table(config):
    """A mart model — the final table for dashboards and reporting."""
    heading("Create a final output table")

    dim("This is the table your dashboards and reports will read from.")
    dim("It pulls from your other models and presents the finished data.")
    print()

    name = ask("What should this table be called? (e.g. recruiter_performance_monthly)")
    folder = _safe_name(name)

    print()
    inputs = ask("What existing models does it pull from?", multiline=True)

    print()
    description = ask("What should the final table contain? What columns,\n  what grain (one row per...)?", multiline=True)

    prompt = f"""\
Generate a dbt MART model.

NAME: {name}
INPUT MODELS: {inputs}
WHAT THE FINAL TABLE SHOULD CONTAIN: {description}

Generate:
1. Mart SQL model (dim_ or fct_ prefix as appropriate)
2. Schema YAML with comprehensive column descriptions and tests
"""
    result = call_llm(prompt, config)
    write_output(result, folder, config.get("output_folder"))
    return folder


def _safe_name(name):
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name.lower().strip())
    return safe.strip("_") or "dbt_model"


# ──────────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────────

MENU = [
    "Create a full model  (the whole thing, start to finish)",
    "Add a staging model  (clean up a raw source table)",
    "Add a transformation (join or reshape existing models)",
    "Add a final table    (the output for dashboards/reports)",
    "Set output folder    (change where files are saved)",
    "Change settings      (switch AI provider or API key)",
]

GENERATORS = [generate_full_model, generate_staging, generate_transformation, generate_final_table]


def main():
    print(BANNER)

    try:
        config = get_config()
    except KeyboardInterrupt:
        print(f"\n\n  {C.DIM}Cancelled.{C.RESET}\n")
        sys.exit(0)

    while True:
        try:
            # Show status
            prov = PROVIDERS.get(config["provider"], {})
            out = config.get("output_folder", "(current directory)")
            print()
            dim(f"Using {prov.get('name', '?')} ({config.get('model', '?')})")
            dim(f"Output → {out}")
            print()

            # Main menu
            print(f"  {C.BOLD}What do you want to do?{C.RESET}")
            print()
            for i, item in enumerate(MENU, 1):
                parts = item.split("(", 1)
                label = parts[0].strip()
                hint = f"({parts[1]}" if len(parts) > 1 else ""
                print(f"    {C.CYAN}{i}{C.RESET})  {label}  {C.DIM}{hint}{C.RESET}")
            print()

            raw = input(f"  {C.DIM}Pick a number (or q to quit){C.RESET}: ").strip().lower()

            if raw in ("q", "quit", "exit"):
                print(f"\n  {C.DIM}Bye!{C.RESET}\n")
                break

            try:
                choice = int(raw)
            except ValueError:
                err("Just type a number.")
                continue

            if choice == 5:
                config = setup_output_folder(config)
                continue

            if choice == 6:
                config = setup_api()
                continue

            if choice < 1 or choice > 6:
                err("Pick 1 to 6.")
                continue

            # Run the generator
            GENERATORS[choice - 1](config)

            # After generation — simple prompt
            print()
            if yesno("Create another model?"):
                continue
            else:
                print(f"\n  {C.DIM}Bye!{C.RESET}\n")
                break

        except KeyboardInterrupt:
            print(f"\n\n  {C.DIM}Cancelled.{C.RESET}")
            print()
            if yesno("Back to menu?"):
                continue
            else:
                print(f"\n  {C.DIM}Bye!{C.RESET}\n")
                break
        except Exception as e:
            err(f"Something went wrong: {e}")
            print()
            if yesno("Try again?"):
                continue
            else:
                break


if __name__ == "__main__":
    main()
