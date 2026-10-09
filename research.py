"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys
import time  # noqa: F401
from collections import Counter  # noqa: F401
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent  # noqa: F401
from model import make_model  # noqa: F401
from sandbox import download, open_sandbox, upload  # noqa: F401

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent
from model import make_model
from sandbox import download, open_sandbox, upload

if os.path.exists(r"C:\Users\asus\docker_wsl") and r"C:\Users\asus\docker_wsl" not in os.environ.get("PATH", ""):
    os.environ["PATH"] = r"C:\Users\asus\docker_wsl;" + os.environ.get("PATH", "")

# Ensure WSL VM never idles out and shuts down during research
try:
    import atexit
    import subprocess
    _wsl_keeper = subprocess.Popen(["wsl.exe", "-d", "Ubuntu", "--", "sleep", "infinity"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    atexit.register(lambda: _wsl_keeper.kill())
except Exception:
    pass

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    topic = (topic or "").strip().lower()
    slug = re.sub(r"[^\w]+", "-", topic)
    slug = re.sub(r"-+", "-", slug).strip("-_")
    if len(slug) > 60:
        slug = slug[:60].rstrip("-_")
    return slug or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return (
        f"Conduct a comprehensive deep research survey on the following topic:\n\n"
        f"\"{topic}\"\n\n"
        f"Follow these strict requirements:\n"
        f"1. Use `write_todos` to plan your steps. Break the research into at least 3 sub-questions and delegate them to `researcher` subagents:\n"
        f"   - Sub-question 1: search arXiv using `arxiv_search` (records have source: 'arxiv').\n"
        f"   - Sub-question 2: search Hugging Face daily trending papers using `hf_daily_papers` (records have source: 'hf-daily').\n"
        f"   - Sub-question 3: search Hugging Face papers by topic using `hf_search_papers` (records have source: 'hf-search').\n"
        f"2. Your consolidated sources in {SOURCES_PATH} and final report MUST cite papers from all 3 source families: `arxiv`, `hf-daily`, and `hf-search`.\n"
        f"3. Read the researcher notes and compile all sources into {SOURCES_PATH}.\n"
        f"4. Write the survey report into {REPORT_PATH} following REPORT_TEMPLATE.md (do NOT write ## References yourself). You MUST cite papers from all 3 source families (`arxiv`, `hf-daily`, `hf-search`) in the text of the report.\n"
        f"5. Run `{FINALIZER_PATH}` using `execute` to generate ## References and finalize citations.\n"
        f"6. Run `{VALIDATOR_PATH}` using `execute` until it prints OK.\n"
        f"7. Have `citation-checker` spot-check 2-3 key claims."
    )


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}.

    PSEUDO-CODE: walk the lead's messages; for every message with tool_calls count call["name"] (subagent_calls = the
    count of "task"); add the input/output token counts from each message's usage_metadata when present.
    (Lead messages only: subagent tokens are not included, so this undercounts the real cost.)
    elapsed_s rounded to 0.1.
    """
    tool_counts = Counter()
    input_tokens = 0
    output_tokens = 0

    for msg in messages:
        t_calls = []
        if isinstance(msg, dict):
            t_calls = msg.get("tool_calls") or []
            usage = msg.get("usage_metadata") or msg.get("response_metadata", {}).get("usage") or {}
        else:
            t_calls = getattr(msg, "tool_calls", None) or []
            usage = getattr(msg, "usage_metadata", None) or getattr(msg, "response_metadata", {}).get("usage") or {}

        for call in t_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
            if name:
                tool_counts[name] += 1

        if isinstance(usage, dict):
            input_tokens += usage.get("input_tokens") or usage.get("prompt_tokens") or 0
            output_tokens += usage.get("output_tokens") or usage.get("completion_tokens") or 0

    subagent_calls = tool_counts.get("task", 0)

    return {
        "model": model_name,
        "elapsed_s": round(float(elapsed), 1),
        "subagent_calls": subagent_calls,
        "tool_calls": dict(tool_counts),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
        },
    }


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(topic)

    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)

    if not report_bytes or not report_bytes.strip():
        raise RuntimeError(f"Report file {REPORT_PATH} is missing or empty")
    if not sources_bytes or not sources_bytes.strip():
        raise RuntimeError(f"Sources file {SOURCES_PATH} is missing or empty")

    try:
        sources_data = json.loads(sources_bytes.decode("utf-8"))
        if not isinstance(sources_data, list):
            raise ValueError("sources.json must be a list of objects")
    except Exception as exc:
        raise RuntimeError(f"Failed to parse {SOURCES_PATH} as JSON: {exc}")

    meta = summarize(messages, elapsed, model_name)
    meta["topic"] = topic
    meta["n_sources"] = len(sources_data)
    families = sorted(list({s.get("source") for s in sources_data if isinstance(s, dict) and s.get("source")}))
    meta["source_families"] = families

    report_file = reports_dir / f"{slug}.md"
    sources_file = reports_dir / f"{slug}.sources.json"
    meta_file = reports_dir / f"{slug}.meta.json"

    sources_file.write_text(json.dumps(sources_data, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    report_file.write_text(report_bytes.decode("utf-8"), encoding="utf-8")

    return report_file


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    topic = (topic or "").strip()
    if not topic:
        print("Usage: python research.py \"<topic>\"", file=sys.stderr)
        return 2

    try:
        model = make_model()
    except Exception as exc:
        print(f"FAILED to configure model: {exc}", file=sys.stderr)
        return 1

    model_name = getattr(model, "model_name", None) or getattr(model, "model", None) or os.getenv("LAB_MODEL", "unknown")
    start = time.monotonic()

    try:
        with open_sandbox() as backend:
            backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
            upload(backend, {
                VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
                FINALIZER_PATH: FINALIZER_SOURCE.read_bytes(),
            })
            agent = build_lead_agent(backend, model)
            prompt = build_prompt(topic)
            max_retries = 3
            result = None
            for attempt in range(max_retries):
                try:
                    result = agent.invoke(
                        {"messages": [{"role": "user", "content": prompt}]},
                        config={"recursion_limit": 1000},
                    )
                    break
                except Exception as exc:
                    err_str = str(exc)
                    if ("503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str) and attempt < max_retries - 1:
                        print(f"Temporary LLM error ({exc}). Retrying attempt {attempt + 2}/{max_retries}...", file=sys.stderr)
                        time.sleep(10)
                        continue
                    raise
            messages = result.get("messages", []) if isinstance(result, dict) else []
            elapsed = time.monotonic() - start
            saved_path = save_outputs(backend, topic, messages, elapsed, model_name)
            print(f"SUCCESS: Report saved to {saved_path}")
            return 0
    except RuntimeError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED with unexpected exception: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
