#!/bin/bash

# Script para atualizar a aplicação no Heroku
echo "Iniciando atualização da aplicação no Heroku..."

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
read -p "Digite o nome do seu app no Heroku: " APP_NAME

if [ -z "$APP_NAME" ]; then
    echo "Nome do app não fornecido. Abortando."
    exit 1
fi

# Verifica se o app existe
heroku apps:info --app $APP_NAME &> /dev/null
if [ $? -ne 0 ]; then
    echo "App '$APP_NAME' não encontrado no Heroku. Verifique o nome e tente novamente."
    exit 1
fi

echo "Atualizando app '$APP_NAME'..."

# Faz o commit das alterações
git add .
git commit -m "Melhoria no sistema de fila para limitar CNPJs em processamento" || true

# Configura o remote do Heroku se necessário
if ! git remote | grep -q heroku; then
    heroku git:remote --app $APP_NAME
fi

# Faz o deploy
echo "Fazendo deploy das alterações..."
git push heroku main

# Reinicia a aplicação
echo "Reiniciando a aplicação..."
heroku restart --app $APP_NAME

# Mostra os logs
echo "Mostrando logs recentes..."
heroku logs --tail --app $APP_NAME
