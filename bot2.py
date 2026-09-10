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
# GERADOR DE LINK COM COMISSÃO AUTOMÁTICA
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    separador = "&" if "?" in url_produto else "?"
    return f"{url_produto}{separador}matt_tool={AFFILIATE_ID}"

# =========================
# BUSCA O PREÇO MAIS BAIXO NO MERCADO LIVRE
# =========================
def buscar_menor_preco(termo_busca):
    try:
        # Ordenado por preço ascendente (sort=price_asc) para pegar SEMPRE o mais barato primeiro
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_busca)}&sort=price_asc&limit=1"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            resultados = response.json().get("results", [])
            if resultados:
                return resultados[0] # Retorna o produto mais barato encontrado
    except Exception as e:
        print(f"Erro na busca: {e}")
    return None

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    banner_url = "https://images.unsplash.com/photo-1607532945533-2de48af48cff?auto=format&fit=crop&w=1000&q=80"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS** | *Seu Assistente Inteligente*\n\n"
        "Seja muito bem-vindo! Vou caçar o **menor preço do Mercado Livre** para qualquer produto que você quiser.\n\n"
        "👉 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

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

    # Atalhos rápidos do teclado inferior
    if texto_usuario == "🎟️ Resgatar Cupons":
        link_cupons = gerar_link_afiliado("https://www.mercadolivre.com.br/cupons")
        await update.message.reply_text(
            f"🎟️ **Central de Cupons do Mercado Livre**\n\nAcesse o link abaixo para resgatar seus descontos:\n\n{link_cupons}",
            parse_mode="Markdown"
        )
        return
    elif texto_usuario == "🔥 Ver Ofertas do Dia":
        texto_usuario = "ofertas imperdíveis"

    # Passo 1: Capturar o nome do usuário se ainda não tiver
    if "nome" not in context.user_data:
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_usuario}!**\n\nAgora, **digite o nome de qualquer produto** que você está procurando (ex: *máquina de solda, tênis, celular, furadeira*):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Celular"), KeyboardButton("👟 Tênis"), KeyboardButton("💻 Notebook")],
                 [KeyboardButton("⚡ Ferramentas"), KeyboardButton("🔥 Ofertas do Dia")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    # Evitar mensagens duplicadas seguidas
    if context.user_data.get("ultima_mensagem") == texto_usuario:
        return
    context.user_data["ultima_mensagem"] = texto_usuario

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🔍 *Merlim garimpando o menor preço para:* `{texto_usuario}`...", 
        parse_mode="Markdown"
    )
    
    # Faz a busca direto pelo termo que o cliente digitou (qualquer produto)
    produto = buscar_menor_preco(texto_usuario)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except:
        pass

    if not produto:
        link_busca_geral = gerar_link_afiliado(f"https://lista.mercadolivre.com.br/{requests.utils.quote(texto_usuario)}")
        texto_fallback = (
            f"📦 **Resultado para '{texto_usuario}', {nome_usuario}:**\n\n"
            f"Não achei um item exato com estoque imediato para esse termo exato, mas você pode ver todas as opções no site oficial:"
        )
        teclado_fallback = [[InlineKeyboardButton("🔗 VER OPÇÕES NO MERCADO LIVRE", url=link_busca_geral)]]
        await context.bot.send_message(chat_id=chat_id, text=texto_fallback, reply_markup=InlineKeyboardMarkup(teclado_fallback), parse_mode="Markdown")
        return

    # Monta os dados do produto mais barato encontrado na API
    titulo = produto.get("title")
    preco_atual = produto.get("price", 0)
    link_original = produto.get("permalink")
    thumbnail = produto.get("thumbnail")
    
    link_monetizado = gerar_link_afiliado(link_original)

    texto_oferta = (
        f"🏆 **ACHEI O MENOR PREÇO PARA VOCÊ!**\n\n"
        f"🛒 **{titulo}**\n\n"
        f"🟢 **Por apenas: R$ {preco_atual:,.2f}**\n\n"
        f"⚡ *Menor valor localizado na base oficial do Mercado Livre com link verificado.*"
    )
    
    teclado = [
        [InlineKeyboardButton("🔗 VER MENOR PREÇO NO SITE", url=link_monetizado)],
        [InlineKeyboardButton("🎟️ RESGATAR CUPONS", url=gerar_link_afiliado("https://www.mercadolivre.com.br/cupons"))]
    ]
    
    try:
        await context.bot.send_photo(
            chat_id=chat_id, 
            photo=thumbnail, 
            caption=texto_oferta, 
            reply_markup=InlineKeyboardMarkup(teclado), 
            parse_mode="Markdown"
        )
    except:
        await context.bot.send_message(
            chat_id=chat_id, 
            text=texto_oferta, 
            reply_markup=InlineKeyboardMarkup(teclado), 
            parse_mode="Markdown"
        )

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

    print("✅ Merlim configurado com busca universal de menor preço!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
