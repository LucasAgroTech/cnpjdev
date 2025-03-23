import pandas as pd

# Lê o arquivo CSV
df = pd.read_csv('exemplo_cnpjs.csv', sep=';')

# Salva como Excel
df.to_excel('exemplo_cnpjs.xlsx', index=False)

print("Arquivo Excel criado com sucesso: exemplo_cnpjs.xlsx")
