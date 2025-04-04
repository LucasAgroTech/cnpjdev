from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import os
import logging
import io
from datetime import datetime, timedelta
import asyncio
import xlsxwriter
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any

from app.models.database import get_db
from app.models import schemas
from app.models.database import CNPJQuery, CNPJData
from app.services.api_manager import APIManager
from app.services.queue import CNPJQueue
from app.utils.file_handler import process_cnpj_file, generate_cnpj_excel
from app.config import (
    RECEITAWS_ENABLED, CNPJWS_ENABLED, CNPJA_OPEN_ENABLED,
    RECEITAWS_REQUESTS_PER_MINUTE, CNPJWS_REQUESTS_PER_MINUTE, CNPJA_OPEN_REQUESTS_PER_MINUTE
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Obtém instância do gerenciador de APIs
def get_api_client():
    return APIManager(
        receitaws_enabled=RECEITAWS_ENABLED,
        cnpjws_enabled=CNPJWS_ENABLED,
        cnpja_open_enabled=CNPJA_OPEN_ENABLED,
        receitaws_requests_per_minute=RECEITAWS_REQUESTS_PER_MINUTE,
        cnpjws_requests_per_minute=CNPJWS_REQUESTS_PER_MINUTE,
        cnpja_open_requests_per_minute=CNPJA_OPEN_REQUESTS_PER_MINUTE
    )

# Obtém instância do gerenciador de fila
async def get_queue_manager(db: Session = Depends(get_db), api_client: APIManager = Depends(get_api_client)):
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
        # Obtém TODOS os CNPJs sem limitação de tempo
        logger.info("Consultando status de todos os CNPJs no banco de dados")
        
        # Usar consultas SQL otimizadas para contagem
        total_count = db.query(func.count(CNPJQuery.id)).scalar()
        completed_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "completed").scalar()
        processing_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "processing").scalar()
        error_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "error").scalar()
        queued_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "queued").scalar()
        rate_limited_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "rate_limited").scalar()
        
        # Obter apenas os CNPJs mais recentes para exibição na tabela (limitado a 100 para performance)
        recent_queries = db.query(CNPJQuery).order_by(CNPJQuery.updated_at.desc()).limit(100).all()
        cnpjs = [query.cnpj for query in recent_queries]
        
        # Criar o objeto de resposta com contagens precisas
        statuses = []
        for cnpj in cnpjs:
            query = db.query(CNPJQuery).filter(CNPJQuery.cnpj == cnpj).order_by(CNPJQuery.created_at.desc()).first()
            
            if query:
                statuses.append(schemas.CNPJStatus(
                    cnpj=cnpj,
                    status=query.status,
                    error_message=query.error_message
                ))
        
        return schemas.CNPJBatchStatus(
            total=total_count,
            completed=completed_count,
            processing=processing_count,
            error=error_count,
            queued=queued_count,
            rate_limited=rate_limited_count,
            results=statuses
        )

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

@router.post("/reset-errors")
async def reset_errors_public(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: APIManager = Depends(get_api_client)
):
    """
    Endpoint público para resetar CNPJs com status de erro
    """
    logger.info("Endpoint público: Resetando CNPJs com status de erro para a fila")
    
    # Encontra todos os CNPJs com status 'error'
    error_queries = db.query(CNPJQuery).filter(CNPJQuery.status == "error").all()
    
    if not error_queries:
        logger.info("Nenhum CNPJ com erro encontrado")
        return {"message": "Nenhum CNPJ com erro encontrado", "count": 0}
    
    # Atualiza o status para 'queued'
    count = 0
    for query in error_queries:
        query.status = "queued"
        query.error_message = None
        query.updated_at = datetime.utcnow()
        count += 1
    
    db.commit()
    logger.info(f"{count} CNPJs com erro resetados para 'queued'")
    
    # Obtém a instância singleton do gerenciador de fila
    queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
    
    # Função para carregar CNPJs pendentes em background
    async def load_and_process():
        try:
            await queue_manager.load_pending_cnpjs()
            logger.info(f"Processamento reiniciado após resetar {count} CNPJs com erro")
        except Exception as e:
            logger.error(f"Erro ao reiniciar processamento: {str(e)}")
    
    # Agenda o processamento em background usando BackgroundTasks
    background_tasks.add_task(load_and_process)
    
    return {"message": f"{count} CNPJs com erro resetados para a fila", "count": count}

