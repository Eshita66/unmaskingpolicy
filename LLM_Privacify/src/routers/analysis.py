from typing import Annotated, List
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session, select
from src.tasks.multiple_document_analysis.rev import run_multiple_document_rev_analysis
from src.tasks.multiple_document_analysis.wrt import run_multiple_document_wrt_analysis
from src.infrastructure.auth import get_current_active_user
from src.infrastructure.dependencies import get_db

from src.models.analysis import MultipleDocumentAnalysis, MultipleDocumentAnalysisCreate, MultipleDocumentAnalysisKinds, MultipleDocumentAnalysisRead, MultipleDocumentAnalysisReadShort, MultipleDocumentAnalysisStates, SingleDocumentAnalysis, SingleDocumentAnalysisRead
from src.models.user import User


router = APIRouter(
    prefix="/analysis"
)

@router.get("/singular/{analysis_id}", response_model=SingleDocumentAnalysisRead)
async def get_user_single_document_analysis(analysis_id: int, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    analysis = db.exec(select(SingleDocumentAnalysis).where(SingleDocumentAnalysis.user_id==user.id).where(SingleDocumentAnalysis.id==analysis_id)).first()
    return analysis

@router.get("/", response_model=List[MultipleDocumentAnalysisReadShort])
async def get_user_multiple_document_analyses(user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    analyses = db.exec(select(MultipleDocumentAnalysis).where(MultipleDocumentAnalysis.user_id==user.id)).all()
    return analyses

@router.post("/", response_model=MultipleDocumentAnalysisRead)
async def create_user_multiple_document_analysis(*, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db),  background_tasks: BackgroundTasks, analysis: MultipleDocumentAnalysisCreate):
    db_analysis = MultipleDocumentAnalysis(
        document_id_primary=analysis.document_id_primary,
        document_id_secondary=analysis.document_id_secondary,
        kind=analysis.kind,
        user_id=user.id,
        state=MultipleDocumentAnalysisStates.PENDING
    )

    db_analysis = MultipleDocumentAnalysis.model_validate(db_analysis)
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    if(db_analysis.kind == MultipleDocumentAnalysisKinds.WRT):
        background_tasks.add_task(run_multiple_document_wrt_analysis, db_analysis)
    elif(db_analysis.kind == MultipleDocumentAnalysisKinds.REV):
        background_tasks.add_task(run_multiple_document_rev_analysis, db_analysis)
    return db_analysis

@router.post("/{analysis_id}", response_model=MultipleDocumentAnalysisRead)
async def get_user_multiple_document_analysis(analysis_id: int, user: Annotated[User, Depends(get_current_active_user)], db: Session = Depends(get_db)):
    analysis = db.exec(select(MultipleDocumentAnalysis).where(MultipleDocumentAnalysis.user_id==user.id).where(MultipleDocumentAnalysis.id==analysis_id)).first()
    return analysis