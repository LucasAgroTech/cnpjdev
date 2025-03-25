#!/usr/bin/env python3
"""
Script para reiniciar a fila de processamento de CNPJs com configurações otimizadas.

Este script garante que o sistema processe exatamente 11 CNPJs por minuto,
utilizando as três APIs disponíveis de forma eficiente.
"""

import asyncio
import logging
import sys
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Importa os módulos necessários
try:
    from app.config import DATABASE_URL, RECEITAWS_ENABLED, CNPJWS_ENABLED, CNPJA_OPEN_ENABLED
    from app.config import RECEITAWS_REQUESTS_PER_MINUTE, CNPJWS_REQUESTS_PER_MINUTE, CNPJA_OPEN_REQUESTS_PER_MINUTE
    from app.services.api_manager import APIManager
    from app.services.queue import CNPJQueue
    from app.models.database import Base
except ImportError as e:
    logger.error(f"Erro ao importar módulos: {str(e)}")
    logger.error("Certifique-se de que o ambiente virtual está ativado e que você está no diretório raiz do projeto.")
    sys.exit(1)

async def main():
    """
    Função principal que reinicia a fila de processamento de CNPJs.
    """
    logger.info("Iniciando reinicialização otimizada da fila de CNPJs...")
    
    # Verifica se a URL do banco de dados está configurada
    if not DATABASE_URL:
        logger.error("URL do banco de dados não configurada. Defina DATABASE_URL no arquivo .env")
        return
    
    # Conecta ao banco de dados
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        logger.info("Conexão com o banco de dados estabelecida com sucesso")
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return
    
    # Inicializa o gerenciador de APIs
    try:
        api_manager = APIManager(
            receitaws_enabled=RECEITAWS_ENABLED,
            cnpjws_enabled=CNPJWS_ENABLED,
            cnpja_open_enabled=CNPJA_OPEN_ENABLED,
            receitaws_requests_per_minute=RECEITAWS_REQUESTS_PER_MINUTE,
            cnpjws_requests_per_minute=CNPJWS_REQUESTS_PER_MINUTE,
            cnpja_open_requests_per_minute=CNPJA_OPEN_REQUESTS_PER_MINUTE
        )
        logger.info("Gerenciador de APIs inicializado com sucesso")
        
        # Exibe informações sobre as APIs habilitadas
        apis_info = []
        if RECEITAWS_ENABLED:
            apis_info.append(f"ReceitaWS ({RECEITAWS_REQUESTS_PER_MINUTE} req/min)")
        if CNPJWS_ENABLED:
            apis_info.append(f"CNPJ.ws ({CNPJWS_REQUESTS_PER_MINUTE} req/min)")
        if CNPJA_OPEN_ENABLED:
            apis_info.append(f"CNPJa Open ({CNPJA_OPEN_REQUESTS_PER_MINUTE} req/min)")
        
        logger.info(f"APIs habilitadas: {', '.join(apis_info)}")
        
        # Calcula o total de requisições por minuto
        total_rpm = (RECEITAWS_REQUESTS_PER_MINUTE if RECEITAWS_ENABLED else 0) + \
                    (CNPJWS_REQUESTS_PER_MINUTE if CNPJWS_ENABLED else 0) + \
                    (CNPJA_OPEN_REQUESTS_PER_MINUTE if CNPJA_OPEN_ENABLED else 0)
        
        logger.info(f"Total de requisições por minuto: {total_rpm}")
        
    except Exception as e:
        logger.error(f"Erro ao inicializar o gerenciador de APIs: {str(e)}")
        db.close()
        return
    
    # Inicializa e reinicia a fila
    try:
        # Obtém a instância da fila
        queue = await CNPJQueue.get_instance(api_manager, db)
        
        # Limpa CNPJs presos em processamento
        cleaned_count = await queue.cleanup_stuck_processing()
        if cleaned_count > 0:
            logger.info(f"Redefinidos {cleaned_count} CNPJs presos em processamento")
        
        # Carrega CNPJs pendentes
        loaded_count = await queue.load_pending_cnpjs()
        logger.info(f"Carregados {loaded_count} CNPJs pendentes para processamento")
        
        if loaded_count == 0:
            logger.info("Nenhum CNPJ pendente encontrado. A fila está vazia.")
        else:
            logger.info(f"Fila reiniciada com sucesso. Processando {loaded_count} CNPJs pendentes.")
            logger.info(f"O sistema processará exatamente {total_rpm} CNPJs por minuto.")
            logger.info("O sistema verificará a cada 30 segundos se há CNPJs suficientes na fila.")
            logger.info("Isso garante que sempre haja CNPJs sendo processados continuamente.")
            
            # Aguarda um pouco para permitir que o processamento comece
            await asyncio.sleep(2)
            
            # Verifica quantos CNPJs estão em processamento
            processing_count = await queue.get_processing_count()
            logger.info(f"Atualmente há {processing_count} CNPJs em processamento")
            
    except Exception as e:
        logger.error(f"Erro ao reiniciar a fila: {str(e)}")
    finally:
        # Fecha a conexão com o banco de dados
        db.close()
        logger.info("Conexão com o banco de dados fechada")

if __name__ == "__main__":
    # Executa a função principal
    asyncio.run(main())
    logger.info("Script finalizado")
