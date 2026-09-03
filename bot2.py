import os
import asyncio
from dotenv import load_dotenv
import quotexpy

# Carrega as variáveis de ambiente
load_dotenv()

# Puxa o e-mail e a senha das variáveis de ambiente
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")

async def main():
    if not EMAIL or not PASSWORD:
        print("Erro: As credenciais QUOTEX_EMAIL e QUOTEX_PASSWORD não foram encontradas!")
        return

    # Vamos tentar instanciar usando o nome padrão da classe na biblioteca (QuotexAPI ou Quotex)
    # Caso a classe mude, verificamos o atributo correto
    client_class = getattr(quotexpy, "QuotexAPI", None) or getattr(quotexpy, "Quotex", None)
    
    if not client_class:
        # Se não encontrar direto, lista o que tem disponível para ajudar a debugar
        print("Classes disponíveis em quotexpy:", dir(quotexpy))
        return

    # Inicializa o cliente
    client = client_class(
        email=EMAIL,
        password=PASSWORD,
        lara_demo=True  # True para conta Demo, False para conta Real
    )

    print("Conectando à Quotex...")
    check, reason = await client.connect()
    
    if check:
        print("Conectado com sucesso!")
        
        # Puxa o saldo atual da conta
        balance = await client.get_balance()
        print(f"Saldo atual: {balance}")
    else:
        print(f"Falha na conexão: {reason}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
