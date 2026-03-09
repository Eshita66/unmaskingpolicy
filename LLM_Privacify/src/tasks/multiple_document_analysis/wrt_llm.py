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

# WRT Analysis Summary
prompt = PromptTemplate(
    template="""You are a helpful, honest assistant. 
    
Here is a summary of a privacy policy:\n\n{primary}

Here is a summary of a second privacy policy which is bound by the first:\n\n{secondary}

Analyze the two privacy policy and summarize aspects of the second privacy policy that violate
terms of the first.

Return this analysis.""",
    input_variables=["primary", "secondary"],
    validate_template=False
)

summary_wrt_chain = LLMChain(prompt=prompt,llm=llm)


# Final Scope Aggregator
response_schemas = [
    ResponseSchema(name="violations", description="A JSON list of 20 unique items or less composed of violations where terms of the secondary privacy policy violate terms of the primary policy."),
]

parser = StructuredOutputParser.from_response_schemas(response_schemas)

prompt = PromptTemplate(
    template="""You are a helpful, honest assistant. 
    
Here is a summary of two privacy policies where certain aspects of a secondary privacy policy violates
terms of the primary privacy policy:\n\n{summary}

Please strictly adhere to the following format instructions. {format_instructions}. 

Please return a formatted summary of the violations found between the two privacy policies.""",
    input_variables=["summary"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
    validate_template=False
)

final_violation_chain = LLMChain(prompt=prompt,llm=llm,output_parser=parser)