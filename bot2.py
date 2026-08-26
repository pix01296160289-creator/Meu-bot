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
PALAVRAS_SINAL = ["sinal", "análise", "mercado", "entrada", "stop"]
PALAVRAS_CHAT = ["oi", "olá", "bom dia", "boa tarde", "boa noite", "ajuda", "tudo bem", "iniciar", "start"]
PALAVRAS_COTACAO = ["cotação", "preço", "valor", "quanto está", "gráfico"]

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# MAPA COMPLETO DE ATIVOS
# =========================
MAPA_ATIVOS = {
    "eurusd": {"par_api": "EUR-USD", "nome": "EUR/USD (Binária M5)", "multiplicador": 10000, "limite_variacao": 8.0},
    "gbpusd": {"par_api": "GBP-USD", "nome": "GBP/USD (Binária M5)", "multiplicador": 10000, "limite_variacao": 10.0},
    "usdjpy": {"par_api": "USD-JPY", "nome": "USD/JPY (Binária M5)", "multiplicador": 100, "limite_variacao": 15.0},
    "audusd": {"par_api": "AUD-USD", "nome": "AUD/USD (Binária M5)", "multiplicador": 10000, "limite_variacao": 8.0},
    "nzdusd": {"par_api": "NZD-USD", "nome": "NZD/USD (Binária M5)", "multiplicador": 10000, "limite_variacao": 8.0},
    "usdcad": {"par_api": "USD-CAD", "nome": "USD/CAD (Binária M5)", "multiplicador": 10000, "limite_variacao": 8.0},
    "usdchf": {"par_api": "USD-CHF", "nome": "USD/CHF (Binária M5)", "multiplicador": 10000, "limite_variacao": 8.0},
    "usdbrl": {"par_api": "USD-BRL", "nome": "Dólar / Real (USD/BRL)", "multiplicador": 10000, "limite_variacao": 15.0},
    "gbpbrl": {"par_api": "GBP-BRL", "nome": "Libra / Real (GBP/BRL)", "multiplicador": 10000, "limite_variacao": 20.0},
    "eurbrl": {"par_api": "EUR-BRL", "nome": "Euro / Real (EUR/BRL)", "multiplicador": 10000, "limite_variacao": 20.0},
    "btc": {"par_api": "BTC-BRL", "nome": "Bitcoin / Real (BTC/BRL)", "multiplicador": 1, "limite_variacao": 500.0},
    "eth": {"par_api": "ETH-BRL", "nome": "Ethereum / Real (ETH/BRL)", "multiplicador": 1, "limite_variacao": 150.0},
    "xau": {"par_api": "XAU-USD", "nome": "Ouro / Dólar (XAU/USD)", "multiplicador": 10, "limite_variacao": 25.0}
}

# =========================
# VERIFICAÇÃO DE MERCADO
# =========================
def verificar_status_mercado(par_api):
    fuso_brasil = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(fuso_brasil)
    
    dia_semana = agora.weekday()
    hora = agora.hour
    data_formatada = agora.strftime('%d/%m/%Y às %H:%M')

    if "BTC" in par_api or "ETH" in par_api:
        return True, f"🟢 **MERCADO CRIPTO 24/7 ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

    if dia_semana == 5:
        return False, f"🔴 **MERCADO FECHADO (FIM DE SEMANA)**\n📅 *DATA/HORA (BR):* {data_formatada}\n⚠️ *FOREX E METAIS FECHADOS.*"
    
    if dia_semana == 6 and hora < 18:
        return False, f"🔴 **MERCADO FECHADO (FIM DE SEMANA)**\n📅 *DATA/HORA (BR):* {data_formatada}\n⚠️ *FOREX E METAIS FECHADOS.*"

    return True, f"🟢 **MERCADO ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

