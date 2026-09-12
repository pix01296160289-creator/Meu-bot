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

# Link de fallback oficial da sua vitrine para os botões do menu
LINK_VITRINE_SOCIAL = "https://www.mercadolivre.com.br/social/fe20250121204050?matt_word=fe20250121204050&matt_tool=72221096&forceInApp=true&ref=BCHCIAky81FsdxQcfbha%2BxMSne6JjpPAkNIDQyptcnf%2BMvfa04OUixCLqRcuFbYvVdd830SIgt7tPGzIzEwcK1t2RUFPtJp2Z6NIsiltU3EhyHO2oBorwOkw0cievtRZijNuMRQADZwieK8as%2F2GHDB2F1l9EuWKBhXJjTNnJYMRClM7y4PxPtJN03wKYNGnzRWjVLfVGaPHSSVvaVjLuh9fRn2eZULxaqINKZfR24VLgZbK#origin=whatsapp"

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY no arquivo .env ou no Railway", flush=True)
    sys.exit(1)

# Inicializa o cliente da Groq (IA)
client_groq = Groq(api_key=GROQ_API_KEY)

# =========================
# BANCO DE DADOS DE BOTÕES
# =========================
MEUS_BOTOES_FUTUROS = [
    {"texto": "⚡ Parafusadeira em oferta", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🛠️ Esmerilhadeira Angular", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🔨 Furadeira de Impacto", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🪚 Serra Circular", "url": LINK_VITRINE_SOCIAL},
    {"texto": "📐 Trena a Laser", "url": LINK_VITRINE_SOCIAL},
]

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# GERADOR DE LINK COM COMISSÃO (TOOL)
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    url_limpa = re.sub(r'([?&])matt_tool=[^&]+', '', url_produto)
    separador = "&" if "?" in url_limpa else "?"
    return f"{url_limpa}{separador}matt_tool={AFFILIATE_ID}"

# =========================
# EXTRAIR ITEM ID DE UM LINK DO MERCADO LIVRE
# =========================
def extrair_item_id_do_link(url):
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
# INTELIGÊNCIA ARTIFICIAL (GROQ) PARA ENTENDER O PEDIDO
# =========================
def interpretar_com_ia(texto_usuario):
    prompt_sistema = (
        "Você é o Merlim, um assistente de e-commerce e buscas no Mercado Livre. "
        "O usuário vai digitar o nome de um produto ou modelo exato (ex: 'celular Samsung A07', 'furadeira bosch'). "
        "Sua tarefa é extrair e retornar o termo exato limpo para pesquisa na API do Mercado Livre, mantendo marcas e modelos. "
        "Não adicione pontuação extra. Se for saudação, retorne 'CONVERSA'."
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
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro na API da Groq: {e}")
        return texto_usuario

# =========================
# BUSCA DIRETÁRIA NO CATÁLOGO DO MERCADO LIVRE
# =========================
def buscar_no_catalogo_mercadolivre(termo):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo)}&limit=10"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            dados = response.json()
            resultados = dados.get("results", [])
            
            # Se não achar nada com o termo completo, tenta buscar pelas duas primeiras palavras
            if not resultados and " " in termo:
                termo_curto = " ".join(termo.split()[:2])
                url_fallback = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_curto)}&limit=10"
                resp_fallback = requests.get(url_fallback, headers=headers, timeout=10)
                if resp_fallback.status_code == 200:
                    resultados = resp_fallback.json().get("results", [])

            if resultados:
                # Ordena os produtos do menor preço para o maior preço no catálogo do Mercado Livre
                resultados_ordenados = sorted(resultados, key=lambda x: float(x.get("price", 0)))
                return resultados_ordenados[0] # Retorna o produto exato mais barato encontrado
    except Exception as e:
        print(f"Erro ao buscar no catálogo do ML: {e}")
    return None

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    banner_url = "https://i.ibb.co/pr5XpyL8/image-1789089291368.jpg"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS** | *Seu Assistente Inteligente*\n\n"
        "Seja muito bem-vindo! Digite o nome de **qualquer produto ou modelo** (ex: *celular Samsung A07*) que eu entro no catálogo do Mercado Livre, acho o produto e te mando o link direto!\n\n"
        "👉 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("🔥 Ver Ofertas do Dia"), KeyboardButton("✨ Parafusadeira em oferta")],
         [KeyboardButton("🛠️ Mais Vendidos / Ferramentas")]],
        resize_keyboard=True
    )

    try:
        await update.message.reply_photo(photo=banner_url, caption=legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    if "Mais Vendidos" in texto_usuario or "Ferramentas" in texto_usuario:
        teclado_lista = []
        for item in MEUS_BOTOES_FUTUROS:
            teclado_lista.append([InlineKeyboardButton(item["texto"], url=item["url"])])
        teclado_lista.append([InlineKeyboardButton("✨ ACESSAR VITRINE COMPLETA NO SITE", url=LINK_VITRINE_SOCIAL)])

        await update.message.reply_text(
            "🛠️ **Mais Vendidos e Ferramentas em Destaque**\n\nEscolha abaixo o equipamento ou ferramenta que você procura:",
            reply_markup=InlineKeyboardMarkup(teclado_lista),
            parse_mode="Markdown"
        )
        return

    # Captura o nome se ainda não estiver definido
    if "nome" not in context.user_data:
        if len(texto_usuario) < 2 or "Ofertas" in texto_usuario or "Celular" in texto_usuario or "Ferramentas" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite o seu nome ou apelido primeiro para continuarmos:")
            return
        
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_usuario}!**\n\nAgora digite o nome do produto exato (ex: celular Samsung A07) que eu busco no catálogo do Mercado Livre e te entrego o link com comissão!\n\n**O que você procura agora?**:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Celular"), KeyboardButton("👟 Tênis"), KeyboardButton("💻 Notebook")],
                 [KeyboardButton("🛠️ Mais Vendidos / Ferramentas"), KeyboardButton("✨ Parafusadeira em oferta")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    # Se mandarem link direto do Mercado Livre
    if "mercadolivre.com" in texto_usuario or "mercadolivre.com.br" in texto_usuario or "ml.com" in texto_usuario:
        msg_aguarde = await context.bot.send_message(chat_id=chat_id, text="🧙‍♂️ *Merlim transformando seu link em card de afiliado...*", parse_mode="Markdown")
        dados_prod = buscar_produto_por_link(texto_usuario)
        link_afiliado_pronto = gerar_link_afiliado(texto_usuario)
        
        titulo_card = "Produto do Mercado Livre"
        foto_card = ""
        if dados_prod:
            titulo_card = dados_prod.get("title", titulo_card)
            pics = dados_prod.get("pictures", [])
            if pics:
                foto_card = pics[0].get("secure_url", pics[0].get("url", ""))
        
        legenda_card = f"*{titulo_card}*\n\n🛒 Garanta o seu com segurança através do link abaixo:"
        teclado_card = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Ver Produto e Comprar", url=link_afiliado_pronto)]])

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
        except Exception:
            pass

        if foto_card:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=foto_card, caption=legenda_card, reply_markup=teclado_card, parse_mode="Markdown")
                return
            except Exception:
                pass
        
        await context.bot.send_message(chat_id=chat_id, text=legenda_card, reply_markup=teclado_card, parse_mode="Markdown")
        return

    # Atalhos rápidos de botões
    if texto_usuario == "📱 Celular":
        termo_busca = "celular smartphone"
    elif texto_usuario == "👟 Tênis":
        termo_busca = "tenis masculino"
    elif texto_usuario == "💻 Notebook":
        termo_busca = "notebook"
    else:
        termo_busca = interpretar_com_ia(texto_usuario)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    msg_aguarde = await context.bot.send_message(chat_id=chat_id, text=f"🧙‍♂️ *Merlim entrando no catálogo do Mercado Livre para buscar:* `{termo_busca}`...", parse_mode="Markdown")

    # BUSCA DIRETAMENTE NO CATÁLOGO DO MERCADO LIVRE
    produto_escolhido = buscar_no_catalogo_mercadolivre(termo_busca)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    if produto_escolhido:
        titulo = produto_escolhido.get("title")
        preco = produto_escolhido.get("price", 0)
        link_original = produto_escolhido.get("permalink") # Link exato do produto no Mercado Livre
        
        # INJEÇÃO AUTOMÁTICA DO SEU CÓDIGO DE AFILIADO TOOL
        link_com_comissao = gerar_link_afiliado(link_original)
        
        foto = produto_escolhido.get("thumbnail", "").replace("-I.jpg", "-O.jpg")

        texto_card = (
            f"🏆 **PRODUTO ENCONTRADO NO MERCADO LIVRE!**\n\n"
            f"🛒 *{titulo}*\n"
            f"🟢 **Preço:** R$ {preco:,.2f}\n\n"
            f"Clique no botão abaixo para ver o produto oficial e comprar:"
        )

        teclado_produto = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Ver Produto Exato e Comprar", url=link_com_comissao)],
            [InlineKeyboardButton("✨ Ver Mais Opções na Vitrine", url=LINK_VITRINE_SOCIAL)]
        ])

        if foto:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=foto, caption=texto_card, reply_markup=teclado_produto, parse_mode="Markdown")
                return
            except Exception:
                pass

        await context.bot.send_message(chat_id=chat_id, text=texto_card, reply_markup=teclado_produto, parse_mode="Markdown")
        return

    # Caso não ache nada, manda para a vitrine geral de backup
    teclado_fallback = [[InlineKeyboardButton("✨ Acessar Vitrine de Ofertas", url=LINK_VITRINE_SOCIAL)]]
    await context.bot.send_message(chat_id=chat_id, text=f"📦 Não encontrei um anúncio ativo para `{termo_busca}` neste segundo, mas você pode conferir as opções na vitrine:", reply_markup=InlineKeyboardMarkup(teclado_fallback), parse_mode="Markdown")

# =========================
# MAIN
# =========================
def main():
    print("🧙‍♂️ Iniciando o Merlim com Busca Direta no Catálogo do Mercado Livre...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim 100% operacional!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
