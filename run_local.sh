#!/bin/bash

# Script para executar a aplicação localmente para testes

echo "Iniciando aplicação CNPJ Consulta localmente..."

# Verifica se o arquivo .env existe
if [ ! -f .env ]; then
    echo "Arquivo .env não encontrado. Criando a partir do .env.example..."
    
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Arquivo .env criado. Por favor, edite-o com suas configurações antes de continuar."
        echo "Execute este script novamente após configurar o arquivo .env."
        exit 0
    else
        echo "Arquivo .env.example não encontrado. Criando um novo arquivo .env..."
        cat > .env << EOF
# API da ReceitaWS
REQUESTS_PER_MINUTE=3

# Banco de dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/cnpj_consulta

# Configuração da aplicação
DEBUG=True
EOF
        echo "Arquivo .env criado. Por favor, edite-o com suas configurações antes de continuar."
        echo "Execute este script novamente após configurar o arquivo .env."
        exit 0
    fi
fi

# Verifica se o ambiente virtual existe
if [ ! -d "venv" ]; then
    echo "Ambiente virtual não encontrado. Criando..."
    python3 -m venv venv
    echo "Ambiente virtual criado."
fi

# Ativa o ambiente virtual
echo "Ativando ambiente virtual..."
source venv/bin/activate

# Instala as dependências
echo "Verificando dependências..."
pip install -r requirements.txt

# Executa a aplicação
echo "Iniciando servidor de desenvolvimento..."
echo "A aplicação estará disponível em: http://localhost:8000"
echo "Pressione Ctrl+C para encerrar."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
