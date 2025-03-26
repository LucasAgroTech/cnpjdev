#!/bin/bash
# Script para implantar as otimizações da fila de consulta de CNPJs

# Cores para saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Iniciando implantação das otimizações da fila de consulta de CNPJs...${NC}"

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
git add app/services/queue.py app/services/api_manager.py restart_optimized_queue.py OTIMIZACAO_FILA.md deploy_optimized_queue.sh

# Commit das alterações
echo -e "${YELLOW}Realizando commit das alterações...${NC}"
git commit -m "Otimização da fila para processar exatamente 11 CNPJs por minuto"

# Verifica se o commit foi bem-sucedido
if [ $? -ne 0 ]; then
    echo -e "${RED}Erro ao realizar commit das alterações.${NC}"
    exit 1
fi

# Implanta no Heroku
echo -e "${YELLOW}Implantando alterações no Heroku...${NC}"
git push heroku master

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

# Verifica se a variável de ambiente REQUESTS_PER_MINUTE está configurada corretamente
echo -e "${YELLOW}Verificando configuração da variável REQUESTS_PER_MINUTE...${NC}"
current_rpm=$(heroku config:get REQUESTS_PER_MINUTE)

# Calcula a soma das taxas individuais das APIs
receitaws_rpm=$(heroku config:get RECEITAWS_REQUESTS_PER_MINUTE || echo "3")
cnpjws_rpm=$(heroku config:get CNPJWS_REQUESTS_PER_MINUTE || echo "3")
cnpja_open_rpm=$(heroku config:get CNPJA_OPEN_REQUESTS_PER_MINUTE || echo "5")

# Converte para números inteiros
receitaws_rpm_int=$((receitaws_rpm))
cnpjws_rpm_int=$((cnpjws_rpm))
cnpja_open_rpm_int=$((cnpja_open_rpm))

# Calcula a soma
total_rpm=$((receitaws_rpm_int + cnpjws_rpm_int + cnpja_open_rpm_int))

if [ "$current_rpm" != "$total_rpm" ]; then
    echo -e "${YELLOW}A variável REQUESTS_PER_MINUTE não está configurada como $total_rpm (soma das taxas individuais). Deseja configurá-la agora? (s/n)${NC}"
    read -r resposta
    if [[ "$resposta" == "s" ]]; then
        heroku config:set REQUESTS_PER_MINUTE=$total_rpm
        echo -e "${GREEN}Variável REQUESTS_PER_MINUTE configurada como $total_rpm.${NC}"
    else
        echo -e "${YELLOW}A variável REQUESTS_PER_MINUTE não foi alterada. O sistema pode não processar corretamente os CNPJs.${NC}"
    fi
else
    echo -e "${GREEN}A variável REQUESTS_PER_MINUTE já está configurada corretamente como $total_rpm.${NC}"
fi

# Verifica as demais variáveis de ambiente relacionadas às APIs
echo -e "${YELLOW}Verificando configuração das variáveis de ambiente das APIs...${NC}"

# ReceitaWS
receitaws_enabled=$(heroku config:get RECEITAWS_ENABLED)
receitaws_rpm=$(heroku config:get RECEITAWS_REQUESTS_PER_MINUTE)

if [ "$receitaws_enabled" != "True" ] || [ "$receitaws_rpm" != "3" ]; then
    echo -e "${YELLOW}As variáveis da API ReceitaWS podem não estar configuradas corretamente:${NC}"
    echo -e "  RECEITAWS_ENABLED=$receitaws_enabled (esperado: True)"
    echo -e "  RECEITAWS_REQUESTS_PER_MINUTE=$receitaws_rpm (esperado: 3)"
    echo -e "${YELLOW}Deseja configurá-las agora? (s/n)${NC}"
    read -r resposta
    if [[ "$resposta" == "s" ]]; then
        heroku config:set RECEITAWS_ENABLED=True RECEITAWS_REQUESTS_PER_MINUTE=3
        echo -e "${GREEN}Variáveis da API ReceitaWS configuradas corretamente.${NC}"
    fi
else
    echo -e "${GREEN}Variáveis da API ReceitaWS já estão configuradas corretamente.${NC}"
fi

# CNPJ.ws
cnpjws_enabled=$(heroku config:get CNPJWS_ENABLED)
cnpjws_rpm=$(heroku config:get CNPJWS_REQUESTS_PER_MINUTE)

if [ "$cnpjws_enabled" != "True" ] || [ "$cnpjws_rpm" != "3" ]; then
    echo -e "${YELLOW}As variáveis da API CNPJ.ws podem não estar configuradas corretamente:${NC}"
    echo -e "  CNPJWS_ENABLED=$cnpjws_enabled (esperado: True)"
    echo -e "  CNPJWS_REQUESTS_PER_MINUTE=$cnpjws_rpm (esperado: 3)"
    echo -e "${YELLOW}Deseja configurá-las agora? (s/n)${NC}"
    read -r resposta
    if [[ "$resposta" == "s" ]]; then
        heroku config:set CNPJWS_ENABLED=True CNPJWS_REQUESTS_PER_MINUTE=3
        echo -e "${GREEN}Variáveis da API CNPJ.ws configuradas corretamente.${NC}"
    fi
else
    echo -e "${GREEN}Variáveis da API CNPJ.ws já estão configuradas corretamente.${NC}"
fi

# CNPJa Open
cnpja_open_enabled=$(heroku config:get CNPJA_OPEN_ENABLED)
cnpja_open_rpm=$(heroku config:get CNPJA_OPEN_REQUESTS_PER_MINUTE)

if [ "$cnpja_open_enabled" != "True" ] || [ "$cnpja_open_rpm" != "5" ]; then
    echo -e "${YELLOW}As variáveis da API CNPJa Open podem não estar configuradas corretamente:${NC}"
    echo -e "  CNPJA_OPEN_ENABLED=$cnpja_open_enabled (esperado: True)"
    echo -e "  CNPJA_OPEN_REQUESTS_PER_MINUTE=$cnpja_open_rpm (esperado: 5)"
    echo -e "${YELLOW}Deseja configurá-las agora? (s/n)${NC}"
    read -r resposta
    if [[ "$resposta" == "s" ]]; then
        heroku config:set CNPJA_OPEN_ENABLED=True CNPJA_OPEN_REQUESTS_PER_MINUTE=5
        echo -e "${GREEN}Variáveis da API CNPJa Open configuradas corretamente.${NC}"
    fi
else
    echo -e "${GREEN}Variáveis da API CNPJa Open já estão configuradas corretamente.${NC}"
fi

# Executa o script de reinicialização da fila otimizada
echo -e "${YELLOW}Executando script de reinicialização da fila otimizada...${NC}"
heroku run python restart_optimized_queue.py

# Verifica se o script foi executado com sucesso
if [ $? -ne 0 ]; then
    echo -e "${RED}Erro ao executar o script de reinicialização da fila otimizada.${NC}"
    exit 1
fi

echo -e "${GREEN}Implantação das otimizações da fila concluída com sucesso!${NC}"
echo -e "${GREEN}O sistema agora processará exatamente 11 CNPJs por minuto.${NC}"
echo -e "${YELLOW}Para verificar o status da fila, execute:${NC}"
echo -e "  heroku run python check_queue_status.py"
echo -e "${YELLOW}Para monitorar os logs, execute:${NC}"
echo -e "  heroku logs --tail"

exit 0
