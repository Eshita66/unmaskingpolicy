from typing import List, Dict, Any
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain.chains import MapReduceDocumentsChain
from langchain.docstore.document import Document as LCDocument
import os
import json


# =====================
# LLM & Splitter
# =====================

llm = ChatOpenAI(
    base_url="http://127.0.0.1:5000/v1",
    api_key="not-needed",
    temperature=0,
    max_tokens=6000
)

text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=3000, chunk_overlap=100
)



# Utility: Save JSON
def save_output_to_file(data: dict, filename: str, folder: str = "llm_outputs"):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"{filename}.json")
    print(f" Saving output to: {filepath}")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("File saved successfully.")
    except Exception as e:
        print(f" Failed to save file: {e}")

# --- Generic categories (MAP) ---
generic_map_template = """Here is an excerpt from a privacy policy:

{docs}

Task: List the DISTINCT CATEGORIES of personal data that may be COLLECTED in THIS excerpt.

DE-DUPE RULE:
- Compare candidates in lowercase and remove duplicates.
- Output each remaining label exactly once, in Title Case.

STRICT FORMAT:
- Output ONLY a NEWLINE-SEPARATED LIST (one item per line).
- Do NOT write any introductions, conclusions, or explanations.
- Do NOT repeat or paraphrase the instructions.
- Do NOT output any text in parentheses.
- If none are present, output exactly: NONE
- Otherwise, NEVER output the word NONE.
"""

generic_map_prompt = PromptTemplate.from_template(generic_map_template)
generic_map_llm = LLMChain(llm=llm, prompt=generic_map_prompt)


data_collected_map_template = """Here is an excerpt from a privacy policy:

{docs}

Task: List the DISTINCT **PERSONAL DATA TYPES** that are COLLECTED in THIS excerpt.

NOTE:
The following examples and definitions are for understanding only.
DO NOT copy, restate, or include any of them in your output.

--- START REFERENCE DEFINITIONS (DO NOT OUTPUT ANY OF THESE) ---
Examples of data fields to INCLUDE:
Email Address, IP Address, Device ID, Username.

Always EXCLUDE:
- Organization names (Inc., LLC, Corp., platform names)
- Roles (Lawyers, Consultants)
- Government or Legal entities (Courts, Law Enforcement)
- Legal or business events (Merger, Divestiture, Sale)
- Generic buckets (Personal Information, Account Information)
- Processes or actions (Verification, Consent)
--- END REFERENCE DEFINITIONS (DO NOT OUTPUT ANY OF THESE) ---

DE-DUPE RULE:
- Compare items in lowercase and remove duplicates.
- Use singular, Title Case (e.g., device ids → Device ID).
- Normalize near-duplicates (e.g., Internet Protocol Address → IP Address).

STRICT OUTPUT FORMAT:
- Output ONLY a NEWLINE-SEPARATED LIST of data types (one per line).
- No numbering, bullets, explanations, or extra text.
- DO NOT list any data type which is not present the policy document
- Do NOT include parentheses or punctuation.
- Do NOT repeat or paraphrase these instructions.
- If no personal data types are present, output exactly: NONE
- Otherwise, NEVER output the word NONE.

FINAL REMINDER:
Your output must contain ONLY the distinct data types found in the given excerpt.
Never include the above examples or any words from the instructions.
"""


data_collected_map_prompt = PromptTemplate.from_template(data_collected_map_template)
collected_map_llm = LLMChain(llm=llm, prompt=data_collected_map_prompt)


data_shared_map_template = """Here is an excerpt from a privacy policy:

{docs}

Task: List the DISTINCT **PERSONAL DATA TYPES** that are SHARED with third parties in THIS excerpt.

CRUCIAL DEFINITIONS:
(Do NOT output anything from this section below — it is only for your understanding.)

--- START DEFINITIONS (DO NOT OUTPUT ANY OF THESE EXAMPLES) ---
Data type examples to INCLUDE:
Email Address, IP Address, Device ID, Username, etc.

Data type examples to EXCLUDE:
Organizations, Roles, Legal Events, Generic Buckets, etc.
--- END DEFINITIONS (DO NOT OUTPUT ANY OF THESE EXAMPLES) ---

DE-DUPE RULE:
Compare in lowercase, remove duplicates, normalize naming.

STRICT FORMAT:
Output ONLY a NEWLINE-SEPARATED LIST of data types (one per line).
If none are present, output exactly: NONE
NEVER output examples or any other text.
DO NOT list any data type which is not present the policy document
"""





data_shared_map_prompt = PromptTemplate.from_template(data_shared_map_template)
shared_map_llm = LLMChain(llm=llm, prompt=data_shared_map_prompt)

