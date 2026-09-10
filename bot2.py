import os
import sys
import asyncio
from dotenv import load_dotenv
import requests
from groq import Groq
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
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY no arquivo .env ou no Railway", flush=True)
    sys.exit(1)

# Inicializa o cliente da Groq (IA)
client_groq = Groq(api_key=GROQ_API_KEY)

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
# INTELIGÊNCIA ARTIFICIAL (GROQ)
# =========================
def interpretar_com_ia(texto_usuario):
    """Usa a IA da Groq para extrair o produto da busca ou gerar uma resposta amigável."""
    prompt_sistema = (
        "Você é o Merlim, um assistente de inteligência artificial especialista em e-commerce e caça a ofertas no Mercado Livre. "
        "O usuário vai digitar algo para você. Sua tarefa é analisar o texto e extrair APENAS o nome limpo do produto ou termo principal "
        "que ele deseja buscar (ex: se ele disser 'preciso de uma parafusadeira boa', você retorna apenas 'parafusadeira'). "
        "Se for uma saudação ou conversa fiada sem produto, responda apenas 'CONVERSA'."
    )
    try:
        chat_completion = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": texto_usuario}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=50
        )
        resposta = chat_completion.choices[0].message.content.strip()
        return resposta
    except Exception as e:
        print(f"Erro na API da Groq: {e}")
        return texto_usuario

# =========================
# BUSCA DE PRODUTOS NO MERCADO LIVRE
# =========================
def buscar_produtos_mercadolivre(termo_busca):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_busca)}&limit=5"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            resultados = response.json().get("results", [])
            if resultados:
                return resultados
    except Exception as e:
        print(f"Erro na busca API ML: {e}")
    return []

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    
    banner_url = "https://images.unsplash.com/photo-1607532945533-2de48af48cff?auto=format&fit=crop&w=1000&q=80"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS** | *Seu Assistente Inteligente*\n\n"
        "Seja muito bem-vindo! Agora sou impulsionado por Inteligência Artificial para caçar o **menor preço do Mercado Livre** para você.\n\n"
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
    except Exception:
        await update.message.reply_text(legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    # Tratamento para os botões fixos
    if texto_usuario == "🎟️ Resgatar Cupons" or "Cupons" in texto_usuario:
        link_cupons = gerar_link_afiliado("https://www.mercadolivre.com.br/cupons")
        await update.message.reply_text(
            f"🎟️ **Central de Cupons do Mercado Livre**\n\nAcesse o link abaixo para resgatar seus descontos:\n\n{link_cupons}",
            parse_mode="Markdown"
        )
        return
    elif texto_usuario == "🔥 Ver Ofertas do Dia" or "Ofertas" in texto_usuario:
        texto_usuario = "ofertas imperdíveis"

    # Captura o nome se ainda não estiver definido
    if "nome" not in context.user_data:
        if len(texto_usuario) < 2 or texto_usuario in ["🔥 Ver Ofertas do Dia", "🎟️ Resgatar Cupons"]:
            await update.message.reply_text("⚠️ Por favor, digite um nome ou apelido válido:")
            return
        
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_usuario}!**\n\nAgora você pode conversar comigo naturalmente. **O que você está procurando hoje?** (ex: *quero uma máquina de solda potente, celular barato, etc*):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Celular"), KeyboardButton("👟 Tênis"), KeyboardButton("💻 Notebook")],
                 [KeyboardButton("⚡ Ferramentas"), KeyboardButton("🔥 Ofertas do Dia")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # IA entra em ação para interpretar o pedido do usuário
    termo_inteligente = interpretar_com_ia(texto_usuario)
    if termo_inteligente == "CONVERSA":
        termo_inteligente = texto_usuario # Se for papo genérico, busca o texto original

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🧙‍♂️ *Merlim (IA) analisando seu pedido e garimpando:* `{termo_inteligente}`...", 
        parse_mode="Markdown"
    )
    
    produtos = buscar_produtos_mercadolivre(termo_inteligente)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    link_busca_geral = gerar_link_afiliado(f"https://lista.mercadolivre.com.br/{requests.utils.quote(termo_inteligente)}")

    if produtos:
        primeiro_produto = produtos[0]
        titulo = primeiro_produto.get("title")
        preco_atual = primeiro_produto.get("price", 0)
        
        texto_oferta = (
            f"🏆 **IA ENCONTROU AS MELHORES OPÇÕES!**\n\n"
            f"🛒 Destaque para: *{titulo}*\n"
            f"🟢 **Menor preço encontrado:** R$ {preco_atual:,.2f}\n\n"
            f"📦 Veja todas as variações e ofertas completas na vitrine oficial abaixo:"
        )
    else:
        texto_oferta = (
            f"📦 **Catálogo Completo: {termo_inteligente.title()}**\n\n"
            f"Olá, {nome_usuario}! Usei minha inteligência para buscar as melhores opções para o seu pedido no Mercado Livre.\n\n"
            f"👇 *Clique no botão abaixo para ver a vitrine completa com segurança:*"
        )

    teclado = [
        [InlineKeyboardButton("🔗 VER VITRINE COMPLETA NO SITE", url=link_busca_geral)],
        [InlineKeyboardButton("🎟️ RESGATAR CUPONS", url=gerar_link_afiliado("https://www.mercadolivre.com.br/cupons"))]
    ]
    
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
    print("🧙‍♂️ Iniciando o Merlim com Inteligência Artificial...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim com IA ativado e pronto!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
