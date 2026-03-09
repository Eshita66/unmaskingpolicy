from typing import List
from langchain.text_splitter import CharacterTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_community.document_loaders import WebBaseLoader
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain.chains.llm import LLMChain
from langchain.chains import MapReduceDocumentsChain, ReduceDocumentsChain
import re

# Define LLM
llm = ChatOpenAI(base_url="http://127.0.0.1:5000/v1", api_key="not-needed", temperature=0, max_tokens=4000)

# Map
map_template = """Here is an excerpt from a given privacy policy: \n\n{docs}
Based on this list, please identify any aspects that are not consistent
with GDPR regulations and restrictions.
"""
map_prompt = PromptTemplate.from_template(map_template)
map_chain = LLMChain(llm=llm, prompt=map_prompt)

# Reduce
reduce_template = """The following is a list of inconsistencies between a privacy policy and what is restricted by the GDPR: \n\n{docs}
Take these inconsistencies it into a final, consolidated summary of these inconsistencies."""
reduce_prompt = PromptTemplate.from_template(reduce_template)

reduce_chain = LLMChain(llm=llm, prompt=reduce_prompt)

# Combination Chain
combination_documents_chain = StuffDocumentsChain(
    llm_chain=reduce_chain, document_variable_name="docs"
)

# Combines and iteratively reduces the mapped documents
reduce_documents_chain = ReduceDocumentsChain(
    combine_documents_chain=combination_documents_chain,
    collapse_documents_chain=combination_documents_chain,
    token_max=4000,
)

# Result Chain
gdpr_summarizer_chain = MapReduceDocumentsChain(
    # Map chain
    llm_chain=map_chain,
    reduce_documents_chain=reduce_documents_chain,
    document_variable_name="docs",
    return_intermediate_steps=False,
)

# Splitter Tool

text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=3000, chunk_overlap=100
)


# Final Scope Aggregator
response_schemas = [
    ResponseSchema(name="inconsistencies", description="A JSON list of 20 unique items or less composed of inconsistencies between the privacy policy and GDPR regulations."),
]

parser = StructuredOutputParser.from_response_schemas(response_schemas)

prompt = PromptTemplate(
    template="""You are a helpful, honest assistant. 
    
Here is a summary of GDPR inconsistencies found in a privacy policy:\n\n{summary}\n\nPlease strictly adhere to the following format instructions. {format_instructions}. 

Please return a formatted summary of the GDPR inconsistencies found in the privacy policy.""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
    validate_template=False
)

final_inconsistency_chain = LLMChain(prompt=prompt,llm=llm,output_parser=parser)