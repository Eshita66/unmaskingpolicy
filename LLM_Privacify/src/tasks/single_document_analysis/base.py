# import json
# import langchain
# from sqlmodel import Session, select
# from src.infrastructure.dependencies import get_db
# from src.models.document import Document
# from src.models.analysis import SingleDocumentAnalysis, SingleDocumentAnalysisKinds, SingleDocumentAnalysisStates

# from typing import List
# from langchain.text_splitter import CharacterTextSplitter
# from langchain_core.prompts import PromptTemplate
# from langchain_openai import ChatOpenAI
# from langchain.output_parsers import ResponseSchema, StructuredOutputParser
# from langchain_community.document_loaders import WebBaseLoader
# from langchain.chains.combine_documents.stuff import StuffDocumentsChain
# from langchain.chains.llm import LLMChain
# from langchain.chains import MapReduceDocumentsChain, ReduceDocumentsChain
# import random


# from src.tasks.single_document_analysis.base_llm import text_splitter, summarizer_chain, shared_map_chain, \
#     collected_map_chain, security_map_chain, final_scope_chain, final_score_chain, final_color_chain, \
#     final_shared_chain, final_collected_chain, final_security_chain, save_output_to_file, final_shared_chain

# from langchain.docstore.document import Document as LangchainDoc


# def reset_and_run_broken_base_analyses():
#     db: Session = next(get_db())

#     broken_jobs = db.exec(
#         select(SingleDocumentAnalysis)
#         .where(SingleDocumentAnalysis.kind == SingleDocumentAnalysisKinds.BASE)
#         .where(SingleDocumentAnalysis.state == SingleDocumentAnalysisStates.IN_PROGRESS)
#     ).all()

#     for job in broken_jobs:
#         job.state = SingleDocumentAnalysisStates.PENDING

#     db.commit()

#     for job in broken_jobs:
#         run_base_analysis(job)


# def request_base_analysis(document_id):
#     db: Session = next(get_db())

#     document = db.exec(select(Document).where(Document.id == document_id)).first()

#     # Create Pending Analysis
#     db_analysis = SingleDocumentAnalysis(
#         document_id=document_id,
#         kind=SingleDocumentAnalysisKinds.BASE,
#         user_id=document.user_id,
#         state=SingleDocumentAnalysisStates.PENDING
#     )

#     db_analysis = SingleDocumentAnalysis.model_validate(db_analysis)
#     db.add(db_analysis)
#     db.commit()
#     db.refresh(db_analysis)

#     run_base_analysis(db_analysis)


# def run_base_analysis(db_analysis: SingleDocumentAnalysis):
#     db: Session = next(get_db())

#     db_analysis = db.exec(
#         select(SingleDocumentAnalysis)
#         .where(SingleDocumentAnalysis.id == db_analysis.id)
#     ).first()

#     db.refresh(db_analysis)

#     # Move to In Progress
#     db_analysis.state = SingleDocumentAnalysisStates.IN_PROGRESS
#     db.commit()
#     db.refresh(db_analysis)

#     # Begin Analysis
#     failure_count = 0
#     failure = False
#     content = ""

#     while (failure_count < 5):
#         failure = False
#         try:
#             document = db.exec(select(Document).where(Document.id == db_analysis.document_id)).first()

#             docs = [LangchainDoc(page_content=document.contents, metadata={"source": "local"})]

#             split_docs = text_splitter.split_documents(docs)

#             print("length", len(split_docs))
#             result_text = summarizer_chain.run(split_docs)
#             shared_text = shared_map_chain.run(split_docs)
#             collected_text = collected_map_chain.run(split_docs)
#             security_text = security_map_chain.run(split_docs)

#             # each scope shared,collected,security
#             summary_scopes = final_scope_chain.invoke({"summary": result_text})
#             shared = final_shared_chain.invoke({"summary": shared_text})
#             collected = final_collected_chain.invoke({"summary": collected_text})
#             security = final_security_chain.invoke({"summary": security_text})

#             print(summary_scopes)
#             print(shared)
#             print(collected)
#             print(security)
            

#             summary_score = final_score_chain.invoke({"summary": result_text})

#             # Generating a random number in between 0 and 2^24
#             color = random.randrange(0, 2 ** 24)

#             # Converting that number from base-10 (decimal) to base-16 (hexadecimal)
#             hex_color = hex(color)

#             std_color = "#" + hex_color[2:]

#             summary_color = {"text": {"color": std_color}}
#             try:
#                 summary_color = final_color_chain.invoke({"summary": result_text})
#             except Exception as e:
#                 pass
#             #"shared": shared['text']['shared'],
#             #"shared": shared['shared_data_mapping'],
#             value = {
#                 "summary": result_text,
#                 "scopes": summary_scopes['text']['scopes'],
#                 "shared": shared['text']['shared'],
#                 "collected": collected['text']['collected'],
#                 "security": security['text']['security'],
#                 "score": summary_score['text']['score'],
#                 "color": summary_color['text']['color']
#             }


            

#             # Optional: run structured output formatting (can replace with final_scope_chain or others)
#             #structured = final_shared_chain.invoke({"summary": shared_text})

