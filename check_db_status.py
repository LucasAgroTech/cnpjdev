#!/usr/bin/env python3
"""
Script de diagnóstico para verificar o status dos CNPJs no banco de dados.
Este script verifica se há discrepâncias entre os logs e o estado real do banco de dados.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Configura o logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("db-diagnostico")

# Importa os modelos do banco de dados
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models.database import CNPJQuery, CNPJData, Base
from app.config import DATABASE_URL

def check_db_status():
    """Verifica o status dos CNPJs no banco de dados"""
    
    # Cria conexão com o banco de dados
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("=== DIAGNÓSTICO DO BANCO DE DADOS ===")
        
        # Verifica se as tabelas existem
        logger.info("Verificando tabelas...")
        inspector = engine.dialect.inspector
        tables = inspector.get_table_names(schema="public")
        if "cnpj_queries" not in tables or "cnpj_data" not in tables:
            logger.error(f"Tabelas necessárias não encontradas. Tabelas existentes: {tables}")
            return
        
        # Conta CNPJs por status
        logger.info("Contando CNPJs por status...")
        total_queries = session.query(func.count(CNPJQuery.id)).scalar()
        total_data = session.query(func.count(CNPJData.id)).scalar()
        
        status_counts = {}
        for status in ["queued", "processing", "completed", "error", "rate_limited"]:
            count = session.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == status).scalar()
            status_counts[status] = count
        
        logger.info(f"Total de consultas: {total_queries}")
        logger.info(f"Total de dados: {total_data}")
        logger.info(f"Status: {status_counts}")
        
        # Verifica CNPJs processados recentemente (últimas 24 horas)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_queries = session.query(CNPJQuery).filter(
            CNPJQuery.updated_at >= yesterday
        ).order_by(CNPJQuery.updated_at.desc()).limit(20).all()
        
        logger.info(f"CNPJs processados recentemente (últimas 24h): {len(recent_queries)}")
        
        # Verifica se há CNPJs com dados mas sem status "completed"
        logger.info("Verificando inconsistências...")
        
        # CNPJs que têm dados mas não estão marcados como "completed"
        data_cnpjs = session.query(CNPJData.cnpj).all()
        data_cnpjs = [cnpj[0] for cnpj in data_cnpjs]
        
        incomplete_cnpjs = session.query(CNPJQuery).filter(
            CNPJQuery.cnpj.in_(data_cnpjs),
            CNPJQuery.status != "completed"
        ).all()
        
        if incomplete_cnpjs:
            logger.warning(f"Encontrados {len(incomplete_cnpjs)} CNPJs com dados mas sem status 'completed':")
            for query in incomplete_cnpjs:
                logger.warning(f"  - CNPJ: {query.cnpj}, Status: {query.status}, Atualizado em: {query.updated_at}")
                
                # Verifica se o CNPJ tem dados
                cnpj_data = session.query(CNPJData).filter(CNPJData.cnpj == query.cnpj).first()
                if cnpj_data:
                    logger.warning(f"    Dados encontrados, criados em: {cnpj_data.created_at}, atualizados em: {cnpj_data.updated_at}")
        else:
            logger.info("Não foram encontradas inconsistências entre dados e status.")
        
        # Verifica se há CNPJs marcados como "completed" mas sem dados
        completed_cnpjs = session.query(CNPJQuery.cnpj).filter(
            CNPJQuery.status == "completed"
        ).all()
        completed_cnpjs = [cnpj[0] for cnpj in completed_cnpjs]
        
        missing_data_cnpjs = []
        for cnpj in completed_cnpjs:
            data = session.query(CNPJData).filter(CNPJData.cnpj == cnpj).first()
            if not data:
                missing_data_cnpjs.append(cnpj)
        
        if missing_data_cnpjs:
            logger.warning(f"Encontrados {len(missing_data_cnpjs)} CNPJs marcados como 'completed' mas sem dados:")
            for cnpj in missing_data_cnpjs[:10]:  # Limita a 10 para não sobrecarregar o log
                logger.warning(f"  - CNPJ: {cnpj}")
            if len(missing_data_cnpjs) > 10:
                logger.warning(f"  ... e mais {len(missing_data_cnpjs) - 10} CNPJs")
        else:
            logger.info("Não foram encontrados CNPJs marcados como 'completed' sem dados correspondentes.")
        
        # Verifica CNPJs presos em processamento
        stuck_processing = session.query(CNPJQuery).filter(
            CNPJQuery.status == "processing",
            CNPJQuery.updated_at < datetime.utcnow() - timedelta(minutes=10)
        ).all()
        
        if stuck_processing:
            logger.warning(f"Encontrados {len(stuck_processing)} CNPJs presos em processamento por mais de 10 minutos:")
            for query in stuck_processing[:10]:  # Limita a 10 para não sobrecarregar o log
                logger.warning(f"  - CNPJ: {query.cnpj}, Atualizado em: {query.updated_at}")
            if len(stuck_processing) > 10:
                logger.warning(f"  ... e mais {len(stuck_processing) - 10} CNPJs")
        else:
            logger.info("Não foram encontrados CNPJs presos em processamento.")
        
        # Verifica se há CNPJs duplicados
        logger.info("Verificando duplicatas...")
        
        duplicate_queries = session.query(
            CNPJQuery.cnpj, func.count(CNPJQuery.id).label('count')
        ).group_by(CNPJQuery.cnpj).having(func.count(CNPJQuery.id) > 1).all()
        
        if duplicate_queries:
            logger.warning(f"Encontrados {len(duplicate_queries)} CNPJs com múltiplas entradas na tabela de consultas:")
            for cnpj, count in duplicate_queries[:10]:  # Limita a 10 para não sobrecarregar o log
                logger.warning(f"  - CNPJ: {cnpj}, Entradas: {count}")
                
                # Verifica os status das entradas duplicadas
                entries = session.query(CNPJQuery).filter(CNPJQuery.cnpj == cnpj).all()
                statuses = [entry.status for entry in entries]
                logger.warning(f"    Status: {statuses}")
            
            if len(duplicate_queries) > 10:
                logger.warning(f"  ... e mais {len(duplicate_queries) - 10} CNPJs duplicados")
        else:
            logger.info("Não foram encontrados CNPJs duplicados na tabela de consultas.")
        
        # Verifica se há CNPJs com múltiplos dados
        duplicate_data = session.query(
            CNPJData.cnpj, func.count(CNPJData.id).label('count')
        ).group_by(CNPJData.cnpj).having(func.count(CNPJData.id) > 1).all()
        
        if duplicate_data:
            logger.warning(f"Encontrados {len(duplicate_data)} CNPJs com múltiplas entradas na tabela de dados:")
            for cnpj, count in duplicate_data[:10]:  # Limita a 10 para não sobrecarregar o log
                logger.warning(f"  - CNPJ: {cnpj}, Entradas: {count}")
            
            if len(duplicate_data) > 10:
                logger.warning(f"  ... e mais {len(duplicate_data) - 10} CNPJs duplicados")
        else:
            logger.info("Não foram encontrados CNPJs duplicados na tabela de dados.")
        
        logger.info("=== FIM DO DIAGNÓSTICO ===")
        
    except Exception as e:
        logger.error(f"Erro durante o diagnóstico: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        session.close()

if __name__ == "__main__":
    check_db_status()
