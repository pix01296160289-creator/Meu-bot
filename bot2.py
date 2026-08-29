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
GROQ_KEY_COTACAO = os.getenv("GROQ_API_COTACAO")
GROQ_KEY_PIX = os.getenv("GROQ_API_PIX")

if not TOKEN or not GROQ_KEY_COTACAO or not GROQ_KEY_PIX:
    print("❌ ERRO: Verifique se o TOKEN, GROQ_API_COTACAO e GROQ_API_PIX estão no .env!", flush=True)
    sys.exit(1)

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# MAPA DE ATIVOS CRIPTO
# =========================
MAPA_ATIVOS = {
    "btc_brl": {"par_api": "BTC-BRL", "nome": "Bitcoin / Real (BTC/BRL)"},
    "btc_usd": {"par_api": "BTC-USD", "nome": "Bitcoin / Dólar (BTC/USD)"},
    "eth_brl": {"par_api": "ETH-BRL", "nome": "Ethereum / Real (ETH/BRL)"},
    "sol_brl": {"par_api": "SOL-BRL", "nome": "Solana / Real (SOL/BRL)"},
    "xau_usd": {"par_api": "GC=F", "nome": "Ouro / Dólar (XAU/USD)"}
}

# =========================
# VERIFICAÇÃO DE MERCADO
# =========================
def verificar_status_mercado(par_api):
    fuso_brasil = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(fuso_brasil)
    data_formatada = agora.strftime('%d/%m/%Y às %H:%M')
    return True, f"🟢 **MERCADO CRIPTO 24/7 ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

# =========================
# OBTER PREÇO (YAHOO FINANCE)
# =========================
def obter_preco_atual(par_api):
    try:
        dados = yf.download(par_api, period="1d", interval="1m", progress=False)
        if not dados.empty and "Close" in dados.columns:
            preco_recente = dados["Close"].iloc[-1]
            if hasattr(preco_recente, "item"):
                preco_recente = preco_recente.item()
            return float(preco_recente)
        else:
            ticker_obj = yf.Ticker(par_api)
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                preco_recente = hist["Close"].iloc[-1]
                if hasattr(preco_recente, "item"):
                    preco_recente = preco_recente.item()
                return float(preco_recente)
        return 0.0
    except Exception:
        return 0.0

# =========================
# API 1: CHAVE DE COTAÇÃO
# =========================
def chamar_groq_cotacao(dados_mercado, nome_usuario="Trader"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY_COTACAO}",
        "Content-Type": "application/json"
    }

    instrucao_sistema = (
        f"Você é o analista sênior do bot. O usuário se chama {nome_usuario}. "
        f"Monte um **Sinal de Trade / Análise Profissional para Cripto** com base nos dados reais fornecidos. "
        f"NÃO inclua nenhum aviso legal. Siga este modelo:\n\n"
        f"🎯 **ANÁLISE CRIPTO - [NOME DO ATIVO]**\n"
        f"• **Status:** Mercado 24/7 🟢\n"
        f"• **Tendência:** [Alta / Baixa / Consolidação]\n"
        f"• **Preço Atual:** [Valor exato]\n\n"
        f"📊 **ESTRATÉGIA DE OPERAÇÃO:**\n"
        f"• **Direção:** [COMPRA / VENDA]\n"
        f"• **Zona de Entrada:** [Preço ideal]\n"
        f"• **Alvo:** [Preço alvo]\n"
        f"• **Stop Loss:** [Preço limite]"
    )

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": instrucao_sistema},
            {"role": "user", "content": f"Gere o relatório com base nestes dados: {dados_mercado}"}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API de Cotação: {response.status_code}"
    except Exception as e:
        return f"❌ Erro de conexão: {e}"

# =========================
# API 2: CHAVE DO PIX (COBRANÇA)
# =========================
def chamar_groq_pix(detalhes_pagamento, nome_usuario="Trader"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY_PIX}",
        "Content-Type": "application/json"
    }

    instrucao_sistema = (
        f"Você é o assistente financeiro responsável por gerar a cobrança Pix para liberar o acesso ao bot. "
        f"O usuário é {nome_usuario}. "
        f"Formate os dados de cobrança em uma **Estrutura de Pix limpa e organizada**, seguindo rigorosamente este modelo:\n\n"
        f"⚡ **COBRANÇA PIX - LIBERAÇÃO DE ACESSO**\n"
        f"• **Chave Pix:** [Chave informada]\n"
        f"• **Favorecido:** [Nome do recebedor]\n"
        f"• **Valor:** R$ [Valor formatado]\n\n"
        f"📋 *Instrução: Realize o pagamento via Pix e envie o comprovante para liberar o painel de cripto.*"
    )

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": instrucao_sistema},
            {"role": "user", "content": f"Organize estes dados de pagamento Pix: {detalhes_pagamento}"}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API do Pix: {response.status_code}"
    except Exception as e:
        return f"❌ Erro de conexão: {e}"

