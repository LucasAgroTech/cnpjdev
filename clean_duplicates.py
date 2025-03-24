#!/usr/bin/env python3
import os
import sys
import asyncio
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models.database import CNPJQuery, CNPJData, Base
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Função para limpar CNPJs duplicados na tabela CNPJQuery
async def clean_duplicate_queries(db_url):
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("Identificando CNPJs duplicados na tabela de consultas...")
        
        # Encontra CNPJs com múltiplas entradas
        duplicates = session.query(CNPJQuery.cnpj, func.count(CNPJQuery.id).label('count')) \
                           .group_by(CNPJQuery.cnpj) \
                           .having(func.count(CNPJQuery.id) > 1) \
                           .all()
        
        print(f"Encontrados {len(duplicates)} CNPJs com entradas duplicadas")
        
        for cnpj, count in duplicates:
            # Para cada CNPJ duplicado, mantém apenas a entrada mais recente
            entries = session.query(CNPJQuery) \
                            .filter(CNPJQuery.cnpj == cnpj) \
                            .order_by(CNPJQuery.updated_at.desc()) \
                            .all()
            
            # Mantém o primeiro (mais recente) e remove os demais
            for entry in entries[1:]:
                session.delete(entry)
            
            print(f"CNPJ {cnpj}: Mantida 1 entrada, removidas {count-1} duplicatas")
        
        session.commit()
        print("Limpeza de consultas duplicadas concluída com sucesso")
        
    except Exception as e:
        session.rollback()
        print(f"Erro ao limpar consultas duplicadas: {str(e)}")
    finally:
        session.close()

# Função para limpar CNPJs duplicados na tabela CNPJData
async def clean_duplicate_data(db_url):
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("Identificando CNPJs duplicados na tabela de dados...")
        
        # Encontra CNPJs com múltiplas entradas
        duplicates = session.query(CNPJData.cnpj, func.count(CNPJData.id).label('count')) \
                           .group_by(CNPJData.cnpj) \
                           .having(func.count(CNPJData.id) > 1) \
                           .all()
        
        print(f"Encontrados {len(duplicates)} CNPJs com dados duplicados")
        
        for cnpj, count in duplicates:
            # Para cada CNPJ duplicado, mantém apenas a entrada mais recente
            entries = session.query(CNPJData) \
                            .filter(CNPJData.cnpj == cnpj) \
                            .order_by(CNPJData.updated_at.desc()) \
                            .all()
            
            # Mantém o primeiro (mais recente) e remove os demais
            for entry in entries[1:]:
                session.delete(entry)
            
            print(f"CNPJ {cnpj}: Mantida 1 entrada de dados, removidas {count-1} duplicatas")
        
        session.commit()
        print("Limpeza de dados duplicados concluída com sucesso")
        
    except Exception as e:
        session.rollback()
        print(f"Erro ao limpar dados duplicados: {str(e)}")
    finally:
        session.close()

# Função principal
async def main():
    # Obtém a URL do banco de dados
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Erro: Variável de ambiente DATABASE_URL não definida")
        sys.exit(1)
    
    # Garante que a URL do PostgreSQL esteja no formato correto
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print(f"Conectando ao banco de dados...")
    
    # Executa a limpeza
    await clean_duplicate_queries(db_url)
    await clean_duplicate_data(db_url)
    
    print("Processo de limpeza concluído")

if __name__ == "__main__":
    asyncio.run(main())
