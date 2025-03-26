import logging
import random
import time
from typing import Dict, List, Optional, Any, Tuple
import asyncio
from collections import defaultdict

from app.services.receitaws import ReceitaWSClient
from app.services.cnpjws import CNPJWSClient
from app.services.cnpja_open import CNPJaOpenClient
from app.config import API_COOLDOWN_AFTER_RATE_LIMIT, API_RATE_LIMIT_SAFETY_FACTOR

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
            # Aplica fator de segurança para evitar atingir o limite exato
            adjusted_limit = int(api.requests_per_minute * API_RATE_LIMIT_SAFETY_FACTOR)
            if adjusted_limit < 1:
                adjusted_limit = 1
                
            self.api_usage[name] = {
                "limit": api.requests_per_minute,
                "adjusted_limit": adjusted_limit,
                "last_used": 0,
                "usage_count": 0,
                "cooldown_until": 0,  # Timestamp até quando a API deve ser evitada após erro 429
                "requests": []  # Lista de timestamps das últimas requisições
            }
            
        if not self.apis:
            raise ValueError("Pelo menos uma API deve estar habilitada")
            
        logger.info(f"Gerenciador de APIs inicializado com {len(self.apis)} APIs: {', '.join(self.api_names)}")
        logger.info(f"Fator de segurança para limites de API: {API_RATE_LIMIT_SAFETY_FACTOR}")
    
    def can_use_api(self, api_name: str) -> bool:
        """
        Verifica se uma API pode ser usada no momento, considerando seu histórico
        de uso recente e se está em período de cooldown após erro 429.
        
        Args:
            api_name: Nome da API a verificar
            
        Returns:
            True se a API pode ser usada, False caso contrário
        """
        now = time.time()
        usage_info = self.api_usage[api_name]
        
        # Verifica se a API está em cooldown após erro 429
        if now < usage_info["cooldown_until"]:
            cooldown_remaining = int(usage_info["cooldown_until"] - now)
            logger.debug(f"API {api_name} em cooldown por mais {cooldown_remaining}s após erro 429")
            return False
        
        # Remove timestamps mais antigos que 60 segundos
        usage_info["requests"] = [t for t in usage_info["requests"] if now - t < 60]
        
        # Verifica se ainda há capacidade disponível
        adjusted_limit = usage_info["adjusted_limit"]
        current_usage = len(usage_info["requests"])
        
        can_use = current_usage < adjusted_limit
        
        if not can_use:
            logger.debug(f"API {api_name} atingiu limite ajustado de {adjusted_limit} req/min (atual: {current_usage})")
        
        return can_use
    
    def mark_api_used(self, api_name: str) -> None:
        """
        Marca uma API como usada, registrando o timestamp atual
        
        Args:
            api_name: Nome da API usada
        """
        now = time.time()
        self.api_usage[api_name]["requests"].append(now)
        self.api_usage[api_name]["last_used"] = now
        self.api_usage[api_name]["usage_count"] += 1
    
    def mark_api_rate_limited(self, api_name: str) -> None:
        """
        Marca uma API como tendo atingido seu limite de requisições,
        colocando-a em cooldown por um período definido
        
        Args:
            api_name: Nome da API que atingiu o limite
        """
        now = time.time()
        self.api_usage[api_name]["cooldown_until"] = now + API_COOLDOWN_AFTER_RATE_LIMIT
        logger.warning(f"API {api_name} marcada como rate limited, em cooldown por {API_COOLDOWN_AFTER_RATE_LIMIT}s")
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Tuple[Dict[str, Any], str]:
        """
        Consulta informações sobre um CNPJ usando uma das APIs disponíveis
        
        Tenta cada API em ordem de disponibilidade até obter sucesso ou esgotar todas as opções.
        
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
            # Verifica se a API pode ser usada no momento
            if not self.can_use_api(api_name):
                logger.info(f"Pulando API {api_name} para CNPJ {cnpj_clean} devido a controle de taxa")
                continue
                
            try:
                logger.info(f"Tentando consultar CNPJ {cnpj_clean} usando API {api_name}")
                
                # Marca a API como usada antes de fazer a requisição
                self.mark_api_used(api_name)
                
                # Faz a requisição
                result = await api.query_cnpj(cnpj_clean, include_simples)
                
                logger.info(f"CNPJ {cnpj_clean} consultado com sucesso usando API {api_name}")
                return result, api_name
            except Exception as e:
                error_str = str(e)
                logger.warning(f"Erro ao consultar CNPJ {cnpj_clean} usando API {api_name}: {error_str}")
                
                # Verifica se é um erro de limite de requisições
                if "Limite de requisições excedido" in error_str or "429" in error_str:
                    self.mark_api_rate_limited(api_name)
                
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
            
            # Calcula o tempo desde o último uso em segundos
            time_since_last_use = now - last_used if last_used > 0 else float('inf')
            
            # Se a API não foi usada recentemente (mais de 60 segundos), ela tem prioridade máxima
            if time_since_last_use > 60:
                score = limit * 2  # Pontuação máxima com bônus para APIs não usadas recentemente
            else:
                # Calcula a capacidade disponível com base no tempo desde o último uso
                # Quanto mais tempo passou desde o último uso, maior a capacidade disponível
                time_factor = min(1.0, time_since_last_use / 60.0)
                
                # Adiciona um pequeno fator aleatório para evitar que todas as APIs com o mesmo
                # tempo desde o último uso tenham exatamente a mesma pontuação
                random_factor = 0.1 * random.random()
                
                # Calcula a pontuação final
                available_capacity = limit * time_factor
                score = available_capacity + random_factor
                
            logger.debug(f"API {name}: tempo desde último uso = {time_since_last_use:.1f}s, pontuação = {score:.2f}")
            
            apis_with_scores.append((api, name, score))
        
        # Ordena por pontuação (maior primeiro)
        apis_with_scores.sort(key=lambda x: x[2], reverse=True)
        
        # Retorna apenas a API e o nome, sem a pontuação
        return [(api, name) for api, name, _ in apis_with_scores]
