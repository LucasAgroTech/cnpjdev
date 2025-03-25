#!/bin/bash
# Script para implantar a correção do problema de status "concluído" no ambiente de produção

echo "===== INICIANDO IMPLANTAÇÃO DA CORREÇÃO ====="
echo "Data e hora: $(date)"
echo

# Verifica se está no diretório correto
if [ ! -f "app/services/queue.py" ] || [ ! -f "app/api/endpoints.py" ]; then
    echo "ERRO: Este script deve ser executado no diretório raiz do projeto."
    exit 1
fi

# Verifica se os scripts de diagnóstico e correção existem
if [ ! -f "check_db_status.py" ] || [ ! -f "fix_incomplete_status.py" ]; then
    echo "ERRO: Os scripts check_db_status.py e fix_incomplete_status.py devem existir no diretório raiz."
    exit 1
fi

# Torna os scripts executáveis
chmod +x check_db_status.py
chmod +x fix_incomplete_status.py

echo "===== ETAPA 1: DIAGNÓSTICO DO BANCO DE DADOS ====="
echo "Executando diagnóstico para verificar o estado atual..."
python check_db_status.py
echo "Diagnóstico concluído."
echo

echo "===== ETAPA 2: CORREÇÃO DE STATUS INCOMPLETOS ====="
echo "Deseja executar a correção de status incompletos? (s/n)"
read -r resposta
if [[ "$resposta" =~ ^[Ss]$ ]]; then
    echo "Executando correção..."
    python fix_incomplete_status.py
    echo "Correção concluída."
else
    echo "Correção ignorada."
fi
echo

echo "===== ETAPA 3: REINICIAR PROCESSAMENTO DA FILA ====="
echo "Deseja reiniciar o processamento da fila? (s/n)"
read -r resposta
if [[ "$resposta" =~ ^[Ss]$ ]]; then
    echo "Reiniciando processamento da fila..."
    
    # Verifica se está em ambiente Heroku
    if command -v heroku &> /dev/null; then
        echo "Ambiente Heroku detectado. Executando via API..."
        curl -X POST https://$(heroku info -s | grep web_url | cut -d= -f2 | sed 's/https:\/\///')/api/admin/queue/restart
    else
        echo "Ambiente local detectado. Executando via script..."
        python restart_queue.py
    fi
    
    echo "Processamento da fila reiniciado."
else
    echo "Reinicialização ignorada."
fi
echo

echo "===== ETAPA 4: VERIFICAÇÃO FINAL ====="
echo "Executando diagnóstico final para verificar se a correção foi aplicada..."
python check_db_status.py
echo "Verificação final concluída."
echo

echo "===== IMPLANTAÇÃO CONCLUÍDA ====="
echo "Data e hora: $(date)"
echo
echo "IMPORTANTE: Monitore os logs para verificar se o problema foi resolvido."
echo "Comando para verificar logs no Heroku: heroku logs --tail"
