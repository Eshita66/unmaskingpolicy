import os
import re
import json
import traceback
from typing import List, Tuple
import time
import random

# Ensure a consistent UA for sites that gate by client
os.environ.setdefault(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

from langchain.docstore.document import Document as LangchainDoc
from langchain_community.document_loaders import WebBaseLoader

# Reuse chains and saver from base_llm.py
from src.tasks.single_document_analysis.base_llm import (
    text_splitter,           
    summarizer_chain,         # map-reduce chain
    shared_map_chain,         # map-reduce chain
    collected_map_chain,      # map-reduce chain
    security_map_chain,       # map-reduce chain
    save_output_to_file,      
)

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin


try:
    from bs4 import BeautifulSoup
    HAVE_BS = True
except Exception:
    HAVE_BS = False


try:
    from langchain_community.document_loaders import PlaywrightURLLoader
    HAVE_PW = True
except Exception:
    HAVE_PW = False


# ------------------------- utils -------------------------

def _sleep_with_jitter(base_seconds: float):
    """Sleep for base_seconds ±20% jitter."""
    if base_seconds <= 0:
        return
    jitter = base_seconds * 0.2
    delay = max(0.0, base_seconds + random.uniform(-jitter, jitter))
    print(f" Sleeping for {delay:.2f}s before next policy…")
    time.sleep(delay)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:100] or "app"


def to_filename(name: str) -> str:
    # keep spaces & case; only replace Windows-illegal chars \ / : * ? " < > |
    out = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    # Windows: filename cannot end with dot or space
    out = out.rstrip(". ")
    return out or "app"


def _safe_parse_json_any(s):
    if isinstance(s, (dict, list)):
        return s
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"```json\s*(.*?)```", s, re.IGNORECASE | re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    m2 = re.search(r"```(.*?)```", s, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1).strip())
        except Exception:
            pass
    m3 = re.search(r"(\{.*\}|\[.*\])", s, re.DOTALL)
    if m3:
        try:
            return json.loads(m3.group(1).strip())
        except Exception:
            pass
    return None


def _fallback_list_from_text(s: str):
    if not isinstance(s, str) or not s.strip():
        return []
    lines = [ln.strip(" -•\t\r") for ln in s.splitlines()]
    items = []
    for ln in lines:
        if not ln:
            continue
        ln = re.sub(r"^\s*\d+[\.\)]\s*", "", ln)  # strip "1." / "3)"
        if len(ln) < 3:
            continue
        parts = [p.strip() for p in re.split(r",\s*", ln) if p.strip()]
        for p in parts:
            if 1 <= len(p.split()) <= 6:
                items.append(p)
    seen = set()
    deduped = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(it)
    return deduped


# Light vocabulary to mine terms if the model won’t JSON
_DATA_TERMS = [
    "Name", "Email address", "Phone number", "Address",
    "User ID", "Username", "Password",
    "IP address", "Device ID", "Advertising ID", "Android ID",
    "Cookies", "Cookie identifiers",
    "Precise location", "Approximate location", "Location",
    "Browsing history", "Search history",
    "Purchase history", "Payment information", "Credit card",
    "Contacts", "Contact list",
    "Photos", "Videos", "Images", "Media",
    "Audio recordings", "Microphone audio",
    "Messages", "In-app messages", "Emails",
    "User-generated content",
    "App interactions", "App activity",
    "Crash logs", "Diagnostics", "Performance data",
    "Device information", "Operating system", "Browser type",
    "Demographics", "Age", "Gender",
    "Health information", "Fitness data",
]


def _extract_terms_from_text(text: str):
    if not isinstance(text, str) or not text.strip():
        return []
    found, tlow = [], text.lower()
    for term in _DATA_TERMS:
        if term.lower() in tlow:
            found.append(term)
    seen, out = set(), []
    for x in found:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


# --- parsers / normalizers ---

