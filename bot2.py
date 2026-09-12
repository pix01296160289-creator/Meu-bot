import os
import sys
import re
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
AFFILIATE_ID = "fe20250121204050"

# Link da sua Vitrine Social oficial do Mercado Livre
LINK_VITRINE_SOCIAL = "https://www.mercadolivre.com.br/social/boletandoofertas?matt_word=diogenes&matt_tool=fe20250121204050&forceInApp=true&ref=BAFmMTXO%2BxWa3NkkmM5w2bxYG1TSxTTbK5V8JaMwh3kwo6xtphbzD16CmPon1AVWSRl0d%2B4xSl8Z5YfGJqCekVhZrEiwhhn0q6lO2AyXaHFG5Y57oWKdQ%2FUi53SzE9J%2BzpO51RD9i0MrBMwG%2FMhmXijlhrZ3MIS%2BPucSDNcbhqhx%2F5AWZfZ9M%2FRwkMz9it%2FfQX3%2FK%2BzOTqdJqKHfcg%3D%3D"

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
# GERADOR DE LINK COM COMISSÃO
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    # Remove parâmetros matt_tool antigos se houver para evitar conflito
    url_limpa = re.sub(r'([?&])matt_tool=[^&]+', '', url_produto)
    separador = "&" if "?" in url_limpa else "?"
    return f"{url_limpa}{separador}matt_tool={AFFILIATE_ID}"

# =========================
# LIMPEZA DE TEXTO
# =========================
def limpar_termo(texto):
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    return ' '.join(texto_limpo.split()).strip()

# =========================
# EXTRAIR ITEM ID DE UM LINK DO MERCADO LIVRE
# =========================
def extrair_item_id_do_link(url):
    # Procura por padrões como MLB-123456789 ou MLB123456789 na URL
    match = re.search(r'MLB-?(\d+)', url)
    if match:
        return f"MLB{match.group(1)}"
    return None

# =========================
# BUSCAR DETALHES DO PRODUTO PELA API DO ML VIA LINK
# =========================
def buscar_produto_por_link(url_produto):
    item_id = extrair_item_id_do_link(url_produto)
    if not item_id:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        url = f"https://api.mercadolibre.com/items/{item_id}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Erro ao buscar produto por ID na API ML: {e}")
    return None

