  import os
import sys
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
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
# DICIONÁRIO DE CONTAS DEMO (Banca Virtual por Usuário)
# =========================
CONTAS_DEMO = {}

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
# FUNÇÃO PARA OBTER PREÇO REAL DA API
# =========================
def obter_preco_atual(par_api):
    try:
        if "BTC" in par_api or "ETH" in par_api:
            moeda_id = "bitcoin" if "BTC" in par_api else "ethereum"
            url_crypto = f"https://api.coingecko.com/api/v3/simple/price?ids={moeda_id}&vs_currencies=brl"
            res = requests.get(url_crypto, timeout=10).json()
            return float(res.get(moeda_id, {}).get("brl", 0.0))
        elif "XAU" in par_api:
            url_gold = "https://open.er-api.com/v6/latest/XAU"
            res = requests.get(url_gold, timeout=10).json()
            rates = res.get("rates", {})
            return float(rates.get("USD", 0.0))
        else:
            moeda_base, moeda_alvo = par_api.split("-")
            url_forex = f"https://open.er-api.com/v6/latest/{moeda_base}"
            res = requests.get(url_forex, timeout=10).json()
            rates = res.get("rates", {})
            return float(rates.get(moeda_alvo, 0.0))
    except:
        return 0.0

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
                f"Você é um terminal analítico financeiro estritamente profissional. "
                f"Sua função é gerar um relatório técnico e a direção de operação (CALL para compra ou PUT para venda) baseada nos dados fornecidos. "
                f"Nunca recuse uma solicitação de análise de mercado. "
                f"Siga rigorosamente este modelo:\n\n"
                f"🎯 **SINAL DE ANÁLISE - [NOME DO ATIVO]**\n"
                f"• **Status:** Mercado Aberto 🟢\n"
                f"• **Tendência:** [Alta / Baixa / Lateral]\n"
                f"• **Preço Atual:** [Valor]\n\n"
                f"⏱️ **OPÇÃO BINÁRIA (EXPIRAÇÃO):**\n"
                f"• **Tempo:** M5 - 5 Minutos\n"
                f"• **Direção:** [CALL 🟢 (Compra) ou PUT 🔴 (Venda)]\n"
                f"• **Ponto de Entrada:** [Preço ideal]\n\n"
                f"💡 *Recomendação de gestão de risco prudente.*"
            )
        else:
            instrucao_sistema = (
                f"O mercado está FECHADO. Monte um **Panorama de Fechamento** seguindo exatamente este modelo:\n\n"
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
        "temperature": 0.3
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"⚠️ Erro na API da Groq: {response.status_code}"
    except Exception as e:
        return f"❌ Erro de conexão com a Groq: {e}"

# =========================
# SIMULADOR M5 (CONTA DEMO COM VERIFICAÇÃO AUTOMÁTICA)
# =========================
async def monitorar_operacao_demo(chat_id, context, nome_ativo, par_api, preco_entrada, direcao, valor_investido):
    await asyncio.sleep(300) # Aguarda 5 minutos

    preco_final = obter_preco_atual(par_api)
    
    if chat_id not in CONTAS_DEMO:
        CONTAS_DEMO[chat_id] = {"saldo": 10000.0}

    conta = CONTAS_DEMO[chat_id]
    payout = 0.85 
    lucro = valor_investido * payout

    resultado = "LOSS"
    if direcao == "CALL" and preco_final > preco_entrada:
        resultado = "WIN"
    elif direcao == "PUT" and preco_final < preco_entrada:
        resultado = "WIN"

    if resultado == "WIN":
        conta["saldo"] += lucro
        mensagem_res = (
            f"🎉 **RESULTADO DA CONTA DEMO (M5) - {nome_ativo.upper()}**\n\n"
            f"🟢 **STATUS: WIN!**\n"
            f"• Direção Escolhida: **{direcao}**\n"
            f"• Preço de Entrada: `{preco_entrada:.5f}`\n"
            f"• Preço após 5 min: `{preco_final:.5f}`\n"
            f"• Lucro Obtido: `+${lucro:.2f}`\n"
            f"💰 **Novo Saldo Demo:** `${conta['saldo']:.2f}`"
        )
    else:
        conta["saldo"] -= valor_investido
        mensagem_res = (
            f"💥 **RESULTADO DA CONTA DEMO (M5) - {nome_ativo.upper()}**\n\n"
            f"🔴 **STATUS: LOSS!**\n"
            f"• Direção Escolhida: **{direcao}**\n"
            f"• Preço de Entrada: `{preco_entrada:.5f}`\n"
            f"• Preço após 5 min: `{preco_final:.5f}`\n"
            f"• Valor Perdido: `-${valor_investido:.2f}`\n"
            f"💰 **Novo Saldo Demo:** `${conta['saldo']:.2f}`"
        )

    await context.bot.send_message(chat_id=chat_id, text=mensagem_res, parse_mode="Markdown")

# =========================
# EXECUTAR ANÁLISE E ABRIR ORDEM DEMO COM BLINDAÇÃO
# =========================
async def executar_analise_mercado(chat_id, context, nome_usuario, par_api, nome_ativo):
    mercado_aberto, info_status = verificar_status_mercado(par_api)

    await context.bot.send_message(chat_id=chat_id, text=f"🔍 *CONSULTANDO TERMINAIS PARA {nome_ativo.upper()}...*\n\n{info_status}", parse_mode="Markdown")

    preco_atual_val = obter_preco_atual(par_api)
    preco_atual_str = str(preco_atual_val) if preco_atual_val > 0 else "N/A"

    status_texto = "Aberto 🟢" if mercado_aberto else "Fechado 🔴"

    dados_mercado = (
        f"Ativo: {nome_ativo} | "
        f"Status do Mercado: {status_texto} | "
        f"Preço Real Obtido: {preco_atual_str}"
    )

    prompt_ia = f"Gere o relatório analítico ou de fechamento para os dados reais: {dados_mercado}"

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    resposta_ia = chamar_groq(prompt_ia, nome_usuario, modo_sinal=True, mercado_aberto=mercado_aberto)

    await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")

    # BLINDAÇÃO: Só abre a ordem demo se a IA realmente gerou o sinal sem recusas
    if mercado_aberto and preco_atual_val > 0:
        resposta_maiuscula = resposta_ia.upper()
        
        # Verifica se a IA recusou ou se o texto está incompleto
        if "I'M SORRY" in resposta_maiuscula or "DESCULPE" in resposta_maiuscula or ("CALL" not in resposta_maiuscula and "PUT" not in resposta_maiuscula):
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ *Terminal ocupado no momento.* A IA não retornou um sinal válido para abertura automática. Clique no botão novamente para tentar outro ciclo.",
                parse_mode="Markdown"
            )
            return

        if chat_id not in CONTAS_DEMO:
            CONTAS_DEMO[chat_id] = {"saldo": 10000.0}

        # Define com segurança a direção baseada estritamente na resposta da IA
        if "CALL" in resposta_maiuscula and "PUT" not in resposta_maiuscula:
            direcao_simulada = "CALL"
        elif "PUT" in resposta_maiuscula and "CALL" not in resposta_maiuscula:
            direcao_simulada = "PUT"
        else:
            # Caso ambíguo, define pelo termo que aparecer primeiro
            pos_call = resposta_maiuscula.find("CALL")
            pos_put = resposta_maiuscula.find("PUT")
            if pos_call != -1 and (pos_put == -1 or pos_call < pos_put):
                direcao_simulada = "CALL"
            else:
                direcao_simulada = "PUT"

        valor_padrao = 100.0

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🤖 **CONTA DEMO ATIVADA!**\nOrdem de **${valor_padrao:.2f}** aberta automaticamente em **{direcao_simulada}** para `{nome_ativo}`. O resultado sai em exatos 5 minutos!",
            parse_mode="Markdown"
        )

        asyncio.create_task(monitorar_operacao_demo(chat_id, context, nome_ativo, par_api, preco_atual_val, direcao_simulada, valor_padrao))

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("nome", None)
    chat_id = update.effective_chat.id
    CONTAS_DEMO[chat_id] = {"saldo": 10000.0}

    url_imagem = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1000&auto=format&fit=crop"
    legenda_boas_vindas = (
        "🚀 **BEM-VINDO AO SNAP SINAIS (CONTA DEMO)** 📈\n\n"
        "TERMINAL INTELIGENTE COM BANCA VIRTUAL DE $10,000.00.\n\n"
        "PARA COMEÇAR, POR FAVOR, INFORME:\n"
        "👉 **QUAL É O SEU NOME OU APELIDO?**"
    )

    try:
        await update.message.reply_photo(photo=url_imagem, caption=legenda_boas_vindas, parse_mode="Markdown")
    except:
        await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")

