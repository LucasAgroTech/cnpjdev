#!/bin/bash

# Script para implantar a correção de violação de restrição única
# Este script faz o commit das alterações e as envia para o Heroku

echo "Iniciando implantação da correção para violação de restrição única..."

# Adiciona as alterações ao git
git add app/services/queue.py

# Faz o commit das alterações
git commit -m "Fix: Pular para o próximo CNPJ quando já existir no banco de dados"

# Envia as alterações para o Heroku
git push heroku main

echo "Implantação concluída!"
echo "A correção foi implantada e o sistema agora irá pular para o próximo CNPJ quando um já existir no banco de dados."
