
import os
import sys
import re
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

# Seu link oficial de afiliado do Mercado Livre (meli.la)
LINK_VITRINE_SOCIAL = "https://meli.la/1FVqCEw"

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY no Railway", flush=True)
    sys.exit(1)

client_groq = Groq(api_key=GROQ_API_KEY)

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

def limpar_termo(texto):
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    return ' '.join(texto_limpo.split()).strip()

def interpretar_com_ia(texto_usuario):
    prompt_sistema = (
        "Você é o Merlim, assistente de e-commerce e ofertas do Mercado Livre. "
        "Extraia APENAS o termo limpo do produto desejado (ex: 'celular', 'furadeira', 'televisao'). "
        "Se for saudação, retorne 'CONVERSA'."
    )
    try:
        chat_completion = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": texto_usuario}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=30
        )
        resposta = chat_completion.choices[0].message.content.strip()
        return limpar_termo(resposta)
    except Exception as e:
        print(f"Erro na API da Groq: {e}")
        return limpar_termo(texto_usuario)

# =========================
# BUSCA O PRODUTO PARA ILUSTRAR
# =========================
def buscar_produto_vitrine(termo_busca):
    termo_tratado = limpar_termo(termo_busca)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Referer": "https://www.mercadolivre.com.br/"
        }
        
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_tratado)}&limit=1"
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            if resultados:
                return resultados[0]
    except Exception as e:
        print(f"❌ Erro na requisição da API: {e}", flush=True)
    return None

# =========================
# COMANDOS E FLUXO DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    banner_url = "https://i.ibb.co/pr5XpyL8/image-1789089291368.jpg"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS**\n\n"
        "Me diga o que você procura (ex: *celular*, *furadeira*, *tênis*), eu encontro a melhor opção e te entrego com acesso direto à sua vitrine oficial com comissão garantida!\n\n"
        "👉 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("✨ Minha Vitrine de Ofertas")]],
        resize_keyboard=True
    )

    try:
        await update.message.reply_photo(photo=banner_url, caption=legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    if "Vitrine" in texto_usuario:
        teclado_inline_vitrine = [
            [InlineKeyboardButton("✨ ACESSAR VITRINE COMPLETA NO SITE", url=LINK_VITRINE_SOCIAL)]
        ]
        await update.message.reply_text(
            "🛍️ **Vitrine Exclusiva do Merlim**\n\nClique abaixo para acessar todas as recomendações:",
            reply_markup=InlineKeyboardMarkup(teclado_inline_vitrine),
            parse_mode="Markdown"
        )
        return

    if "nome" not in context.user_data:
        nome_limpo = limpar_termo(texto_usuario)
        if len(nome_limpo) < 2 or "Vitrine" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite o seu nome ou apelido primeiro:")
            return
        
        context.user_data["nome"] = nome_limpo
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_limpo}!**\n\nAgora digite o que você quer buscar (Ex: *celular*, *furadeira*). Vou buscar a oferta para você!",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Celular"), KeyboardButton("⚡ Furadeira")],
                 [KeyboardButton("✨ Minha Vitrine de Ofertas")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    if "Celular" in texto_usuario:
        texto_usuario = "celular"
    elif "Furadeira" in texto_usuario:
        texto_usuario = "furadeira"

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    termo_inteligente = interpretar_com_ia(texto_usuario)
    if termo_inteligente == "CONVERSA" or not termo_inteligente:
        termo_inteligente = limpar_termo(texto_usuario)

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🔍 *Buscando ofertas de* `{termo_inteligente}`...", 
        parse_mode="Markdown"
    )
    
    produto = buscar_produto_vitrine(termo_inteligente)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    if produto:
        titulo = produto.get("title")
        preco = produto.get("price", 0)
        foto = produto.get("thumbnail", "").replace("-I.jpg", "-O.jpg")

        texto_compartilhamento = (
            f"🔥 **ACHADO EM DESTAQUE!**\n\n"
            f"📦 *{titulo}*\n"
            f"💰 Preço estimado: **R$ {preco:,.2f}**\n\n"
            f"👇 *Toque no botão abaixo para conferir na sua vitrine oficial com comissão garantida:*"
        )

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 VER NA VITRINE OFICIAL", url=LINK_VITRINE_SOCIAL)],
            [InlineKeyboardButton("✨ Acessar Vitrine Completa", url=LINK_VITRINE_SOCIAL)]
        ])

        if foto:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=foto,
                    caption=texto_compartilhamento,
                    reply_markup=teclado,
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass

        await context.bot.send_message(
            chat_id=chat_id,
            text=texto_compartilhamento,
            reply_markup=teclado,
            parse_mode="Markdown"
        )
        return

    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📦 **Ofertas de {termo_inteligente.title()}**\n\nAcesse o link abaixo para ver as opções em destaque na vitrine:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 ACESSAR VITRINE OFICIAL", url=LINK_VITRINE_SOCIAL)],
        ]),
        parse_mode="Markdown"
    )

def main():
    print("🧙‍♂️ Iniciando o Merlim Caçador de Ofertas...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim operando com sucesso!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
