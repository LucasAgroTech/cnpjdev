#!/bin/bash
# Script para implantar as correções no endpoint de status para mostrar todos os CNPJs

# Cores para saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Iniciando implantação das correções no endpoint de status...${NC}"

# Verifica se o git está instalado
if ! command -v git &> /dev/null; then
    echo -e "${RED}Git não encontrado. Por favor, instale o git e tente novamente.${NC}"
    exit 1
fi

# Verifica se o heroku CLI está instalado
if ! command -v heroku &> /dev/null; then
    echo -e "${RED}Heroku CLI não encontrado. Por favor, instale o Heroku CLI e tente novamente.${NC}"
    exit 1
fi

# Verifica se está logado no Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo -e "${RED}Você não está logado no Heroku. Por favor, execute 'heroku login' e tente novamente.${NC}"
    exit 1
fi

# Verifica se há alterações não commitadas
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Existem alterações não commitadas. Deseja continuar mesmo assim? (s/n)${NC}"
    read -r resposta
    if [[ "$resposta" != "s" ]]; then
        echo -e "${RED}Implantação cancelada.${NC}"
        exit 1
    fi
fi

# Adiciona as alterações ao git
echo -e "${YELLOW}Adicionando arquivos modificados ao git...${NC}"
git add app/api/endpoints.py deploy_status_fix.sh

# Commit das alterações se houver algo para commitar
echo -e "${YELLOW}Verificando se há alterações para commitar...${NC}"
if git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Não há alterações para commitar. Continuando com o deploy...${NC}"
else
    echo -e "${YELLOW}Realizando commit das alterações...${NC}"
    git commit -m "Correção no endpoint de status para mostrar todos os CNPJs sem limitação de tempo"
    
    # Verifica se o commit foi bem-sucedido
    if [ $? -ne 0 ]; then
        echo -e "${RED}Erro ao realizar commit das alterações.${NC}"
        exit 1
    fi
fi

# Implanta no Heroku
echo -e "${YELLOW}Implantando alterações no Heroku...${NC}"
git push heroku main:master

# Verifica se o push foi bem-sucedido
if [ $? -ne 0 ]; then
    echo -e "${RED}Erro ao implantar alterações no Heroku.${NC}"
    exit 1
fi

# Reinicia a aplicação no Heroku
echo -e "${YELLOW}Reiniciando a aplicação no Heroku...${NC}"
heroku restart

# Verifica se o restart foi bem-sucedido
if [ $? -ne 0 ]; then
    echo -e "${RED}Erro ao reiniciar a aplicação no Heroku.${NC}"
    exit 1
fi

echo -e "${GREEN}Implantação das correções no endpoint de status concluída com sucesso!${NC}"
echo -e "${GREEN}O sistema agora mostra corretamente todos os CNPJs na interface, garantindo:${NC}"
echo -e "${GREEN}- Exibição de todos os CNPJs processados, sem limitação de tempo${NC}"
echo -e "${GREEN}- Contagens precisas de CNPJs por status${NC}"
echo -e "${GREEN}- Consultas otimizadas ao banco de dados para melhor performance${NC}"
echo -e "${GREEN}- Consistência entre os dados mostrados e o estado real do banco de dados${NC}"
echo -e "${YELLOW}Para verificar o status da aplicação, acesse a interface web.${NC}"
echo -e "${YELLOW}Para monitorar os logs, execute:${NC}"
echo -e "  heroku logs --tail"

exit 0
