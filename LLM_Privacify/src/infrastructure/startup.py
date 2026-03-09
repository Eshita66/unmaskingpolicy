from src.tasks.single_document_analysis.coppa import reset_and_run_broken_coppa_analyses
from src.tasks.single_document_analysis.ferpa import reset_and_run_broken_ferpa_analyses
from src.tasks.single_document_analysis.hipaa import reset_and_run_broken_hipaa_analyses
from src.tasks.single_document_analysis.gdpr import reset_and_run_broken_gdpr_analyses
from src.tasks.single_document_analysis.base import reset_and_run_broken_base_analyses
from .database import create_db_and_tables
from multiprocessing import Process


def on_startup():
    create_db_and_tables()
    p = Process(target=reset_and_run_broken_base_analyses, args=())
    p.start()
    p = Process(target=reset_and_run_broken_gdpr_analyses, args=())
    p.start()
    p = Process(target=reset_and_run_broken_hipaa_analyses, args=())
    p.start()
    p = Process(target=reset_and_run_broken_coppa_analyses, args=())
    p.start()
    p = Process(target=reset_and_run_broken_ferpa_analyses, args=())
    p.start()
