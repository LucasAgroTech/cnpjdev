import requests
import sys
import os

def reset_error_cnpjs(base_url):
    """
    Reseta CNPJs com status de erro para 'queued' e reinicia o processamento
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000 ou https://app-name.herokuapp.com)
    """
    url = f"{base_url}/api/admin/queue/reset-errors"
    
    try:
        print(f"Resetando CNPJs com erro em {url}...")
        response = requests.post(url)
        
        if response.status_code == 200:
            result = response.json()
            count = result.get("count", 0)
            
            if count > 0:
                print(f"Sucesso! {count} CNPJs com erro foram resetados e colocados na fila novamente.")
                print(result.get("message", ""))
            else:
                print("Nenhum CNPJ com erro foi encontrado para resetar.")
            
            return True
        else:
            print(f"Erro ao resetar CNPJs: {response.status_code}")
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
    
    reset_error_cnpjs(base_url)