# --- Security (MAP) ---
security_map_template = """Here is an excerpt from a privacy policy:

{docs}

Task: List the DISTINCT **SECURITY MEASURES** and **USER RIGHTS** mentioned in this excerpt.

(Do NOT output or repeat anything from the examples below—they are only for context.)

INCLUDE examples: Encryption At Rest, Access Controls, Two-Factor Authentication, Data Retention Limits, Right To Deletion, Opt-Out Of Sale.  
EXCLUDE examples: Email Address, Phone Number, Device ID, Cookies, Posts, Payment Info, Organizations, Verification, Registration.

DE-DUPE RULE:
- Compare in lowercase and remove duplicates.
- Use Title Case and normalize similar phrases (e.g., Data Deletion Right → Right To Deletion).

OUTPUT FORMAT:
- NEWLINE-SEPARATED LIST only.
- No bullets, numbering, or explanations.
- If none are found, output exactly: NONE
- Otherwise, NEVER output the word NONE.
"""


security_map_prompt = PromptTemplate.from_template(security_map_template)
security_map_llm = LLMChain(llm=llm, prompt=security_map_prompt)



reduce_template = """You are given multiple partial lists extracted from a privacy policy.
Only the items inside the INPUT block are source material. Do not copy any words from the instructions below.

INPUT (verbatim; do NOT copy these instructions):
<<<
{docs}
>>>

MERGE & NORMALIZE (apply silently; do NOT output these words):
- Case-insensitive deduplication.
- Singular, Title Case.
- Remove lines equal to NONE (any case).
- Remove lines with parentheses.
- Remove meta/instructional text.
- Split CamelCase (EmailAddress -> Email Address).

FILTER OUT (drop lines matching any of these, case-insensitive):
- Org names or suffixes: inc, llc, ltd, corp, company, studios, nintendo, sony, apple, google, microsoft, valve, epic, shopify, xsolla, zendesk, unity, sentry, kids web services.
- Roles/groups/legal: lawyer, consultant, accountant, advisor, subsidiary, affiliate, regulator, government, law enforcement, court.
- Corporate events: merger, divestiture, restructuring, sale, reorganization, dissolution.
- Generic/process buckets: personal information, account information, verification, registration, consent, backend, legal process, public safety.
- Relationship or flow words: sales (noun), records and copies of correspondence [keep only if collected].
- Anything that is not a personal data field.
OUTPUT:
- Output ONLY the final items as a NEWLINE-SEPARATED LIST (one item per line).
- If no valid items remain, output exactly: NONE
"""


reduce_prompt = PromptTemplate.from_template(reduce_template)
reduce_chain = LLMChain(llm=llm, prompt=reduce_prompt)

# Stuff reducer for all MapReduce chains
combination_documents_chain = StuffDocumentsChain(
    llm_chain=reduce_chain, document_variable_name="docs"
)

data_reduce_chain = combination_documents_chain
security_reduce_chain = combination_documents_chain



# MapReduce chains (STRING in/out for map & reduce)


# Generic categories summarizer
summarizer_chain = MapReduceDocumentsChain(
    llm_chain=generic_map_llm,
    reduce_documents_chain=data_reduce_chain,
    document_variable_name="docs",
    return_intermediate_steps=False,
)

# Collected
collected_map_chain = MapReduceDocumentsChain(
    llm_chain=collected_map_llm,
    reduce_documents_chain=data_reduce_chain,
    document_variable_name="docs",
    return_intermediate_steps=False,
)

# Shared
shared_map_chain = MapReduceDocumentsChain(
    llm_chain=shared_map_llm,
    reduce_documents_chain=data_reduce_chain,
    document_variable_name="docs",
    return_intermediate_steps=False,
)

# Security
security_map_chain = MapReduceDocumentsChain(
    llm_chain=security_map_llm,
    reduce_documents_chain=security_reduce_chain,
    document_variable_name="docs",
    return_intermediate_steps=False,
)


# Final formatters (STRING -> structured JSON)
# Final Scope Aggregator -> {"scopes": [...]}
response_schemas_scopes = [
    ResponseSchema(
        name="scopes",
        description="A JSON list (<=20 items) of the unique categories of information that may be collected."
    ),
]
parser_scopes = StructuredOutputParser.from_response_schemas(response_schemas_scopes)

final_scopes_prompt = PromptTemplate(
    template="""You are a helpful, honest assistant.

Here is a consolidated NEWLINE-SEPARATED **UNIQUE** LIST of collectable data categories:
{summary}

Transform it to the required JSON schema.
{format_instructions}
""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser_scopes.get_format_instructions()},
    validate_template=False
)
final_scope_chain = LLMChain(prompt=final_scopes_prompt, llm=llm, output_parser=parser_scopes)

# Final Shared -> {"shared": [...]}
response_schemas_shared = [
    ResponseSchema(name="shared", description="Types of user data that may be shared with third parties.")
]
parser_shared = StructuredOutputParser.from_response_schemas(response_schemas_shared)

final_shared_prompt = PromptTemplate(
    template="""You are a helpful, honest assistant.

Here is a consolidated NEWLINE-SEPARATED LIST of **UNIQUE** **data types** shared with third parties:
{summary}

Transform it to the required JSON schema.
{format_instructions}
""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser_shared.get_format_instructions()},
    validate_template=False
)
final_shared_chain = LLMChain(prompt=final_shared_prompt, llm=llm, output_parser=parser_shared)