# =========================
# OBTER PREÇO (YAHOO FINANCE)
# =========================
def obter_preco_atual(par_api):
    try:
        ticker_map = {
            "EUR-USD": "EURUSD=X", "GBP-USD": "GBPUSD=X", "USD-JPY": "USDJPY=X",
            "AUD-USD": "AUDUSD=X", "NZD-USD": "NZDUSD=X", "USD-CAD": "USDCAD=X",
            "USD-CHF": "USDCHF=X", "USD-BRL": "USDBRL=X", "GBP-BRL": "GBPBRL=X",
            "EUR-BRL": "EURBRL=X", "BTC-BRL": "BTC-BRL", "ETH-BRL": "ETH-BRL",
            "XAU-USD": "GC=F"
        }
        ticker_symbol = ticker_map.get(par_api)
        if not ticker_symbol:
            return 0.0

        dados = yf.download(ticker_symbol, period="1d", interval="1m", progress=False)
        if not dados.empty and "Close" in dados.columns:
            preco_recente = dados["Close"].iloc[-1]
            if hasattr(preco_recente, "item"):
                preco_recente = preco_recente.item()
            return float(preco_recente)
        else:
            ticker_obj = yf.Ticker(ticker_symbol)
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                preco_recente = hist["Close"].iloc[-1]
                if hasattr(preco_recente, "item"):
                    preco_recente = preco_recente.item()
                return float(preco_recente)
        return 0.0
    except Exception as e:
        print(f"❌ Erro ao obter preço do Yahoo Finance: {e}", flush=True)
        return 0.0

# =========================
# CHAMADA À API DA GROQ (COM O SEU MODELO ORIGINAL)
# =========================
def chamar_groq(pergunta_usuario, nome_usuario="Amigo", modo_sinal=False, mercado_aberto=True):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    if modo_sinal:
        if mercado_aberto:
            instrucao_sistema = (
                f"Você é o analista sênior do 'Snap Sinais Pro' especializado em Opções Binárias e Forex. "
                f"O operador se chama {nome_usuario}. O mercado está ABERTO. "
                f"Analise os dados e gere o relatório seguindo estritamente este modelo visual, utilizando obrigatoriamente o preço real fornecido. "
                f"NÃO use itálico em excesso, não coloque aviso legal e termine a mensagem logo após a recomendação prática.\n\n"
                f"🎯 **ANÁLISE TÉCNICA - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Aberto 🟢\n"
                f"• **Tendência:** [Alta Forte / Alta Moderada / Baixa Forte / Baixa Moderada / Lateral]\n"
                f"• **Preço Atual:** [Valor exato fornecido]\n"
                f"• **Volatilidade:** [Alta / Média / Baixa]\n\n"
                f"⏱️ **RECOMENDAÇÃO (EXPIRAÇÃO):**\n"
                f"• **Ativo:** [NOME DO ATIVO]\n"
                f"• **Tempo Gráfico:** M5\n"
                f"• **Ação:** [COMPRA 🟢 (CALL) / VENDA 🔴 (PUT)]\n"
                f"• **Ponto de Entrada Sugerido:** [Preço ideal para entrada]\n"
                f"• **Stop Loss Sugerido:** [Nível de preço para proteção]\n"
                f"• **Take Profit Sugerido:** [Nível de preço para alvo]\n\n"
                f"💡 *[Análise breve de uma frase justificando a ação]*"
            )
        else:
            instrucao_sistema = (
                f"⚠️ O mercado está FECHADO. Monte o **Panorama de Fechamento** para o ativo, focado na tendência macro, "
                f"seguindo estritamente este modelo e usando os dados fornecidos:\n\n"
                f"🔒 **PANORAMA DE FECHAMENTO - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Fechado 🔴\n"
                f"• **Último Preço:** [Valor]\n"
                f"• **Tendência de Longo Prazo:** [Alta / Baixa / Lateral]\n\n"
                f"💡 *[Comentário de uma frase sobre o comportamento do ativo no fechamento]*"
            )
    else:
        instrucao_sistema = f"Você é o assistente executivo senior do 'Snap Sinais Pro'. O usuário se chama {nome_usuario}. Mantenha um tom profissional, eficiente e direto."

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": instrucao_sistema},
            {"role": "user", "content": pergunta_usuario}
        ],
        "temperature": 0.4,
        "max_tokens": 1000
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API da Groq: {response.status_code}"
    except Exception as e:
        print(f"❌ Erro de conexão com a Groq: {e}", flush=True)
        return f"❌ Erro de conexão com a API da Groq: {e}"

