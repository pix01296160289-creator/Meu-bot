import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import requests
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
# FUNÇÃO DE VERIFICAÇÃO DE MERCADO
# =========================
def verificar_status_mercado(par_api):
    agora = datetime.now()
    dia_semana = agora.weekday() # 0 = Segunda, 5 = Sábado, 6 = Domingo
    hora = agora.hour

    data_formatada = agora.strftime('%d/%m/%Y às %H:%M')

    if "BTC" not in par_api and "ETH" not in par_api:
        if dia_semana == 5 or (dia_semana == 6 and hora < 18):
            return False, f"🔴 **MERCADO FECHADO (FIM DE SEMANA)**\n📅 *DATA/HORA:* {data_formatada}\n⚠️ *REABERTURA DOMINGO ÀS 18:00.*"

    return True, f"� **MERCADO ABERTO**\n📅 *DATA/HORA:* {data_formatada}"

# =========================
# FUNÇÃO DE CHAMADA À API DA GROQ
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
                f"O mercado está ABERTO. Monte um **Sinal de Trade Profissional**, incluindo obrigatoriamente o **Tempo de Expiração** para Opções Binárias (ex: M1, M5 ou M15). "
                f"Siga rigorosamente este modelo:\n\n"
                f"🎯 **SINAL DE ANÁLISE - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Aberto �\n"
                f"• **Tendência:** [Alta / Baixa / Lateral]\n"
                f"• **Preço Atual:** [Valor]\n\n"
                f"⏱️ **OPÇÃO BINÁRIA (EXPIRAÇÃO):**\n"
                f"• **Tempo:** [Ex: M5 - 5 Minutos]\n"
                f"• **Direção:** [CALL � (Compra) / PUT 🔴 (Venda)]\n"
                f"• **Ponto de Entrada:** [Preço ideal]\n\n"
                f"💡 *[Recomendação prática curta]*\n\n"
                f"Proíba textos fora deste formato."
            )
        else:
            instrucao_sistema = (
                f"Você é o analista sênior do 'Snap Sinais Bot'. "
                f"O operador se chama {nome_usuario}. "
                f"⚠️ O mercado está FECHADO. Monte um **Panorama de Fechamento** seguindo exatamente este modelo:\n\n"
                f"🔒 **PANORAMA DE FECHAMENTO - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Fechado 🔴\n"
                f"• **Último Preço:** [Valor]\n"
                f"• **Tendência de Fundo:** [Alta / Baixa / Lateral]\n"
                f"• **Zonas Chave:** Suporte: [X] | Resistência: [Y]\n\n"
                f"💡 *Reabertura domingo às 18:00.*"
            )
    else:
        instrucao_sistema = (
            f"Você é o assistente executivo do 'Snap Sinais Bot'. "
            f"O usuário se chama {nome_usuario}. Seja educado, direto e prestativo."
        )

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
            dados = response.json()
            return dados['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API da Groq (Status {response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ Erro de conexão com a Groq: {e}"

# =========================
# FUNÇÕES DE BUSCA E ANÁLISE DE MERCADO
# =========================
async def executar_analise_mercado(chat_id, context, nome_usuario, par_api, nome_ativo):
    mercado_aberto, info_status = verificar_status_mercado(par_api)

    await context.bot.send_message(chat_id=chat_id, text=f"🔍 *CONSULTANDO TERMINAIS PARA {nome_ativo.upper()}...*\n\n{info_status}", parse_mode="Markdown")

    url_api = f"https://economia.awesomeapi.com.br/json/last/{par_api}"
    try:
        resposta_api = requests.get(url_api, timeout=10)
        if resposta_api.status_code == 200:
            dados_json = resposta_api.json()
            chave_json = par_api.replace("-", "")
            ativo = dados_json.get(chave_json)

            if ativo:
                status_texto = "Aberto" if mercado_aberto else "Fechado"

                dados_mercado = (
                    f"Ativo: {ativo.get('name', nome_ativo)} | "
                    f"Status: {status_texto} | "
                    f"Preço Atual (Bid): {ativo.get('bid', 'N/A')} | "
                    f"Máxima: {ativo.get('high', 'N/A')} | "
                    f"Mínima: {ativo.get('low', 'N/A')} | "
                    f"Variação: {ativo.get('pctChange', 'N/A')}%"
                )

                prompt_ia = f"Gere o relatório analítico para os dados: {dados_mercado}"

                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                resposta_ia = chamar_groq(prompt_ia, nome_usuario, modo_sinal=True, mercado_aberto=mercado_aberto)

                await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ ATIVO *{nome_ativo.upper()}* NÃO LOCALIZADO.", parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text="❌ FALHA NA CONEXÃO COM O PROVEDOR DE COTAÇÕES.")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ ERRO CRÍTICO: {e}")

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("nome", None)

    url_imagem = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"

    legenda_boas_vindas = (
        "🚀 **BEM-VINDO AO SNAP SINAIS!** 📈\n\n"
        "TERMINAL INTELIGENTE DE ANÁLISE DE MERCADO E OPÇÕES BINÁRIAS.\n\n"
        "PARA COMEÇAR, POR FAVOR, INFORME:\n"
        "👉 **QUAL É O SEU NOME OU APELIDO?**"
    )

    try:
        await update.message.reply_photo(
            photo=url_imagem,
            caption=legenda_boas_vindas,
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")

async def enviar_menu_principal(update_or_query, context, nome_usuario):
    teclado = [
        [InlineKeyboardButton("📊 OPÇÕES BINÁRIAS (GERAL)", callback_data="menu_binarias")],
        [InlineKeyboardButton("💱 CÂMBIO (FOREX)", callback_data="menu_forex")],
        [InlineKeyboardButton("� CRIPTOMOEDAS", callback_data="menu_cripto")],
        [InlineKeyboardButton("🥇 METAIS & COMMODITIES", callback_data="menu_metais")],
        [InlineKeyboardButton("🔄 REDEFINIR NOME", callback_data="btn_reset")]
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
            InlineKeyboardButton("💶 EUR/USD (Binária)", callback_data="btn_bin_eurusd"),
            InlineKeyboardButton("💷 GBP/USD (Binária)", callback_data="btn_bin_gbpusd")
        ],
        [
            InlineKeyboardButton("💵 USD/JPY (Binária)", callback_data="btn_bin_usdjpy"),
            InlineKeyboardButton("📉 AUD/USD (Binária)", callback_data="btn_bin_audusd")
        ],
        [
            InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"📊 **CATEGORIA: OPÇÕES BINÁRIAS**\n👤 *OPERADOR:* **{nome_usuario.upper()}**\n\nEscolha o par para sinal de expiração:", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_forex(query, nome_usuario):
    teclado = [
        [
            InlineKeyboardButton("💵 USD/BRL", callback_data="btn_usdbrl"),
            InlineKeyboardButton("💶 EUR/USD", callback_data="btn_eurusd")
        ],
        [
            InlineKeyboardButton("💷 GBP/BRL", callback_data="btn_gbpbrl"),
            InlineKeyboardButton("🇪🇺 EUR/BRL", callback_data="btn_eurbrl")
        ],
        [
            InlineKeyboardButton("🇯🇵 JPY/BRL", callback_data="btn_jpybrl"),
            InlineKeyboardButton("🇦🇺 AUD/BRL", callback_data="btn_audbrl")
        ],
        [
            InlineKeyboardButton("🇨🇦 CAD/BRL", callback_data="btn_cadbrl")
        ],
        [
            InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"💱 **CATEGORIA: CÂMBIO (FOREX)**\n👤 *OPERADOR:* **{nome_usuario.upper()}**\n\nEscolha o par de moedas:", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_cripto(query, nome_usuario):
    teclado = [
        [
            InlineKeyboardButton("� BTC/BRL", callback_data="btn_btc"),
            InlineKeyboardButton("🔷 ETH/BRL", callback_data="btn_eth")
        ],
        [
            InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"� **CATEGORIA: CRIPTOMOEDAS**\n👤 *OPERADOR:* **{nome_usuario.upper()}**\n\nEscolha o ativo cripto:", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_metais(query, nome_usuario):
    teclado = [
        [
            InlineKeyboardButton("🥇 OURO (XAU/USD)", callback_data="btn_xau")
        ],
        [
            InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"🥇 **CATEGORIA: METAIS & COMMODITIES**\n👤 *OPERADOR:* **{nome_usuario.upper()}**\n\nEscolha o ativo:", reply_markup=reply_markup, parse_mode="Markdown")

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
    elif data == "menu_metais":
        await mostrar_menu_metais(query, nome_usuario)

    elif data == "btn_bin_eurusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "EUR/USD (Opções Binárias)")
        await mostrar_menu_binarias(query, nome_usuario)
    elif data == "btn_bin_gbpusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-USD", "GBP/USD (Opções Binárias)")
        await mostrar_menu_binarias(query, nome_usuario)
    elif data == "btn_bin_usdjpy":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-JPY", "USD/JPY (Opções Binárias)")
        await mostrar_menu_binarias(query, nome_usuario)
    elif data == "btn_bin_audusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "AUD-USD", "AUD/USD (Opções Binárias)")
        await mostrar_menu_binarias(query, nome_usuario)

    elif data == "btn_usdbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-BRL", "Dólar / Real (USD/BRL)")
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "btn_eurusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "Euro / Dólar (EUR/USD)")
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "btn_gbpbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-BRL", "Libra / Real (GBP/BRL)")
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "btn_eurbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-BRL", "Euro / Real (EUR/BRL)")
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "btn_jpybrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "JPY-BRL", "Iene / Real (JPY/BRL)")
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "btn_audbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "AUD-BRL", "Dólar Australiano / Real (AUD/BRL)")
        await mostrar_menu_forex(query, nome_usuario)
    elif data == "btn_cadbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "CAD-BRL", "Dólar Canadense / Real (CAD/BRL)")
        await mostrar_menu_forex(query, nome_usuario)

    elif data == "btn_btc":
        await executar_analise_mercado(chat_id, context, nome_usuario, "BTC-BRL", "Bitcoin / Real (BTC/BRL)")
        await mostrar_menu_cripto(query, nome_usuario)
    elif data == "btn_eth":
        await executar_analise_mercado(chat_id, context, nome_usuario, "ETH-BRL", "Ethereum / Real (ETH/BRL)")
        await mostrar_menu_cripto(query, nome_usuario)

    elif data == "btn_xau":
        await executar_analise_mercado(chat_id, context, nome_usuario, "XAU-USD", "Ouro / Dólar (XAU/USD)")
        await mostrar_menu_metais(query, nome_usuario)

    elif data == "btn_reset":
        context.user_data.pop("nome", None)
        await query.message.reply_text("🔄 *SESSÃO RESETADA!* POR FAVOR, INFORME SEU NOME NOVAMENTE:", parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip().lower()

    if "nome" not in context.user_data:
        context.user_data["nome"] = update.message.text.strip()
        nome_usuario = context.user_data["nome"]

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        boas_vindas_ia = chamar_groq(f"Dê boas-vindas curtas, diretas e em maiúsculas para mim no Snap Sinais.", nome_usuario, modo_sinal=False)

        await context.bot.send_message(chat_id=chat_id, text=boas_vindas_ia.upper(), parse_mode="Markdown")
        await enviar_menu_principal(update, context, nome_usuario)
        return

    nome_usuario = context.user_data.get("nome", "Operador")

    contem_sinal = any(palavra in texto_usuario for palavra in PALAVRAS_SINAL)
    contem_cotacao = any(palavra in texto_usuario for palavra in PALAVRAS_COTACAO)

    if contem_sinal or contem_cotacao:
        if "dólar" in texto_usuario or "usd" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "USD-BRL", "Dólar / Real (USD/BRL)")
            return
        elif "bitcoin" in texto_usuario or "btc" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "BTC-BRL", "Bitcoin / Real (BTC/BRL)")
            return
        elif "euro" in texto_usuario or "eur" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "Euro / Dólar (EUR/USD)")
            return
        elif "libra" in texto_usuario or "gbp" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-BRL", "Libra / Real (GBP/BRL)")
            return
        elif "ethereum" in texto_usuario or "eth" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "ETH-BRL", "Ethereum / Real (ETH/BRL)")
            return
        elif "ouro" in texto_usuario or "xau" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "XAU-USD", "Ouro / Dólar (XAU/USD)")
            return
        elif "iene" in texto_usuario or "jpy" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "JPY-BRL", "Iene / Real (JPY/BRL)")
            return
        elif "australiano" in texto_usuario or "aud" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "AUD-BRL", "Dólar Australiano / Real (AUD/BRL)")
            return
        elif "canadense" in texto_usuario or "cad" in texto_usuario:
            await executar_analise_mercado(chat_id, context, nome_usuario, "CAD-BRL", "Dólar Canadense / Real (CAD/BRL)")
            return
        else:
            await context.bot.send_message(chat_id=chat_id, text="🔍 *ATIVO NÃO IDENTIFICADO.* ESPECIFIQUE (EX: *DÓLAR*, *BITCOIN*, *IENE*).", parse_mode="Markdown")
            return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta_ia = chamar_groq(update.message.text.strip(), nome_usuario, modo_sinal=False)

    if len(resposta_ia) > 4000:
        for i in range(0, len(resposta_ia), 4000):
            await context.bot.send_message(chat_id=chat_id, text=resposta_ia[i:i+4000])
    else:
        await context.bot.send_message(chat_id=chat_id, text=resposta_ia)

# =========================
# INICIALIZAÇÃO DO BOT
# =========================
def main():
    print("🚀 Iniciando o Snap Sinais Bot...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Bot configurado com sucesso! Aguardando interações no Telegram...", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
