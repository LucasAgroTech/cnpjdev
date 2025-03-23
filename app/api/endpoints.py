from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import logging
from datetime import datetime, timedelta
import asyncio

from app.models.database import get_db
from app.models import schemas
from app.models.database import CNPJQuery, CNPJData
from app.services.receitaws import ReceitaWSClient
from app.services.queue import CNPJQueue
from app.utils.file_handler import process_cnpj_file, generate_cnpj_excel
from app.config import REQUESTS_PER_MINUTE

logger = logging.getLogger(__name__)

router = APIRouter()

# Obtém instância do cliente ReceitaWS
def get_api_client():
    return ReceitaWSClient(requests_per_minute=REQUESTS_PER_MINUTE)

# Obtém instância do gerenciador de fila
async def get_queue_manager(db: Session = Depends(get_db), api_client: ReceitaWSClient = Depends(get_api_client)):
    # Usa o padrão Singleton para garantir que haja apenas uma instância do gerenciador de fila
    return await CNPJQueue.get_instance(api_client=api_client, db=db)

@router.post("/upload-file/", response_model=schemas.CNPJBatchStatus)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
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
        
        # Adiciona CNPJs à fila em background
        async def add_to_queue_background(cnpjs_list):
            try:
                await queue_manager.add_to_queue(cnpjs_list)
                logger.info(f"Processamento em background concluído para {len(cnpjs_list)} CNPJs")
            except Exception as e:
                logger.error(f"Erro no processamento em background: {str(e)}")
        
        # Agenda o processamento em background
        background_tasks.add_task(add_to_queue_background, cnpjs)
        
        # Retorna status imediatamente
        status = get_batch_status(db, cnpjs)
        logger.info(f"Upload de arquivo aceito com sucesso: {len(cnpjs)} CNPJs")
        return status
    
    except Exception as e:
        logger.error(f"Erro no upload de arquivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-cnpjs/", response_model=schemas.CNPJBatchStatus)
async def upload_cnpjs(
    data: schemas.CNPJUpload,
    background_tasks: BackgroundTasks = BackgroundTasks(),
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
        
        # Adiciona CNPJs à fila em background
        async def add_to_queue_background(cnpjs_list):
            try:
                await queue_manager.add_to_queue(cnpjs_list)
                logger.info(f"Processamento em background concluído para {len(cnpjs_list)} CNPJs")
            except Exception as e:
                logger.error(f"Erro no processamento em background: {str(e)}")
        
        # Agenda o processamento em background
        background_tasks.add_task(add_to_queue_background, valid_cnpjs)
        
        # Retorna status imediatamente
        status = get_batch_status(db, valid_cnpjs)
        logger.info(f"Lista de CNPJs aceita com sucesso: {len(valid_cnpjs)} válidos")
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

@router.get("/export-excel/", response_class=Response)
def export_excel(
    cnpjs: List[str] = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Exporta dados de CNPJs para Excel
    
    Se nenhum CNPJ for especificado, exporta todos os CNPJs consultados.
    Opcionalmente, pode-se filtrar por status.
    """
    logger.info("Exportando dados para Excel")
    
    # Consulta os dados no banco
    query = db.query(CNPJData)
    
    # Filtra por CNPJs específicos se fornecidos
    if cnpjs:
        # Limpa CNPJs
        clean_cnpjs = [''.join(filter(str.isdigit, cnpj)) for cnpj in cnpjs]
        query = query.filter(CNPJData.cnpj.in_(clean_cnpjs))
    
    # Filtra por status se fornecido
    if status:
        # Obtém os CNPJs com o status especificado
        cnpj_queries = db.query(CNPJQuery.cnpj).filter(CNPJQuery.status == status).distinct().all()
        status_cnpjs = [q.cnpj for q in cnpj_queries]
        
        if status_cnpjs:
            query = query.filter(CNPJData.cnpj.in_(status_cnpjs))
        else:
            # Se não houver CNPJs com o status especificado, retorna vazio
            raise HTTPException(status_code=404, detail=f"Nenhum CNPJ com status '{status}' encontrado.")
    
    # Executa a consulta
    cnpj_data_list = query.all()
    
    if not cnpj_data_list:
        raise HTTPException(status_code=404, detail="Nenhum dado de CNPJ encontrado.")
    
    # Gera o Excel
    excel_data = generate_cnpj_excel(cnpj_data_list)
    
    # Define o nome do arquivo com a data atual
    filename = f"cnpjs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Retorna o arquivo para download
    return Response(
        content=excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Cria um router separado para endpoints de administração
admin_router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(admin_router)

@admin_router.get("/queue/status")
async def get_queue_status(
    db: Session = Depends(get_db)
):
    """
    Obtém o status da fila de processamento
    """
    logger.info("Consultando status da fila de processamento")
    
    # Conta CNPJs por status
    total_queued = db.query(CNPJQuery).filter(CNPJQuery.status == "queued").count()
    total_processing = db.query(CNPJQuery).filter(CNPJQuery.status == "processing").count()
    total_completed = db.query(CNPJQuery).filter(CNPJQuery.status == "completed").count()
    total_error = db.query(CNPJQuery).filter(CNPJQuery.status == "error").count()
    
    # Obtém os 10 CNPJs mais recentes em processamento ou na fila
    recent_pending = db.query(CNPJQuery).filter(
        CNPJQuery.status.in_(["queued", "processing"])
    ).order_by(CNPJQuery.created_at.desc()).limit(10).all()
    
    pending_cnpjs = [
        {
            "cnpj": query.cnpj,
            "status": query.status,
            "created_at": query.created_at.isoformat(),
            "updated_at": query.updated_at.isoformat()
        }
        for query in recent_pending
    ]
    
    return {
        "queue_status": {
            "queued": total_queued,
            "processing": total_processing,
            "completed": total_completed,
            "error": total_error,
            "total": total_queued + total_processing + total_completed + total_error
        },
        "recent_pending": pending_cnpjs
    }

@admin_router.post("/queue/restart")
async def restart_queue_processing(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: ReceitaWSClient = Depends(get_api_client)
):
    """
    Reinicia o processamento da fila de CNPJs pendentes
    """
    logger.info("Reiniciando processamento da fila")
    
    # Obtém a instância singleton do gerenciador de fila
    queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
    
    # Função para carregar CNPJs pendentes em background
    async def load_and_process():
        try:
            count = await queue_manager.load_pending_cnpjs()
            logger.info(f"Processamento reiniciado com {count} CNPJs pendentes")
        except Exception as e:
            logger.error(f"Erro ao reiniciar processamento: {str(e)}")
    
    # Agenda o processamento em background usando BackgroundTasks
    background_tasks.add_task(load_and_process)
    
    return {"message": "Reinicialização do processamento iniciada"}

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
