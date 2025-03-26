import logging
import time
import random
from typing import Dict, List, Tuple, Any, Optional
import asyncio
from collections import defaultdict

from app.services.token_bucket import TokenBucket
from app.config import (
    API_RATE_LIMIT_SAFETY_FACTOR_LOW,
    API_RATE_LIMIT_SAFETY_FACTOR_HIGH,
    API_RATE_LIMIT_THRESHOLD,
    API_COOLDOWN_AFTER_RATE_LIMIT,
    API_COOLDOWN_MAX
)

logger = logging.getLogger(__name__)

class AdaptiveRateLimiter:
    """
    Gerenciador adaptativo de limites de taxa para múltiplas APIs.
    
    Implementa um sistema de controle de taxa baseado em Token Bucket
    com ajuste dinâmico de fatores de segurança e distribuição inteligente
    de requisições entre as APIs disponíveis.
    """
    
    def __init__(self):
        """
        Inicializa o gerenciador de limites de taxa.
        """
        self.buckets = {}  # Dicionário de token buckets por nome de API
        self.api_info = {}  # Informações adicionais sobre cada API
        self.last_global_request = 0  # Timestamp da última requisição global
        self.global_interval = 0  # Intervalo mínimo entre requisições globais
        self.total_capacity = 0  # Capacidade total de todas as APIs (req/min)
    
    def register_api(
        self, 
        name: str, 
        requests_per_minute: int,
        initial_safety_factor: float = None
    ) -> None:
        """
        Registra uma API no gerenciador de limites de taxa.
        
        Args:
            name: Nome da API
            requests_per_minute: Limite de requisições por minuto
            initial_safety_factor: Fator de segurança inicial (se None, usa o padrão)
        """
        # Determina o fator de segurança inicial
        if initial_safety_factor is None:
            # Se a API tem um limite baixo, usa um fator de segurança mais conservador
            if requests_per_minute <= API_RATE_LIMIT_THRESHOLD:
                safety_factor = API_RATE_LIMIT_SAFETY_FACTOR_LOW
            else:
                safety_factor = API_RATE_LIMIT_SAFETY_FACTOR_HIGH
        else:
            safety_factor = initial_safety_factor
        
        # Converte requisições por minuto para tokens por segundo
        refill_rate = requests_per_minute / 60.0
        
        # Cria o token bucket para esta API
        self.buckets[name] = TokenBucket(
            name=name,
            capacity=requests_per_minute,
            refill_rate=refill_rate,
            safety_factor=safety_factor
        )
        
        # Armazena informações adicionais sobre a API
        self.api_info[name] = {
            "requests_per_minute": requests_per_minute,
            "cooldown_until": 0,  # Timestamp até quando a API deve ser evitada após erro 429
            "error_count": 0,  # Contador de erros para ajuste dinâmico
            "last_used": 0,  # Timestamp da última vez que a API foi usada
            "success_count": 0,  # Contador de sucessos para ajuste dinâmico
        }
        
        # Atualiza a capacidade total e o intervalo global
        self.total_capacity += requests_per_minute
        self.global_interval = 60.0 / self.total_capacity
        
        logger.info(f"API {name} registrada: {requests_per_minute} req/min, "
                   f"fator de segurança={safety_factor:.2f}")
    
    def can_use_api(self, api_name: str) -> bool:
        """
        Verifica se uma API pode ser usada no momento.
        
        Args:
            api_name: Nome da API a verificar
            
        Returns:
            True se a API pode ser usada, False caso contrário
        """
        # Verifica se a API está registrada
        if api_name not in self.buckets:
            logger.warning(f"Tentativa de verificar API não registrada: {api_name}")
            return False
        
        # Verifica se a API está em cooldown após erro 429
        now = time.time()
        if now < self.api_info[api_name]["cooldown_until"]:
            cooldown_remaining = int(self.api_info[api_name]["cooldown_until"] - now)
            logger.debug(f"API {api_name} em cooldown por mais {cooldown_remaining}s após erro 429")
            return False
        
        # Verifica se há tokens disponíveis no bucket
        return self.buckets[api_name].consume(1.0)
    
    def mark_api_used(self, api_name: str, success: bool = True) -> None:
        """
        Marca uma API como usada, atualizando estatísticas.
        
        Args:
            api_name: Nome da API usada
            success: Se a requisição foi bem-sucedida
        """
        if api_name not in self.api_info:
            logger.warning(f"Tentativa de marcar API não registrada como usada: {api_name}")
            return
        
        now = time.time()
        self.api_info[api_name]["last_used"] = now
        self.last_global_request = now
        
        if success:
            self.api_info[api_name]["success_count"] += 1
            
            # Ajusta o fator de segurança com base no histórico de sucesso
            self._adjust_safety_factor(api_name)
    
    def mark_api_rate_limited(self, api_name: str) -> None:
        """
        Marca uma API como tendo atingido seu limite de requisições,
        colocando-a em cooldown por um período definido.
        
        Args:
            api_name: Nome da API que atingiu o limite
        """
        if api_name not in self.api_info:
            logger.warning(f"Tentativa de marcar API não registrada como rate limited: {api_name}")
            return
        
        now = time.time()
        
        # Incrementa o contador de erros
        self.api_info[api_name]["error_count"] += 1
        self.buckets[api_name].mark_error()
        
        # Calcula o tempo de cooldown com base no número de erros
        # Usa backoff exponencial com limite máximo
        error_count = self.api_info[api_name]["error_count"]
        cooldown_time = min(API_COOLDOWN_AFTER_RATE_LIMIT * (2 ** (error_count - 1)), API_COOLDOWN_MAX)
        
        self.api_info[api_name]["cooldown_until"] = now + cooldown_time
        
        # Ajusta o fator de segurança para ser mais conservador
        current_factor = self.buckets[api_name].safety_factor
        new_factor = max(current_factor * 0.8, API_RATE_LIMIT_SAFETY_FACTOR_LOW)
        self.buckets[api_name].adjust_safety_factor(new_factor)
        
        logger.warning(f"API {api_name} marcada como rate limited, em cooldown por {cooldown_time}s, "
                      f"fator de segurança ajustado para {new_factor:.2f}")
    
    def _adjust_safety_factor(self, api_name: str) -> None:
        """
        Ajusta o fator de segurança com base no histórico de sucesso/erro.
        
        Args:
            api_name: Nome da API para ajustar
        """
        # Só ajusta a cada 10 sucessos
        if self.api_info[api_name]["success_count"] % 10 != 0:
            return
        
        bucket = self.buckets[api_name]
        current_factor = bucket.safety_factor
        error_count = self.api_info[api_name]["error_count"]
        
        # Se não houve erros recentes, aumenta gradualmente o fator de segurança
        if error_count == 0:
            # Aumenta em 5%, mas não ultrapassa o limite superior
            new_factor = min(current_factor * 1.05, API_RATE_LIMIT_SAFETY_FACTOR_HIGH)
            
            # Só aplica se a mudança for significativa
            if new_factor > current_factor + 0.01:
                bucket.adjust_safety_factor(new_factor)
                logger.info(f"Fator de segurança para {api_name} aumentado para {new_factor:.2f} "
                           f"devido a histórico de sucesso")
    
    def get_best_api(self) -> Optional[str]:
        """
        Seleciona a melhor API para usar no momento, com base na disponibilidade
        e no histórico de uso.
        
        Returns:
            Nome da melhor API disponível, ou None se nenhuma estiver disponível
        """
        now = time.time()
        
        # Verifica o intervalo global para manter a taxa total
        time_since_last_global = now - self.last_global_request
        if time_since_last_global < self.global_interval:
            # Ainda não é hora de fazer outra requisição global
            return None
        
        # Filtra APIs que não estão em cooldown
        available_apis = [
            name for name in self.buckets.keys()
            if now >= self.api_info[name]["cooldown_until"]
        ]
        
        if not available_apis:
            logger.warning("Nenhuma API disponível no momento (todas em cooldown)")
            return None
        
        # Calcula pontuações para cada API disponível
        api_scores = []
        
        for name in available_apis:
            bucket = self.buckets[name]
            bucket.update()  # Atualiza o bucket para refletir o estado atual
            
            # Se não há tokens disponíveis, pula esta API
            if bucket.tokens < 1.0:
                continue
            
            # Calcula o tempo desde o último uso
            time_since_last_use = now - self.api_info[name]["last_used"] if self.api_info[name]["last_used"] > 0 else float('inf')
            
            # Calcula a pontuação com base em vários fatores
            # 1. Número de tokens disponíveis (normalizado pela capacidade)
            token_score = bucket.tokens / bucket.capacity
            
            # 2. Tempo desde o último uso (normalizado, máximo de 60 segundos)
            time_score = min(time_since_last_use / 60.0, 1.0)
            
            # 3. Fator de erro (inversamente proporcional ao número de erros)
            error_factor = 1.0 / (1.0 + self.api_info[name]["error_count"])
            
            # 4. Pequeno fator aleatório para evitar empates
            random_factor = 0.05 * random.random()
            
            # Pontuação final: combinação ponderada dos fatores
            # Dá mais peso ao número de tokens disponíveis e ao tempo desde o último uso
            final_score = (0.4 * token_score) + (0.4 * time_score) + (0.15 * error_factor) + random_factor
            
            api_scores.append((name, final_score))
            
            logger.debug(f"API {name}: tokens={bucket.tokens:.2f}/{bucket.capacity}, "
                        f"último uso={time_since_last_use:.1f}s atrás, "
                        f"erros={self.api_info[name]['error_count']}, "
                        f"pontuação={final_score:.3f}")
        
        if not api_scores:
            logger.warning("Nenhuma API com tokens disponíveis no momento")
            return None
        
        # Seleciona a API com a maior pontuação
        api_scores.sort(key=lambda x: x[1], reverse=True)
        selected_api = api_scores[0][0]
        
        logger.debug(f"API selecionada: {selected_api} (pontuação: {api_scores[0][1]:.3f})")
        return selected_api
    
    async def wait_for_api_availability(self, timeout: float = 30.0) -> Optional[str]:
        """
        Aguarda até que uma API esteja disponível para uso, com timeout.
        
        Args:
            timeout: Tempo máximo de espera em segundos
            
        Returns:
            Nome da API disponível, ou None se o timeout for atingido
        """
        start_time = time.time()
        
        while True:
            # Verifica se alguma API está disponível agora
            api_name = self.get_best_api()
            if api_name is not None:
                return api_name
            
            # Verifica se o timeout foi atingido
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout de {timeout}s atingido aguardando API disponível")
                return None
            
            # Calcula o menor tempo de espera entre todas as APIs
            min_wait_time = float('inf')
            
            for name, bucket in self.buckets.items():
                # Pula APIs em cooldown
                if time.time() < self.api_info[name]["cooldown_until"]:
                    continue
                
                # Calcula o tempo de espera para esta API
                wait_time = bucket.get_wait_time(1.0)
                min_wait_time = min(min_wait_time, wait_time)
            
            # Se não conseguiu calcular um tempo de espera válido, usa um valor padrão
            if min_wait_time == float('inf') or min_wait_time <= 0:
                min_wait_time = self.global_interval
            
            # Adiciona um pequeno buffer para evitar verificações muito frequentes
            wait_time = min(min_wait_time + 0.1, 1.0)
            
            logger.debug(f"Aguardando {wait_time:.2f}s por API disponível")
            await asyncio.sleep(wait_time)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual do gerenciador de limites de taxa.
        
        Returns:
            Dicionário com informações sobre o estado atual
        """
        status = {
            "total_capacity": self.total_capacity,
            "global_interval": self.global_interval,
            "apis": {}
        }
        
        for name, bucket in self.buckets.items():
            api_status = bucket.get_status()
            api_status.update({
                "cooldown_until": self.api_info[name]["cooldown_until"],
                "cooldown_remaining": max(0, self.api_info[name]["cooldown_until"] - time.time()),
                "error_count": self.api_info[name]["error_count"],
                "success_count": self.api_info[name]["success_count"],
                "last_used": self.api_info[name]["last_used"],
                "time_since_last_use": time.time() - self.api_info[name]["last_used"] if self.api_info[name]["last_used"] > 0 else float('inf')
            })
            
            status["apis"][name] = api_status
        
        return status
