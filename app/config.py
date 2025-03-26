import os
from typing import List
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração das APIs
RECEITAWS_ENABLED: bool = os.environ.get("RECEITAWS_ENABLED", "True").lower() == "true"
CNPJWS_ENABLED: bool = os.environ.get("CNPJWS_ENABLED", "True").lower() == "true"
CNPJA_OPEN_ENABLED: bool = os.environ.get("CNPJA_OPEN_ENABLED", "True").lower() == "true"
RECEITAWS_REQUESTS_PER_MINUTE: int = int(os.environ.get("RECEITAWS_REQUESTS_PER_MINUTE", "3"))
CNPJWS_REQUESTS_PER_MINUTE: int = int(os.environ.get("CNPJWS_REQUESTS_PER_MINUTE", "3"))
CNPJA_OPEN_REQUESTS_PER_MINUTE: int = int(os.environ.get("CNPJA_OPEN_REQUESTS_PER_MINUTE", "5"))

# Mantém para compatibilidade
REQUESTS_PER_MINUTE: int = int(os.environ.get("REQUESTS_PER_MINUTE", "3"))

# Configuração de controle de taxa
MAX_CONCURRENT_PROCESSING: int = int(os.environ.get("MAX_CONCURRENT_PROCESSING", "6"))
API_COOLDOWN_AFTER_RATE_LIMIT: int = int(os.environ.get("API_COOLDOWN_AFTER_RATE_LIMIT", "30"))
API_COOLDOWN_MAX: int = int(os.environ.get("API_COOLDOWN_MAX", "300"))
API_RATE_LIMIT_SAFETY_FACTOR: float = float(os.environ.get("API_RATE_LIMIT_SAFETY_FACTOR", "0.9"))
API_RATE_LIMIT_SAFETY_FACTOR_LOW: float = float(os.environ.get("API_RATE_LIMIT_SAFETY_FACTOR_LOW", "0.7"))
API_RATE_LIMIT_SAFETY_FACTOR_HIGH: float = float(os.environ.get("API_RATE_LIMIT_SAFETY_FACTOR_HIGH", "0.8"))
API_RATE_LIMIT_THRESHOLD: int = int(os.environ.get("API_RATE_LIMIT_THRESHOLD", "3"))

# Configuração do banco de dados
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuração da aplicação
APP_NAME: str = "CNPJ Consulta"
APP_DESCRIPTION: str = "Sistema automatizado de consulta de CNPJs via API da ReceitaWS"
APP_VERSION: str = "1.0.0"
DEBUG: bool = os.environ.get("DEBUG", "False").lower() == "true"

# Configuração de persistência
AUTO_RESTART_QUEUE: bool = os.environ.get("AUTO_RESTART_QUEUE", "True").lower() == "true"
MAX_RETRY_ATTEMPTS: int = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))
