from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging
from datetime import datetime, timedelta

from app.models.database import get_db
from app.models import schemas
from app.models.database import CNPJQuery, CNPJData
from app.services.receitaws import ReceitaWSClient
from app.services.queue import CNPJQueue
from app.utils.file_handler import process_cnpj_file
from app.config import REQUESTS_PER_MINUTE

logger = logging.getLogger(__name__)

router = APIRouter()

# Obtém instância do cliente ReceitaWS
def get_api_client():
    return ReceitaWSClient(requests_per_minute=REQUESTS_PER_MINUTE)

# Obtém instância do gerenciador de fila
def get_queue_manager(db: Session = Depends(get_db), api_client: ReceitaWSClient = Depends(get_api_client)):
    return CNPJQueue(api_client=api_client, db=db)

@router.post("/upload-file/", response_model=schemas.CNPJBatchStatus)
async def upload_file(
    file: UploadFile = File(...),
    queue_manager: CNPJQueue = Depends(get_queue_manager),
    db: Session = Depends(get_db)
):
    """
    Faz upload de um arquivo (CSV ou Excel) contendo CNPJs para processamento
    """
    logger.info(f"Recebido upload de arquivo: {file.filename}")
    
    try:
        # Processa o arquivo
        cnpjs = await process_cnpj_file(file)
        
        # Adiciona CNPJs à fila
        await queue_manager.add_to_queue(cnpjs)
        
        # Retorna status
        status = get_batch_status(db, cnpjs)
        logger.info(f"Upload de arquivo processado com sucesso: {len(cnpjs)} CNPJs")
        return status
    
    except Exception as e:
        logger.error(f"Erro no upload de arquivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-cnpjs/", response_model=schemas.CNPJBatchStatus)
async def upload_cnpjs(
    data: schemas.CNPJUpload,
    queue_manager: CNPJQueue = Depends(get_queue_manager),
    db: Session = Depends(get_db)
):
    """
    Envia uma lista de CNPJs para processamento
    """
    logger.info(f"Recebida lista de {len(data.cnpjs)} CNPJs")
    
    try:
        # Limpa CNPJs
        cnpjs = [''.join(filter(str.isdigit, cnpj)) for cnpj in data.cnpjs]
        valid_cnpjs = [cnpj for cnpj in cnpjs if len(cnpj) == 14]
        
        if not valid_cnpjs:
            logger.warning("Nenhum CNPJ válido fornecido")
            raise HTTPException(status_code=400, detail="Nenhum CNPJ válido fornecido.")
        
        # Adiciona CNPJs à fila
        await queue_manager.add_to_queue(valid_cnpjs)
        
        # Retorna status
        status = get_batch_status(db, valid_cnpjs)
        logger.info(f"Lista de CNPJs processada com sucesso: {len(valid_cnpjs)} válidos")
        return status
    
    except Exception as e:
        logger.error(f"Erro no upload de lista de CNPJs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/", response_model=schemas.CNPJBatchStatus)
def get_status(
    cnpjs: List[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Obtém o status do processamento de CNPJs
    """
    if cnpjs:
        logger.info(f"Consultando status de {len(cnpjs)} CNPJs específicos")
        # Limpa CNPJs
        clean_cnpjs = [''.join(filter(str.isdigit, cnpj)) for cnpj in cnpjs]
        return get_batch_status(db, clean_cnpjs)
    else:
        # Obtém todas as consultas das últimas 24 horas
        logger.info("Consultando status de todos os CNPJs das últimas 24 horas")
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        queries = db.query(CNPJQuery).filter(CNPJQuery.created_at >= yesterday).all()
        cnpjs = [query.cnpj for query in queries]
        
        return get_batch_status(db, cnpjs)

@router.get("/cnpj/{cnpj}", response_model=schemas.CNPJDataFull)
def get_cnpj_data(
    cnpj: str,
    db: Session = Depends(get_db)
):
    """
    Obtém dados de um CNPJ específico
    """
    # Limpa CNPJ
    clean_cnpj = ''.join(filter(str.isdigit, cnpj))
    logger.info(f"Consultando dados do CNPJ: {clean_cnpj}")
    
    # Obtém do banco de dados
    data = db.query(CNPJData).filter(CNPJData.cnpj == clean_cnpj).first()
    
    if not data:
        logger.warning(f"CNPJ não encontrado: {clean_cnpj}")
        raise HTTPException(status_code=404, detail="Dados do CNPJ não encontrados.")
    
    logger.info(f"Dados do CNPJ {clean_cnpj} retornados com sucesso")
    return data

def get_batch_status(db: Session, cnpjs: List[str]) -> schemas.CNPJBatchStatus:
    """
    Obtém status de lote para uma lista de CNPJs
    """
    statuses = []
    total = len(cnpjs)
    completed = 0
    processing = 0
    error = 0
    queued = 0
    
    for cnpj in cnpjs:
        query = db.query(CNPJQuery).filter(CNPJQuery.cnpj == cnpj).order_by(CNPJQuery.created_at.desc()).first()
        
        if query:
            status = query.status
            error_message = query.error_message
            
            if status == "completed":
                completed += 1
            elif status == "processing":
                processing += 1
            elif status == "error":
                error += 1
            elif status == "queued":
                queued += 1
        else:
            status = "unknown"
            error_message = None
        
        statuses.append(schemas.CNPJStatus(
            cnpj=cnpj,
            status=status,
            error_message=error_message
        ))
    
    return schemas.CNPJBatchStatus(
        total=total,
        completed=completed,
        processing=processing,
        error=error,
        queued=queued,
        results=statuses
    )
