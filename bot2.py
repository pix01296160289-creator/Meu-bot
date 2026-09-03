import asyncio
from quotexpy import Quotex

async def main():
    # Inicializa a instância com e-mail e senha
    client = Quotex(
        email="elizeu.lzu250388@gmail.com",
        password="Lzu975310",
        lara_demo=True # True para conta Demo, False para Real
    )

    # Realiza a conexão (geralmente autentica via WebSocket)
    check = await client.connect()

    if check:
        print("Conectado com sucesso!")

        # Puxa o saldo atual da conta
        balance = await client.get_balance()
        print(f"Saldo atual: {balance}")
    else:
        print("Falha na autenticação. Verifique suas credenciais ou barreiras de segurança.")

    await client.close()

# Executa o script assíncrono
if __name__ == "__main__":
    asyncio.run(main())
    
