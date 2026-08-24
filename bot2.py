import os
import sys
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

print(f"🔑 Token encontrado? {'Sim' if TOKEN else 'Não'}", flush=True)
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
PALAVRAS_CHAT = ["oi", "olá", "bom dia", "boa tarde", "boa noite", "ajuda", "tudo bem"]
PALAVRAS_COTACAO = ["cotação", "preço", "valor", "quanto está"]

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# MAPA COMPLETO DE ATIVOS (10 PARES DE MOEDAS + CRIPTO + OURO)
# =========================
MAPA_ATIVOS = {
    # 10 Pares de Moedas Principais
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
    
    # Cripto e Metais
    "btc": {"par_api": "BTC-BRL", "nome": "Bitcoin / Real (BTC/BRL)", "multiplicador": 1, "limite_variacao": 500.0},
    "eth": {"par_api": "ETH-BRL", "nome": "Ethereum / Real (ETH/BRL)", "multiplicador": 1, "limite_variacao": 150.0},
    "xau": {"par_api": "XAU-USD", "nome": "Ouro / Dólar (XAU/USD)", "multiplicador": 10, "limite_variacao": 25.0}
}

# =========================
# FUNÇÃO DE VERIFICAÇÃO DE MERCADO (FUSO DO BRASIL)
# =========================
def verificar_status_mercado(par_api):
    fuso_brasil = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(fuso_brasil)
    
    dia_semana = agora.weekday() # 0 = Segunda, ..., 5 = Sábado, 6 = Domingo
    hora = agora.hour
    data_formatada = agora.strftime('%d/%m/%Y às %H:%M')

    if "BTC" in par_api or "ETH" in par_api:
        return True, f"🟢 **MERCADO CRIPTO 24/7 ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

    if dia_semana == 5:
        return False, f"🔴 **MERCADO FECHADO (FIM DE SEMANA)**\n📅 *DATA/HORA (BR):* {data_formatada}\n⚠️ *FOREX E METAIS FECHADOS. REABERTURA DOMINGO ÀS 18:00.*"
    
    if dia_semana == 6 and hora < 18:
        return False, f"🔴 **MERCADO FECHADO (FIM DE SEMANA)**\n📅 *DATA/HORA (BR):* {data_formatada}\n⚠️ *FOREX E METAIS FECHADOS. REABERTURA DOMINGO ÀS 18:00.*"

    return True, f"🟢 **MERCADO ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

