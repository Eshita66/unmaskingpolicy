import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

class SingleDocumentAnalysisKinds():
    BASE: str = "BASE"
    GDPR: str = "GDPR"
    COPPA: str = "COPPA"
    HIPAA: str = "HIPAA"
    FERPA: str = "FERPA"
        
class SingleDocumentAnalysisStates():
    PENDING: str = "Pending"
    IN_PROGRESS: str = "In Progress"
    COMPLETE: str = "Complete"
    FAILED: str = "Failed"

class SingleDocumentAnalysisBase(SQLModel):
    document_id: int = Field(foreign_key="document.id")
    kind: str

class SingleDocumentAnalysisCreate(SingleDocumentAnalysisBase):
    pass

class SingleDocumentAnalysis(SingleDocumentAnalysisBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    contents: Optional[str] = Field(default=None)
    state: str
    analysis_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class SingleDocumentAnalysisReadShort(SingleDocumentAnalysisBase):
    id: int
    state: str
    analysis_date: datetime.datetime

class SingleDocumentAnalysisRead(SingleDocumentAnalysisReadShort):
    contents: Optional[str]

class MultipleDocumentAnalysisKinds():
    WRT: str = "WRT"
    REV: str = "REV"
        
class MultipleDocumentAnalysisStates():
    PENDING: str = "Pending"
    IN_PROGRESS: str = "In Progress"
    COMPLETE: str = "Complete"
    FAILED: str = "Failed"

class MultipleDocumentAnalysisBase(SQLModel):
    document_id_primary: int = Field(foreign_key="document.id")
    document_id_secondary: int = Field(foreign_key="document.id", exclude=document_id_primary)
    kind: str

class MultipleDocumentAnalysisCreate(MultipleDocumentAnalysisBase):
    pass

class MultipleDocumentAnalysis(MultipleDocumentAnalysisBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    contents: Optional[str] = Field(default=None)
    state: str
    analysis_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class MultipleDocumentAnalysisReadShort(MultipleDocumentAnalysisBase):
    document_id_primary: int
    document_id_secondary: int
    id: int
    state: str
    analysis_date: datetime.datetime

class MultipleDocumentAnalysisRead(MultipleDocumentAnalysisReadShort):
    document_id_primary: int
    document_id_secondary: int
    contents: Optional[str]