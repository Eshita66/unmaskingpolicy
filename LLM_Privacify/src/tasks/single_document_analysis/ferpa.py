import json
import langchain
from sqlmodel import Session, select
from src.infrastructure.dependencies import get_db
from src.models.document import Document
from src.models.analysis import SingleDocumentAnalysis, SingleDocumentAnalysisKinds, SingleDocumentAnalysisStates

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

from src.tasks.single_document_analysis.ferpa_llm import text_splitter, ferpa_summarizer_chain, final_inconsistency_chain

from langchain.docstore.document import Document as LangchainDoc


def reset_and_run_broken_ferpa_analyses():
    db : Session = next(get_db())

    broken_jobs = db.exec(
        select(SingleDocumentAnalysis)
        .where(SingleDocumentAnalysis.kind == SingleDocumentAnalysisKinds.FERPA)
        .where(SingleDocumentAnalysis.state == SingleDocumentAnalysisStates.IN_PROGRESS)
    ).all()

    for job in broken_jobs:
        job.state = SingleDocumentAnalysisStates.PENDING

    db.commit()

    for job in broken_jobs:
        run_ferpa_analysis(job)

def request_ferpa_analysis(document_id):
    db : Session = next(get_db())

    document = db.exec(select(Document).where(Document.id==document_id)).first()

    # Create Pending Analysis
    db_analysis = SingleDocumentAnalysis(
        document_id=document_id,
        kind=SingleDocumentAnalysisKinds.FERPA,
        user_id=document.user_id,
        state=SingleDocumentAnalysisStates.PENDING
    )

    db_analysis = SingleDocumentAnalysis.model_validate(db_analysis)
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    run_ferpa_analysis(db_analysis)

def run_ferpa_analysis(db_analysis : SingleDocumentAnalysis):
    db : Session = next(get_db())

    db_analysis = db.exec(
        select(SingleDocumentAnalysis)
        .where(SingleDocumentAnalysis.id == db_analysis.id)
    ).first()
    
    db.refresh(db_analysis)

    # Move to In Progress
    db_analysis.state=SingleDocumentAnalysisStates.IN_PROGRESS
    db.commit()
    db.refresh(db_analysis)

    # Begin Analysis
    failure_count = 0
    failure = False
    content = ""

    while(failure_count<5):
        failure = False
        try:
            document = db.exec(select(Document).where(Document.id==db_analysis.document_id)).first()

            docs =  [LangchainDoc(page_content=document.contents, metadata={"source": "local"})]

            split_docs = text_splitter.split_documents(docs)

            print("length",len(split_docs))
            result_text = ferpa_summarizer_chain.run(split_docs)
            summary_inconsistencies = final_inconsistency_chain.invoke({"summary": result_text})

            print(summary_inconsistencies)

            value = {
                "summary": result_text,
                "inconsistencies": summary_inconsistencies['text']['inconsistencies'],
            }

            content=json.dumps(value)
        except Exception as e:
            print("Error ", e)
            failure = True
            failure_count+=1

        if failure is False:
            break

    if failure is True:
        db_analysis.state = SingleDocumentAnalysisStates.FAILED
    else:
        db_analysis.state = SingleDocumentAnalysisStates.COMPLETE
        db_analysis.contents = content

    # Move to Complete or Failed
    db.commit()
    db.refresh(db_analysis)
    
    
        

    