import os
import sys
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import requests
import yfinance as yf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# =========================
# CONFIGURAÇÃO E CHAVES (.env)
# =========================
print("🔄 Carregando variáveis do .env...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"🔑 Token do Telegram encontrado? {'Sim' if TOKEN else 'Não'}", flush=True)
print(f"🔑 Groq Key encontrada? {'Sim' if GROQ_API_KEY else 'Não'}", flush=True)

if not TOKEN:
    print("❌ ERRO: O token do Telegram não foi encontrado!", flush=True)
    sys.exit(1)

if not GROQ_API_KEY:
    print("❌ ERRO: A chave GROQ_API_KEY não foi encontrada!", flush=True)
    sys.exit(1)

# =========================
# LISTAS DE PALAVRAS-CHAVE
# =========================
PALAVRAS_SINAL = ["sinal", "análise", "mercado", "entrada", "stop", "comprar", "vender"]
PALAVRAS_CHAT = ["oi", "olá", "bom dia", "boa tarde", "boa noite", "ajuda", "tudo bem"]
PALAVRAS_COTACAO = ["cotação", "preço", "valor", "quanto está"]

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# MAPA DE ATIVOS CRIPTO
# =========================
MAPA_ATIVOS = {
    "btc_brl": {"par_api": "BTC-BRL", "nome": "Bitcoin / Real (BTC/BRL)", "multiplicador": 1, "limite_variacao": 500.0},
    "btc_usd": {"par_api": "BTC-USD", "nome": "Bitcoin / Dólar (BTC/USD)", "multiplicador": 1, "limite_variacao": 100.0},
    "eth_brl": {"par_api": "ETH-BRL", "nome": "Ethereum / Real (ETH/BRL)", "multiplicador": 1, "limite_variacao": 150.0},
    "sol_brl": {"par_api": "SOL-BRL", "nome": "Solana / Real (SOL/BRL)", "multiplicador": 1, "limite_variacao": 20.0},
    "xau_usd": {"par_api": "GC=F", "nome": "Ouro / Dólar (XAU/USD)", "multiplicador": 1, "limite_variacao": 25.0}
}

# =========================
# VERIFICAÇÃO DE MERCADO (CRIPTO É 24/7)
# =========================
def verificar_status_mercado(par_api):
    fuso_brasil = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(fuso_brasil)
    data_formatada = agora.strftime('%d/%m/%Y às %H:%M')
    
    return True, f"🟢 **MERCADO CRIPTO 24/7 ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

# =========================
# OBTER PREÇO (YAHOO FINANCE COM FALLBACK ROBUSTO)
# =========================
def obter_preco_atual(par_api):
    try:
        ticker_symbol = par_api
        ticker_obj = yf.Ticker(ticker_symbol)
        
        # Tentativa 1: Dados intradiários recentes
        dados = ticker_obj.history(period="1d", interval="1m")
        if not dados.empty and "Close" in dados.columns:
            preco_recente = dados["Close"].iloc[-1]
            if hasattr(preco_recente, "item"):
                preco_recente = preco_recente.item()
            if preco_recente and preco_recente > 0:
                return float(preco_recente)
                
        # Tentativa 2: Histórico padrão de 1 dia
        hist = ticker_obj.history(period="1d")
        if not hist.empty and "Close" in hist.columns:
            preco_recente = hist["Close"].iloc[-1]
            if hasattr(preco_recente, "item"):
                preco_recente = preco_recente.item()
            if preco_recente and preco_recente > 0:
                return float(preco_recente)
                
        return 0.0
    except Exception as e:
        print(f"⚠️ Erro ao buscar preço para {par_api}: {e}", flush=True)
        return 0.0

# =========================
# CHAMADA À API DA GROQ (MODELO COMPATÍVEL)
# =========================
def chamar_groq(pergunta_usuario, nome_usuario="Amigo", modo_sinal=False):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    if modo_sinal:
        instrucao_sistema = (
            f"Você é o analista sênior e quantitativo do 'Crypto Signals Bot' especializado em Bitcoin e Criptoativos. "
            f"O trader se chama {nome_usuario}. "
            f"Monte um **Sinal de Trade / Análise Profissional Quantitativa para Cripto**, utilizando obrigatoriamente o preço real fornecido. "
            f"Realize projeções matemáticas e estimativas de risco/retorno (Risk/Reward 1:2 ou 1:3) baseadas na volatilidade atual do ativo. "
            f"NÃO inclua nenhum aviso legal. Termine a mensagem logo após a recomendação prática. "
            f"Siga rigorosamente este modelo visual:\n\n"
            f"🎯 **ANÁLISE QUANTITATIVA - [NOME DO ATIVO]**\n"
            f"• **Status:** Mercado 24/7 🟢\n"
            f"• **Tendência Estatística:** [Alta / Baixa / Consolidação]\n"
            f"• **Preço de Referência:** [Valor exato fornecido]\n\n"
            f"📊 **ESTRATÉGIA MATEMÁTICA DE OPERAÇÃO:**\n"
            f"• **Direção:** [COMPRA (LONG) 🟢 / VENDA (SHORT) 🔴]\n"
            f"• **Zona Ótima de Entrada:** [Preço ideal]\n"
            f"• **Alvo Matemático (Take Profit):** [Preço alvo]\n"
            f"• **Stop Loss Técnico:** [Preço limite de segurança]\n"
            f"• **Relação Risco/Retorno:** [Ex: 1:2.5]\n\n"
            f"💡 *[Análise sintética de momento e fluxo baseada em matemática aplicada]*"
        )
    else:
        instrucao_sistema = f"Você é o assistente executivo focado em criptomoedas, finanças quantitativas e inteligência de mercado do 'Crypto Bot'. O usuário se chama {nome_usuario}."

    # Utilizando o modelo padrão que funciona universalmente em contas Groq
    payload = {
        "model": "gemma2-9b-it",
        "messages": [
            {"role": "system", "content": instrucao_sistema},
            {"role": "user", "content": pergunta_usuario}
        ],
        "temperature": 0.4
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API da Groq: {response.status_code} - Resposta: {response.text}"
    except Exception as e:
        return f"❌ Erro de conexão com a Groq: {e}"

# =========================
# MONITORAMENTO CONTÍNUO E ANÁLISE REAL
# =========================
async def executar_analise_mercado(chat_id, context, nome_usuario, sigla_chave, par_api, nome_ativo):
    mercado_aberto, info_status = verificar_status_mercado(par_api)

    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"👀 *MONITORAMENTO EM TEMPO REAL: {nome_ativo.upper()}*\n\nO bot está rastreando a volatilidade e o livro de preços. Assim que houver variação relevante, a análise técnica será disparada!\n\n{info_status}", 
        parse_mode="Markdown"
    )

    preco_anterior = 0.0
    tentativas = 0
    while preco_anterior == 0.0 and tentativas < 10:
        preco_anterior = obter_preco_atual(par_api)
        if preco_anterior == 0.0:
            tentativas += 1
            await asyncio.sleep(3)

    if preco_anterior == 0.0:
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"❌ Não foi possível obter o preço atual para {nome_ativo} neste momento devido a instabilidade na fonte de dados. Tente novamente em instantes.",
            parse_mode="Markdown"
        )
        return

    print(f"📊 Monitor cripto ativado para {nome_ativo}. Preço base: {preco_anterior}", flush=True)

    ciclos = 0
    max_ciclos = 180  

    while ciclos < max_ciclos:
        try:
            await asyncio.sleep(15)
            ciclos += 1
            preco_atual = obter_preco_atual(par_api)
            
            if preco_atual > 0:
                variacao_absoluta = abs(preco_atual - preco_anterior)
                limite = MAPA_ATIVOS[sigla_chave]["limite_variacao"]
                
                if variacao_absoluta >= limite or ciclos >= 30:
                    print(f"🚨 Movimento detectado em {nome_ativo}: {preco_anterior} ➔ {preco_atual} (Var: {variacao_absoluta})", flush=True)
                    
                    preco_atual_str = f"{preco_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

                    dados_mercado = (
                        f"Ativo: {nome_ativo} | "
                        f"Preço Atualizado Confirmado: {preco_atual_str} | "
                        f"Variação Registrada desde o último ciclo: {variacao_absoluta:,.2f}"
                    )

                    prompt_ia = f"Gere o relatório analítico quantitativo de criptomoeda para os dados reais: {dados_mercado}. Utilize obrigatoriamente o preço atual."

                    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                    resposta_ia = chamar_groq(prompt_ia, nome_usuario, modo_sinal=True)

                    await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")
                    break
                
        except Exception as e:
            print(f"⚠️ Erro no loop de monitoramento: {e}", flush=True)
            await asyncio.sleep(15)

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("nome", None)
    url_imagem = "https://images.unsplash.com/photo-1621416894569-0f39ed31d247?q=80&w=1000&auto=format&fit=crop"
    legenda_boas_vindas = (
        "🚀 **BEM-VINDO AO BITCOIN & CRYPTO BOT** 🪙\n\n"
        "SEU TERMINAL INTELIGENTE DE PREVISÃO E ANÁLISE DE ATIVOS DIGITAIS.\n\n"
        "PARA COMEÇAR, POR FAVOR, INFORME:\n"
        "👉 **QUAL É O SEU NOME OU APELIDO?**"
    )

    try:
        await update.message.reply_photo(photo=url_imagem, caption=legenda_boas_vindas, parse_mode="Markdown")
    except:
        await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")

