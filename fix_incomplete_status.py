#!/usr/bin/env python3
"""
Script para corrigir CNPJs que têm dados mas não estão marcados como "completed".
Este script identifica CNPJs que têm dados na tabela CNPJData mas não estão
marcados como "completed" na tabela CNPJQuery, e atualiza o status desses CNPJs.
"""

import os
import sys
import logging
from datetime import datetime
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

logger = logging.getLogger("fix-status")

# Importa os modelos do banco de dados
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models.database import CNPJQuery, CNPJData, Base
from app.config import DATABASE_URL

def fix_incomplete_status(dry_run=False):
    """
    Corrige CNPJs que têm dados mas não estão marcados como "completed"
    
    Args:
        dry_run: Se True, apenas mostra o que seria feito sem fazer alterações
    """
    
    # Cria conexão com o banco de dados
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("=== CORREÇÃO DE STATUS INCOMPLETOS ===")
        
        # Verifica se as tabelas existem
        logger.info("Verificando tabelas...")
        inspector = engine.dialect.inspector
        tables = inspector.get_table_names()
        if "cnpj_queries" not in tables or "cnpj_data" not in tables:
            logger.error(f"Tabelas necessárias não encontradas. Tabelas existentes: {tables}")
            return
        
        # CNPJs que têm dados
        data_cnpjs = session.query(CNPJData.cnpj).all()
        data_cnpjs = [cnpj[0] for cnpj in data_cnpjs]
        
        logger.info(f"Encontrados {len(data_cnpjs)} CNPJs com dados")
        
        # CNPJs que têm dados mas não estão marcados como "completed"
        incomplete_cnpjs = session.query(CNPJQuery).filter(
            CNPJQuery.cnpj.in_(data_cnpjs),
            CNPJQuery.status != "completed"
        ).all()
        
        if not incomplete_cnpjs:
            logger.info("Não foram encontrados CNPJs com dados mas sem status 'completed'.")
            return
        
        logger.info(f"Encontrados {len(incomplete_cnpjs)} CNPJs com dados mas sem status 'completed':")
        
        # Atualiza o status para "completed"
        count = 0
        for query in incomplete_cnpjs:
            logger.info(f"  - CNPJ: {query.cnpj}, Status atual: {query.status}, Atualizado em: {query.updated_at}")
            
            # Verifica se o CNPJ tem dados
            cnpj_data = session.query(CNPJData).filter(CNPJData.cnpj == query.cnpj).first()
            if cnpj_data:
                logger.info(f"    Dados encontrados, criados em: {cnpj_data.created_at}, atualizados em: {cnpj_data.updated_at}")
                
                if not dry_run:
                    # Atualiza o status para "completed"
                    old_status = query.status
                    query.status = "completed"
                    query.error_message = None
                    query.updated_at = datetime.utcnow()
                    count += 1
                    logger.info(f"    Status atualizado de '{old_status}' para 'completed'")
                else:
                    logger.info(f"    [DRY RUN] Status seria atualizado de '{query.status}' para 'completed'")
        
        if not dry_run and count > 0:
            # Commit das alterações
            session.commit()
            logger.info(f"Commit realizado com sucesso. {count} CNPJs atualizados.")
        elif dry_run:
            logger.info(f"[DRY RUN] {len(incomplete_cnpjs)} CNPJs seriam atualizados.")
        
        logger.info("=== FIM DA CORREÇÃO ===")
        
    except Exception as e:
        logger.error(f"Erro durante a correção: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        if not dry_run:
            session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    # Verifica se é um dry run
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        logger.info("Executando em modo dry run (sem fazer alterações)")
    
    fix_incomplete_status(dry_run=dry_run)