@router.post("/reset-rate-limited")
async def reset_rate_limited_public(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: APIManager = Depends(get_api_client)
):
    """
    Endpoint público para resetar CNPJs com status de limite de requisições excedido
    """
    logger.info("Endpoint público: Resetando CNPJs com status de limite de requisições para a fila")
    
    # Encontra todos os CNPJs com status 'rate_limited'
    rate_limited_queries = db.query(CNPJQuery).filter(CNPJQuery.status == "rate_limited").all()
    
    if not rate_limited_queries:
        logger.info("Nenhum CNPJ com limite de requisições excedido encontrado")
        return {"message": "Nenhum CNPJ com limite de requisições excedido encontrado", "count": 0}
    
    # Atualiza o status para 'queued'
    count = 0
    for query in rate_limited_queries:
        query.status = "queued"
        query.error_message = None
        query.updated_at = datetime.utcnow()
        count += 1
    
    db.commit()
    logger.info(f"{count} CNPJs com limite de requisições resetados para 'queued'")
    
    # Obtém a instância singleton do gerenciador de fila
    queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
    
    # Função para carregar CNPJs pendentes em background
    async def load_and_process():
        try:
            await queue_manager.load_pending_cnpjs()
            logger.info(f"Processamento reiniciado após resetar {count} CNPJs com limite de requisições")
        except Exception as e:
            logger.error(f"Erro ao reiniciar processamento: {str(e)}")
    
    # Agenda o processamento em background usando BackgroundTasks
    background_tasks.add_task(load_and_process)
    
    return {"message": f"{count} CNPJs com limite de requisições resetados para a fila", "count": count}

