import os
import sys
import asyncio
from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# =========================
# CONFIGURAÇÃO E CHAVES
# =========================
print("🔄 Carregando variáveis de ambiente...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
AFFILIATE_ID = os.getenv("AFFILIATE_ID", "")

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY", flush=True)
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
        f"Você é o Merlim das Ofertas, especialista em cupons e descontos reais do Mercado Livre. "
        f"O usuário se chama {nome_usuario}. "
        f"Extraia o produto principal que ele quer buscar (ex: se ele disser 'celular samsung com promoção', retorne 'celular samsung'). Não use pontuação."
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
# GERADOR DE LINK COM COMISSÃO AUTOMÁTICA
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    separador = "&" if "?" in url_produto else "?"
    return f"{url_produto}{separador}matt_tool={AFFILIATE_ID}"

# =========================
# BUSCA DE PROMOÇÕES NO MERCADO LIVRE
# =========================
def buscar_cupons_e_promocoes(termo_busca):
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_busca + ' ofertas')}&sort=price_asc&limit=10"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            resultados = response.json().get("results", [])
            produtos_com_desconto_real = []
            for p in resultados:
                preco_atual = p.get("price", 0)
                preco_antigo = p.get("original_price")
                if preco_antigo and preco_antigo > preco_atual:
                    produtos_com_desconto_real.append(p)
            
            if produtos_com_desconto_real:
                return produtos_com_desconto_real[:3]
            return resultados[:3]
    except Exception as e:
        print(f"Erro na busca: {e}")
    return []

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    # Banner profissional de boas-vindas (Imagem combinando Merlim + E-commerce)
    banner_url = "https://images.unsplash.com/photo-1607532945533-2de48af48cff?auto=format&fit=crop&w=1000&q=80"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS** | *Assistente Oficial de Descontos*\n\n"
        "Seja muito bem-vindo ao seu portal inteligente de economia e achados do Mercado Livre!\n\n"
        "✨ **O que eu faço por você:**\n"
        "• Caço preços baixos e descontos reais em tempo real\n"
        "• Encontro cupons e ofertas relâmpago exclusivas\n"
        "• Direto para o menor preço com segurança\n\n"
        "👉 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

    # Teclado rápido inferior para interatividade profissional
    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("🔥 Ver Ofertas do Dia"), KeyboardButton("🎟️ Resgatar Cupons")]],
        resize_keyboard=True
    )

    try:
        await update.message.reply_photo(
            photo=banner_url, 
            caption=legenda_boas_vindas, 
            reply_markup=teclado_menu, 
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    # Atalhos rápidos do teclado fixo
    if texto_usuario == "🔥 Ver Ofertas do Dia":
        texto_usuario = "ofertas imperdíveis"
    elif texto_usuario == "🎟️ Resgatar Cupons":
        link_cupons = gerar_link_afiliado("https://www.mercadolivre.com.br/cupons")
        await update.message.reply_text(
            f"🎟️ **Central de Cupons do Mercado Livre**\n\nAcesse o link abaixo para resgatar seus cupons ativos:\n\n{link_cupons}",
            parse_mode="Markdown"
        )
        return

    if "nome" not in context.user_data:
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        msg_vinheta = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ *Conectando os servidores de ofertas para {nome_usuario.upper()}...*\n⏳ Autenticando perfil [ 1/3 ]", 
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_vinheta.message_id, text=f"✨ *Perfil:* **{nome_usuario.upper()}**\n⏳ Sincronizando com a base do Mercado Livre [ 2/3 ]", parse_mode="Markdown")
        await asyncio.sleep(0.8)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_vinheta.message_id, text=f"✨ *Perfil:* **{nome_usuario.upper()}**\n✅ Sistema pronto para garimpar! [ 3/3 ]", parse_mode="Markdown")
        await asyncio.sleep(0.8)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_vinheta.message_id)
        except:
            pass

        await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🪄 **Tudo pronto, {nome_usuario}!**\n\nDigite o nome do produto que você deseja encontrar com o **melhor preço** agora:", 
        parse_mode="Markdown"
    )
        return

    if context.user_data.get("ultima_mensagem") == texto_usuario:
        return
    context.user_data["ultima_mensagem"] = texto_usuario

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    termo_ia = interpretar_pedido_com_ia(texto_usuario, nome_usuario)
    
    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🔍 *Merlim varrendo o catálogo por:* `{texto_usuario}`...", 
        parse_mode="Markdown"
    )
    
    produtos = buscar_cupons_e_promocoes(termo_ia)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except:
        pass

    link_cupons_oficial = gerar_link_afiliado("https://www.mercadolivre.com.br/cupons")
    link_busca_ofertas = gerar_link_afiliado(f"https://lista.mercadolivre.com.br/ofertas/{requests.utils.quote(texto_usuario)}")

    if not produtos:
        texto_fallback = (
            f"📦 **Resultado da Busca, {nome_usuario}:**\n\n"
            f"Não encontrei uma oferta exata com queima de estoque imediata para essa pesquisa, mas você pode conferir as tendências globais ou os cupons do dia:"
        )
        teclado = [
            [InlineKeyboardButton("🎟️ RESGATAR CUPONS OFICIAIS", url=link_cupons_oficial)],
            [InlineKeyboardButton("🔥 VER TODAS AS OFERTAS", url=link_busca_ofertas)]
        ]
        await context.bot.send_message(chat_id=chat_id, text=texto_fallback, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")
        return

    for p in produtos:
        titulo = p.get("title")
        preco_atual = p.get("price", 0)
        preco_antigo = p.get("original_price")
        link_original = p.get("permalink")
        thumbnail = p.get("thumbnail")
        
        link_monetizado = gerar_link_afiliado(link_original)
        
        if preco_antigo and preco_antigo > preco_atual:
            desconto_pct = int(100 - (preco_atual * 100 / preco_antigo))
            info_preco = (
                f"❌ ~~R$ {preco_antigo:,.2f}~~ | 🟢 **R$ {preco_atual:,.2f}**\n"
                f"🔥 **DESCONTO REAL: {desconto_pct}% OFF!**"
            )
        else:
            info_preco = f"💰 **Melhor Preço Encontrado:** R$ {preco_atual:,.2f}\n✨ *Produto verificado*"

        texto_oferta = (
            f"🛒 **{titulo}**\n\n"
            f"{info_preco}\n\n"
            f"⚡ *Garantia de menor preço e envio rápido pelo Mercado Livre.*"
        )
        
        teclado = [
            [InlineKeyboardButton("🔗 APROVEITAR DESCONTO NO SITE", url=link_monetizado)],
            [InlineKeyboardButton("🎟️ RESGATAR CUPONS EXTRAS", url=link_cupons_oficial)]
        ]
        reply_markup = InlineKeyboardMarkup(teclado)

        try:
            await context.bot.send_photo(chat_id=chat_id, photo=thumbnail, caption=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")
        except:
            await context.bot.send_message(chat_id=chat_id, text=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")

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

    print("✅ Merlim atualizado com visual profissional!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
