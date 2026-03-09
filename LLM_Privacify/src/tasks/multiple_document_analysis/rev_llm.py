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

# Splitter Tool
text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=3000, chunk_overlap=100
)

# rev Analysis Summary
prompt = PromptTemplate(
    template="""You are a helpful, honest assistant. 
    
Here is a summary of a privacy policy that is current:\n\n{primary}

Here is a summary of an older version of the same privacy policy:\n\n{secondary}

Analyze the two privacy policies and summarize the changes that were made to the older privacy policy in order
to produce the current version.

Return this analysis.""",
    input_variables=["primary", "secondary"],
    validate_template=False
)

summary_rev_chain = LLMChain(prompt=prompt,llm=llm)


# Final Scope Aggregator
response_schemas = [
    ResponseSchema(name="variations", description="A JSON list of 20 unique items or less composed of variations where the current privacy policy was modified from the older privacy policy."),
]

parser = StructuredOutputParser.from_response_schemas(response_schemas)

prompt = PromptTemplate(
    template="""You are a helpful, honest assistant. 
    
Here is a summary of two privacy policies where changes were made to the older privacy policy in order
to produce the current version:\n\n{summary}

Please strictly adhere to the following format instructions. {format_instructions}. 

Please return a formatted summary of the variations found between the two privacy policies.""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
    validate_template=False
)

final_variation_chain = LLMChain(prompt=prompt,llm=llm,output_parser=parser)