@router.get("/export-excel/", response_class=StreamingResponse)
def export_excel_stream(
    cnpjs: List[str] = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Exporta dados de CNPJs para Excel usando streaming
    
    Implementação otimizada que processa os dados em lotes para reduzir o uso de memória
    e evitar timeouts em grandes volumes de dados.
    """
    logger.info("Exportando dados para Excel via streaming")
    
    # Define o nome do arquivo com a data atual
    filename = f"cnpjs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Cria um gerador para streaming
    def generate_excel():
        # Cria um buffer na memória
        output = io.BytesIO()
        
        # Cria o escritor Excel
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'constant_memory': True})
        worksheet = workbook.add_worksheet('CNPJs')
        
        # Define formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0f2940',
            'font_color': '#0df2c9',
            'border': 1
        })
        
        # Escreve cabeçalhos
        headers = ['CNPJ', 'Razão Social', 'Nome Fantasia', 'Situação', 'Endereço', 
                  'Cidade', 'Estado', 'CEP', 'Email', 'Telefone', 
                  'Simples Nacional', 'Data de Opção Simples', 'Data de Consulta']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Consulta os dados em lotes
        row = 1
        batch_size = 500  # Processa 500 CNPJs por vez
        
        # Constrói a consulta base
        query = db.query(CNPJData)
        
        # Aplica filtros
        if cnpjs:
            clean_cnpjs = [''.join(filter(str.isdigit, cnpj)) for cnpj in cnpjs]
            query = query.filter(CNPJData.cnpj.in_(clean_cnpjs))
        
        if status:
            cnpj_queries = db.query(CNPJQuery.cnpj).filter(CNPJQuery.status == status).all()
            status_cnpjs = [q.cnpj for q in cnpj_queries]
            if status_cnpjs:
                query = query.filter(CNPJData.cnpj.in_(status_cnpjs))
            else:
                # Se não houver CNPJs com o status especificado, retorna Excel vazio
                logger.warning(f"Nenhum CNPJ com status '{status}' encontrado.")
        
        # Obtém o total de registros para log
        total_count = query.count()
        logger.info(f"Gerando Excel com {total_count} CNPJs via streaming")
        
        if total_count == 0:
            # Se não houver dados, fecha o workbook e retorna
            workbook.close()
            output.seek(0)
            data = output.getvalue()
            output.close()
            return data
        
        # Processa em lotes para economizar memória
        offset = 0
        while True:
            batch = query.order_by(CNPJData.cnpj).limit(batch_size).offset(offset).all()
            if not batch:
                break
                
            for cnpj_data in batch:
                worksheet.write(row, 0, cnpj_data.cnpj)
                worksheet.write(row, 1, cnpj_data.company_name)
                worksheet.write(row, 2, cnpj_data.trade_name)
                worksheet.write(row, 3, cnpj_data.status)
                worksheet.write(row, 4, cnpj_data.address)
                worksheet.write(row, 5, cnpj_data.city)
                worksheet.write(row, 6, cnpj_data.state)
                worksheet.write(row, 7, cnpj_data.zip_code)
                worksheet.write(row, 8, cnpj_data.email)
                worksheet.write(row, 9, cnpj_data.phone)
                worksheet.write(row, 10, 'Sim' if cnpj_data.simples_nacional else 'Não')
                
                # Trata campos de data com segurança
                if cnpj_data.simples_nacional_date:
                    worksheet.write(row, 11, cnpj_data.simples_nacional_date.strftime('%d/%m/%Y') if hasattr(cnpj_data.simples_nacional_date, 'strftime') else str(cnpj_data.simples_nacional_date))
                else:
                    worksheet.write(row, 11, '')
                    
                if cnpj_data.updated_at:
                    worksheet.write(row, 12, cnpj_data.updated_at.strftime('%d/%m/%Y %H:%M:%S') if hasattr(cnpj_data.updated_at, 'strftime') else str(cnpj_data.updated_at))
                else:
                    worksheet.write(row, 12, '')
                
                row += 1
            
            # Avança para o próximo lote
            offset += batch_size
            logger.debug(f"Processados {min(offset, total_count)} de {total_count} CNPJs")
            
            # Libera memória explicitamente
            del batch
            
        # Ajusta largura das colunas
        for i, col in enumerate(headers):
            worksheet.set_column(i, i, len(col) + 2)
        
        # Fecha o workbook e obtém os dados
        workbook.close()
        
        # Retorna os dados e reinicia o buffer
        output.seek(0)
        data = output.getvalue()
        output.close()
        
        return data
    
    # Retorna uma resposta de streaming
    return StreamingResponse(
        io.BytesIO(generate_excel()),
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
    total_rate_limited = db.query(CNPJQuery).filter(CNPJQuery.status == "rate_limited").count()
    
    # Obtém os 10 CNPJs mais recentes em processamento, na fila ou com limite de requisições
    recent_pending = db.query(CNPJQuery).filter(
        CNPJQuery.status.in_(["queued", "processing", "rate_limited"])
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
            "rate_limited": total_rate_limited,
            "total": total_queued + total_processing + total_completed + total_error + total_rate_limited
        },
        "recent_pending": pending_cnpjs
    }

@admin_router.post("/queue/restart")
async def restart_queue_processing(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: APIManager = Depends(get_api_client)
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

@admin_router.post("/queue/reset-errors")
async def reset_error_cnpjs(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: APIManager = Depends(get_api_client)
):
    """
    Reseta CNPJs com status de erro para 'queued' e reinicia o processamento
    """
    logger.info("Resetando CNPJs com status de erro para a fila")
    
    # Encontra todos os CNPJs com status 'error'
    error_queries = db.query(CNPJQuery).filter(CNPJQuery.status == "error").all()
    
    if not error_queries:
        logger.info("Nenhum CNPJ com erro encontrado")
        return {"message": "Nenhum CNPJ com erro encontrado", "count": 0}
    
    # Atualiza o status para 'queued'
    count = 0
    for query in error_queries:
        query.status = "queued"
        query.error_message = None
        query.updated_at = datetime.utcnow()
        count += 1
    
    db.commit()
    logger.info(f"{count} CNPJs com erro resetados para 'queued'")
    
    # Obtém a instância singleton do gerenciador de fila
    queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
    
    # Função para carregar CNPJs pendentes em background
    async def load_and_process():
        try:
            await queue_manager.load_pending_cnpjs()
            logger.info(f"Processamento reiniciado após resetar {count} CNPJs com erro")
        except Exception as e:
            logger.error(f"Erro ao reiniciar processamento: {str(e)}")
    
    # Agenda o processamento em background usando BackgroundTasks
    background_tasks.add_task(load_and_process)
    
    return {"message": f"{count} CNPJs com erro resetados para a fila", "count": count}

@admin_router.post("/queue/reset-rate-limited")
async def reset_rate_limited_cnpjs(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: APIManager = Depends(get_api_client)
):
    """
    Reseta CNPJs com status de limite de requisições excedido para 'queued' e reinicia o processamento
    """
    logger.info("Resetando CNPJs com status de limite de requisições para a fila")
    
    # Encontra todos os CNPJs com status 'rate_limited'
    rate_limited_queries = db.query(CNPJQuery).filter(CNPJQuery.status == "rate_limited").all()
    
    if not rate_limited_queries:
        logger.info("Nenhum CNPJ com limite de requisições excedido encontrado")
        return {"message": "Nenhum CNPJ com limite de requisições excedido encontrado", "count": 0}
    
    # Atualiza o status para 'queued'
    count = 0
    for query in rate_limited_queries:
        query.status = "queued"
        query.error_message = None
        query.updated_at = datetime.utcnow()
        count += 1
    
    db.commit()
    logger.info(f"{count} CNPJs com limite de requisições resetados para 'queued'")
    
    # Obtém a instância singleton do gerenciador de fila
    queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
    
    # Função para carregar CNPJs pendentes em background
    async def load_and_process():
        try:
            await queue_manager.load_pending_cnpjs()
            logger.info(f"Processamento reiniciado após resetar {count} CNPJs com limite de requisições")
        except Exception as e:
            logger.error(f"Erro ao reiniciar processamento: {str(e)}")
    
    # Agenda o processamento em background usando BackgroundTasks
    background_tasks.add_task(load_and_process)
    
    return {"message": f"{count} CNPJs com limite de requisições resetados para a fila", "count": count}

@admin_router.post("/queue/reset-all-pending")
async def reset_all_pending_cnpjs(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_client: APIManager = Depends(get_api_client)
):
    """
    Reseta todos os CNPJs pendentes (erro e limite de requisições) para 'queued' e reinicia o processamento
    """
    logger.info("Resetando todos os CNPJs pendentes para a fila")
    
    # Encontra todos os CNPJs com status 'error' ou 'rate_limited'
    pending_queries = db.query(CNPJQuery).filter(
        CNPJQuery.status.in_(["error", "rate_limited"])
    ).all()
    
    if not pending_queries:
        logger.info("Nenhum CNPJ pendente encontrado")
        return {"message": "Nenhum CNPJ pendente encontrado", "count": 0}
    
    # Atualiza o status para 'queued'
    count = 0
    for query in pending_queries:
        query.status = "queued"
        query.error_message = None
        query.updated_at = datetime.utcnow()
        count += 1
    
    db.commit()
    logger.info(f"{count} CNPJs pendentes resetados para 'queued'")
    
    # Obtém a instância singleton do gerenciador de fila
    queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
    
    # Função para carregar CNPJs pendentes em background
    async def load_and_process():
        try:
            await queue_manager.load_pending_cnpjs()
            logger.info(f"Processamento reiniciado após resetar {count} CNPJs pendentes")
        except Exception as e:
            logger.error(f"Erro ao reiniciar processamento: {str(e)}")
    
    # Agenda o processamento em background usando BackgroundTasks
    background_tasks.add_task(load_and_process)
    
    return {"message": f"{count} CNPJs pendentes resetados para a fila", "count": count}

@admin_router.post("/cleanup/duplicates")
async def cleanup_duplicates(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Remove CNPJs duplicados do banco de dados
    """
    logger.info("Iniciando limpeza de CNPJs duplicados")
    
    # Função para executar a limpeza em background
    async def run_cleanup():
        try:
            # Limpa duplicados na tabela CNPJQuery
            logger.info("Limpando duplicados na tabela de consultas...")
            
            # Encontra CNPJs com múltiplas entradas
            duplicates_query = db.query(CNPJQuery.cnpj, func.count(CNPJQuery.id).label('count')) \
                              .group_by(CNPJQuery.cnpj) \
                              .having(func.count(CNPJQuery.id) > 1) \
                              .all()
            
            query_count = 0
            for cnpj, count in duplicates_query:
                # Para cada CNPJ duplicado, mantém apenas a entrada mais recente
                entries = db.query(CNPJQuery) \
                           .filter(CNPJQuery.cnpj == cnpj) \
                           .order_by(CNPJQuery.updated_at.desc()) \
                           .all()
                
                # Mantém o primeiro (mais recente) e remove os demais
                for entry in entries[1:]:
                    db.delete(entry)
                    query_count += 1
            
            # Limpa duplicados na tabela CNPJData
            logger.info("Limpando duplicados na tabela de dados...")
            
            # Encontra CNPJs com múltiplas entradas
            duplicates_data = db.query(CNPJData.cnpj, func.count(CNPJData.id).label('count')) \
                             .group_by(CNPJData.cnpj) \
                             .having(func.count(CNPJData.id) > 1) \
                             .all()
            
            data_count = 0
            for cnpj, count in duplicates_data:
                # Para cada CNPJ duplicado, mantém apenas a entrada mais recente
                entries = db.query(CNPJData) \
                           .filter(CNPJData.cnpj == cnpj) \
                           .order_by(CNPJData.updated_at.desc()) \
                           .all()
                
                # Mantém o primeiro (mais recente) e remove os demais
                for entry in entries[1:]:
                    db.delete(entry)
                    data_count += 1
            
            db.commit()
            logger.info(f"Limpeza concluída: Removidas {query_count} consultas duplicadas e {data_count} dados duplicados")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Erro na limpeza de duplicados: {str(e)}")
    
    # Agenda a limpeza para ser executada em background
    background_tasks.add_task(run_cleanup)
    
    return {"message": "Limpeza de CNPJs duplicados iniciada em background"}

def get_batch_status(db: Session, cnpjs: List[str]) -> schemas.CNPJBatchStatus:
    """
    Obtém status de lote para uma lista de CNPJs
    Versão otimizada para consultas mais eficientes
    """
    if not cnpjs:
        return schemas.CNPJBatchStatus(
            total=0,
            completed=0,
            processing=0,
            error=0,
            queued=0,
            rate_limited=0,
            results=[]
        )
    
    # Consulta otimizada para obter todos os CNPJs de uma vez
    # Usamos a subconsulta para pegar apenas o registro mais recente de cada CNPJ
    subquery = db.query(
        CNPJQuery.cnpj,
        CNPJQuery.status,
        CNPJQuery.error_message,
        func.row_number().over(
            partition_by=CNPJQuery.cnpj,
            order_by=CNPJQuery.created_at.desc()
        ).label('rn')
    ).filter(CNPJQuery.cnpj.in_(cnpjs)).subquery()
    
    # Seleciona apenas as linhas com row_number = 1 (mais recentes)
    query_results = db.query(subquery).filter(subquery.c.rn == 1).all()
    
    # Mapeia os resultados para um dicionário para acesso rápido
    cnpj_status_map = {result.cnpj: (result.status, result.error_message) for result in query_results}
    
    # Inicializa contadores
    completed = 0
    processing = 0
    error = 0
    queued = 0
    rate_limited = 0
    
    # Prepara a lista de status
    statuses = []
    for cnpj in cnpjs:
        if cnpj in cnpj_status_map:
            status, error_message = cnpj_status_map[cnpj]
            
            if status == "completed":
                completed += 1
            elif status == "processing":
                processing += 1
            elif status == "error":
                error += 1
            elif status == "queued":
                queued += 1
            elif status == "rate_limited":
                rate_limited += 1
        else:
            status = "unknown"
            error_message = None
        
        statuses.append(schemas.CNPJStatus(
            cnpj=cnpj,
            status=status,
            error_message=error_message
        ))
    
    return schemas.CNPJBatchStatus(
        total=len(cnpjs),
        completed=completed,
        processing=processing,
        error=error,
        queued=queued,
        rate_limited=rate_limited,
        results=statuses
    )