async def enviar_menu_principal(update_or_query, context, nome_usuario):
    teclado = [
        [InlineKeyboardButton("🪙 BITCOIN / REAL (BTC/BRL)", callback_data="btn_btc_brl")],
        [InlineKeyboardButton("💵 BITCOIN / DÓLAR (BTC/USD)", callback_data="btn_btc_usd")],
        [InlineKeyboardButton("🔷 ETHEREUM (ETH/BRL)", callback_data="btn_eth_brl")],
        [InlineKeyboardButton("⚡ SOLANA (SOL/BRL)", callback_data="btn_sol_brl")],
        [InlineKeyboardButton("🥇 OURO (XAU/USD)", callback_data="btn_xau_usd")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    texto_menu = (
        f"🎛️ **PAINEL DE OPERAÇÕES DE CRIPTOMOEDAS**\n"
        f"👤 *TRADER:* **{nome_usuario.upper()}**\n\n"
        f"SELECIONE O ATIVO DESEJADO ABAIXO:"
    )

    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_text(texto_menu, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        try:
            await update_or_query.edit_message_text(texto_menu, reply_markup=reply_markup, parse_mode="Markdown")
        except:
            await update_or_query.message.reply_text(texto_menu, reply_markup=reply_markup, parse_mode="Markdown")

async def botao_clicado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    nome_usuario = context.user_data.get("nome", "Trader")
    data = query.data

    if data == "menu_principal":
        await enviar_menu_principal(query, context, nome_usuario)
    else:
        sigla_chave = data.replace("btn_", "")
        if sigla_chave in MAPA_ATIVOS:
            info = MAPA_ATIVOS[sigla_chave]
            context.application.create_task(
                executar_analise_mercado(chat_id, context, nome_usuario, sigla_chave, info["par_api"], info["nome"])
            )

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip().lower()

    if "nome" not in context.user_data:
        context.user_data["nome"] = update.message.text.strip()
        nome_usuario = context.user_data["nome"]

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        boas_vindas_ia = chamar_groq(f"Dê boas-vindas curtas e em maiúsculas focadas em cripto.", nome_usuario, modo_sinal=False)
        await context.bot.send_message(chat_id=chat_id, text=boas_vindas_ia.upper(), parse_mode="Markdown")
        await enviar_menu_principal(update, context, nome_usuario)
        return

    nome_usuario = context.user_data.get("nome", "Trader")
    
    if "bitcoin" in texto_usuario or "btc" in texto_usuario:
        if "dólar" in texto_usuario or "usd" in texto_usuario:
            info = MAPA_ATIVOS["btc_usd"]
            sigla = "btc_usd"
        else:
            info = MAPA_ATIVOS["btc_brl"]
            sigla = "btc_brl"
        
        context.application.create_task(
            executar_analise_mercado(chat_id, context, nome_usuario, sigla, info["par_api"], info["nome"])
        )
        return
    elif "ethereum" in texto_usuario or "eth" in texto_usuario:
        info = MAPA_ATIVOS["eth_brl"]
        context.application.create_task(
            executar_analise_mercado(chat_id, context, nome_usuario, "eth_brl", info["par_api"], info["nome"])
        )
        return
    elif "solana" in texto_usuario or "sol" in texto_usuario:
        info = MAPA_ATIVOS["sol_brl"]
        context.application.create_task(
            executar_analise_mercado(chat_id, context, nome_usuario, "sol_brl", info["par_api"], info["nome"])
        )
        return
    elif "ouro" in texto_usuario or "xau" in texto_usuario:
        info = MAPA_ATIVOS["xau_usd"]
        context.application.create_task(
            executar_analise_mercado(chat_id, context, nome_usuario, "xau_usd", info["par_api"], info["nome"])
        )
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta_ia = chamar_groq(update.message.text.strip(), nome_usuario, modo_sinal=False)
    await context.bot.send_message(chat_id=chat_id, text=resposta_ia)

# =========================
# INICIALIZAÇÃO DO BOT
# =========================
def main():
    print("🚀 Iniciando o Bitcoin & Crypto Bot...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Bot configurado e pronto para operar Bitcoin!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
