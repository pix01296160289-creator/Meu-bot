import os
from iqoptionapi.stable_api import IQ_Option

api_iq = None

def conectar_iq_option():
    global api_iq
    # Pega as credenciais direto do .env ou do ambiente (Railway)
    iq_email = os.getenv("IQ_EMAIL")
    iq_senha = os.getenv("IQ_SENHA")

    if not iq_email or not iq_senha:
        print("⚠️ IQ_EMAIL ou IQ_SENHA não configurados nas variáveis de ambiente. Automação desativada.", flush=True)
        return False

    try:
        print(f"🔄 Conectando à IQ Option com a conta: {iq_email}...", flush=True)
        api_iq = IQ_Option(iq_email, iq_senha)
        check, reason = api_iq.connect()
        
        if check:
            print("✅ Conectado à IQ Option com sucesso!", flush=True)
            # Define se vai operar na conta de Treinamento (PRACTICE) ou Real (REAL)
            api_iq.change_balance("PRACTICE") 
            return True
        else:
            print(f"❌ Falha ao conectar na IQ Option. Motivo: {reason}", flush=True)
            return False
    except Exception as e:
        print(f"❌ Erro crítico ao conectar na IQ Option: {e}", flush=True)
        return False

def executar_ordem_iq(iq_symbol, direcao_texto):
    global api_iq
    try:
        if not api_iq or not api_iq.check_connect():
            conectou = conectar_iq_option()
            if not conectou:
                return "⚠️ Ordem não enviada (Sem conexão ativa com a IQ Option)."

        # Define a direção com base no texto gerado pela IA
        direcao = "call" if "CALL" in direcao_texto.upper() else "put"
        valor_investimento = 2.0  # Valor da entrada
        expiracao_minutos = 5     # Tempo de expiração (M5)

        print(f"⚡ Enviando ordem: {iq_symbol} | {direcao.upper()} | ${valor_investimento}", flush=True)
        check_status, id_transacao = api_iq.buy(valor_investimento, iq_symbol, direcao, expiracao_minutos)

        if check_status:
            return f"🚀 **Ordem executada na IQ Option com sucesso!** (ID: `{id_transacao}`)"
        else:
            return f"⚠️ **Falha ao abrir ordem na corretora:** `{id_transacao}`"
    except Exception as e:
        return f"❌ Erro ao processar ordem na IQ Option: {e}"