# =========================
# MONITORAMENTO CONTÍNUO E ANÁLISE REAL
# =========================
async def executar_analise_mercado(chat_id, context, nome_usuario, sigla_chave, par_api, nome_ativo):
    mercado_aberto, info_status = verificar_status_mercado(par_api)

    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📡 **INICIANDO ANÁLISE EM TEMPO REAL: {nome_ativo.upper()}** 📊\n\nO terminal está processando os dados. Aguarde a confirmação do sinal.\n\n{info_status}", 
        parse_mode="Markdown"
    )

    preco_anterior = 0.0
    tentativas = 0
    while preco_anterior == 0.0 and tentativas < 10:
        preco_anterior = obter_preco_atual(par_api)
        if preco_anterior == 0.0:
            tentativas += 1
            await asyncio.sleep(2)
    
    if preco_anterior == 0.0:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Falha ao obter dados do mercado para {nome_ativo}. Tente novamente mais tarde.", parse_mode="Markdown")
        return

    print(f"📊 Monitor ativado para {nome_ativo}. Preço base: {preco_anterior}", flush=True)

    while True:
        try:
            await asyncio.sleep(3)
            preco_atual = obter_preco_atual(par_api)
            
            if preco_atual > 0 and preco_atual != preco_anterior:
                print(f"🚨 Mudança real em {nome_ativo}: {preco_anterior} ➔ {preco_atual}", flush=True)
                
                preco_atual_str = f"{preco_atual:.5f}"
                status_texto = "Aberto 🟢" if mercado_aberto else "Fechado 🔴"

                dados_mercado = (
                    f"Ativo: {nome_ativo} | "
                    f"Status do Mercado: {status_texto} | "
                    f"Preço Atualizado Confirmado: {preco_atual_str}"
                )

                prompt_ia = f"Gere o relatório analítico ou de fechamento para os dados reais a seguir. O relatório deve ser profissional e seguir o modelo solicitado:\n\n{dados_mercado}"

                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                resposta_ia = chamar_groq(prompt_ia, nome_usuario, modo_sinal=True, mercado_aberto=mercado_aberto)

                await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")
                break
                
        except Exception as e:
            print(f"❌ Erro no loop de monitoramento: {e}", flush=True)
            await asyncio.sleep(5)

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("nome", None)
    
    # 🖼️ IMAGEM ATUALIZADA (TERMINAL / TRADING PROFISSIONAL):
    url_imagem = "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1000&auto=format&fit=crop"
    
    legenda_boas_vindas = (
        "🚀 **BEM-VINDO AO SNAP SINAIS PRO** 📊✨\n"
        "**TERMINAL ANALÍTICO DE ALTA PERFORMANCE.**\n\n"
        "PARA INICIAR SUA SESSÃO, POR FAVOR, INFORME:\n"
        "👉 **QUAL É O SEU NOME OU APELIDO?**"
    )

    try:
        await update.message.reply_photo(photo=url_imagem, caption=legenda_boas_vindas, parse_mode="Markdown")
    except:
        await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")

