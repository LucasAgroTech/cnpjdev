import logging
import random
import time
from typing import Dict, List, Optional, Any, Tuple
import asyncio
from collections import defaultdict

from app.services.receitaws import ReceitaWSClient
from app.services.cnpjws import CNPJWSClient
from app.services.cnpja_open import CNPJaOpenClient

logger = logging.getLogger(__name__)

class APIManager:
    """
    Gerenciador de APIs para consulta de CNPJ
    
    Gerencia múltiplas APIs para consulta de CNPJ, distribuindo as requisições
    entre elas para maximizar o número de consultas por minuto.
    
    Implementa estratégia de distribuição inteligente para garantir que cada API
    seja utilizada até seu limite máximo, priorizando as APIs com maior capacidade
    disponível no momento.
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
            
        if cnpja_open_enabled:
            self.cnpja_open_client = CNPJaOpenClient(requests_per_minute=cnpja_open_requests_per_minute)
            self.apis.append(self.cnpja_open_client)
            self.api_names.append("CNPJa Open")
            logger.info(f"API CNPJa Open habilitada com {cnpja_open_requests_per_minute} req/min")
        else:
            self.cnpja_open_client = None
            
        # Rastreamento de uso de APIs para distribuição inteligente
        self.api_usage = {}
        for api, name in zip(self.apis, self.api_names):
            self.api_usage[name] = {
                "limit": api.requests_per_minute,
                "last_used": 0,
                "usage_count": 0
            }
            
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
        
        # Ordena as APIs por capacidade disponível (mais disponível primeiro)
        apis_to_try = self._get_apis_by_availability()
        
        last_error = None
        
        # Tenta cada API até obter sucesso
        for api, api_name in apis_to_try:
            try:
                logger.info(f"Tentando consultar CNPJ {cnpj_clean} usando API {api_name}")
                result = await api.query_cnpj(cnpj_clean, include_simples)
                
                # Atualiza o rastreamento de uso da API
                now = time.time()
                self.api_usage[api_name]["last_used"] = now
                self.api_usage[api_name]["usage_count"] += 1
                
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
        
    def _get_apis_by_availability(self) -> List[Tuple[Any, str]]:
        """
        Ordena as APIs por disponibilidade atual, priorizando as que têm mais
        capacidade disponível no momento.
        
        Returns:
            Lista de tuplas (api, api_name) ordenada por disponibilidade
        """
        now = time.time()
        apis_with_scores = []
        
        for api, name in zip(self.apis, self.api_names):
            # Calcula quantas requisições foram feitas no último minuto
            usage_info = self.api_usage[name]
            limit = usage_info["limit"]
            last_used = usage_info["last_used"]
            
            # Se a API não foi usada recentemente, ela tem prioridade máxima
            if last_used == 0 or now - last_used > 60:
                score = limit  # Pontuação máxima
            else:
                # Calcula a capacidade disponível com base no tempo desde o último uso
                # e no número de requisições já feitas
                time_factor = min(1.0, (now - last_used) / 60.0)
                available_capacity = limit * time_factor
                score = available_capacity
            
            apis_with_scores.append((api, name, score))
        
        # Ordena por pontuação (maior primeiro)
        apis_with_scores.sort(key=lambda x: x[2], reverse=True)
        
        # Retorna apenas a API e o nome, sem a pontuação
        return [(api, name) for api, name, _ in apis_with_scores]
