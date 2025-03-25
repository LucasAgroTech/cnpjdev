#!/usr/bin/env python3
"""
Script para reiniciar a fila de processamento de CNPJs com configurações otimizadas.
Este script limpa CNPJs presos em processamento e reinicia a fila.
"""

import requests
import sys
import os
import time
from datetime import datetime

def restart_queue(base_url):
    """
    Reinicia a fila de processamento de CNPJs
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com)
    """
    url = f"{base_url}/api/admin/queue/restart"
    
    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Reiniciando fila de processamento em {url}...")
        response = requests.post(url)
        
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta: {data.get('message', 'Reinicialização iniciada')}")
            print("\nFila reiniciada com sucesso. Aguardando 5 segundos para verificar o status...")
            time.sleep(5)
            check_queue_status(base_url)
        else:
            print(f"Erro ao reiniciar fila: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"Erro ao fazer requisição: {str(e)}")

def check_queue_status(base_url):
    """
    Verifica o status da fila de CNPJs
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com)
    """
    url = f"{base_url}/api/admin/queue/status"
    
    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Verificando status da fila em {url}...")
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            queue_status = data.get("queue_status", {})
            
            print("\n=== STATUS DA FILA ===")
            print(f"Na fila:      {queue_status.get('queued', 0)}")
            print(f"Em processo:  {queue_status.get('processing', 0)}")
            print(f"Concluídos:   {queue_status.get('completed', 0)}")
            print(f"Com erro:     {queue_status.get('error', 0)}")
            print(f"Total:        {queue_status.get('total', 0)}")
            
            # Mostra CNPJs pendentes recentes
            recent_pending = data.get("recent_pending", [])
            if recent_pending:
                print("\n=== CNPJs PENDENTES RECENTES ===")
                for item in recent_pending:
                    cnpj = item.get("cnpj", "")
                    status = item.get("status", "")
                    updated_at = item.get("updated_at", "").replace("T", " ").split(".")[0]
                    print(f"{cnpj} - {status} - Atualizado em: {updated_at}")
        else:
            print(f"Erro ao verificar status: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"Erro ao fazer requisição: {str(e)}")

def reset_errors_and_rate_limited(base_url):
    """
    Reseta CNPJs com status de erro e limite de requisições excedido
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com)
    """
    url = f"{base_url}/api/admin/queue/reset-all-pending"
    
    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Resetando CNPJs com erro e limite excedido em {url}...")
        response = requests.post(url)
        
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta: {data.get('message', 'Reset iniciado')}")
            print("\nCNPJs resetados com sucesso. Aguardando 5 segundos para verificar o status...")
            time.sleep(5)
            check_queue_status(base_url)
        else:
            print(f"Erro ao resetar CNPJs: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"Erro ao fazer requisição: {str(e)}")

def main():
    # Processa argumentos
    base_url = None
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    if not base_url:
        # Tenta obter a URL do Heroku das variáveis de ambiente
        heroku_app = os.environ.get("HEROKU_APP_NAME")
        if heroku_app:
            base_url = f"https://{heroku_app}.herokuapp.com"
        else:
            base_url = input("Digite a URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com): ")
    
    print(f"Usando URL base: {base_url}")
    
    # Verifica o status atual
    print("\n=== VERIFICANDO STATUS ATUAL ===")
    check_queue_status(base_url)
    
    # Reseta CNPJs com erro e limite excedido
    print("\n=== RESETANDO CNPJs COM ERRO E LIMITE EXCEDIDO ===")
    reset_errors_and_rate_limited(base_url)
    
    # Reinicia a fila
    print("\n=== REINICIANDO FILA DE PROCESSAMENTO ===")
    restart_queue(base_url)
    
    print("\nProcesso concluído. A fila foi reiniciada com as configurações otimizadas.")
    print("Agora o sistema deve processar até 11 CNPJs por minuto.")
    print("\nPara monitorar o status da fila em tempo real, execute:")
    print(f"python check_queue_status.py {base_url} 10 0")

if __name__ == "__main__":
    main()
