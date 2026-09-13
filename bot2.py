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
AFFILIATE_ID = os.getenv("AFFILIATE_ID", "72221096") # Seu código Matt Tool configurado

# Link da sua vitrine social de backup/geral
LINK_VITRINE_SOCIAL = "https://www.mercadolivre.com.br/social/fe20250121204050?matt_word=fe20250121204050&matt_tool=72221096&forceInApp=true&ref=BOjxjRP0JfIdxgeD6HICroH6V3KT5oSzPmxPAfx%2FcXkUiqE9JAgL38r3CvjMjfk6qEKST%2BPRODeLqjdF%2F%2Bp2o670f%2BFkU7UrCz8YgPkWed1zCp7rXiUzZ0AvRD3Fh%2Fpp0d9Xaz%2BB7ghvvzVHs7bpuv4MAymDzj3m0y%2FsTYbrixIXDIxivYq2u%2FAG36FmjHPBX9AEjNsZ0q8mRMXLUiti3LORlQnP9PIIj2ETFoUB2q0%3D#origin=whatsapp"

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY no Railway", flush=True)
    sys.exit(1)

client_groq = Groq(api_key=GROQ_API_KEY)

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# GERADOR DE LINK COM MATT_TOOL
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    separador = "&" if "?" in url_produto else "?"
    return f"{url_produto}{separador}matt_tool={AFFILIATE_ID}"

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
# BUSCA O PRIMEIRO PRODUTO DA VITRINE (BLINDADA)
# =========================
def buscar_primeiro_produto(termo_busca):
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
        
        print(f"📡 Status da API do ML para '{termo_tratado}': {response.status_code}", flush=True)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            if resultados:
                return resultados[0] # Pega exatamente o primeiro produto da vitrine/busca
        else:
            print(f"⚠️ Erro ML Status {response.status_code}: {response.text}", flush=True)
            
    except Exception as e:
        print(f"❌ Erro crítico na requisição da API: {e}", flush=True)
    return None

# =========================
# COMANDOS E FLUXO DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    banner_url = "https://i.ibb.co/pr5XpyL8/image-1789089291368.jpg"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS**\n\n"
        "Me diga o que você procura (ex: *celular*, *furadeira*, *tênis*), eu entro na vitrine do Mercado Livre, pego o primeiro produto em destaque e te entrego com o seu link de afiliado pronto!\n\n"
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
            text=f"✨ **Tudo pronto, {nome_limpo}!**\n\nAgora digite o que você quer buscar (Ex: *celular*, *furadeira*). Vou vasculhar a vitrine e te mandar o link direto do primeiro produto com comissão ativa!",
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
        text=f"🔍 *Vasculhando a vitrine do Mercado Livre para:* `{termo_inteligente}`...", 
        parse_mode="Markdown"
    )
    
    # O bot busca o produto e entra na página do primeiro item da vitrine
    produto = buscar_primeiro_produto(termo_inteligente)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    if produto:
        titulo = produto.get("title")
        preco = produto.get("price", 0)
        link_original = produto.get("permalink", "") # Link exato da página do produto escolhido
        foto = produto.get("thumbnail", "").replace("-I.jpg", "-O.jpg") # Foto em alta qualidade
        
        # Insere o seu matt_tool de afiliado no link do produto
        link_com_comissao = gerar_link_afiliado(link_original)

        texto_compartilhamento = (
            f"🔥 **ACHADO EM DESTAQUE NA VITRINE!**\n\n"
            f"📦 *{titulo}*\n"
            f"💰 Preço: **R$ {preco:,.2f}**\n\n"
            f"👇 *Toque no botão abaixo para ver a página do produto e garantir sua comissão:*"
        )

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 ACESSAR PÁGINA DO PRODUTO", url=link_com_comissao)],
            [InlineKeyboardButton("✨ Ver Mais na Vitrine", url=LINK_VITRINE_SOCIAL)]
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

    # Fallback caso ocorra qualquer instabilidade na API
    link_fallback = gerar_link_afiliado(f"https://lista.mercadolivre.com.br/{requests.utils.quote(termo_inteligente)}")
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📦 **Ofertas de {termo_inteligente.title()}**\n\nAcesse o link abaixo para ver as opções em destaque:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 VER LISTA DE OFERTAS", url=link_fallback)],
            [InlineKeyboardButton("✨ MINHA VITRINE SOCIAL", url=LINK_VITRINE_SOCIAL)]
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
