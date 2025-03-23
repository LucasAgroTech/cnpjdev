import httpx
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class CNPJAClient:
    """
    Cliente para a API da CNPJA com suporte a múltiplas chaves e controle de taxa de requisições
    """
    
    def __init__(self, api_keys: List[str], requests_per_minute: int = 3):
        """
        Inicializa o cliente CNPJA com múltiplas chaves de API
        
        Args:
            api_keys: Lista de chaves de API para usar
            requests_per_minute: Máximo de requisições por minuto por chave
        """
        if not api_keys:
            raise ValueError("Pelo menos uma chave de API deve ser fornecida")
            
        self.api_keys = api_keys
        self.base_url = "https://api.cnpja.com"
        self.current_key_index = 0
        self.requests_per_minute = requests_per_minute
        
        # Rastreia timestamps de requisições para controle de limite
        self.request_timestamps = {key: [] for key in api_keys}
        
        logger.info(f"Cliente CNPJA inicializado com {len(api_keys)} chaves e limite de {requests_per_minute} req/min")
        
    def _get_current_key(self) -> str:
        """
        Obtém a chave de API atual e rotaciona para a próxima
        
        Returns:
            Chave de API atual
        """
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    def _can_make_request(self, api_key: str) -> bool:
        """
        Verifica se uma requisição pode ser feita com a chave de API fornecida
        
        Args:
            api_key: Chave de API para verificar
            
        Returns:
            True se uma requisição pode ser feita, False caso contrário
        """
        now = time.time()
        # Remove timestamps mais antigos que 60 segundos
        self.request_timestamps[api_key] = [
            ts for ts in self.request_timestamps[api_key] 
            if now - ts < 60
        ]
        
        # Verifica se pode fazer uma requisição
        return len(self.request_timestamps[api_key]) < self.requests_per_minute
    
    async def _make_request(self, endpoint: str, api_key: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Faz uma requisição para a API da CNPJA
        
        Args:
            endpoint: Endpoint da API para chamar
            api_key: Chave de API para usar
            params: Parâmetros de consulta
            
        Returns:
            Resposta da API como um dicionário
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": api_key}
            url = f"{self.base_url}/{endpoint}"
            
            logger.debug(f"Requisitando {url} com a chave {api_key[:5]}...")
            
            response = await client.get(url, headers=headers, params=params)
            
            # Registra o timestamp da requisição
            self.request_timestamps[api_key].append(time.time())
            
            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.content else {"message": "Erro desconhecido"}
                error_message = f"Erro na API: {response.status_code} - {error_data.get('message', 'Erro desconhecido')}"
                logger.error(error_message)
                raise Exception(error_message)
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Dict[str, Any]:
        """
        Consulta informações sobre um CNPJ
        
        Args:
            cnpj: CNPJ a consultar
            include_simples: Se deve incluir dados do Simples Nacional
            
        Returns:
            Dados do CNPJ como um dicionário
        """
        # Limpa o CNPJ (remove caracteres não numéricos)
        cnpj_clean = ''.join(filter(str.isdigit, cnpj))
        
        if len(cnpj_clean) != 14:
            raise ValueError(f"CNPJ inválido: {cnpj}. Deve conter 14 dígitos numéricos.")
        
        # Encontra uma chave de API disponível
        available_key = None
        for _ in range(len(self.api_keys) * 2):  # Tenta cada chave duas vezes
            key = self._get_current_key()
            if self._can_make_request(key):
                available_key = key
                break
            # Espera um pouco antes de tentar a próxima chave
            logger.debug(f"Chave {key[:5]} em limite de taxa. Aguardando...")
            await asyncio.sleep(1)  
        
        if available_key is None:
            raise Exception("Nenhuma chave de API disponível para requisição. Limite de taxa atingido para todas as chaves.")
        
        # Constrói parâmetros
        params = {}
        if include_simples:
            params["simples"] = "true"
        
        # Faz a requisição
        logger.info(f"Consultando CNPJ: {cnpj_clean}")
        endpoint = f"office/{cnpj_clean}"
        return await self._make_request(endpoint, available_key, params)