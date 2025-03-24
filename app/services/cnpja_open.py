import httpx
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import traceback

logger = logging.getLogger(__name__)

class CNPJaOpenClient:
    """
    Cliente para a API Pública CNPJa Open com controle de taxa de requisições
    """
    
    def __init__(self, requests_per_minute: int = 5):
        """
        Inicializa o cliente CNPJa Open
        
        Args:
            requests_per_minute: Máximo de requisições por minuto (padrão: 5)
        """
        self.base_url = "https://open.cnpja.com"
        self.requests_per_minute = requests_per_minute
        
        # Rastreia timestamps de requisições para controle de limite
        self.request_timestamps = []
        
        logger.info(f"Cliente CNPJa Open inicializado com limite de {requests_per_minute} req/min")
        
    def _can_make_request(self) -> bool:
        """
        Verifica se uma requisição pode ser feita respeitando o limite de taxa
        
        Returns:
            True se uma requisição pode ser feita, False caso contrário
        """
        now = time.time()
        # Remove timestamps mais antigos que 60 segundos
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 60]
        
        # Verifica se pode fazer uma requisição
        return len(self.request_timestamps) < self.requests_per_minute
    
    async def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Faz uma requisição para a API CNPJa Open
        
        Args:
            endpoint: Endpoint completo da API para chamar
            
        Returns:
            Resposta da API como um dicionário
        """
        # Reduzindo o timeout para 15 segundos para evitar o erro H28 do Heroku
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.base_url}/{endpoint}"
            
            logger.debug(f"Requisitando {url}...")
            
            try:
                response = await client.get(url)
                
                # Registra o timestamp da requisição
                self.request_timestamps.append(time.time())
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    raise Exception("Limite de requisições excedido. Tente novamente mais tarde.")
                elif response.status_code == 404:
                    raise Exception(f"CNPJ não encontrado na base de dados da CNPJa Open.")
                else:
                    error_data = response.json() if response.content else {"message": "Erro desconhecido"}
                    error_message = f"Erro na API: {response.status_code} - {error_data.get('message', 'Erro desconhecido')}"
                    logger.error(error_message)
                    raise Exception(error_message)
            except httpx.TimeoutException:
                logger.error(f"Timeout ao consultar endpoint {endpoint}")
                raise Exception(f"Timeout ao consultar endpoint {endpoint}. A requisição excedeu o limite de tempo.")
            except httpx.RequestError as e:
                logger.error(f"Erro de conexão ao consultar endpoint {endpoint}: {str(e)}")
                raise Exception(f"Erro de conexão ao consultar endpoint {endpoint}: {str(e)}")
            except Exception as e:
                logger.error(f"Erro inesperado ao consultar endpoint {endpoint}: {str(e)}")
                logger.debug(traceback.format_exc())
                raise
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Dict[str, Any]:
        """
        Consulta informações sobre um CNPJ
        
        Args:
            cnpj: CNPJ a consultar
            include_simples: Parâmetro mantido para compatibilidade (sempre incluído na API CNPJa Open)
            
        Returns:
            Dados do CNPJ como um dicionário
        """
        # Limpa o CNPJ (remove caracteres não numéricos)
        cnpj_clean = ''.join(filter(str.isdigit, cnpj))
        
        if len(cnpj_clean) != 14:
            raise ValueError(f"CNPJ inválido: {cnpj}. Deve conter 14 dígitos numéricos.")
        
        # Verifica se pode fazer uma requisição
        if not self._can_make_request():
            # Aguarda até que possa fazer uma requisição
            wait_time = 60 - (time.time() - min(self.request_timestamps))
            logger.debug(f"Limite de taxa atingido. Aguardando {wait_time:.2f} segundos...")
            await asyncio.sleep(wait_time + 1)  # Adiciona 1 segundo extra por segurança
        
        # Adiciona timeout para toda a operação
        try:
            # Cria uma tarefa com timeout
            endpoint = f"office/{cnpj_clean}"
            task = asyncio.create_task(self._make_request(endpoint))
            # Aguarda a tarefa com timeout de 20 segundos
            result = await asyncio.wait_for(task, timeout=20.0)
            
            # Mapeia a resposta da CNPJa Open para o formato esperado pelo resto da aplicação
            logger.info(f"CNPJ consultado com sucesso: {cnpj_clean}")
            mapped_result = self._map_response(result)
            
            return mapped_result
        except asyncio.TimeoutError:
            logger.error(f"Timeout global ao consultar CNPJ {cnpj_clean}")
            raise Exception(f"A consulta do CNPJ {cnpj_clean} excedeu o tempo limite global.")
        except Exception as e:
            logger.error(f"Erro ao consultar CNPJ {cnpj_clean}: {str(e)}")
            raise
    
    def _map_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mapeia a resposta da CNPJa Open para o formato esperado pelo resto da aplicação
        
        Args:
            response: Resposta da API CNPJa Open
            
        Returns:
            Dados mapeados para o formato esperado
        """
        # Extrai dados da empresa
        company = response.get("company", {})
        
        # Extrai dados do simples nacional
        simples = company.get("simples", {})
        simples_optant = simples.get("optant", False) if simples else False
        simples_date = simples.get("since") if simples else None
        
        # Extrai dados de endereço
        address = response.get("address", {})
        
        # Extrai contatos
        phones = response.get("phones", [])
        emails = response.get("emails", [])
        
        # Formata telefones
        formatted_phones = []
        for phone in phones:
            if phone and phone.get("number"):
                formatted_phones.append({"phone": phone.get("number")})
        
        # Formata emails
        formatted_emails = []
        for email in emails:
            if email and email.get("address"):
                formatted_emails.append({"email": email.get("address")})
        
        # Combina contatos
        contacts = formatted_emails + formatted_phones
        
        # Cria estrutura similar à resposta da CNPJA para manter compatibilidade
        mapped = {
            "company": {
                "name": company.get("name", ""),
                "status": {
                    "text": response.get("status", {}).get("text", "")
                },
                "simples": {
                    "optant": simples_optant,
                    "since": simples_date
                }
            },
            "alias": response.get("alias", ""),
            "address": {
                "street": address.get("street", ""),
                "number": address.get("number", ""),
                "details": address.get("details", ""),
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "zip": address.get("zip", "").replace(".", "").replace("-", "") if address.get("zip") else ""
            },
            "contacts": contacts,
            # Mantém os dados originais para referência
            "original_response": response
        }
        
        return mapped
