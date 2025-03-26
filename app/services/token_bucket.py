import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TokenBucket:
    """
    Implementação do algoritmo Token Bucket para controle de taxa de requisições.
    
    O Token Bucket é um algoritmo usado para controlar a taxa na qual um processo
    pode consumir recursos. Neste caso, é usado para controlar a taxa de requisições
    para uma API específica.
    
    Cada bucket é preenchido com tokens a uma taxa constante (refill_rate).
    Quando uma requisição é feita, um token é consumido do bucket.
    Se não houver tokens disponíveis, a requisição é rejeitada.
    """
    
    def __init__(
        self, 
        name: str, 
        capacity: float, 
        refill_rate: float, 
        safety_factor: float = 1.0,
        initial_tokens: float = None
    ):
        """
        Inicializa um novo Token Bucket.
        
        Args:
            name: Nome do bucket (geralmente o nome da API)
            capacity: Capacidade máxima do bucket (número máximo de tokens)
            refill_rate: Taxa de preenchimento (tokens por segundo)
            safety_factor: Fator de segurança para reduzir a capacidade efetiva (0.0 a 1.0)
            initial_tokens: Número inicial de tokens (se None, usa capacity * safety_factor)
        """
        self.name = name
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens por segundo
        self.safety_factor = safety_factor
        
        # Capacidade efetiva após aplicar o fator de segurança
        self.effective_capacity = capacity * safety_factor
        
        # Inicializa com a capacidade efetiva ou o valor especificado
        self.tokens = initial_tokens if initial_tokens is not None else self.effective_capacity
        
        # Timestamp da última atualização
        self.last_update = time.time()
        
        # Estatísticas
        self.stats = {
            "requests_allowed": 0,
            "requests_rejected": 0,
            "total_tokens_consumed": 0,
            "last_allowed": 0,
            "last_rejected": 0,
            "error_count": 0
        }
        
        logger.info(f"Token Bucket para {name} inicializado: capacidade={capacity}, "
                   f"taxa={refill_rate} tokens/s, fator de segurança={safety_factor}")
    
    def update(self) -> None:
        """
        Atualiza o número de tokens no bucket com base no tempo decorrido
        desde a última atualização.
        """
        now = time.time()
        time_passed = now - self.last_update
        self.last_update = now
        
        # Calcula quantos tokens adicionar com base no tempo decorrido
        new_tokens = time_passed * self.refill_rate
        
        # Atualiza o número de tokens, sem exceder a capacidade efetiva
        self.tokens = min(self.effective_capacity, self.tokens + new_tokens)
    
    def consume(self, tokens: float = 1.0) -> bool:
        """
        Tenta consumir tokens do bucket.
        
        Args:
            tokens: Número de tokens a consumir (padrão: 1.0)
            
        Returns:
            True se os tokens foram consumidos com sucesso, False caso contrário
        """
        self.update()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            self.stats["requests_allowed"] += 1
            self.stats["total_tokens_consumed"] += tokens
            self.stats["last_allowed"] = time.time()
            return True
        else:
            self.stats["requests_rejected"] += 1
            self.stats["last_rejected"] = time.time()
            return False
    
    def get_wait_time(self, tokens: float = 1.0) -> float:
        """
        Calcula o tempo de espera necessário até que o número especificado
        de tokens esteja disponível.
        
        Args:
            tokens: Número de tokens necessários (padrão: 1.0)
            
        Returns:
            Tempo de espera em segundos (0 se os tokens já estiverem disponíveis)
        """
        self.update()
        
        if self.tokens >= tokens:
            return 0.0
        else:
            # Calcula quanto tempo levará para ter tokens suficientes
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate
    
    def mark_error(self) -> None:
        """
        Marca que ocorreu um erro ao usar este bucket (ex: erro de rate limit).
        Isso pode ser usado para ajustar o fator de segurança dinamicamente.
        """
        self.stats["error_count"] += 1
    
    def adjust_safety_factor(self, new_factor: float) -> None:
        """
        Ajusta o fator de segurança do bucket.
        
        Args:
            new_factor: Novo fator de segurança (0.0 a 1.0)
        """
        if new_factor < 0.0 or new_factor > 1.0:
            raise ValueError("O fator de segurança deve estar entre 0.0 e 1.0")
        
        old_factor = self.safety_factor
        self.safety_factor = new_factor
        self.effective_capacity = self.capacity * new_factor
        
        # Ajusta o número atual de tokens proporcionalmente
        if old_factor > 0:
            self.tokens = min(self.effective_capacity, self.tokens * (new_factor / old_factor))
        else:
            self.tokens = self.effective_capacity
        
        logger.info(f"Fator de segurança para {self.name} ajustado: {old_factor:.2f} -> {new_factor:.2f}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna o status atual do bucket.
        
        Returns:
            Dicionário com informações sobre o estado atual do bucket
        """
        self.update()
        
        return {
            "name": self.name,
            "capacity": self.capacity,
            "effective_capacity": self.effective_capacity,
            "current_tokens": self.tokens,
            "refill_rate": self.refill_rate,
            "safety_factor": self.safety_factor,
            "fullness_percentage": (self.tokens / self.effective_capacity) * 100 if self.effective_capacity > 0 else 0,
            "stats": self.stats.copy()
        }
