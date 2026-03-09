from sqlmodel import Session, select
from src.infrastructure.dependencies import get_db
from src.models.analysis import MultipleDocumentAnalysis, MultipleDocumentAnalysisStates, SingleDocumentAnalysis, SingleDocumentAnalysisKinds
import json

from src.tasks.multiple_document_analysis.rev_llm import text_splitter, summary_rev_chain, final_variation_chain

from langchain.docstore.document import Document as LangchainDoc


def run_multiple_document_rev_analysis(db_analysis : MultipleDocumentAnalysis):
    db : Session = next(get_db())

    db_analysis = db.exec(
        select(MultipleDocumentAnalysis)
        .where(MultipleDocumentAnalysis.id == db_analysis.id)
    ).first()
    
    db.refresh(db_analysis)

    # Move to In Progress
    db_analysis.state=MultipleDocumentAnalysisStates.IN_PROGRESS
    db.commit()
    db.refresh(db_analysis)

    # Begin Analysis
    failure_count = 0
    failure = False
    content = ""

    while(failure_count<5):
        failure = False
        try:
            primary_document_base_analysis = db.exec(select(SingleDocumentAnalysis)
                .where(SingleDocumentAnalysis.document_id==db_analysis.document_id_primary)
                .where(SingleDocumentAnalysis.kind==SingleDocumentAnalysisKinds.BASE)
                .where(SingleDocumentAnalysis.user_id==db_analysis.user_id)).first()
            
            secondary_document_base_analysis = db.exec(select(SingleDocumentAnalysis)
                .where(SingleDocumentAnalysis.document_id==db_analysis.document_id_secondary)
                .where(SingleDocumentAnalysis.kind==SingleDocumentAnalysisKinds.BASE)
                .where(SingleDocumentAnalysis.user_id==db_analysis.user_id)).first()
            
            analysis_one_summary = json.loads(primary_document_base_analysis.contents)["summary"]
            analysis_two_summary = json.loads(secondary_document_base_analysis.contents)["summary"]

            ##analysis_one =  [LangchainDoc(page_content=analysis_one_summary, metadata={"source": "local"})]
            ##analysis_two =  [LangchainDoc(page_content=analysis_two_summary, metadata={"source": "local"})]

            ##analysis_one_split_docs = text_splitter.split_documents(analysis_one)
            ##analysis_two_split_docs = text_splitter.split_documents(analysis_two)

            result_text = summary_rev_chain.invoke({"primary": analysis_one_summary, "secondary": analysis_two_summary})

            summary_variations = final_variation_chain({"summary": result_text})

            value = {
                "summary": result_text,
                "inconsistencies": summary_variations['text']['variations'],
            }

            content=json.dumps(value)
        except Exception as e:
            print("Error ", e)
            failure = True
            failure_count+=1

        if failure is False:
            break

    if failure is True:
        db_analysis.state = MultipleDocumentAnalysisStates.FAILED
    else:
        db_analysis.state = MultipleDocumentAnalysisStates.COMPLETE
        db_analysis.contents = content

    # Move to Complete or Failed
    db.commit()
    db.refresh(db_analysis)