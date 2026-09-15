import os
import sys
import re
from dotenv import load_dotenv
import requests
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# ==============================================================================
# CONFIGURAÇÃO E CHAVES (VARIÁVEIS DE AMBIENTE DO RAILWAY)
# ==============================================================================
print("🔄 Carregando variáveis de ambiente...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==============================================================================
# LINKS OFICIAIS DE AFILIADO DO MERCADO LIVRE (MELL.LA)
# ==============================================================================
LINK_VITRINE_SOCIAL = "https://meli.la/1FVqCEw"
LINK_SAMSUNG        = "https://meli.la/2gjHtvf"
LINK_CONSTRUCAO     = "https://meli.la/2Wy5ujN"
LINK_RELOGIOS       = "https://meli.la/2cyMfNN"
LINK_CALCADOS       = "https://meli.la/1sUVhQX"
LINK_ELETRONICOS    = "https://meli.la/1v7VNAK"
LINK_COZINHA        = "https://meli.la/2jU6k4f"
LINK_GAMES          = "https://meli.la/25w7Wsk"
LINK_INFORMATICA    = "https://meli.la/32JAaW3"
LINK_FERRAMENTAS    = "https://meli.la/33oTwjv"

ARQUIVO_USUARIOS = "usuarios.txt"

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY no Railway", flush=True)
    sys.exit(1)

client_groq = Groq(api_key=GROQ_API_KEY)

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

def limpar_termo(texto):
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    return ' '.join(texto_limpo.split()).strip()

# ==============================================================================
# GERENCIAMENTO INTELIGENTE DE USUÁRIOS
# ==============================================================================
def registrar_usuario(chat_id):
    chat_id_str = str(chat_id)
    usuarios = set()
    
    if os.path.exists(ARQUIVO_USUARIOS):
        with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
            for linha in f:
                uid = linha.strip()
                if uid:
                    usuarios.add(uid)
                    
    if chat_id_str not in usuarios:
        usuarios.add(chat_id_str)
        with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
            for uid in usuarios:
                f.write(f"{uid}\n")
                
    return len(usuarios)

# ==============================================================================
# PROCESSAMENTO INTELIGENTE VIA GROQ (LLAMA 3.3)
# ==============================================================================
def interpretar_com_ia(texto_usuario):
    prompt_sistema = (
        "Você é o Merlim, assistente de e-commerce e ofertas do Mercado Livre. "
        "Extraia APENAS o termo limpo do produto desejado para busca (ex: 'celular', 'furadeira', 'televisao'). "
        "Se for saudação ou conversa fiada, retorne 'CONVERSA'."
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

# ==============================================================================
# BUSCA DE PRODUTOS DIRETAMENTE NA API DO MERCADO LIVRE
# ==============================================================================
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

# ==============================================================================
# FLUXO PRINCIPAL DO TELEGRAM
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    registrar_usuario(chat_id)
    
    context.user_data.clear()
    banner_url = "https://i.ibb.co/pr5XpyL8/image-1789089291368.jpg"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **M E R L I M   D A S   O F E R T A S** 🌟\n\n"
        "✨ *Seu assistente inteligente de achados e promoções diárias!*\n\n"
        "🔍 Me diga o que você procura (*ex: celular, tênis, fone de ouvido*), e eu encontro o melhor preço e te entrego com o seu link de afiliado garantido!\n\n"
        "👇 **Para começarmos, digite o seu nome ou apelido abaixo:**"
    )

    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("✨ Acessar Vitrine Completa 🛍️", style="primary")]],
        resize_keyboard=True
    )

    try:
        await update.message.reply_photo(photo=banner_url, caption=legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")

async def estatisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = 0
    if os.path.exists(ARQUIVO_USUARIOS):
        with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
            total = sum(1 for linha in f if linha.strip())
            
    await update.message.reply_text(
        f"📊 **PAINEL DE ESTATÍSTICAS - MERLIM**\n\n👥 Total de usuários únicos cadastrados: **{total}** 🚀",
        parse_mode="Markdown"
    )

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    registrar_usuario(chat_id)
    texto_usuario = update.message.text.strip()

    # Tratamento da Vitrine Geral
    if "Vitrine Completa" in texto_usuario or "Vitrine" in texto_usuario:
        teclado_inline_vitrine = [
            [InlineKeyboardButton("✨ ACESSAR VITRINE COMPLETA NO SITE 🌐", url=LINK_VITRINE_SOCIAL)]
        ]
        await update.message.reply_text(
            "🛍️ **Vitrine Exclusiva do Merlim**\n\nClique abaixo para acessar todas as recomendações e ofertas especiais:",
            reply_markup=InlineKeyboardMarkup(teclado_inline_vitrine),
            parse_mode="Markdown"
        )
        return

    # Botão especial para Celulares em Oferta
    if "Celulares em Oferta" in texto_usuario or "Celulares" in texto_usuario:
        teclado_inline_samsung = [
            [InlineKeyboardButton("📱 VER CELULARES EM OFERTA ⚡", url=LINK_SAMSUNG)],
            [InlineKeyboardButton("✨ Acessar Vitrine Completa 🛍️", url=LINK_VITRINE_SOCIAL)]
        ]
        await update.message.reply_text(
            "📱 **Ofertas Exclusivas - Celulares & Smartphones**\n\nToque no botão abaixo para ver as melhores opções com seu link de afiliado garantido:",
            reply_markup=InlineKeyboardMarkup(teclado_inline_samsung),
            parse_mode="Markdown"
        )
        return

    # Etapa 1: Captura de Nome do Usuário
    if "nome" not in context.user_data:
        nome_limpo = limpar_termo(texto_usuario)
        if len(nome_limpo) < 2 or "Vitrine" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite o seu nome ou apelido válido para continuar:")
            return
        
        context.user_data["nome"] = nome_limpo
        
        # Teclado do rodapé estilizado com cor azul (primary) em cada botão
        teclado_opcoes = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Celulares em Oferta", style="primary"), KeyboardButton("⚡ Ferramentas", style="primary")],
                [KeyboardButton("💻 Informática", style="primary"), KeyboardButton("🏠 Casa e Cozinha", style="primary")],
                [KeyboardButton("🎮 Games", style="primary"), KeyboardButton("📺 Eletrônicos", style="primary")],
                [KeyboardButton("👟 Calçados", style="primary"), KeyboardButton("⌚ Relógios", style="primary")],
                [KeyboardButton("🔧 Construção", style="primary"), KeyboardButton("✨ Acessar Vitrine Completa 🛍️", style="primary")]
            ],
            resize_keyboard=True
        )

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_limpo}!** 🧙‍♂️\n\nEscolha uma categoria abaixo ou digite qualquer produto que você deseja buscar:",
            reply_markup=teclado_opcoes,
            parse_mode="Markdown"
        )
        return

    # Identificação e direcionamento inteligente por categoria do teclado
    link_destino = LINK_VITRINE_SOCIAL

    if "Ferramenta" in texto_usuario:
        texto_usuario = "ferramenta"
        link_destino = LINK_FERRAMENTAS
    elif "Informática" in texto_usuario:
        texto_usuario = "informatica"
        link_destino = LINK_INFORMATICA
    elif "Casa" in texto_usuario:
        texto_usuario = "casa"
        link_destino = LINK_COZINHA
    elif "Game" in texto_usuario:
        texto_usuario = "games"
        link_destino = LINK_GAMES
    elif "Eletrônico" in texto_usuario:
        texto_usuario = "eletronicos"
        link_destino = LINK_ELETRONICOS
    elif "Calçado" in texto_usuario:
        texto_usuario = "calcados"
        link_destino = LINK_CALCADOS
    elif "Relógio" in texto_usuario:
        texto_usuario = "relogios"
        link_destino = LINK_RELOGIOS
    elif "Construção" in texto_usuario:
        texto_usuario = "construcao"
        link_destino = LINK_CONSTRUCAO

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    termo_inteligente = interpretar_com_ia(texto_usuario)
    if termo_inteligente == "CONVERSA" or not termo_inteligente:
        termo_inteligente = limpar_termo(texto_usuario)

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🔍 *Buscando as melhores ofertas de* `{termo_inteligente}`...", 
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
            f"🔥 **ACHADO EM DESTAQUE!** ⚡\n\n"
            f"📦 *{titulo}*\n"
            f"💰 Preço estimado: **R$ {preco:,.2f}**\n\n"
            f"👇 *Toque no botão abaixo para conferir na vitrine com comissão garantida:*"
        )

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 VER NA VITRINE OFICIAL 🚀", url=link_destino)],
            [InlineKeyboardButton("✨ Acessar Vitrine Completa 🛍️", url=LINK_VITRINE_SOCIAL)]
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
            [InlineKeyboardButton("🔗 ACESSAR VITRINE OFICIAL 🚀", url=link_destino)],
        ]),
        parse_mode="Markdown"
    )

def main():
    print("🧙‍♂️ Iniciando o Merlim Caçador de Ofertas...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", estatisticas))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim operando com sucesso!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
