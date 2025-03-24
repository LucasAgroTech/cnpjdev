import httpx
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import traceback

logger = logging.getLogger(__name__)

class CNPJWSClient:
    """
    Cliente para a API Pública CNPJ.ws com controle de taxa de requisições
    """
    
    def __init__(self, requests_per_minute: int = 3):
        """
        Inicializa o cliente CNPJ.ws
        
        Args:
            requests_per_minute: Máximo de requisições por minuto (padrão: 3)
        """
        self.base_url = "https://publica.cnpj.ws/cnpj"
        self.requests_per_minute = requests_per_minute
        
        # Rastreia timestamps de requisições para controle de limite
        self.request_timestamps = []
        
        logger.info(f"Cliente CNPJ.ws inicializado com limite de {requests_per_minute} req/min")
        
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
    
    async def _make_request(self, cnpj: str) -> Dict[str, Any]:
        """
        Faz uma requisição para a API Pública CNPJ.ws
        
        Args:
            cnpj: CNPJ a consultar
            
        Returns:
            Resposta da API como um dicionário
        """
        # Reduzindo o timeout para 15 segundos para evitar o erro H28 do Heroku
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{self.base_url}/{cnpj}"
            
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
                    raise Exception(f"CNPJ {cnpj} não encontrado na base de dados da CNPJ.ws.")
                else:
                    error_data = response.json() if response.content else {"message": "Erro desconhecido"}
                    error_message = f"Erro na API: {response.status_code} - {error_data.get('message', 'Erro desconhecido')}"
                    logger.error(error_message)
                    raise Exception(error_message)
            except httpx.TimeoutException:
                logger.error(f"Timeout ao consultar CNPJ {cnpj}")
                raise Exception(f"Timeout ao consultar CNPJ {cnpj}. A requisição excedeu o limite de tempo.")
            except httpx.RequestError as e:
                logger.error(f"Erro de conexão ao consultar CNPJ {cnpj}: {str(e)}")
                raise Exception(f"Erro de conexão ao consultar CNPJ {cnpj}: {str(e)}")
            except Exception as e:
                logger.error(f"Erro inesperado ao consultar CNPJ {cnpj}: {str(e)}")
                logger.debug(traceback.format_exc())
                raise
    
    async def query_cnpj(self, cnpj: str, include_simples: bool = True) -> Dict[str, Any]:
        """
        Consulta informações sobre um CNPJ
        
        Args:
            cnpj: CNPJ a consultar
            include_simples: Parâmetro mantido para compatibilidade (sempre incluído na API CNPJ.ws)
            
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
            task = asyncio.create_task(self._make_request(cnpj_clean))
            # Aguarda a tarefa com timeout de 20 segundos
            result = await asyncio.wait_for(task, timeout=20.0)
            
            # Mapeia a resposta da CNPJ.ws para o formato esperado pelo resto da aplicação
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
        Mapeia a resposta da CNPJ.ws para o formato esperado pelo resto da aplicação
        
        Args:
            response: Resposta da API CNPJ.ws
            
        Returns:
            Dados mapeados para o formato esperado
        """
        # Extrai dados do estabelecimento
        estabelecimento = response.get("estabelecimento", {})
        
        # Extrai dados do simples nacional
        simples = response.get("simples", {})
        simples_optant = simples.get("simples", "").lower() == "sim" if simples else False
        simples_date = simples.get("data_opcao_simples") if simples else None
        
        # Cria estrutura similar à resposta da CNPJA para manter compatibilidade
        mapped = {
            "company": {
                "name": response.get("razao_social", ""),
                "status": {
                    "text": estabelecimento.get("situacao_cadastral", "")
                },
                "simples": {
                    "optant": simples_optant,
                    "since": simples_date
                }
            },
            "alias": estabelecimento.get("nome_fantasia", ""),
            "address": {
                "street": estabelecimento.get("logradouro", ""),
                "number": estabelecimento.get("numero", ""),
                "details": estabelecimento.get("complemento", ""),
                "city": estabelecimento.get("cidade", {}).get("nome", "") if estabelecimento.get("cidade") else "",
                "state": estabelecimento.get("estado", {}).get("sigla", "") if estabelecimento.get("estado") else "",
                "zip": estabelecimento.get("cep", "").replace(".", "").replace("-", "")
            },
            "contacts": [
                {"email": estabelecimento.get("email", "")} if estabelecimento.get("email") else {},
                {"phone": f"{estabelecimento.get('ddd1', '')}{estabelecimento.get('telefone1', '')}"} 
                if estabelecimento.get("telefone1") else {}
            ],
            # Mantém os dados originais para referência
            "original_response": response
        }
        
        return mapped
