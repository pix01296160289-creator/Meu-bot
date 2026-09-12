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

# Link oficial da sua Vitrine Social (usado para os botões do catálogo)
LINK_VITRINE_SOCIAL = "https://www.mercadolivre.com.br/social/fe20250121204050?matt_word=fe20250121204050&matt_tool=72221096&forceInApp=true&ref=BCHCIAky81FsdxQcfbha%2BxMSne6JjpPAkNIDQyptcnf%2BMvfa04OUixCLqRcuFbYvVdd830SIgt7tPGzIzEwcK1t2RUFPtJp2Z6NIsiltU3EhyHO2oBorwOkw0cievtRZijNuMRQADZwieK8as%2F2GHDB2F1l9EuWKBhXJjTNnJYMRClM7y4PxPtJN03wKYNGnzRWjVLfVGaPHSSVvaVjLuh9fRn2eZULxaqINKZfR24VLgZbK#origin=whatsapp"

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY no arquivo .env ou no Railway", flush=True)
    sys.exit(1)

# Inicializa o cliente da Groq (IA)
client_groq = Groq(api_key=GROQ_API_KEY)

# =========================
# BANCO DE DADOS DE BOTÕES (MAIS VENDIDOS E FERRAMENTAS)
# =========================
MEUS_BOTOES_FUTUROS = [
    {"texto": "⚡ Parafusadeira em oferta", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🛠️ Esmerilhadeira Angular", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🔨 Furadeira de Impacto", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🪚 Serra Circular", "url": LINK_VITRINE_SOCIAL},
    {"texto": "📐 Trena a Laser", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🧰 Maleta de Ferramentas Completa", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🪛 Jogo de Chaves e Brocas", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🪵 Lixadeira Orbital", "url": LINK_VITRINE_SOCIAL},
    {"texto": "⚙️ Serra Tico-Tico", "url": LINK_VITRINE_SOCIAL},
    {"texto": "🔌 Politriz / Lixadeira Automotiva", "url": LINK_VITRINE_SOCIAL},
]

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
# INTELIGÊNCIA ARTIFICIAL (GROQ)
# =========================
def interpretar_com_ia(texto_usuario):
    prompt_sistema = (
        "Você é o Merlim, um assistente de inteligência artificial especialista em e-commerce e busca de produtos no Mercado Livre. "
        "O usuário vai digitar o nome de um produto ou modelo (ex: 'celular Samsung A07', 'furadeira de impacto bosch'). "
        "Sua tarefa é extrair e retornar o termo de busca exato e otimizado para o Mercado Livre. "
        "Não remova marcas ou modelos importantes (como Samsung A07). Retorne apenas o termo limpo para pesquisa, sem pontuação extra. "
        "Se o usuário disser apenas 'oi', 'olá' ou saudações, retorne apenas 'CONVERSA'."
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
# BUSCA DE PRODUTOS NO MERCADO LIVRE (COM MENOR PREÇO)
# =========================
def buscar_produtos_mercadolivre(termo_busca):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        # Faz a busca na API do Mercado Livre
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_busca)}&limit=10"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            resultados = response.json().get("results", [])
            if resultados:
                # Organiza os produtos encontrados do menor preço para o maior preço automaticamente!
                resultados_ordenados = sorted(resultados, key=lambda x: x.get("price", 0))
                return resultados_ordenados
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
        "Seja muito bem-vindo! Digite o nome de **qualquer produto ou modelo** (ex: *celular Samsung A07*, *parafusadeira*) que eu entro no Mercado Livre e acho o menor preço para você.\n\n"
        "👉 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("🔥 Ver Ofertas do Dia"), KeyboardButton("✨ Parafusadeira em oferta")],
         [KeyboardButton("🛠️ Mais Vendidos / Ferramentas")]],
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

    # Botão para exibir a lista com os mais vendidos e ferramentas
    if "Mais Vendidos" in texto_usuario or "Ferramentas" in texto_usuario:
        teclado_lista = []
        for item in MEUS_BOTOES_FUTUROS:
            teclado_lista.append([InlineKeyboardButton(item["texto"], url=item["url"])])
        
        teclado_lista.append([InlineKeyboardButton("✨ ACESSAR VITRINE COMPLETA NO SITE", url=LINK_VITRINE_SOCIAL)])

        await update.message.reply_text(
            "🛠️ **Mais Vendidos e Ferramentas em Destaque**\n\n"
            "Escolha abaixo o equipamento ou ferramenta que você procura:",
            reply_markup=InlineKeyboardMarkup(teclado_lista),
            parse_mode="Markdown"
        )
        return

    if "Parafusadeira" in texto_usuario and len(texto_usuario) < 30:
        teclado_inline_vitrine = [
            [InlineKeyboardButton("✨ ACESSAR VITRINE COMPLETA NO SITE", url=LINK_VITRINE_SOCIAL)],
            [InlineKeyboardButton("🔥 VER PRODUTOS EM DESTAQUE", url=LINK_VITRINE_SOCIAL)]
        ]
        await update.message.reply_text(
            "🛍️ **Parafusadeira em oferta**\n\n"
            "Tire proveito de todas as ofertas selecionadas na minha página oficial. "
            "Clique no botão abaixo para abrir a vitrine completa:",
            reply_markup=InlineKeyboardMarkup(teclado_inline_vitrine),
            parse_mode="Markdown"
        )
        return

    # Captura o nome se ainda não estiver definido
    if "nome" not in context.user_data:
        if len(texto_usuario) < 2 or "Ofertas" in texto_usuario or "Celular" in texto_usuario or "Tênis" in texto_usuario or "Ferramentas" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite o seu nome ou apelido primeiro para continuarmos:")
            return
        
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_usuario}!**\n\nAgora você pode digitar o nome de **qualquer produto ou modelo** (ex: celular Samsung A07, tênis Nike, furadeira) que eu busco a melhor oferta com o seu código de afiliado!\n\n**O que você deseja buscar agora?**:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Celular"), KeyboardButton("👟 Tênis"), KeyboardButton("💻 Notebook")],
                 [KeyboardButton("🛠️ Mais Vendidos / Ferramentas"), KeyboardButton("✨ Parafusadeira em oferta")]],
                resize_keyboard=True
            ),
            parse_mode="Markdown"
        )
        return

    # SE O USUÁRIO MANDAR UM LINK DO MERCADO LIVRE DIRETO
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
        
        legenda_card = (
            f"*{titulo_card}*\n\n"
            f"🛒 Garanta o seu com segurança através do link abaixo:"
        )
        
        teclado_card = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Ver Produto e Comprar", url=link_afiliado_pronto)]
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
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=legenda_card,
            reply_markup=teclado_card,
            parse_mode="Markdown"
        )
        return

    # Atalhos rápidos dos botões do menu
    if texto_usuario == "📱 Celular":
        texto_usuario = "celular smartphone"
    elif texto_usuario == "👟 Tênis":
        texto_usuario = "tenis masculino"
    elif texto_usuario == "💻 Notebook":
        texto_usuario = "notebook"

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # IA interpreta o pedido do usuário
    termo_inteligente = interpretar_com_ia(texto_usuario)
    if termo_inteligente == "CONVERSA" or not termo_inteligente:
        termo_inteligente = texto_usuario

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🧙‍♂️ *Merlim (IA) buscando o menor preço para:* `{termo_inteligente}`...", 
        parse_mode="Markdown"
    )
    
    # BUSCA OS PRODUTOS REAIS NO MERCADO LIVRE E ORDENA PELO MENOR PREÇO
    produtos = buscar_produtos_mercadolivre(termo_inteligente)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    if produtos:
        # Pega o primeiro produto (que agora é garantido ser o de menor preço da lista ordenada)
        melhor_oferta = produtos[0]
        titulo = melhor_oferta.get("title")
        preco_atual = melhor_oferta.get("price", 0)
        link_original_produto = melhor_oferta.get("permalink")
        
        # Converte o link adicionando o seu ID de afiliado tool
        link_afiliado_produto = gerar_link_afiliado(link_original_produto)

        foto_url = melhor_oferta.get("thumbnail", "")
        if foto_url:
            foto_url = foto_url.replace("-I.jpg", "-O.jpg")

        texto_oferta = (
            f"🏆 **MENOR PREÇO ENCONTRADO!**\n\n"
            f"🛒 *{titulo}*\n"
            f"🟢 **Preço:** R$ {preco_atual:,.2f}\n\n"
            f"Clique no botão abaixo para garantir sua oferta com segurança:"
        )

        teclado_produto_especifico = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Ver Oferta e Comprar", url=link_afiliado_produto)],
            [InlineKeyboardButton("✨ Ver Vitrine Completa", url=LINK_VITRINE_SOCIAL)]
        ])

        if foto_url:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=foto_url,
                    caption=texto_oferta,
                    reply_markup=teclado_produto_especifico,
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass

        await context.bot.send_message(
            chat_id=chat_id,
            text=texto_oferta,
            reply_markup=teclado_produto_especifico,
            parse_mode="Markdown"
        )
        return

    # Caso não ache nenhum produto
    teclado_fallback = [
        [InlineKeyboardButton("✨ Acessar Vitrine de Ofertas", url=LINK_VITRINE_SOCIAL)]
    ]
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📦 Não encontrei resultados para `{termo_inteligente}` no momento, mas você pode conferir as melhores opções na minha vitrine:", 
        reply_markup=InlineKeyboardMarkup(teclado_fallback), 
        parse_mode="Markdown"
    )

# =========================
# MAIN
# =========================
def main():
    print("🧙‍♂️ Iniciando o Merlim com IA e Menor Preço Automático...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim 100% operacional com inteligência de busca!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
