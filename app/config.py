import os
from typing import List
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração da API
REQUESTS_PER_MINUTE: int = int(os.environ.get("REQUESTS_PER_MINUTE", "3"))

# Configuração do banco de dados
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuração da aplicação
APP_NAME: str = "CNPJ Consulta"
APP_DESCRIPTION: str = "Sistema automatizado de consulta de CNPJs via API da ReceitaWS"
APP_VERSION: str = "1.0.0"
DEBUG: bool = os.environ.get("DEBUG", "False").lower() == "true"
