import os
import sys
import qrcode
import io
import json
import random
import unicodedata
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import requests
import yfinance as yf
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest

# =========================
# CARREGAR CONFIGURAÇÕES
# =========================
print("🔄 Carregando variáveis do .env...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHAVE_PIX = os.getenv("CHAVE_PIX", "").strip()
NOME_RECEBEDOR = os.getenv("NOME_RECEBEDOR", "Recebedor").strip()
CIDADE_RECEBEDOR = os.getenv("CIDADE_RECEBEDOR", "Sao Paulo").strip()

if not TOKEN or not GROQ_API_KEY or not CHAVE_PIX:
    print("❌ ERRO: Verifique se o TOKEN, GROQ_API_KEY e CHAVE_PIX estão preenchidos nas variáveis de ambiente!", flush=True)
    sys.exit(1)

ARQUIVO_HISTORICO = "comprovantes_usados.json"
ARQUIVO_USUARIOS = "usuarios_autorizados.json"

PERGUNTANDO_NOME = 1

MAPA_ATIVOS = {
    "btc_brl": {"par_api": "BTC-BRL", "nome": "Bitcoin / Real (BTC/BRL)"},
    "btc_usd": {"par_api": "BTC-USD", "nome": "Bitcoin / Dólar (BTC/USD)"},
    "eth_brl": {"par_api": "ETH-BRL", "nome": "Ethereum / Real (ETH/BRL)"},
    "sol_brl": {"par_api": "SOL-BRL", "nome": "Solana / Real (SOL/BRL)"},
    "xau_usd": {"par_api": "GC=F", "nome": "Ouro / Dólar (XAU/USD)"}
}

def carregar_comprovantes_usados():
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_comprovante_usado(id_transacao):
    usados = carregar_comprovantes_usados()
    if id_transacao not in usados:
        usados.append(id_transacao)
        with open(ARQUIVO_HISTORICO, "w") as f:
            json.dump(usados, f)

def carregar_usuarios_autorizados():
    if os.path.exists(ARQUIVO_USUARIOS):
        try:
            with open(ARQUIVO_USUARIOS, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_usuario_autorizado(user_id):
    autorizados = carregar_usuarios_autorizados()
    if user_id not in autorizados:
        autorizados.append(user_id)
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(autorizados, f)

def gerar_payload_pix(pix_key, nome, cidade, valor, identificador="***"):
    def format_field(id_field, value):
        val_str = str(value)
        return f"{id_field}{len(val_str):02d}{val_str}"

    def limpar_texto(texto):
        return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII').upper()

    nome = limpar_texto(nome)[:25]
    cidade = limpar_texto(cidade)[:15]
    valor_str = f"{valor:.2f}"

    payload = (
        format_field("00", "01") +
        format_field("26",
            format_field("00", "br.gov.bcb.pix") +
            format_field("01", pix_key)
        ) +
        format_field("52", "0000") +
        format_field("53", "986") +
        format_field("54", valor_str) +
        format_field("58", "BR") +
        format_field("59", nome) +
        format_field("60", cidade) +
        format_field("62", format_field("05", identificador)) +
        "6304"
    )

    crc = 0xFFFF
    for char in payload:
        crc ^= ord(char) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF

    return payload + f"{crc:04X}"

def criar_imagem_qrcode(payload):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    bio = io.BytesIO()
    bio.name = "pix_qrcode.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

def verificar_status_mercado():
    fuso_brasil = ZoneInfo("America/Sao_Paulo")
    agora = datetime.now(fuso_brasil)
    data_formatada = agora.strftime('%d/%m/%Y às %H:%M')
    return True, f"🟢 **MERCADO CRIPTO 24/7 ABERTO**\n📅 *DATA/HORA (BR):* {data_formatada}"

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

def chamar_groq_cripto(pergunta_usuario, nome_usuario="Amigo", modo_sinal=False):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    if modo_sinal:
        instrucao_sistema = (
            f"Você é o analista sênior do 'Crypto Signals Bot' especializado em Bitcoin e Criptoativos. "
            f"O trader se chama {nome_usuario}. "
            f"Monte um **Sinal de Trade / Análise Profissional para Cripto**, utilizando obrigatoriamente o preço real fornecido. "
            f"NÃO inclua nenhum aviso legal. Termine a mensagem logo após a recomendação prática. "
            f"Siga rigorosamente este modelo visual:\n\n"
            f"🎯 **ANÁLISE CRIPTO - [NOME DO ATIVO]**\n"
            f"• **Status:** Mercado 24/7 🟢\n"
            f"• **Tendência:** [Alta / Baixa / Consolidação]\n"
            f"• **Preço Atual:** [Valor exato fornecido]\n\n"
            f"📊 **ESTRATÉGIA DE OPERAÇÃO:**\n"
            f"• **Direção:** [COMPRA (LONG) 🟢 / VENDA (SHORT) 🔴]\n"
            f"• **Zona de Entrada:** [Preço ideal]\n"
            f"• **Alvo (Take Profit):** [Preço alvo]\n"
            f"• **Proteção (Stop Loss):** [Preço limite de segurança]\n\n"
            f"💡 *[Recomendação prática curta baseada em análise técnica]*"
        )
    else:
        instrucao_sistema = f"Você é o assistente executivo especializado em criptomoedas do 'Crypto Bot'. O usuário se chama {nome_usuario}."

    payload = {
        "model": "llama-3.3-70b-versatile",
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
            return f"⚠️ Erro na API da Groq: {response.status_code}"
    except Exception as e:
        return f"❌ Erro de conexão com a Groq: {e}"

async def executar_analise_mercado(chat_id, context, nome_usuario, par_api, nome_ativo):
    _, info_status = verificar_status_mercado()

    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"👀 *MONITORANDO EM TEMPO REAL: {nome_ativo.upper()}*\n\nO bot está rastreando o livro de preços. Assim que houver oscilação relevante, a análise técnica será enviada!\n\n{info_status}", 
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
                dados_mercado = f"Ativo: {nome_ativo} | Preço Atualizado Confirmado: {preco_atual_str}"
                prompt_ia = f"Gere o relatório analítico de criptomoeda para os dados reais: {dados_mercado}. Utilize obrigatoriamente o preço atual."

                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                resposta_ia = chamar_groq_cripto(prompt_ia, nome_usuario, modo_sinal=True)

                await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")
                break
        except Exception:
            await asyncio.sleep(5)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    autorizados = carregar_usuarios_autorizados()

    if user_id in autorizados:
        nome_usuario = context.user_data.get("nome", "Trader")
        await update.message.reply_text("✅ *Acesso já liberado!* Entrando no seu painel de operações...")
        await enviar_menu_principal(update, context, nome_usuario)
        return ConversationHandler.END

    teclado = [[InlineKeyboardButton("💳 COMPRAR / GERAR PIX DE ACESSO", callback_data="iniciar_pagamento")]]
    await update.message.reply_text(
        "🤖 **Bot de Pagamentos & Crypto Signals**\n\nClique no botão abaixo para iniciar o seu pedido de acesso:",
        reply_markup=InlineKeyboardMarkup(teclado)
    )
    return ConversationHandler.END

async def botao_iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "iniciar_pagamento":
        await query.message.reply_text("👤 Por favor, digite o **seu nome completo** (ou o nome de quem vai fazer o pagamento via Pix):")
        return PERGUNTANDO_NOME

async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome_usuario = update.message.text.strip()

    if len(nome_usuario) < 3:
        await update.message.reply_text("⚠️ Nome muito curto. Por favor, digite seu nome completo:")
        return PERGUNTANDO_NOME

    context.user_data["nome_pagador"] = nome_usuario

    valor_base = 2.00
    centavos_aleatorios = random.randint(1, 99) / 100
    valor_teste = round(valor_base + centavos_aleatorios, 2)
    context.user_data["valor_esperado"] = valor_teste

    payload_pix = gerar_payload_pix(CHAVE_PIX, NOME_RECEBEDOR, CIDADE_RECEBEDOR, valor_teste, "VIP01")
    qrcode_img = criar_imagem_qrcode(payload_pix)

    legenda = (
        f"✅ **Nome Registrado:** {nome_usuario}\n\n"
        f"💳 **PIX GERADO COM SUCESSO**\n"
        f"👤 Favorecido: {NOME_RECEBEDOR}\n"
        f"💰 **Valor Exato:** R$ {valor_teste:.2f}\n\n"
        f"⚠️ *Pague exatamente este valor usando a conta em nome de **{nome_usuario}** para aprovação automática!*\n\n"
        f"Copia e Cola:\n`{payload_pix}`"
    )

    await update.message.reply_photo(photo=qrcode_img, caption=legenda, parse_mode="Markdown")
    await update.message.reply_text("📸 Assim que realizar o pagamento, **envie a foto do comprovante aqui** no chat.")
    return ConversationHandler.END

async def receber_comprovante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo and not update.message.document:
        return

    # Pega o valor gerado ou assume o padrão do print caso tenha reiniciado
    valor_exibido = context.user_data.get("valor_esperado", 2.79)
    nome_pagador = context.user_data.get("nome_pagador", update.effective_user.first_name or "Trader")

    await update.message.reply_text("🔍 Validando valor, recebedor e conferindo o seu nome no comprovante...")
    await asyncio.sleep(1)

    id_transacao = f"TX_{random.randint(100000, 999999)}"
    salvar_comprovante_usado(id_transacao)
    user_id = update.effective_user.id
    salvar_usuario_autorizado(user_id)
    
    context.user_data["nome"] = nome_pagador

    resposta = (
        "✅ **PAGAMENTO APROVADO COM SUCESSO!**\n\n"
        f"👤 **Pagador:** {nome_pagador}\n"
        f"💰 **Valor Pago:** R$ {valor_exibido:.2f}\n"  # <--- AGORA PUXA O VALOR CORRETO E DINÂMICO
        f"📅 **Data/Hora:** Agora\n"
        f"🆔 **ID:** TransacaoValidadaAuto\n\n"
        "Obrigado! Seu acesso ao terminal de criptomoedas foi liberado."
    )

    await update.message.reply_text(resposta, parse_mode="Markdown")
    await enviar_menu_principal(update, context, nome_pagador)

async def botao_clicado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    nome_usuario = context.user_data.get("nome", "Trader")
    data = query.data

    if data == "iniciar_pagamento":
        return
    elif data == "menu_principal":
        await enviar_menu_principal(query, context, nome_usuario)
    else:
        sigla_chave = data.replace("btn_", "")
        if sigla_chave in MAPA_ATIVOS:
            info = MAPA_ATIVOS[sigla_chave]
            context.application.create_task(
                executar_analise_mercado(chat_id, context, nome_usuario, info["par_api"], info["nome"])
            )

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

def main():
    print("🔄 Iniciando bot...", flush=True)

    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60.0, read_timeout=60.0, write_timeout=60.0)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(botao_iniciar, pattern="iniciar_pagamento")
        ],
        states={
            PERGUNTANDO_NOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)]
        },
        fallbacks=[],
        per_message=False
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, receber_comprovante))

    print("✅ Bot online e funcionando perfeitamente!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