# =========================
# FUNÇÃO PARA OBTER PREÇO REAL VIA YAHOO FINANCE
# =========================
def obter_preco_atual(par_api):
    try:
        ticker_map = {
            "EUR-USD": "EURUSD=X",
            "GBP-USD": "GBPUSD=X",
            "USD-JPY": "USDJPY=X",
            "AUD-USD": "AUDUSD=X",
            "NZD-USD": "NZDUSD=X",
            "USD-CAD": "USDCAD=X",
            "USD-CHF": "USDCHF=X",
            "USD-BRL": "USDBRL=X",
            "GBP-BRL": "GBPBRL=X",
            "EUR-BRL": "EURBRL=X",
            "BTC-BRL": "BTC-BRL",
            "ETH-BRL": "ETH-BRL",
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
        print(f"❌ Erro ao buscar preço no Yahoo Finance: {e}", flush=True)
        return 0.0

# =========================
# FUNÇÃO DE CHAMADA À API DA GROQ (COM GPT-OSS 120B)
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
                f"Você é o analista sênior do 'Snap Sinais Bot' especializado em Opções Binárias e Forex. "
                f"O operador se chama {nome_usuario}. "
                f"O mercado está ABERTO. Monte um **Sinal de Trade Profissional**, utilizando obrigatoriamente o preço real fornecido pelo usuário. "
                f"Siga rigorosamente este modelo visual:\n\n"
                f"🎯 **SINAL DE ANÁLISE - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Aberto 🟢\n"
                f"• **Tendência:** [Alta / Baixa / Lateral]\n"
                f"• **Preço Atual:** [Valor exato fornecido]\n\n"
                f"⏱️ **OPÇÃO BINÁRIA (EXPIRAÇÃO):**\n"
                f"• **Tempo:** M5 - 5 Minutos\n"
                f"• **Direção:** [CALL 🟢 (Compra) / PUT 🔴 (Venda)]\n"
                f"• **Ponto de Entrada:** [Preço ideal baseado no preço atual]\n\n"
                f"💡 *[Recomendação prática curta]*"
            )
        else:
            instrucao_sistema = (
                f"⚠️ O mercado está FECHADO. Monte um **Panorama de Fechamento** seguindo exatamente este modelo:\n\n"
                f"🔒 **PANORAMA DE FECHAMENTO - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Fechado 🔴\n"
                f"• **Último Preço (Fechamento):** [Valor]\n"
                f"• **Tendência de Fundo:** [Alta / Baixa / Lateral]\n\n"
                f"💡 *Mercado fechado no momento. Reabertura domingo às 18:00 (Horário de Brasília).*"
            )
    else:
        instrucao_sistema = f"Você é o assistente executivo do 'Snap Sinais Bot'. O usuário se chama {nome_usuario}."

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": instrucao_sistema},
            {"role": "user", "content": pergunta_usuario}
        ],
        "temperature": 0.5
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API da Groq: {response.status_code} - {response.text}"
    except Exception as e:
        return f"❌ Erro de conexão com a Groq: {e}"

# =========================
# EXECUTAR ANÁLISE DE MERCADO
# =========================
async def executar_analise_mercado(chat_id, context, nome_usuario, par_api, nome_ativo):
    mercado_aberto, info_status = verificar_status_mercado(par_api)

    await context.bot.send_message(chat_id=chat_id, text=f"🔍 *CONSULTANDO TERMINAIS PARA {nome_ativo.upper()}...*\n\n{info_status}", parse_mode="Markdown")

    preco_atual_val = obter_preco_atual(par_api)
    preco_atual_str = f"{preco_atual_val:.5f}" if preco_atual_val > 0 else "N/A"

    status_texto = "Aberto 🟢" if mercado_aberto else "Fechado 🔴"

    dados_mercado = (
        f"Ativo: {nome_ativo} | "
        f"Status do Mercado: {status_texto} | "
        f"Preço Real Obtido agora: {preco_atual_str}"
    )

    prompt_ia = f"Gere o relatório analítico ou de fechamento para os dados reais: {dados_mercado}. Utilize obrigatoriamente o Preço Real Obtido informado."

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta_ia = chamar_groq(prompt_ia, nome_usuario, modo_sinal=True, mercado_aberto=mercado_aberto)

    await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")

