"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"


import re
from collections import Counter

_GROUP = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")   # [3]  [1, 2]  [1-3]  [2-3]; not [3](link)
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REF_HEADING = re.compile(r"(?m)^##[ \t]+References[ \t]*$")


def _group_numbers(group):
    numbers = []
    for part in re.split(r"\s*,\s*", group):
        span = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if span:
            a, b = int(span.group(1)), int(span.group(2))
            numbers.extend(range(a, b + 1) if 0 <= b - a <= 200 else [a, b])
        else:
            numbers.append(int(part))
    return numbers


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK)."""
    problems = []

    # 1. sources cannot be empty and must be list of dicts
    if not isinstance(sources, list) or len(sources) == 0:
        return ["no sources in sources.json"]

    # 2. Check each source entry
    seen_urls = set()
    source_by_n = {}
    for entry in sources:
        if not isinstance(entry, dict):
            problems.append(f"invalid source entry: {entry!r} is not a dict")
            continue
        n = entry.get("n")
        if not isinstance(n, int):
            problems.append(f"source {entry!r}: n must be an int")
        elif n in source_by_n:
            problems.append(f"source n={n} appears multiple times in sources.json")
        else:
            source_by_n[n] = entry

        url = entry.get("url")
        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            problems.append(f"source n={n!r}: url must start with http:// or https:// (got {url!r})")
        elif url in seen_urls:
            problems.append(f"source n={n!r}: duplicate url {url}")
        else:
            seen_urls.add(url)

    # 3. Check heading ## References
    matches = list(_REF_HEADING.finditer(report_text))
    if not matches:
        problems.append('missing heading "## References"')
        body = report_text
        ref_text = ""
    else:
        body = report_text[:matches[-1].start()]
        ref_text = report_text[matches[-1].end():]

    # 4. Citations in the body (ignore code blocks and markdown links)
    cited = set()
    segments = _CODE.split(body)
    for i, segment in enumerate(segments):
        if i % 2:  # inside code block / span
            continue
        for match in _GROUP.finditer(segment):
            for num in _group_numbers(match.group(1)):
                cited.add(num)

    for num in sorted(cited):
        if num not in source_by_n:
            problems.append(f"[{num}] cited but missing from sources.json")

    for n in sorted(source_by_n.keys()):
        if n not in cited:
            problems.append(f"source [{n}] never cited")

    # 5 & 6. References section lines
    ref_lines = []
    for line in ref_text.splitlines():
        line_str = line.strip()
        if re.match(r"^\[\d+\]", line_str):
            ref_lines.append(line_str)

    ref_counts = Counter()
    for line in ref_lines:
        m = re.match(r"^\[(\d+)\]", line)
        if m:
            n = int(m.group(1))
            ref_counts[n] += 1
            if n not in source_by_n:
                problems.append(f"reference line [{n}] is not a source in sources.json")
            else:
                expected_url = source_by_n[n]["url"]
                urls = re.findall(r"https?://\S+", line)
                # Clean trailing punctuation from URLs if needed
                cleaned_urls = []
                for u in urls:
                    if u != expected_url and u.rstrip(".,;)") == expected_url:
                        cleaned_urls.append(u.rstrip(".,;)"))
                    else:
                        cleaned_urls.append(u)
                if len(cleaned_urls) != 1:
                    problems.append(f"reference line [{n}] must contain exactly one URL (found {len(cleaned_urls)})")
                elif cleaned_urls[0] != expected_url:
                    problems.append(f"reference line [{n}] URL {cleaned_urls[0]!r} does not match source URL {expected_url!r}")

    for n in sorted(source_by_n.keys()):
        count = ref_counts[n]
        if count == 0:
            problems.append(f"missing reference line for source [{n}]")
        elif count > 1:
            problems.append(f"duplicate reference line for source [{n}] ({count} times)")

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
