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
git add app/services/queue.py app/services/api_manager.py app/services/token_bucket.py app/services/adaptive_rate_limiter.py app/config.py restart_optimized_queue.py check_queue_status.py OTIMIZACAO_FILA.md deploy_optimized_queue.sh

# Commit das alterações
echo -e "${YELLOW}Realizando commit das alterações...${NC}"
git commit -m "Implementação do sistema de Token Bucket adaptativo para controle de taxa de APIs"

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

# Verifica as novas variáveis de ambiente de controle de taxa
echo -e "${YELLOW}Verificando configuração das variáveis de ambiente de controle de taxa...${NC}"

max_concurrent=$(heroku config:get MAX_CONCURRENT_PROCESSING || echo "")
api_cooldown=$(heroku config:get API_COOLDOWN_AFTER_RATE_LIMIT || echo "")
api_cooldown_max=$(heroku config:get API_COOLDOWN_MAX || echo "")
api_safety_factor=$(heroku config:get API_RATE_LIMIT_SAFETY_FACTOR || echo "")
api_safety_factor_low=$(heroku config:get API_RATE_LIMIT_SAFETY_FACTOR_LOW || echo "")
api_safety_factor_high=$(heroku config:get API_RATE_LIMIT_SAFETY_FACTOR_HIGH || echo "")
api_threshold=$(heroku config:get API_RATE_LIMIT_THRESHOLD || echo "")

echo -e "${YELLOW}Variáveis de controle de taxa atuais:${NC}"
echo -e "  MAX_CONCURRENT_PROCESSING=$max_concurrent (esperado: 4)"
echo -e "  API_COOLDOWN_AFTER_RATE_LIMIT=$api_cooldown (esperado: 60)"
echo -e "  API_COOLDOWN_MAX=$api_cooldown_max (esperado: 300)"
echo -e "  API_RATE_LIMIT_SAFETY_FACTOR=$api_safety_factor (esperado: 0.9)"
echo -e "  API_RATE_LIMIT_SAFETY_FACTOR_LOW=$api_safety_factor_low (esperado: 0.7)"
echo -e "  API_RATE_LIMIT_SAFETY_FACTOR_HIGH=$api_safety_factor_high (esperado: 0.8)"
echo -e "  API_RATE_LIMIT_THRESHOLD=$api_threshold (esperado: 3)"

echo -e "${YELLOW}Deseja configurar todas as variáveis de controle de taxa com os valores recomendados? (s/n)${NC}"
read -r resposta
if [[ "$resposta" == "s" ]]; then
    heroku config:set \
        MAX_CONCURRENT_PROCESSING=4 \
        API_COOLDOWN_AFTER_RATE_LIMIT=60 \
        API_COOLDOWN_MAX=300 \
        API_RATE_LIMIT_SAFETY_FACTOR=0.9 \
        API_RATE_LIMIT_SAFETY_FACTOR_LOW=0.7 \
        API_RATE_LIMIT_SAFETY_FACTOR_HIGH=0.8 \
        API_RATE_LIMIT_THRESHOLD=3
    echo -e "${GREEN}Variáveis de controle de taxa configuradas corretamente.${NC}"
else
    echo -e "${YELLOW}As variáveis de controle de taxa não foram alteradas.${NC}"
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

echo -e "${GREEN}Implantação do sistema de Token Bucket adaptativo concluída com sucesso!${NC}"
echo -e "${GREEN}O sistema agora gerenciará as APIs de forma inteligente, garantindo:${NC}"
echo -e "${GREEN}- Respeito aos limites individuais de cada API${NC}"
echo -e "${GREEN}- Maximização do throughput total (11 CNPJs por minuto)${NC}"
echo -e "${GREEN}- Adaptação dinâmica às condições de cada API${NC}"
echo -e "${GREEN}- Monitoramento detalhado do uso das APIs${NC}"
echo -e "${YELLOW}Para verificar o status da fila, execute:${NC}"
echo -e "  heroku run python check_queue_status.py"
echo -e "${YELLOW}Para monitorar os logs, execute:${NC}"
echo -e "  heroku logs --tail"

exit 0
