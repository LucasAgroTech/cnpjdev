import pandas as pd
from fastapi import UploadFile, HTTPException
from typing import List
import io
import logging
from app.models.database import CNPJData

logger = logging.getLogger(__name__)

async def process_cnpj_file(file: UploadFile) -> List[str]:
    """
    Processa um arquivo enviado contendo CNPJs
    
    Args:
        file: Arquivo enviado (CSV ou Excel)
        
    Returns:
        Lista de CNPJs extraídos do arquivo
    """
    logger.info(f"Processando arquivo: {file.filename}")
    
    # Verifica a extensão do arquivo
    if file.filename.endswith('.csv'):
        df = await read_csv(file)
    elif file.filename.endswith(('.xlsx', '.xls')):
        df = await read_excel(file)
    else:
        logger.error(f"Formato de arquivo não suportado: {file.filename}")
        raise HTTPException(
            status_code=400, 
            detail="Formato de arquivo não suportado. Por favor, envie um arquivo CSV ou Excel."
        )
    
    # Encontra a coluna de CNPJ
    cnpj_columns = [col for col in df.columns if 'cnpj' in str(col).lower()]
    
    if not cnpj_columns:
        logger.warning("Nenhuma coluna com 'cnpj' no nome encontrada, usando a primeira coluna")
        # Se nenhuma coluna tiver 'cnpj' no nome, usa a primeira coluna
        if len(df.columns) == 0:
            raise HTTPException(status_code=400, detail="Arquivo vazio ou sem colunas válidas.")
        cnpj_column = df.columns[0]
    else:
        cnpj_column = cnpj_columns[0]
    
    # Extrai CNPJs e limpa
    logger.info(f"Usando coluna '{cnpj_column}' para extrair CNPJs")
    cnpjs = df[cnpj_column].astype(str).tolist()
    
    # Remove caracteres não numéricos e filtra valores vazios
    cleaned_cnpjs = [''.join(filter(str.isdigit, cnpj)) for cnpj in cnpjs]
    valid_cnpjs = [cnpj for cnpj in cleaned_cnpjs if len(cnpj) == 14]  # CNPJ tem 14 dígitos
    
    if not valid_cnpjs:
        logger.error("Nenhum CNPJ válido encontrado no arquivo")
        raise HTTPException(status_code=400, detail="Nenhum CNPJ válido encontrado no arquivo.")
    
    logger.info(f"Encontrados {len(valid_cnpjs)} CNPJs válidos no arquivo")
    return valid_cnpjs

async def read_csv(file: UploadFile) -> pd.DataFrame:
    """
    Lê um arquivo CSV em um DataFrame pandas
    
    Args:
        file: Arquivo CSV enviado
        
    Returns:
        DataFrame contendo os dados do CSV
    """
    content = await file.read()
    try:
        # Tenta várias codificações comuns
        for encoding in ['utf-8', 'latin1', 'iso-8859-1']:
            try:
                return pd.read_csv(io.BytesIO(content), encoding=encoding)
            except UnicodeDecodeError:
                continue
        
        # Se todas as codificações falharem, tenta sem especificar
        return pd.read_csv(io.BytesIO(content))
    except Exception as e:
        logger.error(f"Erro ao ler arquivo CSV: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo CSV: {str(e)}")

async def read_excel(file: UploadFile) -> pd.DataFrame:
    """
    Lê um arquivo Excel em um DataFrame pandas
    
    Args:
        file: Arquivo Excel enviado
        
    Returns:
        DataFrame contendo os dados do Excel
    """
    content = await file.read()
    try:
        return pd.read_excel(io.BytesIO(content))
    except Exception as e:
        logger.error(f"Erro ao ler arquivo Excel: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Erro ao ler arquivo Excel: {str(e)}")

def generate_cnpj_excel(cnpj_data_list: List[CNPJData]) -> bytes:
    """
    Gera um arquivo Excel a partir de uma lista de dados de CNPJ
    
    Args:
        cnpj_data_list: Lista de objetos CNPJData
        
    Returns:
        Conteúdo do arquivo Excel em bytes
    """
    logger.info(f"Gerando Excel com {len(cnpj_data_list)} CNPJs")
    
    # Cria um DataFrame com os dados
    data = []
    for cnpj_data in cnpj_data_list:
        data.append({
            'CNPJ': cnpj_data.cnpj,
            'Razão Social': cnpj_data.company_name,
            'Nome Fantasia': cnpj_data.trade_name,
            'Situação': cnpj_data.status,
            'Endereço': cnpj_data.address,
            'Cidade': cnpj_data.city,
            'Estado': cnpj_data.state,
            'CEP': cnpj_data.zip_code,
            'Email': cnpj_data.email,
            'Telefone': cnpj_data.phone,
            'Simples Nacional': 'Sim' if cnpj_data.simples_nacional else 'Não',
            'Data de Opção Simples': cnpj_data.simples_nacional_date,
            'Data de Consulta': cnpj_data.updated_at
        })
    
    df = pd.DataFrame(data)
    
    # Cria um buffer para o Excel
    output = io.BytesIO()
    
    try:
        # Salva o DataFrame como Excel no buffer
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='CNPJs', index=False)
            
            # Ajusta largura das colunas
            worksheet = writer.sheets['CNPJs']
            for i, col in enumerate(df.columns):
                max_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_width)
        
        # Retorna o conteúdo do buffer
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Erro ao gerar Excel: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar Excel: {str(e)}")