def _normalize_shared_to_list(shared_any) -> list[str]:
    """Accepts list[str] OR list[dict{data,shared_with}] OR dict with 'shared' key.
    Returns a flat, deduped list[str] of data types.
    """
    if isinstance(shared_any, dict) and "shared" in shared_any:
        shared_any = shared_any["shared"]

    items = []
    if isinstance(shared_any, list):
        for it in shared_any:
            if isinstance(it, str):
                s = it.strip()
                if s:
                    items.append(s)
            elif isinstance(it, dict):
                val = str(it.get("data", "")).strip()
                if val:
                    items.append(val)

    seen, out = set(), []
    for s in items:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _extract_marked_json(s: str):
    """If your prompts return JSON between <<<JSON>>> ... <<<END>>> markers, parse it."""
    if not isinstance(s, str):
        return None
    m = re.search(r'<<<JSON>>>(.*?)<<<END>>>', s, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    block = m.group(1).strip()
    try:
        return json.loads(block)
    except Exception:
        return None


def _force_english_url(url: str) -> str:
    """Add ?lang=en if no explicit language param is present."""
    try:
        p = urlparse(url)
        q = dict(parse_qsl(p.query, keep_blank_values=True))
    except Exception:
        return url
    existing_lang_keys = {"lang", "locale", "hl", "l"}
    if any(k in q for k in existing_lang_keys):
        return url
    q["lang"] = "en"
    new_query = urlencode(q, doseq=True)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def _is_english(text: str) -> bool:
    """Prefer langdetect; otherwise simple heuristic."""
    if not text or len(text) < 200:
        return True
    sample = text[:2000]
    try:
        from langdetect import detect
        return detect(sample) == "en"
    except Exception:
        pass
    ascii_letters = len(re.findall(r"[A-Za-z]", sample))
    total_chars = max(1, len(sample))
    ascii_ratio = ascii_letters / total_chars
    tokens = set(w.lower() for w in re.findall(r"[A-Za-z]+", sample))
    hits = tokens & {"the", "and", "for", "with", "you", "your", "data", "policy", "privacy", "we"}
    return ascii_ratio > 0.25 and len(hits) >= 2


def _find_english_alt_url(html: str, base_url: str) -> str | None:
    """Discover explicit English alternates (hreflang=en or obvious links)."""
    if not HAVE_BS or not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None

    # <link rel="alternate" hreflang="en">
    for link in soup.find_all("link"):
        rel = (link.get("rel") or [])
        hreflang = (link.get("hreflang") or "").lower().strip()
        href = link.get("href")
        if href and rel and any("alternate" == r.lower() for r in rel):
            if hreflang in {"en", "en-us", "en-gb"}:
                return urljoin(base_url, href)

    # Anchor patterns
    candidates = []
    for a in soup.find_all("a"):
        text = (a.get_text() or "").strip().lower()
        href = a.get("href")
        if not href:
            continue
        if "english" in text:
            candidates.append(href)
        h = href.lower()
        if any(tok in h for tok in ["/en", "lang=en", "locale=en", "hl=en"]):
            candidates.append(href)

    if not candidates:
        return None

    ranked = sorted(
        {urljoin(base_url, c) for c in candidates},
        key=lambda u: (("lang=en" not in u.lower()), ("/en" not in u.lower()))
    )
    return ranked[0] if ranked else None


def _ascii_ratio(s: str) -> float:
    if not s:
        return 0.0
    letters = sum(ch.isalpha() for ch in s)
    ascii_letters = sum(('A' <= ch <= 'Z') or ('a' <= ch <= 'z') for ch in s)
    return ascii_letters / max(1, letters)


def _looks_english_text(s: str) -> bool:
    try:
        from langdetect import detect
        return bool(s) and detect(s[:2000]) == "en"
    except Exception:
        pass
    if not s:
        return False
    sample = s[:4000]
    if _ascii_ratio(sample) < 0.5:
        return False
    toks = set(w.lower() for w in re.findall(r"[A-Za-z]+", sample))
    hits = toks & {"privacy", "policy", "data", "information", "we", "you", "your", "use", "collect", "share"}
    return len(hits) >= 2


def _extract_english_text_from_html(html: str) -> str:
    """Strip non-English DOM parts to keep English content for mixed-locale pages."""
    if not HAVE_BS or not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    # Remove subtrees with lang != en
    for node in soup.find_all(True, attrs={"lang": True}):
        lang = (node.get("lang") or "").strip().lower()
        if lang and not lang.startswith("en"):
            node.decompose()

    # Heuristic pruning
    block_tags = {"section", "article", "div", "p", "li", "dd", "dt", "span"}
    for node in list(soup.find_all(block_tags)):
        keep = False
        cur = node
        while cur:
            lang = (cur.attrs.get("lang") or "").strip().lower() if hasattr(cur, "attrs") else ""
            if lang:
                if lang.startswith("en"):
                    keep = True
                break
            cur = cur.parent
        if keep:
            continue
        txt = node.get_text(" ", strip=True)
        if txt and not _looks_english_text(txt):
            node.decompose()

    text = soup.get_text("\n", strip=True)
    text = "\n".join(line for line in (ln.strip() for ln in text.splitlines()) if line)
    return text


#normalize any chain output to plain text
def _coerce_to_text(x) -> str:
    """Best-effort: turn LangChain outputs (dicts, messages, lists) into a string."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x

    # LangChain BaseMessage (AIMessage, HumanMessage, etc.)
    try:
        from langchain.schema import BaseMessage
        if isinstance(x, BaseMessage):
            return x.content or ""
    except Exception:
        pass

    # Common dict shapes
    if isinstance(x, dict):
        for k in ("output_text", "text", "result", "content", "response", "output"):
            if k in x and isinstance(x[k], (str, list, dict)):
                return _coerce_to_text(x[k])
        # last resort: join all stringy values
        parts = []
        for v in x.values():
            s = _coerce_to_text(v)
            if s:
                parts.append(s)
        return "\n".join(parts)

    # Lists / tuples
    if isinstance(x, (list, tuple)):
        parts = [_coerce_to_text(v) for v in x]
        return "\n".join([p for p in parts if p])

    # Objects with .content or .text
    for attr in ("content", "text"):
        if hasattr(x, attr):
            try:
                s = getattr(x, attr)
                return s if isinstance(s, str) else _coerce_to_text(s)
            except Exception:
                pass

    try:
        return str(x)
    except Exception:
        return ""


# ------------------------- fetcher (EN-only) -------------------------

def _load_policy_text(url: str, app_label: str = "app") -> str:
    """
    Fetch the policy content, ensuring the final text is English-only (else return "").
    Adds verbose source notes so you can see where content came from.
    """
    import re as _re
    from urllib.parse import urlparse as _urlparse, urlunparse as _urlunparse, parse_qsl as _parse_qsl, urlencode as _urlencode

    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    headers = {
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def _note(msg: str):
        print(f"  [fetch] {msg}")

    def _local_is_english(text: str) -> bool:
        if not text:
            return False
        sample = text[:4000]
        try:
            from langdetect import detect
            return detect(sample) == "en"
        except Exception:
            pass
        ascii_letters = len(_re.findall(r"[A-Za-z]", sample))
        total = max(1, len(sample))
        if ascii_letters / total < 0.25:
            return False
        toks = set(w.lower() for w in _re.findall(r"[A-Za-z]+", sample))
        hits = toks & {"privacy", "policy", "data", "information", "we", "you", "your",
                       "collect", "use", "share", "cookies", "purpose", "rights"}
        return len(hits) >= 2

    def _force_english_url_local(u: str) -> str:
        try:
            p = _urlparse(u)
            q = dict(_parse_qsl(p.query, keep_blank_values=True))
            if any(k in q for k in ("lang", "locale", "hl", "l")):
                return u
            q["lang"] = "en"
            return _urlunparse((p.scheme, p.netloc, p.path, p.params, _urlencode(q, doseq=True), p.fragment))
        except Exception:
            return u

    def _try_wb(u: str) -> str:
        try:
            wb = WebBaseLoader(u, requests_kwargs={"headers": headers, "timeout": (10, 45)})
            docs = wb.load() or []
            return "\n\n".join(d.page_content for d in docs if getattr(d, "page_content", None))
        except Exception:
            return ""

    def _try_pw(u: str) -> str:
        if not HAVE_PW:
            return ""
        try:
            pw = PlaywrightURLLoader(
                urls=[u],
                remove_selectors=["nav", "footer", "script", "style"],
                wait_until="networkidle",
                timeout=45000,
            )
            docs = pw.load() or []
            return "\n\n".join(d.page_content for d in docs if getattr(d, "page_content", None))
        except Exception:
            return ""

    def _try_mirror(u: str) -> str:
        try:
            stripped = u.replace("https://", "").replace("http://", "")
            mirror = f"https://r.jina.ai/http://{stripped}"
            wb = WebBaseLoader(mirror, requests_kwargs={"headers": headers, "timeout": (10, 45)})
            docs = wb.load() or []
            return "\n\n".join(d.page_content for d in docs if getattr(d, "page_content", None))
        except Exception:
            return ""

    def _fetch_html(u: str) -> str:
        try:
            import requests
            r = requests.get(u, headers=headers, timeout=(10, 45))
            return r.text if r and r.text else ""
        except Exception:
            return ""

    # Force-English URL
    try:
        url_en = _force_english_url(url)
    except Exception:
        url_en = _force_english_url_local(url)

    def _english(text: str) -> bool:
        try:
            return _is_english(text)
        except Exception:
            return _local_is_english(text)

    text = _try_wb(url_en)
    if _english(text):
        _note(f"WB forced (?lang=en), {len(text)} chars")
    else:
        t = _try_wb(url)
        if _english(t):
            _note(f"WB original, {len(t)} chars")
            text = t

    if not _english(text):
        t = _try_pw(url_en)
        if _english(t):
            _note(f"PW forced (?lang=en), {len(t)} chars")
            text = t
        else:
            t = _try_pw(url)
            if _english(t):
                _note(f"PW original, {len(t)} chars")
                text = t

    if not _english(text):
        html0 = _fetch_html(url) or _fetch_html(url_en)
        alt = _find_english_alt_url(html0, url) if html0 else None
        if alt:
            t = _try_wb(alt)
            if _english(t):
                _note(f"ALT WB ({alt}), {len(t)} chars")
                text = t
            else:
                t = _try_pw(alt)
                if _english(t):
                    _note(f"ALT PW ({alt}), {len(t)} chars")
                    text = t
        else:
            alt = None

    if not _english(text):
        t = _try_mirror(url_en)
        if _english(t):
            _note(f"MIRROR forced, {len(t)} chars")
            text = t
    if not _english(text):
        t = _try_mirror(url)
        if _english(t):
            _note(f"MIRROR original, {len(t)} chars")
            text = t
    if not _english(text) and 'alt' in locals() and alt:
        t = _try_mirror(alt)
        if _english(t):
            _note(f"MIRROR alt, {len(t)} chars")
            text = t

    # Mixed-locale pages (e.g., webtoons.com): HTML clean fallback.
    if not _english(text) or ("webtoons.com" in url.lower()):
        html = _fetch_html(url) or _fetch_html(url_en)
        if not html and 'alt' in locals() and alt:
            html = _fetch_html(alt)
        if html:
            en_text = _extract_english_text_from_html(html)
            if _english(en_text) and len(en_text) > 600:
                _note(f"HTML clean, {len(en_text)} chars")
                return en_text

    if _english(text):
        _note(f"RETURN English text, {len(text)} chars")
        return text
    _note("RETURN empty (non-English or unavailable)")
    return ""


# ------------------------- analysis -------------------------
# --- SAFE CHUNK GUARD -------------------------------------------------

def _approx_tokens(s: str) -> int:
    """Rough token count. Uses tiktoken if available; else ~4 chars/token."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(s))
    except Exception:
        return max(1, len(s) // 4)

def _retokenize_if_needed(chunks, max_tokens_per_chunk: int = 1500, overlap_tokens: int = 200):
    """
    Keep your original chunking 'style' from `text_splitter`, but if any chunk
    is too large for your ~8.5k context (prompt + chunk + instructions),
    re-split just that chunk with a token-aware splitter.
    """
    fixed = []
    too_big = 0
    try:
        from langchain_text_splitters import TokenTextSplitter
        re_splitter = TokenTextSplitter(
            encoding_name="cl100k_base",
            chunk_size=max_tokens_per_chunk,
            chunk_overlap=overlap_tokens
        )
        token_based = True
    except Exception:
        # fallback to character-based; choose sizes that ~map to 1500 tokens
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        re_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_tokens_per_chunk * 4,  # ~ char len
            chunk_overlap=overlap_tokens * 4,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        token_based = False

    for d in chunks:
        txt = getattr(d, "page_content", "") or ""
        if _approx_tokens(txt) > max_tokens_per_chunk:
            too_big += 1
            fixed.extend(re_splitter.split_documents([d]))
        else:
            fixed.append(d)

    if too_big:
        mode = "TokenTextSplitter" if token_based else "CharacterTextSplitter"
        print(f"  [chunk-guard] re-split {too_big} oversized chunk(s) using {mode} "
              f"-> total chunks now: {len(fixed)}")
    return fixed

def _dedupe_in_order(seq):
    """De-duplicate while preserving the original order."""
    seen = set()
    out = []
    for x in seq:
        k = str(x).strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(str(x).strip())
    return out

def _rank_by_first_occurrence(items, ref_text: str):
    """
    Stable-rank items by their first occurrence in ref_text (policy body).
    Items not found keep their relative order and are placed after those found.
    """
    ref = (ref_text or "").lower()
    pos = {it: (ref.find(it.lower()) if it else -1) for it in items}
    # keep original order for ties / not found
    return sorted(items, key=lambda it: (pos[it] if pos[it] >= 0 else 10**9))



def _analyze_policy_text(body_text: str) -> dict:
    """Run your provided chains, coerce outputs to strings, parse robustly."""
    docs = [LangchainDoc(page_content=body_text, metadata={"source": "local"})]
    chunks = text_splitter.split_documents(docs)
    print(f"splitter: {text_splitter.__class__.__name__} -> chunks: {len(chunks)}")
        # ensure no single chunk can overflow the model context
    chunks = _retokenize_if_needed(chunks, max_tokens_per_chunk=1500, overlap_tokens=200)

    def run_chain(chain, name):
        try:
            raw = chain.invoke(chunks)  # safer than .run()
            out = _coerce_to_text(raw).strip()
            preview = (out[:120] + "…") if len(out) > 120 else out
            print(f"  {name} ok, len={len(out) if out else '0'}, preview={preview!r}")
            return out
        except Exception as e:
            print(f"  {name} failed: {e}")
            traceback.print_exc()
            return ""

    summary   = run_chain(summarizer_chain,   "summary")
    shared_tx = run_chain(shared_map_chain,   "shared")
    coll_tx   = run_chain(collected_map_chain,"collected")
    secu_tx   = run_chain(security_map_chain, "security")

        # ---- parse with tolerant markers/JSON
    shared_marked = _extract_marked_json(shared_tx)
    coll_marked   = _extract_marked_json(coll_tx)

    def _parse_any_json(s):
        v = _safe_parse_json_any(s)
        return v if v is not None else []

    # ------------------- COLLECTED -------------------
    collected_out = []

    # 1) Marker JSON wins, but only if non-empty
    if isinstance(coll_marked, dict) and isinstance(coll_marked.get("collected"), list) and len(coll_marked["collected"]) > 0:
        collected_out = [str(x).strip() for x in coll_marked["collected"] if str(x).strip()]
    else:
        v = _parse_any_json(coll_tx)

        # accept dict only if it has a non-empty list under common keys
        if isinstance(v, dict):
            for key in ("collected", "data_collected", "dataCollected", "items"):
                if isinstance(v.get(key), list) and len(v[key]) > 0:
                    collected_out = [str(x).strip() for x in v[key] if str(x).strip()]
                    break

        # accept list only if non-empty
        if not collected_out and isinstance(v, list) and len(v) > 0:
            collected_out = [str(x).strip() for x in v if str(x).strip()]

        # fallback to mining when JSON is absent or empty
        if not collected_out:
            mined = set()

            # 1) Try to mine bullet/line items from the collected chain text itself
            mined |= set(_fallback_list_from_text(coll_tx))

            # 2) Add signal terms from the raw policy body (helps when model returns prose)
            mined |= set(_extract_terms_from_text(body_text))

            # 3) Optionally include summary terms too
            if summary:
                mined |= set(_extract_terms_from_text(summary))

            #collected_out = sorted({t.strip() for t in mined if t and t.strip()}) ###Sorted order when storing
            collected_candidates = [t.strip() for t in mined if t and t.strip()]
            collected_out = _dedupe_in_order(collected_candidates)
            collected_out = _rank_by_first_occurrence(collected_out, body_text)

    # shared
    if shared_marked is not None:
        shared_out = _normalize_shared_to_list(shared_marked)
    else:
        v = _safe_parse_json_any(shared_tx)
        shared_out = _normalize_shared_to_list(v) if v is not None else []
        if not shared_out:
            #shared_out = sorted({t for t in _fallback_list_from_text(shared_tx) if t})
            _shared_candidates = [t for t in _fallback_list_from_text(shared_tx) if t]
            shared_out = _dedupe_in_order(_shared_candidates)
            shared_out = _rank_by_first_occurrence(shared_out, body_text)

    print(f"  parsed -> shared:{len(shared_out)} collected:{len(collected_out)}")
    return {"shared": shared_out, "collected": collected_out}


def _read_link_pairs(path: str) -> List[Tuple[str, str]]:
    """Read file with alternating lines: AppLabel, URL."""
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    pairs = []
    for i in range(0, len(lines), 2):
        if i + 1 >= len(lines):
            break
        app, url = lines[i], lines[i + 1]
        if "no policy" in url.lower():  # skip
            continue
        pairs.append((app, url))
    return pairs


# ------------------------- main -------------------------

def main():
    
    INPUT_FILE = "data/input/privacy_policy_links.txt"
    SLEEP_SECONDS = 8.0  # fixed sleep time between policies (in seconds)

    os.makedirs("llm_outputs", exist_ok=True)

    pairs = _read_link_pairs(INPUT_FILE)
    print(f"Found {len(pairs)} app/url pairs.")

    for idx, (app_label, url) in enumerate(pairs, start=1):
        try:
            print(f"\n[{idx}/{len(pairs)}] Processing: {app_label} | {url}")
            body = _load_policy_text(url, app_label)
            if not body:
                print("  [analyze] skipped: empty or non-English body")
                _sleep_with_jitter(SLEEP_SECONDS)
                continue

            print(f"  [analyze] body length: {len(body)} chars")
            result = _analyze_policy_text(body)
            # Save ONE combined JSON per app
            fname = f"{to_filename(app_label)}.json"
            path = os.path.join("llm_outputs", fname)
            base, ext = os.path.splitext(path)
            k = 1
            while os.path.exists(path):
                path = f"{base}_{k}{ext}"
                k += 1
            path = os.path.join("llm_outputs", fname)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f" Saved: {path}")

        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting gracefully.")
            return
        except Exception as e:
            print(f" Failed on {app_label}: {e}")
            traceback.print_exc()
        finally:
            _sleep_with_jitter(SLEEP_SECONDS)


if __name__ == "__main__":
    main()