# =========================
# INTELIGÊNCIA ARTIFICIAL (GROQ)
# =========================
def interpretar_com_ia(texto_usuario):
    prompt_sistema = (
        "Você é o Merlim, um assistente de inteligência artificial especialista em e-commerce e caça a ofertas no Mercado Livre. "
        "O usuário vai digitar algo para você. Sua tarefa é analisar o texto e extrair APENAS o nome limpo do produto ou termo principal "
        "que ele deseja buscar (ex: se ele disser 'preciso de uma parafusadeira boa', você retorna apenas 'parafusadeira'). "
        "Se o usuário disser 'oi', 'olá', 'bom dia' ou outra saudação sem pedir produto, responda apenas 'CONVERSA'."
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
        return limpar_termo(resposta)
    except Exception as e:
        print(f"Erro na API da Groq: {e}")
        return limpar_termo(texto_usuario)

# =========================
# BUSCA DE PRODUTOS NO MERCADO LIVRE
# =========================
def buscar_produtos_mercadolivre(termo_busca):
    termo_tratado = limpar_termo(termo_busca)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_tratado)}&limit=5"
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
    
    banner_url = "https://i.ibb.co/pr5XpyL8/image-1789089291368.jpg"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS** | *Seu Assistente Inteligente*\n\n"
        "Seja muito bem-vindo! Agora sou impulsionado por Inteligência Artificial e trago as melhores ofertas do Mercado Livre para você.\n\n"
        "👉 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("🔥 Ver Ofertas do Dia"), KeyboardButton("✨ Minha Vitrine de Ofertas")]],
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

    # Tratamento para o botão da Vitrine Social
    if "Vitrine" in texto_usuario:
        teclado_inline_vitrine = [
            [InlineKeyboardButton("✨ ACESSAR VITRINE COMPLETA NO SITE", url=LINK_VITRINE_SOCIAL)],
            [InlineKeyboardButton("🔥 VER PRODUTOS EM DESTAQUE", url=LINK_VITRINE_SOCIAL)]
        ]
        await update.message.reply_text(
            "🛍️ **Vitrine Exclusiva do Merlim**\n\n"
            "Tire proveito de todas as ofertas selecionadas na minha página oficial. "
            "Clique no botão abaixo para abrir a vitrine completa:",
            reply_markup=InlineKeyboardMarkup(teclado_inline_vitrine),
            parse_mode="Markdown"
        )
        return

    # Captura o nome se ainda não estiver definido
    if "nome" not in context.user_data:
        nome_limpo = limpar_termo(texto_usuario)
        if len(nome_limpo) < 2 or "Ofertas" in texto_usuario or "Vitrine" in texto_usuario or "Celular" in texto_usuario or "Tênis" in texto_usuario or "Notebook" in texto_usuario or "Ferramentas" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite o seu nome ou apelido primeiro para continuarmos:")
            return
        
        context.user_data["nome"] = nome_limpo
        nome_usuario = context.user_data["nome"]

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_usuario}!**\n\nAgora você pode conversar comigo, usar os botões ou **enviar qualquer link de produto do Mercado Livre** para gerar o card com o seu código de afiliado!\n\n**O que você deseja fazer?**:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Celular"), KeyboardButton("👟 Tênis"), KeyboardButton("💻 Notebook")],
                 [KeyboardButton("⚡ Ferramentas"), KeyboardButton("✨ Minha Vitrine de Ofertas")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    # SE O USUÁRIO MANDAR UM LINK DO MERCADO LIVRE
    if "mercadolivre.com" in texto_usuario or "mercadolivre.com.br" in texto_usuario or "ml.com" in texto_usuario:
        msg_aguarde = await context.bot.send_message(chat_id=chat_id, text="🧙‍♂️ *Merlim transformando seu link em card de afiliado...*", parse_mode="Markdown")
        
        dados_prod = buscar_produto_por_link(texto_usuario)
        link_afiliado_pronto = gerar_link_afiliado(texto_usuario)
        
        titulo_card = "Produto Selecionado no Mercado Livre"
        foto_card = ""
        
        if dados_prod:
            titulo_card = dados_prod.get("title", titulo_card)
            pics = dados_prod.get("pictures", [])
            if pics:
                foto_card = pics[0].get("secure_url", pics[0].get("url", ""))
        
        legenda_card = (
            f"*{titulo_card}*\n\n"
            f"Visite a página e encontre todos os produtos de {AFFILIATE_ID} em um só lugar."
        )
        
        teclado_card = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Ver Produto e Ofertas", url=link_afiliado_pronto)]
        ])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
        except Exception:
            pass

        if foto_card:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=foto_card,
                    caption=legenda_card,
                    reply_markup=teclado_card,
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass
        
        # Caso não consiga a foto, envia em texto com o botão
        await context.bot.send_message(
            chat_id=chat_id,
            text=legenda_card,
            reply_markup=teclado_card,
            parse_mode="Markdown"
        )
        return

    # Atalhos rápidos dos botões do menu
    if "Celular" in texto_usuario:
        texto_usuario = "celular"
    elif "Tênis" in texto_usuario:
        texto_usuario = "tenis"
    elif "Notebook" in texto_usuario:
        texto_usuario = "notebook"
    elif "Ferramentas" in texto_usuario:
        texto_usuario = "ferramentas"
    elif "Ofertas" in texto_usuario:
        texto_usuario = "ofertas imperdíveis"

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    termo_inteligente = interpretar_com_ia(texto_usuario)
    
    if termo_inteligente == "CONVERSA" or not termo_inteligente:
        termo_inteligente = limpar_termo(texto_usuario)

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🧙‍♂️ *Merlim (IA) analisando e garimpando:* `{termo_inteligente}`...", 
        parse_mode="Markdown"
    )
    
    produtos = buscar_produtos_mercadolivre(termo_inteligente)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    teclado = [
        [InlineKeyboardButton("🔗 VER BUSCA NA LISTA GERAL", url=gerar_link_afiliado(f"https://lista.mercadolivre.com.br/{requests.utils.quote(termo_inteligente)}"))],
        [InlineKeyboardButton("✨ EXPLORAR MINHA VITRINE SOCIAL", url=LINK_VITRINE_SOCIAL)]
    ]

    if produtos:
        primeiro_produto = produtos[0]
        titulo = primeiro_produto.get("title")
        preco_atual = primeiro_produto.get("price", 0)
        
        foto_url = primeiro_produto.get("thumbnail", "")
        if foto_url:
            foto_url = foto_url.replace("-I.jpg", "-O.jpg")

        texto_oferta = (
            f"🏆 **IA ENCONTROU A MELHOR OFERTA!**\n\n"
            f"🛒 *{titulo}*\n"
            f"🟢 **Menor preço:** R$ {preco_atual:,.2f}\n\n"
            f"Visite a página e encontre todos os produtos de {AFFILIATE_ID} em um só lugar."
        )

        if foto_url:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=foto_url,
                    caption=texto_oferta,
                    reply_markup=InlineKeyboardMarkup(teclado),
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass

    texto_catalogo = (
        f"📦 **Catálogo Completo: {termo_inteligente.title()}**\n\n"
        f"Olá, {nome_usuario}! Usei minha inteligência para buscar as melhores opções no Mercado Livre.\n\n"
        f"Visite a página e encontre todos os produtos de {AFFILIATE_ID} em um só lugar."
    )
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=texto_catalogo, 
        reply_markup=InlineKeyboardMarkup(teclado), 
        parse_mode="Markdown"
    )

# =========================
# MAIN
# =========================
def main():
    print("🧙‍♂️ Iniciando o Merlim com Conversor de Links e Vitrine Social...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim 100% operacional!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
