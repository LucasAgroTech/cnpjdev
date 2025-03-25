#!/bin/bash
# Script para implantar a correção do problema de SQLAlchemy no Heroku

echo "===== INICIANDO IMPLANTAÇÃO DA CORREÇÃO DO SQLALCHEMY ====="
echo "Data e hora: $(date)"
echo

# Verifica se o Heroku CLI está instalado
if ! command -v heroku &> /dev/null; then
    echo "Heroku CLI não encontrado. Por favor, instale-o primeiro."
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
    echo "App '$APP_NAME' não encontrado no Heroku. Abortando."
    exit 1
fi

echo "===== ETAPA 1: COMMIT DAS ALTERAÇÕES ====="
echo "Adicionando arquivos modificados ao git..."
git add fix_incomplete_status.py check_db_status.py app/services/queue.py restart_queue.py
git commit -m "Corrige problema de SQLAlchemy e transações no banco de dados"

echo "===== ETAPA 2: DEPLOY PARA O HEROKU ====="
echo "Fazendo push para o Heroku..."
git push heroku main

echo "===== ETAPA 3: EXECUTANDO SCRIPTS DE CORREÇÃO ====="
echo "Executando diagnóstico inicial..."
heroku run python check_db_status.py --app $APP_NAME

echo "Executando correção de status incompletos..."
heroku run python fix_incomplete_status.py --app $APP_NAME

echo "===== ETAPA 4: REINICIANDO PROCESSAMENTO DA FILA ====="
echo "Reiniciando processamento da fila..."
heroku run python restart_queue.py --app $APP_NAME

echo "===== ETAPA 5: VERIFICAÇÃO FINAL ====="
echo "Executando diagnóstico final..."
heroku run python check_db_status.py --app $APP_NAME

echo "===== IMPLANTAÇÃO CONCLUÍDA ====="
echo "Data e hora: $(date)"
echo
echo "IMPORTANTE: Monitore os logs para verificar se o problema foi resolvido."
echo "Comando para verificar logs: heroku logs --tail --app $APP_NAME"
