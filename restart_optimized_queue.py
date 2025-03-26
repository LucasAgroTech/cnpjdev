#!/usr/bin/env python
"""
Script para reiniciar a fila otimizada de processamento de CNPJs

Este script é executado após o deploy para garantir que a fila de processamento
seja reiniciada com as novas configurações otimizadas.
"""

import asyncio
import logging
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("restart_optimized_queue")

# Importa as dependências necessárias
try:
    from app.config import DATABASE_URL
    from app.models.database import CNPJQuery, get_db
    from app.services.api_manager import APIManager
    from app.services.queue import CNPJQueue
    from app.config import (
        RECEITAWS_ENABLED, CNPJWS_ENABLED, CNPJA_OPEN_ENABLED,
        RECEITAWS_REQUESTS_PER_MINUTE, CNPJWS_REQUESTS_PER_MINUTE, CNPJA_OPEN_REQUESTS_PER_MINUTE
    )
except ImportError as e:
    logger.error(f"Erro ao importar dependências: {e}")
    sys.exit(1)

async def main():
    """
    Função principal para reiniciar a fila otimizada
    """
    logger.info("Iniciando reinicialização da fila otimizada")
    
    try:
        # Cria uma sessão do banco de dados
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Cria o gerenciador de APIs
        api_client = APIManager(
            receitaws_enabled=RECEITAWS_ENABLED,
            cnpjws_enabled=CNPJWS_ENABLED,
            cnpja_open_enabled=CNPJA_OPEN_ENABLED,
            receitaws_requests_per_minute=RECEITAWS_REQUESTS_PER_MINUTE,
            cnpjws_requests_per_minute=CNPJWS_REQUESTS_PER_MINUTE,
            cnpja_open_requests_per_minute=CNPJA_OPEN_REQUESTS_PER_MINUTE
        )
        
        # Obtém a instância do gerenciador de fila
        queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
        
        # Limpa CNPJs presos em processamento
        stuck_count = await queue_manager.cleanup_stuck_processing()
        if stuck_count > 0:
            logger.info(f"Redefinidos {stuck_count} CNPJs presos em processamento")
        
        # Carrega CNPJs pendentes
        pending_count = await queue_manager.load_pending_cnpjs()
        logger.info(f"Carregados {pending_count} CNPJs pendentes para processamento")
        
        # Exibe informações sobre as APIs configuradas
        total_rpm = (RECEITAWS_REQUESTS_PER_MINUTE + 
                     CNPJWS_REQUESTS_PER_MINUTE + 
                     CNPJA_OPEN_REQUESTS_PER_MINUTE)
        
        logger.info(f"Configuração das APIs:")
        logger.info(f"- ReceitaWS: {'habilitada' if RECEITAWS_ENABLED else 'desabilitada'} ({RECEITAWS_REQUESTS_PER_MINUTE} req/min)")
        logger.info(f"- CNPJ.ws: {'habilitada' if CNPJWS_ENABLED else 'desabilitada'} ({CNPJWS_REQUESTS_PER_MINUTE} req/min)")
        logger.info(f"- CNPJa Open: {'habilitada' if CNPJA_OPEN_ENABLED else 'desabilitada'} ({CNPJA_OPEN_REQUESTS_PER_MINUTE} req/min)")
        logger.info(f"Total de requisições por minuto: {total_rpm}")
        
        # Aguarda um pouco para garantir que o processamento seja iniciado
        await asyncio.sleep(2)
        
        logger.info("Reinicialização da fila otimizada concluída com sucesso")
        
    except Exception as e:
        logger.error(f"Erro ao reiniciar a fila otimizada: {e}")
        sys.exit(1)
    finally:
        # Fecha a sessão do banco de dados
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
