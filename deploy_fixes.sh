#!/bin/bash

# Script para implantar as correções de contabilização no Heroku

# Cores para saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Script de Implantação de Correções de Contabilização ===${NC}"

# Verifica se o nome do app Heroku foi fornecido
if [ -z "$1" ]; then
    read -p "Digite o nome do seu app no Heroku: " HEROKU_APP_NAME
else
    HEROKU_APP_NAME=$1
fi

echo -e "${YELLOW}Implantando correções para o app: ${GREEN}$HEROKU_APP_NAME${NC}"

# Verifica se o Heroku CLI está instalado
if ! command -v heroku &> /dev/null; then
    echo -e "${RED}Erro: Heroku CLI não está instalado.${NC}"
    echo "Por favor, instale o Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Verifica se está logado no Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo -e "${YELLOW}Você não está logado no Heroku. Fazendo login...${NC}"
    heroku login
fi

# Verifica se o app existe
if ! heroku apps:info --app $HEROKU_APP_NAME &> /dev/null; then
    echo -e "${RED}Erro: O app '$HEROKU_APP_NAME' não existe ou você não tem acesso a ele.${NC}"
    exit 1
fi

echo -e "${YELLOW}Enviando alterações para o Heroku...${NC}"

# Adiciona as alterações ao git
git add .env app/services/queue.py app/api/endpoints.py clean_duplicates.py CORRECOES_CONTABILIZACAO.md

# Commit das alterações
git commit -m "Correções na contabilização de CNPJs e remoção de duplicados"

# Push para o Heroku
git push heroku master

# Verifica se o push foi bem-sucedido
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Alterações enviadas com sucesso!${NC}"
else
    echo -e "${RED}Erro ao enviar alterações para o Heroku.${NC}"
    exit 1
fi

# Reinicia o app
echo -e "${YELLOW}Reiniciando o app...${NC}"
heroku restart --app $HEROKU_APP_NAME

# Verifica se o restart foi bem-sucedido
if [ $? -eq 0 ]; then
    echo -e "${GREEN}App reiniciado com sucesso!${NC}"
else
    echo -e "${RED}Erro ao reiniciar o app.${NC}"
    exit 1
fi

# Reinicia a fila de processamento
echo -e "${YELLOW}Reiniciando a fila de processamento...${NC}"
python restart_queue.py https://$HEROKU_APP_NAME.herokuapp.com

# Limpa CNPJs duplicados
echo -e "${YELLOW}Limpando CNPJs duplicados...${NC}"
curl -X POST "https://$HEROKU_APP_NAME.herokuapp.com/api/admin/cleanup/duplicates"

echo -e "${GREEN}Implantação concluída com sucesso!${NC}"
echo -e "${YELLOW}Recomendações:${NC}"
echo "1. Verifique os logs do Heroku para garantir que tudo está funcionando corretamente:"
echo "   heroku logs --tail --app $HEROKU_APP_NAME"
echo "2. Monitore o status da fila usando o script check_queue_status.py:"
echo "   python check_queue_status.py https://$HEROKU_APP_NAME.herokuapp.com 30 0"
echo "3. Consulte o arquivo CORRECOES_CONTABILIZACAO.md para mais informações sobre as correções implementadas."

exit 0
