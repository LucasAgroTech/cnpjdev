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
            base_url = input("Digite a URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com): ")
    
    restart_queue(base_url)
