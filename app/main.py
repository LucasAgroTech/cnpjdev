import logging
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.api.endpoints import router as api_router
from app.models.database import Base, engine, create_tables
from app.config import (
    APP_NAME, APP_DESCRIPTION, APP_VERSION, DEBUG, AUTO_RESTART_QUEUE,
    RECEITAWS_ENABLED, CNPJWS_ENABLED, CNPJA_OPEN_ENABLED,
    RECEITAWS_REQUESTS_PER_MINUTE, CNPJWS_REQUESTS_PER_MINUTE, CNPJA_OPEN_REQUESTS_PER_MINUTE
)

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)
logger.info(f"Iniciando aplicação {APP_NAME} v{APP_VERSION}")

# Cria tabelas com tratamento de erro
logger.info("Criando tabelas no banco de dados, se necessário")
try:
    create_tables()
    logger.info("Tabelas criadas com sucesso")
except Exception as e:
    logger.error(f"Erro ao criar tabelas: {str(e)}")

# Cria aplicação FastAPI
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    debug=DEBUG
)

# Adiciona middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui router da API
logger.info("Registrando rotas da API")
app.include_router(api_router, prefix="/api")

# Serve arquivos estáticos
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
templates_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

if os.path.exists(static_path):
    logger.info(f"Servindo arquivos estáticos de {static_path}")
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Configura templates
logger.info(f"Carregando templates de {templates_path}")
templates = Jinja2Templates(directory=templates_path)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Serve a página principal
    """
    logger.debug("Requisição para a página principal")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """
    Endpoint de verificação de saúde
    """
    logger.debug("Verificação de saúde")
    return {"status": "ok", "version": APP_VERSION}

@app.on_event("startup")
async def startup_event():
    """
    Evento executado na inicialização da aplicação
    """
    logger.info(f"{APP_NAME} v{APP_VERSION} iniciado com sucesso")
    
    # Carrega CNPJs pendentes e retoma o processamento se AUTO_RESTART_QUEUE estiver habilitado
    if AUTO_RESTART_QUEUE:
        # Agenda a inicialização da fila para ser executada após um breve atraso
        # Isso permite que o servidor inicie completamente antes de começar o processamento
        asyncio.create_task(delayed_queue_initialization(2.0))
    else:
        logger.info("Reinicialização automática da fila desabilitada (AUTO_RESTART_QUEUE=False)")

async def delayed_queue_initialization(delay_seconds: float):
    """
    Inicializa a fila de processamento após um atraso
    
    Args:
        delay_seconds: Tempo de espera em segundos
    """
    try:
        logger.info(f"Agendando inicialização da fila em {delay_seconds} segundos")
        await asyncio.sleep(delay_seconds)
        
        from app.models.database import get_db
        from app.services.api_manager import APIManager
        from app.services.queue import CNPJQueue
        
        # Obtém uma sessão do banco de dados
        db_generator = get_db()
        db = next(db_generator)
        
        # Cria instâncias necessárias
        api_client = APIManager(
            receitaws_enabled=RECEITAWS_ENABLED,
            cnpjws_enabled=CNPJWS_ENABLED,
            cnpja_open_enabled=CNPJA_OPEN_ENABLED,
            receitaws_requests_per_minute=RECEITAWS_REQUESTS_PER_MINUTE,
            cnpjws_requests_per_minute=CNPJWS_REQUESTS_PER_MINUTE,
            cnpja_open_requests_per_minute=CNPJA_OPEN_REQUESTS_PER_MINUTE
        )
        
        # Obtém a instância singleton do gerenciador de fila
        queue_manager = await CNPJQueue.get_instance(api_client=api_client, db=db)
        
        # Executa limpeza de CNPJs presos em processamento
        stuck_count = await queue_manager.cleanup_stuck_processing()
        if stuck_count > 0:
            logger.warning(f"Redefinidos {stuck_count} CNPJs presos em processamento durante a inicialização")
        
        # Define um timeout para a operação de carregamento
        try:
            # Carrega CNPJs pendentes com timeout
            await asyncio.wait_for(
                queue_manager.load_pending_cnpjs(),
                timeout=30.0  # 30 segundos de timeout
            )
            logger.info("Verificação de CNPJs pendentes iniciada com sucesso")
        except asyncio.TimeoutError:
            logger.error("Timeout ao carregar CNPJs pendentes")
        except Exception as e:
            logger.error(f"Erro ao carregar CNPJs pendentes: {str(e)}")
            
    except Exception as e:
        logger.error(f"Erro na inicialização da fila: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento executado no encerramento da aplicação
    """
    logger.info(f"{APP_NAME} v{APP_VERSION} encerrado")
