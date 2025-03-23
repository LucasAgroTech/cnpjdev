import logging
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.api.endpoints import router as api_router
from app.models.database import Base, engine
from app.config import APP_NAME, APP_DESCRIPTION, APP_VERSION, DEBUG, AUTO_RESTART_QUEUE, REQUESTS_PER_MINUTE

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
    # Verifica se as tabelas já existem antes de tentar criá-las
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    # Lista de tabelas que precisamos criar
    tables_to_create = []
    existing_tables = inspector.get_table_names()
    
    # Verifica quais tabelas precisam ser criadas
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            tables_to_create.append(table)
    
    # Cria apenas as tabelas que não existem
    if tables_to_create:
        logger.info(f"Criando {len(tables_to_create)} tabelas: {', '.join(t.name for t in tables_to_create)}")
        # Cria apenas as tabelas específicas que não existem
        for table in tables_to_create:
            table.create(bind=engine, checkfirst=True)
        logger.info("Tabelas criadas com sucesso")
    else:
        logger.info("Todas as tabelas já existem no banco de dados")
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
        try:
            from app.models.database import get_db
            from app.services.receitaws import ReceitaWSClient
            from app.services.queue import CNPJQueue
            
            # Obtém uma sessão do banco de dados
            db_generator = get_db()
            db = next(db_generator)
            
            # Cria instâncias necessárias
            api_client = ReceitaWSClient(requests_per_minute=REQUESTS_PER_MINUTE)
            queue_manager = CNPJQueue(api_client=api_client, db=db)
            
            # Carrega CNPJs pendentes
            asyncio.create_task(queue_manager.load_pending_cnpjs())
            
            logger.info("Verificação de CNPJs pendentes iniciada")
        except Exception as e:
            logger.error(f"Erro ao carregar CNPJs pendentes: {str(e)}")
    else:
        logger.info("Reinicialização automática da fila desabilitada (AUTO_RESTART_QUEUE=False)")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento executado no encerramento da aplicação
    """
    logger.info(f"{APP_NAME} v{APP_VERSION} encerrado")
