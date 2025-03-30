#!/bin/bash
# Script para implantar as otimizações de exportação de Excel com streaming

# Cores para saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Iniciando implantação das otimizações de exportação de Excel com streaming...${NC}"

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
git add app/api/endpoints.py templates/index.html deploy_streaming_excel.sh

# Commit das alterações se houver algo para commitar
echo -e "${YELLOW}Verificando se há alterações para commitar...${NC}"
if git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Não há alterações para commitar. Continuando com o deploy...${NC}"
else
    echo -e "${YELLOW}Realizando commit das alterações...${NC}"
    git commit -m "Implementação de exportação de Excel com streaming para otimização de memória"
    
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

# Verifica a configuração de memória do dyno
echo -e "${YELLOW}Verificando configuração de memória do dyno...${NC}"
current_dyno=$(heroku ps)

echo -e "${YELLOW}Configuração atual do dyno:${NC}"
echo "$current_dyno"

echo -e "${YELLOW}Recomendação: Para grandes volumes de dados, considere aumentar o tamanho do dyno.${NC}"
echo -e "${YELLOW}Você pode fazer isso com o comando:${NC}"
echo -e "  heroku ps:resize web=standard-2x"
echo -e "${YELLOW}Deseja aumentar o tamanho do dyno agora? (s/n)${NC}"
read -r resposta
if [[ "$resposta" == "s" ]]; then
    echo -e "${YELLOW}Qual o tamanho desejado para o dyno? (standard-1x, standard-2x, performance-m, performance-l)${NC}"
    read -r dyno_size
    heroku ps:resize web=$dyno_size
    echo -e "${GREEN}Tamanho do dyno alterado para $dyno_size.${NC}"
else
    echo -e "${YELLOW}O tamanho do dyno não foi alterado.${NC}"
fi

echo -e "${GREEN}Implantação das otimizações de exportação de Excel com streaming concluída com sucesso!${NC}"
echo -e "${GREEN}O sistema agora exporta Excel de forma otimizada, garantindo:${NC}"
echo -e "${GREEN}- Menor consumo de memória durante a exportação${NC}"
echo -e "${GREEN}- Processamento em lotes para evitar timeouts${NC}"
echo -e "${GREEN}- Suporte a grandes volumes de dados${NC}"
echo -e "${GREEN}- Interface atualizada com opções de exportação otimizada${NC}"
echo -e "${YELLOW}Para testar a exportação, acesse a aplicação e use o botão 'EXPORTAR' no painel de monitoramento.${NC}"
echo -e "${YELLOW}Para monitorar os logs, execute:${NC}"
echo -e "  heroku logs --tail"

exit 0