# =========================
# MONITOR DE VARIAÇÃO RÁPIDA
# =========================
async def monitorar_variacao_mercado(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    nome_usuario = job.data.get("nome", "Operador")
    par_api = job.data.get("par_api", "EUR-USD")
    nome_ativo = job.data.get("nome_ativo", "EUR/USD")
    multiplicador = job.data.get("multiplicador", 10000)
    limite_disparo = job.data.get("limite_variacao", 10.0)

    if not hasattr(job, "ultimo_preco"):
        job.ultimo_preco = None

    preco_atual = obter_preco_atual(par_api)
    if preco_atual <= 0:
        return

    if job.ultimo_preco is not None:
        diferenca = preco_atual - job.ultimo_preco
        unidades = abs(diferenca) * multiplicador

        if unidades >= limite_disparo:
            direcao_movimento = "⚡ ALTA FORTE (SPIKE COMPRADOR)" if diferenca > 0 else "⚡ QUEDA FORTE (SPIKE VENDEDOR)"
            
            alerta_texto = (
                f"🚨 **ALERTA DE VARIAÇÃO RÁPIDA - {nome_ativo}** 🚨\n\n"
                f"• **Movimento:** {direcao_movimento}\n"
                f"• **Variação detectada:** `{unidades:.1f}` pontos\n"
                f"• **Preço Atual:** `{preco_atual:.5f}`\n\n"
                f"💡 *O mercado esticou rápido! Analisando oportunidade imediata...*"
            )
            await context.bot.send_message(chat_id=chat_id, text=alerta_texto, parse_mode="Markdown")
            await executar_analise_mercado(chat_id, context, nome_usuario, par_api, nome_ativo)

    job.ultimo_preco = preco_atual

async def comando_alertar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    nome_usuario = context.user_data.get("nome", "Operador")

    args = context.args
    if not args:
        current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
        for j in current_jobs:
            j.schedule_removal()
        await update.message.reply_text("🔕 *MONITORES DE VARIAÇÃO DESATIVADOS PARA ESTE CHAT.*", parse_mode="Markdown")
        return

    try:
        minutos = int(args[0])
        if minutos < 1:
            raise ValueError()
        
        sigla_ativo = args[1].lower() if len(args) > 1 else "eurusd"
        
        if sigla_ativo not in MAPA_ATIVOS:
            lista_disponiveis = ", ".join(MAPA_ATIVOS.keys())
            await update.message.reply_text(f"⚠️ Ativo inválido! Escolha um destes:\n`{lista_disponiveis}`", parse_mode="Markdown")
            return

        info = MAPA_ATIVOS[sigla_ativo]

        current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
        for j in current_jobs:
            j.schedule_removal()

        dados_alerta = {
            "nome": nome_usuario, 
            "par_api": info["par_api"], 
            "nome_ativo": info["nome"],
            "multiplicador": info["multiplicador"],
            "limite_variacao": info["limite_variacao"]
        }
        
        context.job_queue.run_repeating(
            monitorar_variacao_mercado,
            interval=minutos * 60,
            first=5,
            chat_id=chat_id,
            data=dados_alerta,
            name=str(chat_id)
        )

        await update.message.reply_text(
            f"🔔 *MONITOR DE VARIAÇÃO ATIVADO!*\n\n"
            f"Monitorando **{info['nome']}** a cada **{minutos} minuto(s)**.\n"
            f"Sensibilidade de disparo ajustada para este ativo.\n"
            f"Para desativar, digite `/alertar` sem parâmetros.",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("⚠️ Use o formato correto, ex: `/alertar 5 btc` ou `/alertar 2 eurusd`.", parse_mode="Markdown")

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("nome", None)
    url_imagem = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"
    legenda_boas_vindas = (
        "🚀 **BEM-VINDO AO SNAP SINAIS** 📈\n\n"
        "TERMINAL INTELIGENTE DE ANÁLISE DE MERCADO.\n\n"
        "PARA COMEÇAR, POR FAVOR, INFORME:\n"
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
        [
            InlineKeyboardButton("💶 EUR/USD", callback_data="btn_eurusd"),
            InlineKeyboardButton("💷 GBP/USD", callback_data="btn_gbpusd")
        ],
        [
            InlineKeyboardButton("💵 USD/JPY", callback_data="btn_usdjpy"),
            InlineKeyboardButton("📉 AUD/USD", callback_data="btn_audusd")
        ],
        [
            InlineKeyboardButton("🇳🇿 NZD/USD", callback_data="btn_nzdusd"),
            InlineKeyboardButton("🇨🇦 USD/CAD", callback_data="btn_usdcad")
        ],
        [
            InlineKeyboardButton("🇨🇭 USD/CHF", callback_data="btn_usdchf"),
            InlineKeyboardButton("🌐 VOLTAR", callback_data="menu_principal")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"📊 **PARES PRINCIPAIS DE FOREX / BINÁRIAS (M5)**\nEscolha o ativo:", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_forex(query, nome_usuario):
    teclado = [
        [
            InlineKeyboardButton("💵 USD/BRL", callback_data="btn_usdbrl"),
            InlineKeyboardButton("💷 GBP/BRL", callback_data="btn_gbpbrl")
        ],
        [
            InlineKeyboardButton("💶 EUR/BRL", callback_data="btn_eurbrl"),
            InlineKeyboardButton("⬅️ VOLTAR", callback_data="menu_principal")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"💱 **CÂMBIO CONTRA O REAL (BRL)**", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_cripto(query, nome_usuario):
    teclado = [
        [
            InlineKeyboardButton("🪙 BTC/BRL", callback_data="btn_btc"),
            InlineKeyboardButton("🔷 ETH/BRL", callback_data="btn_eth")
        ],
        [
            InlineKeyboardButton("🥇 OURO (XAU/USD)", callback_data="btn_xau"),
            InlineKeyboardButton("⬅️ VOLTAR", callback_data="menu_principal")
        ]
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

    elif data == "btn_eurusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "EUR/USD")
    elif data == "btn_gbpusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-USD", "GBP/USD")
    elif data == "btn_usdjpy":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-JPY", "USD/JPY")
    elif data == "btn_audusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "AUD-USD", "AUD/USD")
    elif data == "btn_nzdusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "NZD-USD", "NZD/USD")
    elif data == "btn_usdcad":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-CAD", "USD/CAD")
    elif data == "btn_usdchf":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-CHF", "USD/CHF")
    elif data == "btn_usdbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-BRL", "USD/BRL")
    elif data == "btn_gbpbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-BRL", "GBP/BRL")
    elif data == "btn_eurbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-BRL", "EUR/BRL")
    elif data == "btn_btc":
        await executar_analise_mercado(chat_id, context, nome_usuario, "BTC-BRL", "Bitcoin / Real (BTC/BRL)")
    elif data == "btn_eth":
        await executar_analise_mercado(chat_id, context, nome_usuario, "ETH-BRL", "Ethereum / Real (ETH/BRL)")
    elif data == "btn_xau":
        await executar_analise_mercado(chat_id, context, nome_usuario, "XAU-USD", "Ouro / Dólar (XAU/USD)")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip().lower()

    if "nome" not in context.user_data:
        context.user_data["nome"] = update.message.text.strip()
        nome_usuario = context.user_data["nome"]

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        boas_vindas_ia = chamar_groq(f"Dê boas-vindas curtas e em maiúsculas.", nome_usuario, modo_sinal=False)
        await context.bot.send_message(chat_id=chat_id, text=boas_vindas_ia.upper(), parse_mode="Markdown")
        await enviar_menu_principal(update, context, nome_usuario)
        return

    nome_usuario = context.user_data.get("nome", "Operador")
    contem_sinal = any(palavra in texto_usuario for palavra in PALAVRAS_SINAL)
    contem_cotacao = any(palavra in texto_usuario for palavra in PALAVRAS_COTACAO)

    if contem_sinal or contem_cotacao:
        if "dólar" in texto_usuario or "usdbrl" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "USD-BRL", "USD/BRL")
            return
        elif "bitcoin" in texto_usuario or "btc" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "BTC-BRL", "Bitcoin / Real (BTC/BRL)")
            return
        elif "euro" in texto_usuario or "eur" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "EUR/USD")
            return
        else:
            await context.bot.send_message(chat_id=chat_id, text="🔍 *ATIVO NÃO IDENTIFICADO.*", parse_mode="Markdown")
            return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta_ia = chamar_groq(update.message.text.strip(), nome_usuario, modo_sinal=False)
    await context.bot.send_message(chat_id=chat_id, text=resposta_ia)

# =========================
# INICIALIZAÇÃO DO BOT
# =========================
def main():
    print("🚀 Iniciando o Snap Sinais Bot...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alertar", comando_alertar))
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Bot configurado com sucesso!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()



