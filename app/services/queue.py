import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import traceback
import time

from app.models.database import CNPJQuery, CNPJData
from app.services.api_manager import APIManager
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from app.config import MAX_RETRY_ATTEMPTS, REQUESTS_PER_MINUTE

logger = logging.getLogger(__name__)

# Singleton para o gerenciador de fila
_queue_instance = None
_queue_lock = asyncio.Lock()

class CNPJQueue:
    """
    Gerenciador de fila para consultas de CNPJ
    
    Status possíveis:
    - queued: CNPJ na fila para processamento
    - processing: CNPJ em processamento
    - completed: CNPJ processado com sucesso
    - error: Erro permanente no processamento (CNPJ não encontrado, etc)
    - rate_limited: Erro temporário por limite de requisições excedido
    """
    
    @classmethod
    async def get_instance(cls, api_client: APIManager, db: Session):
        """
        Obtém a instância singleton do gerenciador de fila
        
        Args:
            api_client: Gerenciador de APIs para consulta de CNPJ
            db: Sessão do banco de dados
            
        Returns:
            Instância do gerenciador de fila
        """
        global _queue_instance
        
        async with _queue_lock:
            if _queue_instance is None:
                _queue_instance = cls(api_client, db)
                logger.info("Nova instância do gerenciador de fila criada")
            else:
                # Atualiza a sessão do banco de dados e o cliente da API
                _queue_instance.db = db
                _queue_instance.api_client = api_client
                logger.debug("Instância existente do gerenciador de fila reutilizada")
                
        return _queue_instance
    
    def __init__(self, api_client: APIManager, db: Session):
        """
        Inicializa o gerenciador de fila
        
        Args:
            api_client: Gerenciador de APIs para consulta de CNPJ
            db: Sessão do banco de dados
        """
        self.api_client = api_client
        self.db = db
        self._queue = None
        self.processing = False
        self._last_cleanup = datetime.utcnow()
        logger.info("Gerenciador de fila inicializado")
    
    @property
    async def queue(self):
        """
        Obtém a fila assíncrona, criando-a se necessário
        """
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue
    
    async def get_processing_count(self) -> int:
        """
        Obtém o número de CNPJs atualmente em processamento
        
        Returns:
            Número de CNPJs em processamento
        """
        try:
            count = self.db.query(func.count(CNPJQuery.id)).filter(
                CNPJQuery.status == "processing"
            ).scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Erro ao obter contagem de CNPJs em processamento: {str(e)}")
            return 0
    
    async def cleanup_stuck_processing(self) -> int:
        """
        Limpa CNPJs que estão presos no status "processing" por muito tempo
        
        Returns:
            Número de CNPJs redefinidos
        """
        try:
            # Verifica se é hora de fazer a limpeza (a cada 1 minuto)
            now = datetime.utcnow()
            if (now - self._last_cleanup).total_seconds() < 60:  # 1 minuto
                return 0
                
            self._last_cleanup = now
            
            # Encontra CNPJs que estão em "processing" por mais de 3 minutos (reduzido de 5)
            timeout_threshold = now - timedelta(minutes=3)
            
            # Usa uma transação para garantir atomicidade
            count = 0
            
            # Verifica se já existe uma transação em andamento
            in_transaction = False
            try:
                # Tenta executar uma consulta simples para verificar se já estamos em uma transação
                self.db.execute("SELECT 1")
                # Se chegou aqui, não estamos em uma transação explícita
                in_transaction = False
            except Exception as e:
                if "A transaction is already begun on this Session" in str(e):
                    logger.debug("Já existe uma transação em andamento, usando a transação existente")
                    in_transaction = True
                else:
                    # Outro tipo de erro, propaga
                    raise
            
            try:
                # Inicia uma transação apenas se não estiver em uma
                if not in_transaction:
                    self.db.begin()
                
                # Usa FOR UPDATE para bloquear as linhas durante a atualização
                stuck_queries = self.db.query(CNPJQuery).filter(
                    and_(
                        CNPJQuery.status == "processing",
                        CNPJQuery.updated_at < timeout_threshold
                    )
                ).with_for_update().all()
                
                if not stuck_queries:
                    logger.debug("Nenhum CNPJ preso em processamento encontrado")
                    if not in_transaction:
                        self.db.rollback()  # Não há nada para atualizar, faz rollback da transação
                    return 0
                
                # Redefine o status para "error" ou mantém "rate_limited"
                for query in stuck_queries:
                    # Verifica se o erro está relacionado a limite de requisições
                    if query.error_message and "Limite de requisições excedido" in query.error_message:
                        query.status = "rate_limited"
                        logger.warning(f"CNPJ {query.cnpj} mantido como rate_limited após timeout")
                    else:
                        query.status = "error"
                        query.error_message = "Processamento interrompido por timeout"
                    
                    query.updated_at = now
                    count += 1
                
                # Commit da transação apenas se iniciamos uma nova
                if not in_transaction:
                    self.db.commit()
                    logger.warning(f"Redefinidos {count} CNPJs presos em processamento")
            except Exception as e:
                # Em caso de erro, faz rollback da transação apenas se iniciamos uma nova
                if not in_transaction:
                    self.db.rollback()
                logger.error(f"Erro na transação ao limpar CNPJs presos: {str(e)}")
                return 0
                
            return count
            
        except Exception as e:
            logger.error(f"Erro ao limpar CNPJs presos: {str(e)}")
            return 0
    
    async def load_pending_cnpjs(self) -> int:
        """
        Carrega CNPJs pendentes do banco de dados para a fila
        
        Isso permite que o processamento continue de onde parou
        caso o servidor seja reiniciado
        
        Returns:
            Número de CNPJs carregados
        """
        # Limpa CNPJs presos em processamento
        await self.cleanup_stuck_processing()
        
        logger.info("Carregando CNPJs pendentes do banco de dados")
        
        # Busca CNPJs com status "queued", "processing" ou "rate_limited"
        pending_queries = self.db.query(CNPJQuery).filter(
            or_(
                CNPJQuery.status == "queued",
                CNPJQuery.status == "processing",
                CNPJQuery.status == "rate_limited"
            )
        ).order_by(CNPJQuery.created_at.asc()).all()
        
        if not pending_queries:
            logger.info("Nenhum CNPJ pendente encontrado")
            return 0
        
        # Obtém a fila
        queue = await self.queue
        
        # Adiciona CNPJs à fila
        count = 0
        for query in pending_queries:
            # Atualiza status para "queued" (caso esteja como "processing" ou "rate_limited")
            if query.status in ["processing", "rate_limited"]:
                query.status = "queued"
                query.updated_at = datetime.utcnow()
            
            # Adiciona à fila
            await queue.put(query.cnpj)
            count += 1
        
        self.db.commit()
        logger.info(f"{count} CNPJs pendentes carregados para processamento")
        
        # Inicia o processamento se não estiver em execução
        if count > 0 and not self.processing:
            logger.info("Iniciando processamento da fila de CNPJs pendentes")
            asyncio.create_task(self.process_queue())
        
        return count
    
    async def add_to_queue(self, cnpjs: List[str]) -> None:
        """
        Adiciona CNPJs à fila de processamento, evitando duplicatas
        
        Args:
            cnpjs: Lista de CNPJs para processar
        """
        logger.info(f"Adicionando {len(cnpjs)} CNPJs à fila")
        
        # Obtém a fila
        queue = await self.queue
        
        # Lista para armazenar CNPJs realmente adicionados
        added_cnpjs = []
        
        for cnpj in cnpjs:
            # Limpa o CNPJ e adiciona formatação
            cnpj_clean = ''.join(filter(str.isdigit, cnpj))
            
            # Verifica se o CNPJ já está na fila ou já foi processado recentemente
            existing_query = self.db.query(CNPJQuery).filter(
                CNPJQuery.cnpj == cnpj_clean,
                CNPJQuery.status.in_(["queued", "processing", "completed"])
            ).first()
            
            if existing_query and existing_query.status == "completed":
                # Se já foi processado com sucesso, verifica se foi recente (últimos 7 dias)
                if existing_query.updated_at > datetime.utcnow() - timedelta(days=7):
                    logger.info(f"CNPJ {cnpj_clean} já processado recentemente, ignorando")
                    continue
            
            if existing_query and existing_query.status in ["queued", "processing"]:
                logger.info(f"CNPJ {cnpj_clean} já está na fila ou em processamento, ignorando")
                continue
            
            # Se chegou aqui, o CNPJ pode ser adicionado ou atualizado
            if existing_query:
                # Atualiza o registro existente
                existing_query.status = "queued"
                existing_query.error_message = None
                existing_query.updated_at = datetime.utcnow()
            else:
                # Cria um novo registro
                new_query = CNPJQuery(cnpj=cnpj_clean, status="queued")
                self.db.add(new_query)
            
            # Adiciona à fila assíncrona
            await queue.put(cnpj_clean)
            added_cnpjs.append(cnpj_clean)
        
        self.db.commit()
        logger.info(f"{len(added_cnpjs)} CNPJs adicionados à fila com sucesso")
        
        # Inicia o processamento se não estiver em execução e houver CNPJs adicionados
        if added_cnpjs and not self.processing:
            logger.info("Iniciando processamento da fila")
            asyncio.create_task(self.process_queue())
    
    async def process_queue(self) -> None:
        """
        Processa a fila de CNPJs
        
        Implementa mecanismo de persistência para garantir que o processamento
        continue mesmo após reinicialização do servidor
        
        Limita o número de CNPJs em processamento simultâneo para respeitar
        o limite de requisições por minuto da API
        """
        self.processing = True
        
        try:
            # Obtém a fila
            queue = await self.queue
            
            # Contador para pausar periodicamente e permitir que outras tarefas sejam executadas
            processed_count = 0
            
            # Calcula o intervalo mínimo entre requisições para respeitar o limite de requisições por minuto
            # Adiciona 1 segundo extra por segurança
            min_interval_seconds = (60.0 / REQUESTS_PER_MINUTE) + 1
            last_process_time = 0
            
            while not queue.empty():
                # Limpa CNPJs presos em processamento
                await self.cleanup_stuck_processing()
                
                # Verifica quantos CNPJs já estão em processamento
                processing_count = await self.get_processing_count()
                
                # Limita o número de CNPJs em processamento simultâneo
                # Mantém no máximo REQUESTS_PER_MINUTE + 2 CNPJs em processamento
                # para garantir que sempre haja CNPJs prontos para serem processados
                max_processing = REQUESTS_PER_MINUTE + 2
                
                if processing_count >= max_processing:
                    logger.debug(f"Já existem {processing_count} CNPJs em processamento. Aguardando...")
                    await asyncio.sleep(min_interval_seconds)
                    continue
                
                # Respeita o intervalo mínimo entre requisições
                current_time = time.time()
                time_since_last_process = current_time - last_process_time
                
                if time_since_last_process < min_interval_seconds:
                    wait_time = min_interval_seconds - time_since_last_process
                    logger.debug(f"Aguardando {wait_time:.2f}s para respeitar o limite de requisições")
                    await asyncio.sleep(wait_time)
                
                # A cada 5 CNPJs processados, pausa brevemente para permitir que outras tarefas sejam executadas
                if processed_count >= 5:
                    logger.debug("Pausando brevemente o processamento da fila para permitir outras tarefas")
                    await asyncio.sleep(0.1)  # Pausa curta
                    processed_count = 0
                
                # Define um timeout para o processamento de cada CNPJ
                try:
                    # Obtém o próximo CNPJ com timeout
                    cnpj = await asyncio.wait_for(queue.get(), timeout=5.0)
                    processed_count += 1
                    last_process_time = time.time()
                    
                    # Processa o CNPJ em uma tarefa separada com timeout global
                    asyncio.create_task(self._process_single_cnpj(cnpj))
                    
                except asyncio.TimeoutError:
                    logger.error("Timeout ao processar CNPJ da fila")
                    continue  # Continua para o próximo CNPJ
                except Exception as e:
                    logger.error(f"Erro ao obter CNPJ da fila: {str(e)}")
                    continue  # Continua para o próximo CNPJ
        
        except Exception as e:
            logger.error(f"Erro no processamento da fila: {str(e)}")
            logger.debug(traceback.format_exc())
        
        finally:
            self.processing = False
            logger.info("Processamento da fila finalizado")
            
            # Verifica se ainda há CNPJs pendentes no banco de dados
            try:
                pending_count = self.db.query(CNPJQuery).filter(
                    CNPJQuery.status.in_(["queued", "processing", "rate_limited"])
                ).count()
                
                if pending_count > 0:
                    logger.info(f"Ainda há {pending_count} CNPJs pendentes. Reiniciando processamento.")
                    # Agenda a tarefa para ser executada após um breve intervalo
                    asyncio.create_task(self._delayed_restart(1.0))
            except Exception as e:
                logger.error(f"Erro ao verificar CNPJs pendentes: {str(e)}")
    
    async def _delayed_restart(self, delay_seconds: float) -> None:
        """
        Reinicia o processamento após um atraso
        
        Args:
            delay_seconds: Tempo de espera em segundos
        """
        await asyncio.sleep(delay_seconds)
        await self.load_pending_cnpjs()
    
    async def _process_single_cnpj(self, cnpj: str) -> None:
        """
        Processa um único CNPJ
        
        Args:
            cnpj: CNPJ a ser processado
        """
        # Número máximo de tentativas para processar um CNPJ
        max_retries = MAX_RETRY_ATTEMPTS
        retry_count = 0
        success = False
        
        # Atualiza o status da consulta
        query = self.db.query(CNPJQuery).filter(
            CNPJQuery.cnpj == cnpj, 
            or_(
                CNPJQuery.status == "queued",
                CNPJQuery.status == "processing",
                CNPJQuery.status == "rate_limited"
            )
        ).first()
        
        if query:
            query.status = "processing"
            query.updated_at = datetime.utcnow()
            self.db.commit()
        else:
            # Se não encontrou a consulta, pode ter sido um erro
            logger.warning(f"CNPJ {cnpj} não encontrado na base de dados para processamento")
            # Marca a tarefa como concluída e retorna
            queue = await self.queue
            queue.task_done()
            return
        
        # Tenta processar o CNPJ com retry em caso de falha
        start_time = time.time()
        
        try:
            while retry_count < max_retries and not success:
                # Verifica se o tempo total de processamento está próximo do limite do Heroku (50s)
                elapsed_time = time.time() - start_time
                if elapsed_time > 45:  # 45 segundos para dar margem de segurança
                    logger.warning(f"Abortando processamento do CNPJ {cnpj} após {elapsed_time:.1f}s para evitar timeout")
                    
                    # Marca como erro por timeout
                    if query:
                        query.status = "error"
                        query.error_message = "Processamento abortado para evitar timeout do servidor"
                        query.updated_at = datetime.utcnow()
                        self.db.commit()
                    
                    break  # Sai do loop de retry
                
                try:
                    # Se não for a primeira tentativa, aguarda um pouco mais
                    if retry_count > 0:
                        wait_time = min(2 ** retry_count, 8)  # Backoff exponencial com limite máximo de 8s
                        logger.info(f"Tentativa {retry_count+1} para CNPJ {cnpj}, aguardando {wait_time}s")
                        await asyncio.sleep(wait_time)
                    
                    # Consulta a API com timeout
                    logger.info(f"Processando CNPJ: {cnpj}")
                    result, api_used = await self.api_client.query_cnpj(cnpj, include_simples=True)
                    
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
                    
                    # Adiciona informação sobre qual API foi usada
                    result["api_used"] = api_used
                    
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
                        # Removido log de diagnóstico para economizar memória
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
                        # Removido log de diagnóstico para economizar memória
                    
                    # Atualiza o status da consulta
                    if query:
                        # Removidos logs de diagnóstico para economizar memória
                        query.status = "completed"
                        query.error_message = None
                        query.updated_at = datetime.utcnow()
                    else:
                        logger.warning(f"Query não encontrada para CNPJ {cnpj} ao tentar atualizar status")
                    
                    try:
                        # Removidos logs de diagnóstico para economizar memória
                        self.db.commit()
                        
                        # Verificação pós-commit simplificada
                        verification_query = self.db.query(CNPJQuery).filter(CNPJQuery.cnpj == cnpj).first()
                        if not verification_query:
                            logger.warning(f"Verificação pós-commit: CNPJ {cnpj} não encontrado no banco de dados!")
                    except Exception as e:
                        logger.error(f"Erro durante commit para CNPJ {cnpj}: {str(e)}")
                        logger.error(traceback.format_exc())
                        raise
                    
                    logger.info(f"CNPJ {cnpj} processado com sucesso")
                    
                    # Marca como sucesso para sair do loop de retry
                    success = True
                    
                except Exception as e:
                    error_message = str(e)
                    
                    # Verifica se é um erro de violação de restrição única
                    if "duplicate key value violates unique constraint" in error_message:
                        logger.info(f"CNPJ {cnpj} já existe no banco de dados, marcando como completed e pulando para o próximo")
                        
                        # Atualiza o status da consulta para completed
                        if query:
                            query.status = "completed"
                            query.error_message = None
                            query.updated_at = datetime.utcnow()
                            self.db.commit()
                            
                        # Marca como sucesso para sair do loop de retry
                        success = True
                    else:
                        # Para outros erros, mantém a lógica de retry existente
                        retry_count += 1
                        logger.warning(f"Erro ao processar CNPJ {cnpj} (tentativa {retry_count}/{max_retries}): {str(e)}")
                        
                        # Se for a última tentativa, verifica o tipo de erro
                        if retry_count >= max_retries:
                            logger.error(f"Falha ao processar CNPJ {cnpj} após {max_retries} tentativas: {error_message}")
                            logger.debug(traceback.format_exc())
                            
                            # Atualiza o status da consulta com base no tipo de erro
                            if query:
                                # Verifica se é um erro de limite de requisições
                                if "Limite de requisições excedido" in error_message:
                                    query.status = "rate_limited"
                                    logger.warning(f"CNPJ {cnpj} marcado como rate_limited devido a limite de requisições")
                                else:
                                    query.status = "error"
                                
                                query.error_message = error_message
                                query.updated_at = datetime.utcnow()
                                self.db.commit()
        except Exception as e:
            error_message = str(e)
            logger.error(f"Erro global ao processar CNPJ {cnpj}: {error_message}")
            logger.debug(traceback.format_exc())
            
            # Verifica se é um erro de violação de restrição única
            if "duplicate key value violates unique constraint" in error_message:
                logger.info(f"CNPJ {cnpj} já existe no banco de dados, marcando como completed e pulando para o próximo")
                
                # Atualiza o status da consulta para completed
                if query and query.status == "processing":
                    query.status = "completed"
                    query.error_message = None
                    query.updated_at = datetime.utcnow()
                    self.db.commit()
            else:
                # Atualiza o status da consulta com base no tipo de erro
                if query and query.status == "processing":
                    # Verifica se é um erro de limite de requisições
                    if "Limite de requisições excedido" in error_message:
                        query.status = "rate_limited"
                        logger.warning(f"CNPJ {cnpj} marcado como rate_limited devido a limite de requisições")
                    else:
                        query.status = "error"
                    
                    query.error_message = f"Erro global: {error_message}"
                    query.updated_at = datetime.utcnow()
                    self.db.commit()
        finally:
            # Marca a tarefa como concluída
            queue = await self.queue
            queue.task_done()