# =========================
# MONITORAMENTO DE MERCADO (EXCLUSIVO PARA USUÁRIOS PAGOS)
# =========================
async def executar_analise_mercado(chat_id, context, nome_usuario, par_api, nome_ativo):
    _, info_status = verificar_status_mercado(par_api)

    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"👀 *MONITORANDO EM TEMPO REAL: {nome_ativo.upper()}*\n\n{info_status}", 
        parse_mode="Markdown"
    )

    preco_anterior = 0.0
    while preco_anterior == 0.0:
        preco_anterior = obter_preco_atual(par_api)
        if preco_anterior == 0.0:
            await asyncio.sleep(3)

    while True:
        try:
            await asyncio.sleep(5)
            preco_atual = obter_preco_atual(par_api)
            
            if preco_atual > 0 and preco_atual != preco_anterior:
                preco_atual_str = f"{preco_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                dados_mercado = f"Ativo: {nome_ativo} | Preço Atualizado: {preco_atual_str}"

                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                resposta_ia = chamar_groq_cotacao(dados_mercado, nome_usuario)

                await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")
                break
        except Exception:
            await asyncio.sleep(5)

# =========================
# COMANDOS DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Reseta os dados para forçar o fluxo do zero
    context.user_data.pop("nome", None)
    context.user_data.pop("pago", None)
    
    legenda = (
        "🚀 **BEM-VINDO AO SISTEMA DE ANÁLISES** ⚡\n\n"
        "Para ter acesso ao painel de cotações de cripto, é necessário efetuar o pagamento da taxa de ativação.\n\n"
        "👉 **PRIMEIRO, INFORME SEU NOME OU APELIDO:**"
    )
    await update.message.reply_text(legenda, parse_mode="Markdown")

async def comando_liberar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando exclusivo para o administrador liberar o acesso do usuário após o pagamento."""
    context.user_data["pago"] = True
    nome_usuario = context.user_data.get("nome", "Usuário")
    await update.message.reply_text(f"✅ **ACESSO LIBERADO!** O usuário {nome_usuario} agora pode usar o painel de cotações.", parse_mode="Markdown")
    await enviar_menu_principal(update, context, nome_usuario)

async def enviar_menu_principal(update_or_query, context, nome_usuario):
    # O painel de cripto só é exibido se o usuário estiver pago
    if not context.user_data.get("pago"):
        texto_bloqueado = (
            f"🔒 **ACESSO BLOQUEADO**\n\n"
            f"Olá, **{nome_usuario.upper()}**. O acesso ao painel de criptomoedas exige o pagamento prévio via Pix.\n\n"
            f"⚡ *Envie os dados do Pix para gerar a cobrança (ex: sua chave e o valor) ou digite `/pix [chave] [valor]`.*"
        )
        if hasattr(update_or_query, "message") and update_or_query.message:
            await update_or_query.message.reply_text(texto_bloqueado, parse_mode="Markdown")
        else:
            await update_or_query.message.reply_text(texto_bloqueado, parse_mode="Markdown")
        return

    # Se estiver pago, exibe o painel completo de ativos
    teclado = [
        [InlineKeyboardButton("🪙 BITCOIN / REAL (BTC/BRL)", callback_data="btn_btc_brl")],
        [InlineKeyboardButton("💵 BITCOIN / DÓLAR (BTC/USD)", callback_data="btn_btc_usd")],
        [InlineKeyboardButton("🔷 ETHEREUM (ETH/BRL)", callback_data="btn_eth_brl")],
        [InlineKeyboardButton("⚡ SOLANA (SOL/BRL)", callback_data="btn_sol_brl")],
        [InlineKeyboardButton("🥇 OURO (XAU/USD)", callback_data="btn_xau_usd")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    texto_menu = (
        f"🎛️ **PAINEL DE ATENDIMENTO LIBERADO**\n"
        f"👤 *OPERADOR:* **{nome_usuario.upper()}** ✅\n\n"
        f"Selecione o ativo desejado abaixo:"
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

    if not context.user_data.get("pago"):
        await query.message.reply_text("🔒 Acesso bloqueado. Efetue o pagamento via Pix primeiro para liberar os botões.", parse_mode="Markdown")
        return

    chat_id = query.message.chat_id
    nome_usuario = context.user_data.get("nome", "Usuário")
    data = query.data

    sigla_chave = data.replace("btn_", "")
    if sigla_chave in MAPA_ATIVOS:
        info = MAPA_ATIVOS[sigla_chave]
        context.application.create_task(
            executar_analise_mercado(chat_id, context, nome_usuario, info["par_api"], info["nome"])
        )

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    # Passo 1: Captura o nome
    if "nome" not in context.user_data:
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Assim que informa o nome, exibe a cobrança Pix obrigatória antes de qualquer coisa
        cobranca_pix = chamar_groq_pix("Chave Pix padrão para liberação: pagamento@sistema.com | Valor: R$ 50,00", nome_usuario)
        await context.bot.send_message(chat_id=chat_id, text=cobranca_pix, parse_mode="Markdown")
        return

    nome_usuario = context.user_data.get("nome", "Usuário")

    # Se o usuário enviar os dados de pagamento ou comprovante, aciona a API de Pix
    if not context.user_data.get("pago"):
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        resposta_pix = chamar_groq_pix(texto_usuario, nome_usuario)
        await context.bot.send_message(chat_id=chat_id, text=resposta_pix, parse_mode="Markdown")
        await context.bot.send_message(chat_id=chat_id, text="📌 *Aguardando confirmação do pagamento para liberação do painel.* (Se você for o admin, digite `/liberar` para liberar o acesso).", parse_mode="Markdown")
        return

    # Se já estiver pago, exibe o menu
    await enviar_menu_principal(update, context, nome_usuario)

# =========================
# INICIALIZAÇÃO DO BOT
# =========================
def main():
    print("🚀 Iniciando o Bot com Paywall Pix Obrigatório...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("liberar", comando_liberar)) # Comando para liberar o acesso manualmente
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Bot configurado com sucesso!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