#             # Save structured output
#             #save_output_to_file(structured, f"analysis_{db_analysis.id}")

#             save_output_to_file(value, f"analysis_{db_analysis.id}")



#             content = json.dumps(value)
#         except Exception as e:
#             print("Error ", e)
#             failure = True
#             failure_count += 1
#         # except Exception as e:
#         #     print("🚨 Exception occurred in run_base_analysis():", e)
#         #     import traceback
#         #     traceback.print_exc()  # <-- this will print the full error traceback to the console
#         #     failure = True
#         #     failure_count += 1


#         if failure is False:
#             break

#     if failure is True:
#         db_analysis.state = SingleDocumentAnalysisStates.FAILED
#     else:
#         db_analysis.state = SingleDocumentAnalysisStates.COMPLETE
#         db_analysis.contents = content

#     # Move to Complete or Failed
#     db.commit()
#     db.refresh(db_analysis)

import json
import random
import re
import traceback

from typing import List
from sqlmodel import Session, select

from src.infrastructure.dependencies import get_db
from src.models.document import Document
from src.models.analysis import (
    SingleDocumentAnalysis,
    SingleDocumentAnalysisKinds,
    SingleDocumentAnalysisStates,
)

from langchain.docstore.document import Document as LangchainDoc

# Chains & utils from base_llm.py
from src.tasks.single_document_analysis.base_llm import (
    text_splitter,
    summarizer_chain,
    shared_map_chain,
    collected_map_chain,
    security_map_chain,
    final_scope_chain,
    final_score_chain,
    final_color_chain,
    save_output_to_file,
)


def _safe_parse_json_any(s):
    """Best-effort JSON parser that tolerates fenced code blocks and raw strings."""
    if isinstance(s, (dict, list)):
        return s
    if not isinstance(s, str):
        return None
    # 1) direct JSON
    try:
        return json.loads(s)
    except Exception:
        pass
    # 2) fenced ```json ... ```
    m = re.search(r"```json\s*(.*?)```", s, re.IGNORECASE | re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    # 3) any fenced ```
    m2 = re.search(r"```(.*?)```", s, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1).strip())
        except Exception:
            pass
    # 4) best-effort object/array substring
    m3 = re.search(r"(\{.*\}|\[.*\])", s, re.DOTALL)
    if m3:
        try:
            return json.loads(m3.group(1).strip())
        except Exception:
            pass
    return None


def _fallback_list_from_text(s: str):
    """Turn a blob of text into a list of clean items if JSON parsing failed."""
    if not isinstance(s, str) or not s.strip():
        return []
    lines = [ln.strip(" -•\t\r") for ln in s.splitlines()]
    items = []
    for ln in lines:
        if not ln:
            continue
        # strip numeric prefixes like "1." or "3)"
        ln = re.sub(r"^\s*\d+[\.\)]\s*", "", ln)
        # drop super-vague lines
        if len(ln) < 3:
            continue
        # split on commas for lists like "Email, Phone, Address"
        parts = [p.strip() for p in re.split(r",\s*", ln) if p.strip()]
        # heuristic: prefer short phrases (< 6 words) as atomic items
        for p in parts:
            if 1 <= len(p.split()) <= 6:
                items.append(p)
    # dedupe, preserve order
    seen = set()
    deduped = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(it)
    return deduped


def _try_run_chain(chain, docs, label):
    """Run a chain safely, never raise; return string output."""
    try:
        out = chain.run(docs)
        print(f"✅ {label} chain ok ({len(out) if hasattr(out,'__len__') else 'n/a'} chars)")
        return out
    except Exception as e:
        print(f"⚠️ {label} chain failed:", e)
        traceback.print_exc()
        return ""  # safe default


def reset_and_run_broken_base_analyses():
    db: Session = next(get_db())

    broken_jobs = (
        db.exec(
            select(SingleDocumentAnalysis)
            .where(SingleDocumentAnalysis.kind == SingleDocumentAnalysisKinds.BASE)
            .where(SingleDocumentAnalysis.state == SingleDocumentAnalysisStates.IN_PROGRESS)
        ).all()
    )

    for job in broken_jobs:
        job.state = SingleDocumentAnalysisStates.PENDING

    db.commit()

    for job in broken_jobs:
        run_base_analysis(job)


def request_base_analysis(document_id: int):
    db: Session = next(get_db())

    document = db.exec(select(Document).where(Document.id == document_id)).first()

    # Create Pending Analysis
    db_analysis = SingleDocumentAnalysis(
        document_id=document_id,
        kind=SingleDocumentAnalysisKinds.BASE,
        user_id=document.user_id,
        state=SingleDocumentAnalysisStates.PENDING,
    )

    db_analysis = SingleDocumentAnalysis.model_validate(db_analysis)
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    run_base_analysis(db_analysis)


