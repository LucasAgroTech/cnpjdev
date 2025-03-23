import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.api.endpoints import router as api_router
from app.models.database import Base, engine
from app.config import APP_NAME, APP_DESCRIPTION, APP_VERSION, DEBUG

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)
logger.info(f"Iniciando aplicação {APP_NAME} v{APP_VERSION}")

# Cria tabelas
logger.info("Criando tabelas no banco de dados, se necessário")
Base.metadata.create_all(bind=engine)

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

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento executado no encerramento da aplicação
    """
    logger.info(f"{APP_NAME} v{APP_VERSION} encerrado")