import logging
import random
from typing import Dict, List, Optional, Any, Tuple
import asyncio

from app.services.receitaws import ReceitaWSClient
from app.services.cnpjws import CNPJWSClient

logger = logging.getLogger(__name__)

class APIManager:
    """
    Gerenciador de APIs para consulta de CNPJ
    
    Gerencia múltiplas APIs para consulta de CNPJ, distribuindo as requisições
    entre elas para maximizar o número de consultas por minuto.
    """
    
    def __init__(
        self, 
        receitaws_enabled: bool = True,
        cnpjws_enabled: bool = True,
        receitaws_requests_per_minute: int = 3,
        cnpjws_requests_per_minute: int = 3
    ):
        """
        Inicializa o gerenciador de APIs
        
        Args:
            receitaws_enabled: Se a API ReceitaWS está habilitada
            cnpjws_enabled: Se a API CNPJ.ws está habilitada
            receitaws_requests_per_minute: Máximo de requisições por minuto para ReceitaWS
            cnpjws_requests_per_minute: Máximo de requisições por minuto para CNPJ.ws
        """
        self.apis = []
        self.api_names = []
        
        # Inicializa os clientes de API habilitados
        if receitaws_enabled:
            self.receitaws_client = ReceitaWSClient(requests_per_minute=receitaws_requests_per_minute)
            self.apis.append(self.receitaws_client)
            self.api_names.append("ReceitaWS")
            logger.info(f"API ReceitaWS habilitada com {receitaws_requests_per_minute} req/min")
        else:
            self.receitaws_client = None
            
        if cnpjws_enabled:
            self.cnpjws_client = CNPJWSClient(requests_per_minute=cnpjws_requests_per_minute)
            self.apis.append(self.cnpjws_client)
            self.api_names.append("CNPJ.ws")
            logger.info(f"API CNPJ.ws habilitada com {cnpjws_requests_per_minute} req/min")
        else:
            self.cnpjws_client = None
            
        if not self.apis:
            raise ValueError("Pelo menos uma API deve estar habilitada")
            
        logger.info(f"Gerenciador de APIs inicializado com {len(self.apis)} APIs: {', '.join(self.api_names)}")
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Tuple[Dict[str, Any], str]:
        """
        Consulta informações sobre um CNPJ usando uma das APIs disponíveis
        
        Tenta cada API em ordem aleatória até obter sucesso ou esgotar todas as opções.
        
        Args:
            cnpj: CNPJ a consultar
            include_simples: Se deve incluir dados do Simples Nacional
            
        Returns:
            Tuple contendo os dados do CNPJ como um dicionário e o nome da API usada
        """
        # Limpa o CNPJ (remove caracteres não numéricos)
        cnpj_clean = ''.join(filter(str.isdigit, cnpj))
        
        if len(cnpj_clean) != 14:
            raise ValueError(f"CNPJ inválido: {cnpj}. Deve conter 14 dígitos numéricos.")
        
        # Embaralha a ordem das APIs para distribuir as requisições
        apis_to_try = list(zip(self.apis, self.api_names))
        random.shuffle(apis_to_try)
        
        last_error = None
        
        # Tenta cada API até obter sucesso
        for api, api_name in apis_to_try:
            try:
                logger.info(f"Tentando consultar CNPJ {cnpj_clean} usando API {api_name}")
                result = await api.query_cnpj(cnpj_clean, include_simples)
                logger.info(f"CNPJ {cnpj_clean} consultado com sucesso usando API {api_name}")
                return result, api_name
            except Exception as e:
                logger.warning(f"Erro ao consultar CNPJ {cnpj_clean} usando API {api_name}: {str(e)}")
                last_error = e
                # Continua para a próxima API
                continue
        
        # Se chegou aqui, todas as APIs falharam
        error_message = f"Todas as APIs falharam ao consultar CNPJ {cnpj_clean}"
        if last_error:
            error_message += f": {str(last_error)}"
            
        logger.error(error_message)
        raise Exception(error_message)