async def enviar_menu_principal(update_or_query, context, nome_usuario):
    teclado = [
        [InlineKeyboardButton("📊 OPÇÕES BINÁRIAS (M5)", callback_data="menu_binarias")],
        [InlineKeyboardButton("💱 CÂMBIO & REAIS", callback_data="menu_forex")],
        [InlineKeyboardButton("🪙 CRIPTOMOEDAS & METAIS", callback_data="menu_cripto")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    texto_menu = (
        f"🎛️ **PAINEL EXECUTIVO DE OPERAÇÕES**\n"
        f"👤 *OPERADOR:* **{nome_usuario.upper()}**\n\n"
        f"SELECIONE A CATEGORIA DESEJADA ABAIXO:"
    )

    if hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_text(texto_menu, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        try:
            await update_or_query.edit_message_text(texto_menu, reply_markup=reply_markup, parse_mode="Markdown")
        except:
            await update_or_query.message.reply_text(texto_menu, reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_binarias(query, nome_usuario):
    teclado = [
        [InlineKeyboardButton("💶 EUR/USD", callback_data="btn_eurusd"), InlineKeyboardButton("💷 GBP/USD", callback_data="btn_gbpusd")],
        [InlineKeyboardButton("💵 USD/JPY", callback_data="btn_usdjpy"), InlineKeyboardButton("📉 AUD/USD", callback_data="btn_audusd")],
        [InlineKeyboardButton("🇳🇿 NZD/USD", callback_data="btn_nzdusd"), InlineKeyboardButton("🇨🇦 USD/CAD", callback_data="btn_usdcad")],
        [InlineKeyboardButton("🇨🇭 USD/CHF", callback_data="btn_usdchf"), InlineKeyboardButton("🌐 VOLTAR", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"📊 **PARES PRINCIPAIS DE FOREX / BINÁRIAS (M5)**\nEscolha o ativo:", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_forex(query, nome_usuario):
    teclado = [
        [InlineKeyboardButton("💵 USD/BRL", callback_data="btn_usdbrl"), InlineKeyboardButton("💷 GBP/BRL", callback_data="btn_gbpbrl")],
        [InlineKeyboardButton("💶 EUR/BRL", callback_data="btn_eurbrl"), InlineKeyboardButton("⬅️ VOLTAR", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"💱 **CÂMBIO CONTRA O REAL (BRL)**", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_cripto(query, nome_usuario):
    teclado = [
        [InlineKeyboardButton("🪙 BTC/BRL", callback_data="btn_btc"), InlineKeyboardButton("🔷 ETH/BRL", callback_data="btn_eth")],
        [InlineKeyboardButton("🥇 OURO (XAU/USD)", callback_data="btn_xau"), InlineKeyboardButton("⬅️ VOLTAR", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"🪙 **CRIPTOMOEDAS E METAIS**", reply_markup=reply_markup, parse_mode="Markdown")

async def botao_clicado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    nome_usuario = context.user_data.get("nome", "Operador")
    data = query.data

    if data == "menu_principal":
        await enviar_menu_principal(query, context, nome_usuario)
    elif data == "menu_binarias":
        await mostrar_menu_binarias(query, nome_usuario)
    elif data == "menu_forex":
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "menu_cripto":
        await mostrar_menu_cripto(query, nome_usuario)
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
        boas_vindas_ia = chamar_groq(f"Dê boas-vindas executivas curtas e em maiúsculas.", nome_usuario, modo_sinal=False)
        await context.bot.send_message(chat_id=chat_id, text=boas_vindas_ia.upper(), parse_mode="Markdown")
        await enviar_menu_principal(update, context, nome_usuario)
        return

    nome_usuario = context.user_data.get("nome", "Operador")
    contem_sinal = any(palavra in texto_usuario for palavra in PALAVRAS_SINAL)
    contem_cotacao = any(palavra in texto_usuario for palavra in PALAVRAS_COTACAO)

    if contem_sinal or contem_cotacao:
        if "dólar" in texto_usuario or "usdbrl" in texto_usuario:
            info = MAPA_ATIVOS["usdbrl"]
            context.application.create_task(
                executar_analise_mercado(chat_id, context, nome_usuario, "usdbrl", info["par_api"], info["nome"])
            )
            return
        elif "bitcoin" in texto_usuario or "btc" in texto_usuario:
            info = MAPA_ATIVOS["btc"]
            context.application.create_task(
                executar_analise_mercado(chat_id, context, nome_usuario, "btc", info["par_api"], info["nome"])
            )
            return
        elif "euro" in texto_usuario or "eur" in texto_usuario:
            info = MAPA_ATIVOS["eurusd"]
            context.application.create_task(
                executar_analise_mercado(chat_id, context, nome_usuario, "eurusd", info["par_api"], info["nome"])
            )
            return
        else:
            await context.bot.send_message(chat_id=chat_id, text="🔍 *ATIVO NÃO IDENTIFICADO NO SISTEMA PRO.*", parse_mode="Markdown")
            return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta_ia = chamar_groq(update.message.text.strip(), nome_usuario, modo_sinal=False)
    await context.bot.send_message(chat_id=chat_id, text=resposta_ia)

# =========================
# INICIALIZAÇÃO DO BOT
# =========================
def main():
    print("🚀 Iniciando o Snap Sinais Pro...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Bot configurado e pronto para rodar!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

