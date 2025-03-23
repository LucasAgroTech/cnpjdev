import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
import traceback

from app.models.database import CNPJQuery, CNPJData
from app.services.receitaws import ReceitaWSClient
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class CNPJQueue:
    """
    Gerenciador de fila para consultas de CNPJ
    """
    
    def __init__(self, api_client: ReceitaWSClient, db: Session):
        """
        Inicializa o gerenciador de fila
        
        Args:
            api_client: Cliente da API ReceitaWS
            db: Sessão do banco de dados
        """
        self.api_client = api_client
        self.db = db
        self.queue = asyncio.Queue()
        self.processing = False
        logger.info("Gerenciador de fila inicializado")
    
    async def add_to_queue(self, cnpjs: List[str]) -> None:
        """
        Adiciona CNPJs à fila de processamento
        
        Args:
            cnpjs: Lista de CNPJs para processar
        """
        logger.info(f"Adicionando {len(cnpjs)} CNPJs à fila")
        
        for cnpj in cnpjs:
            # Limpa o CNPJ e adiciona formatação
            cnpj_clean = ''.join(filter(str.isdigit, cnpj))
            
            # Cria um registro de consulta no banco de dados
            query = CNPJQuery(cnpj=cnpj_clean, status="queued")
            self.db.add(query)
            
            # Adiciona à fila assíncrona
            await self.queue.put(cnpj_clean)
        
        self.db.commit()
        logger.info(f"{len(cnpjs)} CNPJs adicionados à fila com sucesso")
        
        # Inicia o processamento se não estiver em execução
        if not self.processing:
            logger.info("Iniciando processamento da fila")
            asyncio.create_task(self.process_queue())
    
    async def process_queue(self) -> None:
        """
        Processa a fila de CNPJs
        """
        self.processing = True
        
        try:
            while not self.queue.empty():
                cnpj = await self.queue.get()
                
                try:
                    # Atualiza o status da consulta
                    query = self.db.query(CNPJQuery).filter(
                        CNPJQuery.cnpj == cnpj, 
                        CNPJQuery.status == "queued"
                    ).first()
                    
                    if query:
                        query.status = "processing"
                        self.db.commit()
                    
                    # Consulta a API
                    logger.info(f"Processando CNPJ: {cnpj}")
                    result = await self.api_client.query_cnpj(cnpj, include_simples=True)
                    
                    # Extrai dados relevantes
                    company_name = result.get("company", {}).get("name", "")
                    trade_name = result.get("alias", "")
                    status = result.get("company", {}).get("status", {}).get("text", "")
                    
                    # Extrai dados de endereço
                    address_data = result.get("address", {})
                    address = f"{address_data.get('street', '')} {address_data.get('number', '')}"
                    if address_data.get('details'):
                        address += f", {address_data.get('details')}"
                    
                    city = address_data.get("city", "")
                    state = address_data.get("state", "")
                    zip_code = address_data.get("zip", "")
                    
                    # Extrai contatos
                    contacts = result.get("contacts", [])
                    email = next((c.get("email") for c in contacts if c.get("email")), "")
                    phone = next((c.get("phone") for c in contacts if c.get("phone")), "")
                    
                    # Extrai informações do Simples Nacional
                    simples_data = result.get("company", {}).get("simples", {})
                    simples_nacional = simples_data.get("optant", False)
                    simples_nacional_date = None
                    if simples_data.get("since"):
                        try:
                            simples_nacional_date = datetime.strptime(simples_data.get("since"), "%Y-%m-%d")
                        except:
                            pass
                    
                    # Salva no banco de dados
                    cnpj_data = self.db.query(CNPJData).filter(CNPJData.cnpj == cnpj).first()
                    
                    if not cnpj_data:
                        cnpj_data = CNPJData(
                            cnpj=cnpj,
                            raw_data=result,
                            company_name=company_name,
                            trade_name=trade_name,
                            status=status,
                            address=address,
                            city=city,
                            state=state,
                            zip_code=zip_code,
                            email=email,
                            phone=phone,
                            simples_nacional=simples_nacional,
                            simples_nacional_date=simples_nacional_date
                        )
                        self.db.add(cnpj_data)
                    else:
                        cnpj_data.raw_data = result
                        cnpj_data.company_name = company_name
                        cnpj_data.trade_name = trade_name
                        cnpj_data.status = status
                        cnpj_data.address = address
                        cnpj_data.city = city
                        cnpj_data.state = state
                        cnpj_data.zip_code = zip_code
                        cnpj_data.email = email
                        cnpj_data.phone = phone
                        cnpj_data.simples_nacional = simples_nacional
                        cnpj_data.simples_nacional_date = simples_nacional_date
                        cnpj_data.updated_at = datetime.utcnow()
                    
                    # Atualiza o status da consulta
                    if query:
                        query.status = "completed"
                    
                    self.db.commit()
                    logger.info(f"CNPJ {cnpj} processado com sucesso")
                    
                except Exception as e:
                    logger.error(f"Erro ao processar CNPJ {cnpj}: {str(e)}")
                    logger.debug(traceback.format_exc())
                    
                    # Atualiza o status da consulta com erro
                    if query:
                        query.status = "error"
                        query.error_message = str(e)
                        self.db.commit()
                
                # Marca a tarefa como concluída
                self.queue.task_done()
                
                # Aguarda um pouco para evitar sobrecarga
                await asyncio.sleep(0.5)
        
        except Exception as e:
            logger.error(f"Erro no processamento da fila: {str(e)}")
            logger.debug(traceback.format_exc())
        
        finally:
            self.processing = False
            logger.info("Processamento da fila finalizado")
