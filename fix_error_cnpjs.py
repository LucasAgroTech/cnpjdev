#!/usr/bin/env python3
import os
import sys
import argparse
import requests
from datetime import datetime

# Tenta importar psycopg2 e python-dotenv
try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    print("ERRO: O módulo 'psycopg2' não está instalado.")
    print("Instale-o com: pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERRO: O módulo 'python-dotenv' não está instalado.")
    print("Instale-o com: pip install python-dotenv")
    sys.exit(1)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Reseta CNPJs com status de erro para "queued"')
    parser.add_argument('--db-url', help='URL de conexão com o banco de dados (ex: postgresql://usuario:senha@host:porta/nome_banco)')
    parser.add_argument('--api-url', help='URL base da API para reiniciar a fila (ex: https://seu-app.herokuapp.com)')
    parser.add_argument('--no-restart', action='store_true', help='Não reiniciar a fila após resetar os CNPJs')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar informações detalhadas')
    
    return parser.parse_args()

def get_database_url(args):
    """Get database URL from args or environment"""
    # Prioridade: 1. Argumento da linha de comando, 2. Variável de ambiente
    if args.db_url:
        return args.db_url
    
    # Tenta carregar do arquivo .env
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        print("ERRO: URL do banco de dados não fornecida.")
        print("Forneça a URL do banco de dados usando o argumento --db-url ou defina DATABASE_URL no arquivo .env")
        sys.exit(1)
    
    return db_url

def get_api_url(args):
    """Get API URL from args or environment"""
    if args.api_url:
        return args.api_url
    
    # Tenta obter do ambiente
    heroku_app = os.environ.get("HEROKU_APP_NAME")
    if heroku_app:
        return f"https://{heroku_app}.herokuapp.com"
    
    return None

def connect_to_database(db_url):
    """Connect to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"ERRO: Não foi possível conectar ao banco de dados: {str(e)}")
        sys.exit(1)

def reset_error_cnpjs(conn, verbose=False):
    """Reset CNPJs with error status to queued"""
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Primeiro, conta quantos CNPJs estão com erro
            cur.execute("SELECT COUNT(*) FROM cnpj_queries WHERE status = 'error'")
            error_count = cur.fetchone()[0]
            
            if error_count == 0:
                print("Nenhum CNPJ com erro encontrado.")
                return 0
            
            # Obtém os CNPJs com erro para exibir detalhes se verbose=True
            if verbose:
                cur.execute("SELECT cnpj, error_message, updated_at FROM cnpj_queries WHERE status = 'error'")
                error_cnpjs = cur.fetchall()
                print(f"\nDetalhes dos {error_count} CNPJs com erro:")
                for i, row in enumerate(error_cnpjs, 1):
                    print(f"{i}. CNPJ: {row['cnpj']}")
                    print(f"   Erro: {row['error_message']}")
                    print(f"   Última atualização: {row['updated_at']}")
                    print()
            
            # Atualiza o status para "queued"
            now = datetime.utcnow()
            cur.execute("""
                UPDATE cnpj_queries 
                SET status = 'queued', 
                    error_message = NULL, 
                    updated_at = %s 
                WHERE status = 'error'
            """, (now,))
            
            # Confirma as alterações
            conn.commit()
            
            print(f"Sucesso! {error_count} CNPJs com erro foram resetados para 'queued'.")
            return error_count
            
    except Exception as e:
        conn.rollback()
        print(f"ERRO: Falha ao resetar CNPJs: {str(e)}")
        return 0

def restart_queue(api_url):
    """Restart the queue processing by calling the API"""
    if not api_url:
        print("URL da API não fornecida. A fila não será reiniciada automaticamente.")
        return False
    
    url = f"{api_url}/api/admin/queue/restart"
    
    try:
        print(f"Reiniciando fila em {url}...")
        response = requests.post(url)
        
        if response.status_code == 200:
            print("Fila reiniciada com sucesso!")
            return True
        else:
            print(f"Erro ao reiniciar fila: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Erro ao fazer requisição para reiniciar a fila: {str(e)}")
        return False

def main():
    """Main function"""
    args = parse_args()
    
    # Obtém a URL do banco de dados
    db_url = get_database_url(args)
    
    # Conecta ao banco de dados
    print(f"Conectando ao banco de dados...")
    conn = connect_to_database(db_url)
    
    try:
        # Reseta CNPJs com erro
        print("Resetando CNPJs com erro para 'queued'...")
        reset_count = reset_error_cnpjs(conn, args.verbose)
        
        # Reinicia a fila se necessário
        if reset_count > 0 and not args.no_restart:
            api_url = get_api_url(args)
            if api_url:
                restart_queue(api_url)
            else:
                print("\nPara reiniciar a fila, execute o comando:")
                print("python3 restart_queue.py [URL_BASE]")
    finally:
        # Fecha a conexão com o banco de dados
        conn.close()

if __name__ == "__main__":
    main()