# Final Collected -> {"collected": [...]}
response_schemas_collected = [
    ResponseSchema(name="collected", description="All **UNIQUE** data types collected per the privacy policy.")
]
parser_collected = StructuredOutputParser.from_response_schemas(response_schemas_collected)

final_collected_prompt = PromptTemplate(
    template="""You are a helpful, honest assistant.

Here is a consolidated NEWLINE-SEPARATED **UNIQUE** LIST of data types collected:
{summary}

Transform it to the required JSON schema.
{format_instructions}
""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser_collected.get_format_instructions()},
    validate_template=False
)
final_collected_chain = LLMChain(prompt=final_collected_prompt, llm=llm, output_parser=parser_collected)

# Final Security -> {"security": [...]}
response_schemas_security = [
    ResponseSchema(
        name="security",
        description="Security measures and user rights stated in the policy (array of short phrases)."
    )
]
parser_security = StructuredOutputParser.from_response_schemas(response_schemas_security)

final_security_prompt = PromptTemplate(
    template="""You are a helpful, honest assistant.

Here is a consolidated NEWLINE-SEPARATED LIST of security measures and user rights:
{summary}

Transform it to the required JSON schema.
{format_instructions}
""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser_security.get_format_instructions()},
    validate_template=False
)
final_security_chain = LLMChain(prompt=final_security_prompt, llm=llm, output_parser=parser_security)

# Final Score -> {"score": int}
response_schemas_score = [
    ResponseSchema(
        name="score",
        description="An integer 0..100 indicating privacy friendliness of the policy."
    ),
]
parser_score = StructuredOutputParser.from_response_schemas(response_schemas_score)

final_score_prompt = PromptTemplate(
    template="""You are a helpful, honest assistant.

Given this consolidated NEWLINE-SEPARATED LIST of data categories and/or practices:
{summary}

Return ONLY a JSON object with key "score" (0..100).
{format_instructions}
""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser_score.get_format_instructions()},
    validate_template=False
)
final_score_chain = LLMChain(prompt=final_score_prompt, llm=llm, output_parser=parser_score)

# Final Color -> {"color": "#RRGGBB"}
response_schemas_color = [
    ResponseSchema(name="color", description="A hexadecimal color (branding)."),
]
parser_color = StructuredOutputParser.from_response_schemas(response_schemas_color)

final_color_prompt = PromptTemplate(
    template="""You are a helpful, honest assistant.

Here is a summary or brand context as a NEWLINE-SEPARATED LIST (or brief text):
{summary}

Return ONLY a JSON object with key "color" (hex like "#0A84FF").
{format_instructions}
""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser_color.get_format_instructions()},
    validate_template=False
)
final_color_chain = LLMChain(prompt=final_color_prompt, llm=llm, output_parser=parser_color)



def _to_documents(text: str) -> List[LCDocument]:
    chunks = text_splitter.split_text(text)
    return [LCDocument(page_content=ch) for ch in chunks]

def run_all(policy_text: str) -> Dict[str, Any]:
    docs = _to_documents(policy_text)

    # MapReduce (STRING in/out)
    scopes_text    = summarizer_chain.run(documents=docs)      
    collected_text = collected_map_chain.run(documents=docs)   
    shared_text    = shared_map_chain.run(documents=docs)      
    security_text  = security_map_chain.run(documents=docs)    

    # Final formatters (STRING -> JSON)
    scopes_final    = final_scope_chain.invoke({"summary": scopes_text})
    collected_final = final_collected_chain.invoke({"summary": collected_text})
    shared_final    = final_shared_chain.invoke({"summary": shared_text})
    security_final  = final_security_chain.invoke({"summary": security_text})

   
    score_final     = final_score_chain.invoke({"summary": scopes_text})
    color_final     = final_color_chain.invoke({"summary": scopes_text})

    return {
        "scopes": scopes_final.get("scopes"),
        "collected": collected_final.get("collected"),
        "shared": shared_final.get("shared"),
        "security": security_final.get("security"),
        "score": score_final.get("score"),
        "color": color_final.get("color"),
    }


# =====================
# Exports
# =====================

__all__ = [
    "text_splitter",
    "summarizer_chain",
    "shared_map_chain",
    "collected_map_chain",
    "security_map_chain",
    "final_scope_chain",
    "final_shared_chain",
    "final_collected_chain",
    "final_security_chain",
    "final_score_chain",
    "final_color_chain",
    "run_all",
    "save_output_to_file",
]
