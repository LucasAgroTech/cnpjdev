from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class CNPJQueryBase(BaseModel):
    """Schema base para consulta de CNPJ"""
    cnpj: str

class CNPJQueryCreate(CNPJQueryBase):
    """Schema para criação de consulta de CNPJ"""
    pass

class CNPJQuery(CNPJQueryBase):
    """Schema completo de consulta de CNPJ"""
    id: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class CNPJDataBase(BaseModel):
    """Schema base para dados de CNPJ"""
    cnpj: str

class CNPJData(CNPJDataBase):
    """Schema resumido de dados de CNPJ"""
    id: int
    company_name: Optional[str] = None
    trade_name: Optional[str] = None
    status: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    simples_nacional: Optional[bool] = None
    simples_nacional_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class CNPJDataFull(CNPJData):
    """Schema completo de dados de CNPJ, incluindo dados brutos"""
    raw_data: Dict[str, Any]

class CNPJUpload(BaseModel):
    """Schema para upload de lista de CNPJs"""
    cnpjs: List[str]

class CNPJStatus(BaseModel):
    """Schema para status de consulta de CNPJ"""
    cnpj: str
    status: str
    error_message: Optional[str] = None

class CNPJBatchStatus(BaseModel):
    """Schema para status de lote de consultas de CNPJ"""
    total: int
    completed: int
    processing: int
    error: int
    queued: int
    rate_limited: int = 0
    results: List[CNPJStatus]
