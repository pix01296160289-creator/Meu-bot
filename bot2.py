import os
import asyncio
from dotenv import load_dotenv
from quotex.api import Quotex

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")

async def main():
    if not EMAIL or not PASSWORD:
        print("Erro: As credenciais QUOTEX_EMAIL e QUOTEX_PASSWORD não foram encontradas!")
        return

    # Inicializa o cliente da Quotex
    client = Quotex(
        email=EMAIL,
        password=PASSWORD,
        lara_demo=True  # True para conta Demo, False para conta Real
    )

    print("Conectando à Quotex...")

    try:
        check, reason = await client.connect()
        if check:
            print("Conectado com sucesso!")

            # Obtém o saldo atual da conta
            balance = await client.get_balance()
            print(f"Saldo atual: {balance}")
        else:
            print(f"Falha na conexão: {reason}")

    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
