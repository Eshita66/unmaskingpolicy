from typing import Annotated, List

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import delete
from sqlmodel import Session, select

from langchain_community.document_loaders import WebBaseLoader
from src.tasks.single_document_analysis.coppa import request_coppa_analysis, run_coppa_analysis
from src.tasks.single_document_analysis.ferpa import request_ferpa_analysis, run_ferpa_analysis
from src.tasks.single_document_analysis.hipaa import request_hipaa_analysis, run_hipaa_analysis
from src.infrastructure.auth import get_current_active_user
from src.models.analysis import SingleDocumentAnalysis, SingleDocumentAnalysisRead, SingleDocumentAnalysisReadShort, SingleDocumentAnalysisStates

from src.models.user import User
from src.tasks.single_document_analysis.base import request_base_analysis, run_base_analysis
from src.tasks.single_document_analysis.gdpr import request_gdpr_analysis, run_gdpr_analysis

from ..infrastructure.dependencies import get_db
from ..models.document import *

router = APIRouter(
    prefix="/document"
)

@router.get("/{document_id}", response_model=DocumentRead)
async def get_user_document(document_id: int, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    document = db.exec(select(Document).where(Document.user_id==user.id).where(Document.id==document_id)).first()
    return document

@router.get("/{document_id}/analyses", response_model=List[SingleDocumentAnalysisReadShort])
async def get_user_document_analyses(document_id: int, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    analyses = db.exec(select(SingleDocumentAnalysis).where(SingleDocumentAnalysis.user_id==user.id).where(SingleDocumentAnalysis.document_id==document_id)).all()
    return analyses

@router.get("/", response_model=List[DocumentReadShort])
async def get_user_documents(user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    documents = db.exec(select(Document).where(Document.user_id==user.id)).all()
    return documents

@router.post("/", response_model=DocumentRead)
async def create_user_document(*, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db),  background_tasks: BackgroundTasks, document: DocumentCreate):
    loader = WebBaseLoader(document.url)
    content = loader.load()

    db_document = Document(
        title=document.title,
        url=document.url,
        user_id=user.id,
        contents=content[0].page_content
    )

    db_document = Document.model_validate(db_document)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    #request_base_analysis(db_document.id)
    background_tasks.add_task(request_base_analysis, db_document.id)
    background_tasks.add_task(request_gdpr_analysis, db_document.id)
    background_tasks.add_task(request_coppa_analysis, db_document.id)
    background_tasks.add_task(request_hipaa_analysis, db_document.id)
    background_tasks.add_task(request_ferpa_analysis, db_document.id)
    return db_document

@router.post("/{document_id}/refresh")
async def refresh_document(*, document_id: int, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db), background_tasks: BackgroundTasks):
    document = db.exec(select(Document).where(Document.id==document_id).where(Document.user_id==user.id)).first()

    if document is not None:
        loader = WebBaseLoader(document.url)
        content = loader.load()

        document.contents = content[0].page_content
        db.commit()
        db.refresh(document)

        old_jobs = db.exec(
            select(SingleDocumentAnalysis)
        ).all()

        for job in old_jobs:
            job.state = SingleDocumentAnalysisStates.PENDING

        db.commit()

        for job in old_jobs:
            if SingleDocumentAnalysis.kind=="BASE":
                background_tasks.add_task(run_base_analysis, job)
            if SingleDocumentAnalysis.kind=="GDPR":
                background_tasks.add_task(run_gdpr_analysis, job)
            if SingleDocumentAnalysis.kind=="COPPA":
                background_tasks.add_task(run_coppa_analysis, job)
            if SingleDocumentAnalysis.kind=="FERPA":
                background_tasks.add_task(run_ferpa_analysis, job)
            if SingleDocumentAnalysis.kind=="HIPAA":
                background_tasks.add_task(run_hipaa_analysis, job)

@router.delete("/{document_id}")
async def delete_user_document(*, document_id: int, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    db.exec(delete(Document).where(Document.id==document_id).where(Document.user_id==user.id))
    db.exec(delete(SingleDocumentAnalysis).where(SingleDocumentAnalysis.document_id==document_id).where(SingleDocumentAnalysis.user_id==user.id))
    db.commit()