"""tools.py - STUDENT IMPLEMENTS.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"

_last_arxiv_time = 0.0


def _redact_key(text: str) -> str:
    key = (os.getenv("EXA_API_KEY") or "").strip()
    if key and key in text:
        text = text.replace(key, "[REDACTED]")
    return text


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


# ---- TODO 1: retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError, wait and call it again."""
    for attempt in range(attempts):
        try:
            return fn()
        except (RetryableError, httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == attempts - 1:
                raise
            retry_after = getattr(exc, "retry_after", None)
            if retry_after is None and isinstance(exc, httpx.HTTPStatusError):
                ra = exc.response.headers.get("Retry-After")
                if ra:
                    try:
                        retry_after = float(ra)
                    except ValueError:
                        pass
            if retry_after is not None:
                delay = float(retry_after)
            else:
                delay = base * (2 ** attempt) + random.uniform(0, 1)
            delay = min(delay, cap)
            time.sleep(delay)


# ---- TODO 2: arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}."""
    global _last_arxiv_time
    try:
        terms = re.findall(r"\w+", query)
        if not terms:
            return "NO RESULTS"
        search_query = " AND ".join(f"all:{t}" for t in terms)
        clamped_results = max(1, min(max_results, 30))
        params = {
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": clamped_results,
        }

        def _call():
            global _last_arxiv_time
            now = time.time()
            elapsed = now - _last_arxiv_time
            if elapsed < 3.0:
                time.sleep(3.0 - elapsed)
            _last_arxiv_time = time.time()
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(ARXIV_URL, params=params)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    ra = resp.headers.get("Retry-After")
                    retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
                    raise RetryableError(f"arXiv HTTP {resp.status_code}", retry_after=retry_after)
                resp.raise_for_status()
                return resp.text

        content = with_retry(_call, attempts=5, base=2.0, cap=60.0)
        root = ET.fromstring(content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        if not entries:
            return "NO RESULTS"

        records = []
        for entry in entries:
            id_elem = entry.find("atom:id", ns)
            if id_elem is None or not id_elem.text:
                continue
            raw_id = id_elem.text.strip()
            if "/abs/" in raw_id:
                raw_id = raw_id.split("/abs/")[-1]
            paper_id = re.sub(r"v\d+$", "", raw_id)
            url = f"https://arxiv.org/abs/{paper_id}"

            pub_elem = entry.find("atom:published", ns)
            published = pub_elem.text.strip()[:10] if pub_elem is not None and pub_elem.text else ""

            title_elem = entry.find("atom:title", ns)
            title = " ".join((title_elem.text or "").split()) if title_elem is not None else ""

            summary_elem = entry.find("atom:summary", ns)
            summary = " ".join((summary_elem.text or "").split())[:600] if summary_elem is not None else ""

            records.append({
                "id": paper_id,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
            })

        if not records:
            return "NO RESULTS"
        return json.dumps(records, ensure_ascii=False)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 3: Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = what is trending in AI research. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    `keyword` filters title/summary; there is no topic search on this endpoint (use hf_search_papers for a topic)."""
    try:
        clamped_limit = max(1, min(limit, 100))
        params = {"limit": clamped_limit}
        if date.strip():
            params["date"] = date.strip()

        def _call():
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(HF_DAILY_URL, params=params)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    ra = resp.headers.get("Retry-After")
                    retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
                    raise RetryableError(f"HF Daily HTTP {resp.status_code}", retry_after=retry_after)
                resp.raise_for_status()
                return resp.json()

        data = with_retry(_call, attempts=5, base=1.0, cap=30.0)
        if not isinstance(data, list) or not data:
            return "NO RESULTS"

        records = []
        kw = keyword.strip().lower()
        for item in data:
            paper = item.get("paper") if isinstance(item, dict) else None
            if not paper or not isinstance(paper, dict) or not paper.get("id"):
                continue
            paper_id = paper["id"]
            title = " ".join((paper.get("title") or item.get("title") or "").split())
            summary = " ".join((paper.get("summary") or item.get("summary") or "").split())[:600]
            published = (paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            upvotes = paper.get("upvotes", 0)
            github = paper.get("githubRepo") or ""
            stars = paper.get("githubStars", 0)

            if kw:
                combined = (title + " " + summary).lower()
                if kw not in combined:
                    continue

            records.append({
                "id": paper_id,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": upvotes,
                "github": github,
                "stars": stars,
            })

        records.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
        if not records:
            return "NO RESULTS"
        return json.dumps(records, ensure_ascii=False)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}."""
    try:
        if not query.strip():
            return "NO RESULTS"
        clamped_limit = max(1, min(limit, 50))
        params = {"q": query.strip(), "limit": clamped_limit}

        def _call():
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(HF_SEARCH_URL, params=params)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    ra = resp.headers.get("Retry-After")
                    retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
                    raise RetryableError(f"HF Search HTTP {resp.status_code}", retry_after=retry_after)
                resp.raise_for_status()
                return resp.json()

        data = with_retry(_call, attempts=5, base=1.0, cap=30.0)
        if not isinstance(data, list) or not data:
            return "NO RESULTS"

        records = []
        for item in data:
            paper = item.get("paper") if isinstance(item, dict) and isinstance(item.get("paper"), dict) else item
            if not isinstance(paper, dict) or not paper.get("id"):
                continue
            paper_id = paper["id"]
            title = " ".join((paper.get("title") or item.get("title") or "").split())
            raw_summary = paper.get("ai_summary") or item.get("ai_summary") or paper.get("summary") or item.get("summary") or ""
            summary = " ".join(raw_summary.split())[:600]
            published = (paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            upvotes = paper.get("upvotes", 0)
            github = paper.get("githubRepo") or ""
            stars = paper.get("githubStars", 0)

            records.append({
                "id": paper_id,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": upvotes,
                "github": github,
                "stars": stars,
            })

        if not records:
            return "NO RESULTS"
        return json.dumps(records, ensure_ascii=False)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 4: web search / fetch through the Exa MCP endpoint ----
def _call_exa_mcp(tool_name: str, arguments: dict):
    exa_key = (os.getenv("EXA_API_KEY") or "").strip()
    url = f"{EXA_URL}?exaApiKey={exa_key}" if exa_key else EXA_URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if exa_key:
        headers["Authorization"] = f"Bearer {exa_key}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    def _call():
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code in {429, 500, 502, 503, 504}:
                ra = resp.headers.get("Retry-After")
                retry_after = float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
                raise RetryableError(f"Exa HTTP {resp.status_code}", retry_after=retry_after)
            resp.raise_for_status()

            body = resp.text
            parsed_data = None
            for line in body.splitlines():
                if line.startswith("data:"):
                    line_data = line[len("data:"):].strip()
                    if line_data:
                        try:
                            parsed_data = json.loads(line_data)
                            break
                        except json.JSONDecodeError:
                            continue
            if parsed_data is None:
                try:
                    parsed_data = json.loads(body)
                except Exception:
                    raise Exception(f"Unparseable Exa response: {body[:300]}")

            if "error" in parsed_data:
                err_msg = str(parsed_data["error"])
                if "rate limit" in err_msg.lower() or "free mcp" in err_msg.lower():
                    raise RetryableError("Exa free tier rate limit", retry_after=20.0)
                raise Exception(f"Exa RPC error: {err_msg}")

            result = parsed_data.get("result", {})
            meta = result.get("_meta", {})
            if any("rate" in str(k).lower() or "limit" in str(k).lower() for k in meta.keys()) or \
               any("rate" in str(v).lower() or "limit" in str(v).lower() for v in meta.values()):
                raise RetryableError("Exa rate limit flag in _meta", retry_after=20.0)

            content = result.get("content", [])
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_val = item.get("text", "")
                    if "rate limit" in text_val.lower() and "exa" in text_val.lower():
                        raise RetryableError("Exa rate limit message in text", retry_after=20.0)
                    texts.append(text_val)

            return "\n\n".join(texts).strip()

    return with_retry(_call, attempts=3, base=1.0, cap=10.0)


@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    try:
        if not query.strip():
            return "NO RESULTS"
        obj = objective.strip() or f"Find information and survey articles about {query.strip()}"
        num = max(1, min(num_results, 10))
        text = _call_exa_mcp("web_search_exa", {"query": query.strip(), "objective": obj, "numResults": num})
        if not text:
            return "NO RESULTS"
        return text
    except Exception as exc:
        return _redact_key(f"ERROR: {type(exc).__name__}: {exc}")


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    try:
        if not url.strip():
            return "NO RESULTS"
        text = _call_exa_mcp("web_fetch_exa", {"urls": [url.strip()]})
        if not text:
            return "NO RESULTS"
        return text[:12000]
    except Exception as exc:
        return _redact_key(f"ERROR: {type(exc).__name__}: {exc}")


# ---- TODO 5: registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        try:
            print(f"== {name}\n{fn.invoke(args)[:400]}\n")
        except NotImplementedError as exc:
            print(f"== {name}: not implemented yet ({exc})\n")
