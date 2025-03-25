import requests
import sys
import os

def restart_queue(base_url):
    """
    Reinicia o processamento da fila de CNPJs
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com)
    """
    url = f"{base_url}/api/admin/queue/restart"
    
    try:
        print(f"Reiniciando fila em {url}...")
        response = requests.post(url)
        
        if response.status_code == 200:
            print("Fila reiniciada com sucesso!")
            print(response.json())
            return True
        else:
            print(f"Erro ao reiniciar fila: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Erro ao fazer requisição: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        # Tenta obter a URL do Heroku das variáveis de ambiente
        heroku_app = os.environ.get("HEROKU_APP_NAME")
        if heroku_app:
            base_url = f"https://{heroku_app}.herokuapp.com"
        else:
            # Verifica se estamos rodando no Heroku
            if os.environ.get("DATABASE_URL") and "herokuapp.com" in os.environ.get("DATABASE_URL", ""):
                # Extrai o nome do app do DATABASE_URL
                try:
                    # Formato típico: postgresql://user:pass@host.compute-1.amazonaws.com:5432/dbname
                    db_url = os.environ.get("DATABASE_URL")
                    # Extrai o nome do app do host
                    host_part = db_url.split("@")[1].split(".")[0]
                    # Usa o nome do app para construir a URL da API
                    base_url = f"https://{host_part}.herokuapp.com"
                    print(f"Detectado ambiente Heroku, usando URL: {base_url}")
                except Exception as e:
                    print(f"Erro ao extrair nome do app do DATABASE_URL: {str(e)}")
                    base_url = "https://cnpjdev-b37ba96f9678.herokuapp.com"  # URL padrão para o app
                    print(f"Usando URL padrão: {base_url}")
            else:
                base_url = input("Digite a URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com): ")
    
    restart_queue(base_url)
