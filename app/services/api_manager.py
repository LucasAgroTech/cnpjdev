import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import asyncio

from app.services.receitaws import ReceitaWSClient
from app.services.cnpjws import CNPJWSClient
from app.services.cnpja_open import CNPJaOpenClient
from app.services.adaptive_rate_limiter import AdaptiveRateLimiter
from app.config import (
    API_RATE_LIMIT_SAFETY_FACTOR,
    API_RATE_LIMIT_SAFETY_FACTOR_LOW,
    API_RATE_LIMIT_SAFETY_FACTOR_HIGH,
    API_RATE_LIMIT_THRESHOLD
)

logger = logging.getLogger(__name__)

class APIManager:
    """
    Gerenciador de APIs para consulta de CNPJ
    
    Gerencia múltiplas APIs para consulta de CNPJ, distribuindo as requisições
    entre elas para maximizar o número de consultas por minuto.
    
    Implementa um sistema de controle de taxa adaptativo baseado em Token Bucket
    para garantir que os limites individuais das APIs sejam respeitados enquanto
    maximiza o throughput total.
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
        self.api_map = {}  # Mapeamento de nome para instância da API
        
        # Inicializa o gerenciador de limites de taxa adaptativo
        self.rate_limiter = AdaptiveRateLimiter()
        
        # Inicializa os clientes de API habilitados
        if receitaws_enabled:
            self.receitaws_client = ReceitaWSClient(requests_per_minute=receitaws_requests_per_minute)
            self.apis.append(self.receitaws_client)
            self.api_names.append("ReceitaWS")
            self.api_map["ReceitaWS"] = self.receitaws_client
            
            # Registra a API no gerenciador de limites de taxa
            self.rate_limiter.register_api(
                "ReceitaWS", 
                receitaws_requests_per_minute
            )
            
            logger.info(f"API ReceitaWS habilitada com {receitaws_requests_per_minute} req/min")
        else:
            self.receitaws_client = None
            
        if cnpjws_enabled:
            self.cnpjws_client = CNPJWSClient(requests_per_minute=cnpjws_requests_per_minute)
            self.apis.append(self.cnpjws_client)
            self.api_names.append("CNPJ.ws")
            self.api_map["CNPJ.ws"] = self.cnpjws_client
            
            # Registra a API no gerenciador de limites de taxa
            self.rate_limiter.register_api(
                "CNPJ.ws", 
                cnpjws_requests_per_minute
            )
            
            logger.info(f"API CNPJ.ws habilitada com {cnpjws_requests_per_minute} req/min")
        else:
            self.cnpjws_client = None
            
        if cnpja_open_enabled:
            self.cnpja_open_client = CNPJaOpenClient(requests_per_minute=cnpja_open_requests_per_minute)
            self.apis.append(self.cnpja_open_client)
            self.api_names.append("CNPJa Open")
            self.api_map["CNPJa Open"] = self.cnpja_open_client
            
            # Registra a API no gerenciador de limites de taxa
            self.rate_limiter.register_api(
                "CNPJa Open", 
                cnpja_open_requests_per_minute
            )
            
            logger.info(f"API CNPJa Open habilitada com {cnpja_open_requests_per_minute} req/min")
        else:
            self.cnpja_open_client = None
            
        if not self.apis:
            raise ValueError("Pelo menos uma API deve estar habilitada")
            
        logger.info(f"Gerenciador de APIs inicializado com {len(self.apis)} APIs: {', '.join(self.api_names)}")
    
    def can_use_api(self, api_name: str) -> bool:
        """
        Verifica se uma API pode ser usada no momento, utilizando o gerenciador
        de limites de taxa adaptativo.
        
        Args:
            api_name: Nome da API a verificar
            
        Returns:
            True se a API pode ser usada, False caso contrário
        """
        return self.rate_limiter.can_use_api(api_name)
    
    def mark_api_used(self, api_name: str, success: bool = True) -> None:
        """
        Marca uma API como usada, atualizando estatísticas no gerenciador
        de limites de taxa adaptativo.
        
        Args:
            api_name: Nome da API usada
            success: Se a requisição foi bem-sucedida
        """
        self.rate_limiter.mark_api_used(api_name, success)
    
    def mark_api_rate_limited(self, api_name: str) -> None:
        """
        Marca uma API como tendo atingido seu limite de requisições,
        colocando-a em cooldown por um período definido.
        
        Args:
            api_name: Nome da API que atingiu o limite
        """
        self.rate_limiter.mark_api_rate_limited(api_name)
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Tuple[Dict[str, Any], str]:
        """
        Consulta informações sobre um CNPJ usando uma das APIs disponíveis
        
        Utiliza o gerenciador de limites de taxa adaptativo para selecionar a melhor API
        disponível no momento, respeitando os limites individuais de cada API.
        
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
        
        # Tenta até 3 vezes, com timeout de 30 segundos para cada tentativa
        max_attempts = 3
        attempt = 0
        last_error = None
        
        while attempt < max_attempts:
            attempt += 1
            
            try:
                # Aguarda até que uma API esteja disponível (com timeout)
                api_name = await self.rate_limiter.wait_for_api_availability(timeout=30.0)
                
                if api_name is None:
                    logger.warning(f"Timeout aguardando API disponível para CNPJ {cnpj_clean} (tentativa {attempt}/{max_attempts})")
                    continue
                
                # Obtém a instância da API
                api = self.api_map.get(api_name)
                if api is None:
                    logger.error(f"API {api_name} selecionada pelo rate limiter, mas não encontrada no mapeamento")
                    continue
                
                logger.info(f"Tentando consultar CNPJ {cnpj_clean} usando API {api_name} (tentativa {attempt}/{max_attempts})")
                
                # Marca a API como usada antes de fazer a requisição
                self.mark_api_used(api_name)
                
                # Faz a requisição
                result = await api.query_cnpj(cnpj_clean, include_simples)
                
                # Marca a API como usada com sucesso
                self.mark_api_used(api_name, success=True)
                
                logger.info(f"CNPJ {cnpj_clean} consultado com sucesso usando API {api_name}")
                return result, api_name
                
            except Exception as e:
                error_str = str(e)
                logger.warning(f"Erro ao consultar CNPJ {cnpj_clean} usando API {api_name}: {error_str}")
                
                # Verifica se é um erro de limite de requisições
                if api_name and ("Limite de requisições excedido" in error_str or "429" in error_str):
                    self.mark_api_rate_limited(api_name)
                
                last_error = e
                # Continua para a próxima tentativa
                continue
        
        # Se chegou aqui, todas as tentativas falharam
        error_message = f"Todas as tentativas falharam ao consultar CNPJ {cnpj_clean}"
        if last_error:
            error_message += f": {str(last_error)}"
            
        logger.error(error_message)
        raise Exception(error_message)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual do gerenciador de APIs, incluindo informações
        detalhadas sobre o uso de cada API e o estado do gerenciador de limites de taxa.
        
        Returns:
            Dicionário com informações sobre o estado atual
        """
        return {
            "apis_enabled": self.api_names,
            "rate_limiter": self.rate_limiter.get_status()
        }
