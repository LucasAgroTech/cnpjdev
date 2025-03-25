#!/bin/bash

# Script para facilitar o deploy no Heroku
echo "Iniciando deploy para o Heroku..."

# Verifica se o Heroku CLI está instalado
if ! command -v heroku &> /dev/null; then
    echo "Heroku CLI não encontrado. Por favor, instale-o primeiro:"
    echo "  brew install heroku/brew/heroku (macOS)"
    echo "  ou visite https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Verifica se o usuário está logado no Heroku
heroku whoami &> /dev/null
if [ $? -ne 0 ]; then
    echo "Você não está logado no Heroku. Fazendo login..."
    heroku login
fi

# Pergunta o nome do app
read -p "Digite o nome do seu app no Heroku (ou deixe em branco para criar um novo): " APP_NAME

if [ -z "$APP_NAME" ]; then
    echo "Criando um novo app no Heroku..."
    APP_NAME=$(heroku create | grep -o 'https://[^ ]*.herokuapp.com' | sed 's/https:\/\///' | sed 's/.herokuapp.com//')
    echo "App criado: $APP_NAME"
else
    # Verifica se o app já existe
    heroku apps:info --app $APP_NAME &> /dev/null
    if [ $? -ne 0 ]; then
        echo "Criando app '$APP_NAME' no Heroku..."
        heroku create $APP_NAME
    else
        echo "Usando app existente: $APP_NAME"
    fi
fi

# Adiciona o PostgreSQL
echo "Verificando se o PostgreSQL já está configurado..."
if ! heroku addons:info --app $APP_NAME postgresql &> /dev/null; then
    echo "Adicionando PostgreSQL ao app..."
    heroku addons:create --app $APP_NAME heroku-postgresql:mini
else
    echo "PostgreSQL já está configurado."
fi

# Configura as variáveis de ambiente
echo "Configurando variáveis de ambiente..."
echo "Digite o número máximo de requisições por minuto (padrão: 3):"
read REQUESTS_PER_MINUTE
REQUESTS_PER_MINUTE=${REQUESTS_PER_MINUTE:-3}

echo "Ativar modo de debug? (true/false, padrão: false):"
read DEBUG
DEBUG=${DEBUG:-false}

echo "Reiniciar automaticamente a fila na inicialização? (true/false, padrão: true):"
read AUTO_RESTART_QUEUE
AUTO_RESTART_QUEUE=${AUTO_RESTART_QUEUE:-true}

echo "Número máximo de tentativas para processar um CNPJ (padrão: 3):"
read MAX_RETRY_ATTEMPTS
MAX_RETRY_ATTEMPTS=${MAX_RETRY_ATTEMPTS:-3}

# Configura as variáveis no Heroku
heroku config:set --app $APP_NAME REQUESTS_PER_MINUTE=$REQUESTS_PER_MINUTE
heroku config:set --app $APP_NAME DEBUG=$DEBUG
heroku config:set --app $APP_NAME AUTO_RESTART_QUEUE=$AUTO_RESTART_QUEUE
heroku config:set --app $APP_NAME MAX_RETRY_ATTEMPTS=$MAX_RETRY_ATTEMPTS

# Faz o deploy
echo "Fazendo deploy do código..."
git add .
git commit -m "Preparação para deploy no Heroku" || true
heroku git:remote --app $APP_NAME
git push heroku main

# Abre a aplicação
echo "Deploy concluído! Abrindo a aplicação..."
heroku open --app $APP_NAME

echo "Você pode verificar os logs com: heroku logs --tail --app $APP_NAME"
