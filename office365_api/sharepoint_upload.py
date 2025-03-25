import os
import sys
import pandas as pd
import io
from pathlib import PurePath
from dotenv import load_dotenv
import logging
from datetime import datetime

# Adicionar o caminho do diretório raiz ao sys.path
load_dotenv()
ROOT = os.getenv('ROOT')
PATH_OFFICE = os.path.abspath(os.path.join(ROOT, 'office365_api'))

# Adiciona o diretório correto ao sys.path
sys.path.append(PATH_OFFICE)

from office365_api.office365_api import SharePoint

logger = logging.getLogger(__name__)

def upload_cnpj_data_to_sharepoint(cnpj_data_list, filename="consulta_cnpjs_apis_publicas.xlsx"):
    """
    Gera um arquivo Excel com os dados de CNPJs e faz upload para o SharePoint
    
    Args:
        cnpj_data_list: Lista de objetos CNPJData
        filename: Nome do arquivo Excel a ser criado no SharePoint
        
    Returns:
        Dicionário com informações sobre o resultado do upload
    """
    logger.info(f"Preparando upload de {len(cnpj_data_list)} CNPJs para o SharePoint")
    
    try:
        # Gera o arquivo Excel em memória
        excel_data = generate_cnpj_excel(cnpj_data_list)
        
        # Salva temporariamente o arquivo
        storage_dir = os.path.join(os.path.dirname(__file__), 'storage', 'upload')
        
        # Garante que o diretório de armazenamento existe
        os.makedirs(storage_dir, exist_ok=True)
        
        temp_file_path = os.path.join(storage_dir, filename)
        with open(temp_file_path, 'wb') as f:
            f.write(excel_data)
        
        # Obtém as configurações do SharePoint do .env
        sharepoint_site = os.getenv('sharepoint_url_site')
        sharepoint_site_name = os.getenv('sharepoint_site_name')
        sharepoint_doc = os.getenv('sharepoint_doc_library')
        
        # Faz upload para o SharePoint
        sharepoint = SharePoint()
        response = sharepoint.upload_file(
            folder_name="",  # Pasta raiz
            sharepoint_site=sharepoint_site,
            sharepoint_site_name=sharepoint_site_name,
            sharepoint_doc=sharepoint_doc,
            file_name=filename,
            content=excel_data
        )
        
        # Remove o arquivo temporário
        os.remove(temp_file_path)
        
        logger.info(f"Upload para SharePoint concluído com sucesso: {filename}")
        return {
            "success": True,
            "message": f"Arquivo {filename} enviado com sucesso para o SharePoint",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro ao fazer upload para SharePoint: {str(e)}")
        return {
            "success": False,
            "message": f"Erro ao fazer upload para SharePoint: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

def generate_cnpj_excel(cnpj_data_list) -> bytes:
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
