from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class CNPJQuery(Base):
    """Modelo para rastrear consultas de CNPJ"""
    __tablename__ = "cnpj_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String, index=True)
    status = Column(String)  # 'queued', 'processing', 'completed', 'error'
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class CNPJData(Base):
    """Modelo para armazenar dados de CNPJ"""
    __tablename__ = "cnpj_data"
    
    id = Column(Integer, primary_key=True, index=True)
    cnpj = Column(String, index=True, unique=True)
    raw_data = Column(JSON)  # Dados brutos da API
    
    # Dados extraídos para fácil acesso
    company_name = Column(String, nullable=True)  # Nome da empresa
    trade_name = Column(String, nullable=True)    # Nome fantasia
    status = Column(String, nullable=True)        # Situação cadastral
    address = Column(String, nullable=True)       # Endereço completo
    city = Column(String, nullable=True)          # Cidade
    state = Column(String, nullable=True)         # Estado
    zip_code = Column(String, nullable=True)      # CEP
    email = Column(String, nullable=True)         # Email
    phone = Column(String, nullable=True)         # Telefone
    
    # Info sobre Simples Nacional
    simples_nacional = Column(Boolean, nullable=True)
    simples_nacional_date = Column(DateTime, nullable=True)
    
    # Metadados
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_db():
    """Função para obter conexão com o banco de dados"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()