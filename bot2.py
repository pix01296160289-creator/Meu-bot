import os
import sys
import asyncio
from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# =========================
# CONFIGURAÇÃO E CHAVES (.env)
# =========================
print("🔄 Carregando variáveis do .env...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves no arquivo .env", flush=True)
    sys.exit(1)

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# INTERPRETAÇÃO COM IA (GROQ)
# =========================
def interpretar_pedido_com_ia(pergunta_usuario, nome_usuario="Amigo"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    instrucao_sistema = (
        f"Você é o Merlim das Ofertas, um assistente especialista em caçar promoções reais e cupons. "
        f"O usuário se chama {nome_usuario}. "
        f"Retorne APENAS o termo principal para busca focado em achar produtos em promoção (ex: se ele disser 'celular com promoção', retorne 'smartphone em oferta' ou 'celular desconto'). Não use pontuação."
    )

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
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            return pergunta_usuario
    except Exception as e:
        return pergunta_usuario

# =========================
# BUSCA DE PROMOÇÕES REAIS (MERCADO LIVRE)
# =========================
def buscar_promocoes_mercado_livre(termo_busca, termo_original=""):
    # Filtros de ordenação na API do ML para priorizar ofertas/relevância com desconto
    termos_para_testar = [
        f"{termo_busca} oferta", 
        f"{termo_original} promoção", 
        termo_busca, 
        termo_original
    ]
    
    for t in termos_para_testar:
        if not t:
            continue
        try:
            # Adicionamos parâmetros para buscar itens com desconto/oferta relâmpago se disponível na API
            url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(t)}&sort=price_asc&limit=5"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                resultados = response.json().get("results", [])
                if resultados:
                    # Filtramos para garantir que pegamos itens que tenham preço original maior (com desconto real)
                    produtos_com_desconto = []
                    for p in resultados:
                        precio = p.get("price", 0)
                        original_price = p.get("original_price")
                        
                        # Se o ML informou preço original e ele for maior que o atual, é promoção real!
                        if original_price and original_price > precio:
                            produtos_com_desconto.insert(0, p) # Joga para o topo
                        else:
                            produtos_com_desconto.append(p)
                            
                    return produtos_com_desconto[:3] # Retorna os 3 melhores
        except Exception as e:
            print(f"Erro na busca ({t}): {e}")
            
    return []

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    legenda_boas_vindas = (
        "🧙‍♂️ **OLÁ! EU SOU O MERLIM DAS OFERTAS** 🔥\n\n"
        "O seu mago especialista em encontrar **preços baixos reais, descontos e cupons**!\n\n"
        "Para iniciarmos, por favor:\n"
        "👉 **DIGITE SEU NOME OU APELIDO:**"
    )
    await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    if "nome" not in context.user_data:
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        msg_vinheta = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ *Varinha mágica ativada para {nome_usuario.upper()}...*\n⏳ Escaneando ofertas relâmpago [ 1/3 ]", 
            parse_mode="Markdown"
        )
        await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_vinheta.message_id, text=f"✨ *Portal aberto para:* **{nome_usuario.upper()}**\n⏳ Caçando cupons e descontos reais [ 2/3 ]", parse_mode="Markdown")
        await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_vinheta.message_id, text=f"✨ *Portal aberto para:* **{nome_usuario.upper()}**\n✅ Merlim pronto para economizar! [ 3/3 ]", parse_mode="Markdown")
        await asyncio.sleep(1)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_vinheta.message_id)
        except:
            pass

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🪄 **Tudo pronto, {nome_usuario}!**\n\nQual produto você quer achar com **desconto ou promoção real** hoje?", 
            parse_mode="Markdown"
        )
        return

    if context.user_data.get("ultima_mensagem") == texto_usuario:
        return
    context.user_data["ultima_mensagem"] = texto_usuario

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    resposta_ia = interpretar_pedido_com_ia(texto_usuario, nome_usuario)
    palavras_resposta = resposta_ia.split()

    is_duvida = any(termo in texto_usuario.lower() for termo in ["como", "qual", "onde", "ajuda", "cupom", "olá"])
    
    if len(palavras_resposta) <= 6 and not is_duvida:
        termo_busca = resposta_ia
        msg_aguarde = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🔥 *Merlim caçando promoções para:* `{texto_usuario}`...", 
            parse_mode="Markdown"
        )
        
        produtos = buscar_promocoes_mercado_livre(termo_busca, termo_original=texto_usuario)
        
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
        except:
            pass

        if not produtos:
            link_busca_ml = f"https://lista.mercadolivre.com.br/ofertas/{requests.utils.quote(texto_usuario)}"
            texto_fallback = (
                f"🔥 **Ofertas encontradas, {nome_usuario}!**\n\n"
                f"Abri a seção oficial de **Ofertas e Descontos** do Mercado Livre para **'{texto_usuario}'**."
            )
            teclado = [[InlineKeyboardButton("🔥 VER SEÇÃO DE OFERTAS NO SITE", url=link_busca_ml)]]
            await context.bot.send_message(chat_id=chat_id, text=texto_fallback, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")
            return

        for p in produtos:
            titulo = p.get("title")
            preco_atual = p.get("price", 0)
            preco_antigo = p.get("original_price")
            link = p.get("permalink")
            thumbnail = p.get("thumbnail")
            
            # Monta o texto destacando o desconto igualzinho no aplicativo
            if preco_antigo and preco_antigo > preco_atual:
                desconto_pct = int(100 - (preco_atual * 100 / preco_antigo))
                info_preco = (
                    f"❌ ~~R$ {preco_antigo:,.2f}~~ | 🟢 **R$ {preco_atual:,.2f}**\n"
                    f"🔥 **DESCONTO REAL: {desconto_pct}% OFF!**"
                )
            else:
                info_preco = f"💰 **Preço:** R$ {preco_atual:,.2f}\n🔥 *Preço competitivo encontrado!*"

            texto_oferta = (
                f"🛒 **{titulo}**\n\n"
                f"{info_preco}\n\n"
                f"⚡ *Caçado pelo Merlim das Ofertas*"
            )
            
            teclado = [[InlineKeyboardButton("🔗 APROVEITAR PROMOÇÃO", url=link)]]
            reply_markup = InlineKeyboardMarkup(teclado)

            try:
                await context.bot.send_photo(chat_id=chat_id, photo=thumbnail, caption=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=chat_id, text=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")

# =========================
# MAIN
# =========================
def main():
    print("🧙‍♂️ Iniciando o Merlim das Ofertas...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim configurado para caçar promoções reais!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