def run_base_analysis(db_analysis: SingleDocumentAnalysis):
    db: Session = next(get_db())

    db_analysis = (
        db.exec(
            select(SingleDocumentAnalysis).where(SingleDocumentAnalysis.id == db_analysis.id)
        ).first()
    )
    db.refresh(db_analysis)

    # Move to In Progress
    db_analysis.state = SingleDocumentAnalysisStates.IN_PROGRESS
    db.commit()
    db.refresh(db_analysis)

    try:
        # Load document
        document = db.exec(select(Document).where(Document.id == db_analysis.document_id)).first()
        docs = [LangchainDoc(page_content=document.contents, metadata={"source": "local"})]
        split_docs = text_splitter.split_documents(docs)
        print("chunks:", len(split_docs))
        if not split_docs:
            print("⚠️ No chunks produced; continuing with empty strings.")

        # ----- run chains individually (never crash) -----
        result_text    = _try_run_chain(summarizer_chain, split_docs, "summary")
        shared_text    = _try_run_chain(shared_map_chain, split_docs, "shared")
        collected_text = _try_run_chain(collected_map_chain, split_docs, "collected")
        security_text  = _try_run_chain(security_map_chain, split_docs, "security")

        # Save raw outputs (always)
        try:
            save_output_to_file({"raw": result_text},    f"analysis_{db_analysis.id}_summary_raw")
            save_output_to_file({"raw": shared_text},    f"analysis_{db_analysis.id}_shared_raw")
            save_output_to_file({"raw": collected_text}, f"analysis_{db_analysis.id}_collected_raw")
            save_output_to_file({"raw": security_text},  f"analysis_{db_analysis.id}_security_raw")
        except Exception as e:
            print("⚠️ Failed saving raw outputs:", e)

        # ----- parse new JSON shapes safely -----
        shared_parsed    = _safe_parse_json_any(shared_text)
        collected_parsed = _safe_parse_json_any(collected_text)

        if isinstance(shared_parsed, dict) and "shared" in shared_parsed:
            shared_out = shared_parsed["shared"]
        elif isinstance(shared_parsed, list):
            shared_out = shared_parsed
        else:
            # fallback: produce [{"data": "...", "shared_with": ["Not specified"]}, ...]
            extracted = _fallback_list_from_text(shared_text)
            shared_out = [{"data": it, "shared_with": ["Not specified"]} for it in extracted]

        if isinstance(collected_parsed, dict) and "collected" in collected_parsed:
            collected_out = collected_parsed["collected"]
        elif isinstance(collected_parsed, list):
            collected_out = collected_parsed
        else:
            collected_out = _fallback_list_from_text(collected_text)

        # ----- optional final chains (never block completion) -----
        scopes = []
        try:
            scopes_resp = final_scope_chain.invoke({"summary": result_text})
            if isinstance(scopes_resp, dict):
                scopes = (scopes_resp.get("text", {}) or {}).get("scopes", []) or []
        except Exception:
            print("⚠️ final_scope_chain failed")
            traceback.print_exc()

        score = None
        try:
            score_resp = final_score_chain.invoke({"summary": result_text})
            if isinstance(score_resp, dict):
                score = (score_resp.get("text", {}) or {}).get("score", None)
        except Exception:
            print("⚠️ final_score_chain failed")
            traceback.print_exc()

        color = "#%06x" % random.randrange(0, 2**24)
        try:
            color_resp = final_color_chain.invoke({"summary": result_text})
            if isinstance(color_resp, dict):
                candidate = (color_resp.get("text", {}) or {}).get("color", color)
                if isinstance(candidate, str) and candidate.startswith("#") and len(candidate) in (4, 7):
                    color = candidate
        except Exception:
            print("⚠️ final_color_chain failed")
            traceback.print_exc()

        # ----- build final bundle + save -----
        value = {
            "summary":   result_text or "",
            "scopes":    scopes or [],
            "shared":    shared_out if shared_out is not None else [],
            "collected": collected_out if collected_out is not None else [],
            "security":  security_text or "",
            "score":     score,
            "color":     color,
        }

        # Save ONE combined file (never crash)
        try:
            save_output_to_file(value, f"analysis_{db_analysis.id}")
        except Exception:
            print("⚠️ save_output_to_file(value) failed")
            traceback.print_exc()

        # Persist to DB (force-serializable)
        db_analysis.state = SingleDocumentAnalysisStates.COMPLETE
        db_analysis.contents = json.dumps(value, ensure_ascii=False, default=str)
        db.commit()
        db.refresh(db_analysis)
        print("✅ Analysis COMPLETE for id:", db_analysis.id)

    except Exception as e:
        print("❌ Fatal in run_base_analysis:", e)
        traceback.print_exc()
        # last resort: save something & mark failed
        try:
            last_value = {
                "summary":   locals().get("result_text", ""),
                "shared":    locals().get("shared_text", ""),
                "collected": locals().get("collected_text", ""),
                "security":  locals().get("security_text", ""),
            }
            save_output_to_file(last_value, f"analysis_{db_analysis.id}_last_resort")
        except Exception:
            pass
        db_analysis.state = SingleDocumentAnalysisStates.FAILED
        db.commit()
        db.refresh(db_analysis)
        print("🚨 Marked FAILED for id:", db_analysis.id)
