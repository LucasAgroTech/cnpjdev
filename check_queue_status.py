import requests
import sys
import os
import time
from datetime import datetime

def check_queue_status(base_url, interval=10, count=1):
    """
    Verifica o status da fila de CNPJs
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com)
        interval: Intervalo em segundos entre verificações (padrão: 10)
        count: Número de verificações a realizar (padrão: 1, 0 para contínuo)
    """
    url = f"{base_url}/api/admin/queue/status"
    
    checks = 0
    continuous = count == 0
    
    try:
        while continuous or checks < count:
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
            
            checks += 1
            
            if continuous or checks < count:
                print(f"\nAguardando {interval} segundos para próxima verificação...")
                time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\nVerificação interrompida pelo usuário.")

if __name__ == "__main__":
    # Processa argumentos
    base_url = None
    interval = 10
    count = 1
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        
        if len(sys.argv) > 2:
            try:
                interval = int(sys.argv[2])
            except ValueError:
                print(f"Intervalo inválido: {sys.argv[2]}. Usando padrão: 10 segundos.")
        
        if len(sys.argv) > 3:
            try:
                count = int(sys.argv[3])
            except ValueError:
                print(f"Contagem inválida: {sys.argv[3]}. Usando padrão: 1 verificação.")
    
    if not base_url:
        # Tenta obter a URL do Heroku das variáveis de ambiente
        heroku_app = os.environ.get("HEROKU_APP_NAME")
        if heroku_app:
            base_url = f"https://{heroku_app}.herokuapp.com"
        else:
            base_url = input("Digite a URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com): ")
    
    print(f"Verificando status da fila em {base_url}")
    print(f"Intervalo: {interval} segundos")
    print(f"Contagem: {count if count > 0 else 'contínuo'}")
    
    check_queue_status(base_url, interval, count)