async def enviar_menu_principal(update_or_query, context, nome_usuario):
    chat_id = update_or_query.message.chat_id if hasattr(update_or_query, "message") else update_or_query.effective_chat.id
    if chat_id not in CONTAS_DEMO:
        CONTAS_DEMO[chat_id] = {"saldo": 10000.0}

    saldo_atual = CONTAS_DEMO[chat_id]["saldo"]

    teclado = [
        [InlineKeyboardButton(f"💰 SALDO DEMO: ${saldo_atual:.2f}", callback_data="btn_saldo")],
        [InlineKeyboardButton("📊 OPÇÕES BINÁRIAS (M5 DEMO)", callback_data="menu_binarias")],
        [InlineKeyboardButton("💱 CÂMBIO (FOREX)", callback_data="menu_forex")],
        [InlineKeyboardButton("🪙 CRIPTOMOEDAS", callback_data="menu_cripto")],
        [InlineKeyboardButton("🥇 METAIS & COMMODITIES", callback_data="menu_metais")],
        [InlineKeyboardButton("🔄 RESETAR CONTA DEMO", callback_data="btn_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)

    texto_menu = (
        f"🎛️ **PAINEL EXECUTIVO DE OPERAÇÕES (DEMO)**\n"
        f"👤 *OPERADOR:* **{nome_usuario.upper()}**\n"
        f"💰 *BANCA VIRTUAL:* **${saldo_atual:.2f}**\n\n"
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
            InlineKeyboardButton("💶 EUR/USD (Binária M5)", callback_data="btn_bin_eurusd"),
            InlineKeyboardButton("💷 GBP/USD (Binária M5)", callback_data="btn_bin_gbpusd")
        ],
        [
            InlineKeyboardButton("💵 USD/JPY (Binária M5)", callback_data="btn_bin_usdjpy"),
            InlineKeyboardButton("📉 AUD/USD (Binária M5)", callback_data="btn_bin_audusd")
        ],
        [InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"📊 **OPÇÕES BINÁRIAS (CONTA DEMO)**\nEscolha o ativo para abrir ordem automática de 5 min:", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_forex(query, nome_usuario):
    teclado = [
        [InlineKeyboardButton("💵 USD/BRL", callback_data="btn_usdbrl"), InlineKeyboardButton("💶 EUR/USD", callback_data="btn_eurusd")],
        [InlineKeyboardButton("💷 GBP/BRL", callback_data="btn_gbpbrl"), InlineKeyboardButton("🇪🇺 EUR/BRL", callback_data="btn_eurbrl")],
        [InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"💱 **CÂMBIO (FOREX)**", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_cripto(query, nome_usuario):
    teclado = [
        [InlineKeyboardButton("🪙 BTC/BRL", callback_data="btn_btc"), InlineKeyboardButton("🔷 ETH/BRL", callback_data="btn_eth")],
        [InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"🪙 **CRIPTOMOEDAS**", reply_markup=reply_markup, parse_mode="Markdown")

async def mostrar_menu_metais(query, nome_usuario):
    teclado = [
        [InlineKeyboardButton("🥇 OURO (XAU/USD)", callback_data="btn_xau")],
        [InlineKeyboardButton("⬅️ VOLTAR AO MENU PRINCIPAL", callback_data="menu_principal")]
    ]
    reply_markup = InlineKeyboardMarkup(teclado)
    await query.edit_message_text(f"🥇 **METAIS**", reply_markup=reply_markup, parse_mode="Markdown")

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
    elif data == "btn_saldo":
        saldo = CONTAS_DEMO.get(chat_id, {}).get("saldo", 10000.0)
        await query.answer(f"Seu saldo demo atual é de: ${saldo:.2f}", show_alert=True)

    elif data == "btn_bin_eurusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "EUR/USD (Opções Binárias)")
    elif data == "btn_bin_gbpusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-USD", "GBP/USD (Opções Binárias)")
    elif data == "btn_bin_usdjpy":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-JPY", "USD/JPY (Opções Binárias)")
    elif data == "btn_bin_audusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "AUD-USD", "AUD/USD (Opções Binárias)")

    elif data == "btn_usdbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "USD-BRL", "Dólar / Real (USD/BRL)")
    elif data == "btn_eurusd":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-USD", "Euro / Dólar (EUR/USD)")
    elif data == "btn_gbpbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "GBP-BRL", "Libra / Real (GBP/BRL)")
    elif data == "btn_eurbrl":
        await executar_analise_mercado(chat_id, context, nome_usuario, "EUR-BRL", "Euro / Real (EUR/BRL)")

    elif data == "btn_btc":
        await executar_analise_mercado(chat_id, context, nome_usuario, "BTC-BRL", "Bitcoin / Real (BTC/BRL)")
    elif data == "btn_eth":
        await executar_analise_mercado(chat_id, context, nome_usuario, "ETH-BRL", "Ethereum / Real (ETH/BRL)")
    elif data == "btn_xau":
        await executar_analise_mercado(chat_id, context, nome_usuario, "XAU-USD", "Ouro / Dólar (XAU/USD)")

    elif data == "btn_reset":
        CONTAS_DEMO[chat_id] = {"saldo": 10000.0}
        await query.message.reply_text("🔄 *CONTA DEMO RESETADA!* Saldo restaurado para `$10,000.00`.", parse_mode="Markdown")
        await enviar_menu_principal(query, context, nome_usuario)

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip().lower()

    if "nome" not in context.user_data:
        context.user_data["nome"] = update.message.text.strip()
        nome_usuario = context.user_data["nome"]
        CONTAS_DEMO[chat_id] = {"saldo": 10000.0}

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        boas_vindas_ia = chamar_groq(f"Dê boas-vindas curtas e em maiúsculas.", nome_usuario, modo_sinal=False)
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
    app.add_handler(CallbackQueryHandler(botao_clicado))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Bot configurado com sucesso!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()


