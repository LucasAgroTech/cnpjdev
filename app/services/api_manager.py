import logging
import random
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import time

from app.services.receitaws import ReceitaWSClient
from app.services.cnpjws import CNPJWSClient
from app.services.cnpja_open import CNPJaOpenClient

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
        cnpja_open_enabled: bool = True,
        receitaws_requests_per_minute: int = 3,
        cnpjws_requests_per_minute: int = 3,
        cnpja_open_requests_per_minute: int = 5
    ):
        """
        Inicializa o gerenciador de APIs
        
        Args:
            receitaws_enabled: Se a API ReceitaWS está habilitada
            cnpjws_enabled: Se a API CNPJ.ws está habilitada
            cnpja_open_enabled: Se a API CNPJa Open está habilitada
            receitaws_requests_per_minute: Máximo de requisições por minuto para ReceitaWS
            cnpjws_requests_per_minute: Máximo de requisições por minuto para CNPJ.ws
            cnpja_open_requests_per_minute: Máximo de requisições por minuto para CNPJa Open
        """
        self.apis = []
        self.api_names = []
        self.api_weights = []
        self.current_api_index = 0
        self._last_api_rotation = time.time()
        
        # Inicializa os clientes de API habilitados
        if receitaws_enabled:
            self.receitaws_client = ReceitaWSClient(requests_per_minute=receitaws_requests_per_minute)
            self.apis.append(self.receitaws_client)
            self.api_names.append("ReceitaWS")
            self.api_weights.append(receitaws_requests_per_minute)
            logger.info(f"API ReceitaWS habilitada com {receitaws_requests_per_minute} req/min")
        else:
            self.receitaws_client = None
            
        if cnpjws_enabled:
            self.cnpjws_client = CNPJWSClient(requests_per_minute=cnpjws_requests_per_minute)
            self.apis.append(self.cnpjws_client)
            self.api_names.append("CNPJ.ws")
            self.api_weights.append(cnpjws_requests_per_minute)
            logger.info(f"API CNPJ.ws habilitada com {cnpjws_requests_per_minute} req/min")
        else:
            self.cnpjws_client = None
            
        if cnpja_open_enabled:
            self.cnpja_open_client = CNPJaOpenClient(requests_per_minute=cnpja_open_requests_per_minute)
            self.apis.append(self.cnpja_open_client)
            self.api_names.append("CNPJa Open")
            self.api_weights.append(cnpja_open_requests_per_minute)
            logger.info(f"API CNPJa Open habilitada com {cnpja_open_requests_per_minute} req/min")
        else:
            self.cnpja_open_client = None
            
        if not self.apis:
            raise ValueError("Pelo menos uma API deve estar habilitada")
            
        # Calcula o total de requisições por minuto
        self.total_requests_per_minute = sum(self.api_weights)
        
        logger.info(f"Gerenciador de APIs inicializado com {len(self.apis)} APIs: {', '.join(self.api_names)}")
        logger.info(f"Total de requisições por minuto: {self.total_requests_per_minute}")
    
    def _get_next_api(self) -> Tuple[Any, str]:
        """
        Obtém a próxima API a ser usada, usando um algoritmo de rodízio ponderado
        
        Returns:
            Tuple contendo a API e seu nome
        """
        # Verifica se é hora de rotacionar as APIs (a cada 5 segundos)
        current_time = time.time()
        if current_time - self._last_api_rotation > 5:
            # Embaralha as APIs para evitar padrões previsíveis
            apis_with_names = list(zip(self.apis, self.api_names, self.api_weights))
            random.shuffle(apis_with_names)
            self.apis, self.api_names, self.api_weights = zip(*apis_with_names)
            self.apis = list(self.apis)
            self.api_names = list(self.api_names)
            self.api_weights = list(self.api_weights)
            self._last_api_rotation = current_time
        
        # Seleciona a próxima API com base no índice atual
        api = self.apis[self.current_api_index]
        api_name = self.api_names[self.current_api_index]
        
        # Atualiza o índice para a próxima chamada
        self.current_api_index = (self.current_api_index + 1) % len(self.apis)
        
        return api, api_name
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Tuple[Dict[str, Any], str]:
        """
        Consulta informações sobre um CNPJ usando uma das APIs disponíveis
        
        Usa um algoritmo de rodízio para distribuir as requisições entre as APIs,
        respeitando os limites de cada uma.
        
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
        
        # Obtém a próxima API a ser usada
        api, api_name = self._get_next_api()
        
        try:
            logger.info(f"Consultando CNPJ {cnpj_clean} usando API {api_name}")
            result = await api.query_cnpj(cnpj_clean, include_simples)
            logger.info(f"CNPJ {cnpj_clean} consultado com sucesso usando API {api_name}")
            return result, api_name
        except Exception as e:
            logger.warning(f"Erro ao consultar CNPJ {cnpj_clean} usando API {api_name}: {str(e)}")
            
            # Em caso de falha, tenta com as outras APIs
            apis_tried = [api_name]
            
            for i in range(len(self.apis) - 1):
                try:
                    # Obtém a próxima API
                    next_api, next_api_name = self._get_next_api()
                    
                    # Evita tentar a mesma API novamente
                    if next_api_name in apis_tried:
                        continue
                    
                    apis_tried.append(next_api_name)
                    
                    logger.info(f"Tentando consultar CNPJ {cnpj_clean} usando API alternativa {next_api_name}")
                    result = await next_api.query_cnpj(cnpj_clean, include_simples)
                    logger.info(f"CNPJ {cnpj_clean} consultado com sucesso usando API alternativa {next_api_name}")
                    return result, next_api_name
                except Exception as e2:
                    logger.warning(f"Erro ao consultar CNPJ {cnpj_clean} usando API alternativa {next_api_name}: {str(e2)}")
                    continue
            
            # Se chegou aqui, todas as APIs falharam
            error_message = f"Todas as APIs falharam ao consultar CNPJ {cnpj_clean}: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
