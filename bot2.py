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
# PROCESSAMENTO INTELIGENTE VIA GROQ (LLAMA 3.3) - CATEGORIZAÇÃO AUTOMÁTICA
# ==============================================================================
def interpretar_com_ia(texto_usuario):
    prompt_sistema = (
        "Você é o assistente inteligente do Merlim. "
        "Analise o texto do usuário e responda estritamente separado por vírgula com dois dados: "
        "1. O termo limpo para busca do produto. "
        "2. A categoria mais adequada entre: 'celulares', 'ferramentas', 'informatica', 'cozinha', 'games', 'eletronicos', 'calcados', 'relogios', 'construcao' ou 'geral'. "
        "Exemplo para 'batedeira': batedeira, cozinha"
    )
    try:
        chat_completion = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": texto_usuario}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=40
        )
        resposta = chat_completion.choices[0].message.content.strip()
        return resposta
    except Exception as e:
        print(f"Erro na API da Groq: {e}")
        return f"{limpar_termo(texto_usuario)}, geral"

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
        "🔍 Me diga o que você procura (*ex: celular, tênis, fone de ouvido*), e eu encontro o melhor preço e te entrego com o seu link de afiliado garantido!"
    )

    teclado_menu = ReplyKeyboardMarkup(
        [[KeyboardButton("✨ Acessar Vitrine Completa 🛍️")]],
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

    # Etapa 1: Captura de Nome do Usuário
    if "nome" not in context.user_data:
        nome_limpo = limpar_termo(texto_usuario)
        if len(nome_limpo) < 2 or "Vitrine" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite o seu nome ou apelido válido para continuar:")
            return
        
        context.user_data["nome"] = nome_limpo
        
        teclado_opcoes = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📱 Celulares em Oferta"), KeyboardButton("⚡ Ferramentas")],
                [KeyboardButton("💻 Informática"), KeyboardButton("🏠 Casa e Cozinha")],
                [KeyboardButton("🎮 Games"), KeyboardButton("📺 Eletrônicos")],
                [KeyboardButton("👟 Calçados"), KeyboardButton("⌚ Relógios")],
                [KeyboardButton("🔧 Construção"), KeyboardButton("✨ Acessar Vitrine Completa 🛍️")]
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

    # Mapeamento dos botões do teclado ou processamento inteligente via IA
    link_destino = LINK_VITRINE_SOCIAL
    termo_busca_usuario = texto_usuario

    if "Ferramenta" in texto_usuario:
        termo_busca_usuario = "ferramenta"
        link_destino = LINK_FERRAMENTAS
    elif "Informática" in texto_usuario:
        termo_busca_usuario = "informatica"
        link_destino = LINK_INFORMATICA
    elif "Casa" in texto_usuario:
        termo_busca_usuario = "casa"
        link_destino = LINK_COZINHA
    elif "Game" in texto_usuario:
        termo_busca_usuario = "games"
        link_destino = LINK_GAMES
    elif "Eletrônico" in texto_usuario:
        termo_busca_usuario = "eletronicos"
        link_destino = LINK_ELETRONICOS
    elif "Calçado" in texto_usuario:
        termo_busca_usuario = "calcados"
        link_destino = LINK_CALCADOS
    elif "Relógio" in texto_usuario:
        termo_busca_usuario = "relogios"
        link_destino = LINK_RELOGIOS
    elif "Construção" in texto_usuario:
        termo_busca_usuario = "construcao"
        link_destino = LINK_CONSTRUCAO
    elif "Celulares em Oferta" in texto_usuario or "Celulares" in texto_usuario:
        termo_busca_usuario = "celular"
        link_destino = LINK_SAMSUNG
    else:
        # Texto livre: a IA limpa o termo e descobre a categoria correta
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        resposta_ia = interpretar_com_ia(texto_usuario)
        
        partes = [p.strip() for p in resposta_ia.split(",")]
        termo_busca_usuario = partes[0] if len(partes) > 0 else texto_usuario
        categoria_ia = partes[1].lower() if len(partes) > 1 else "geral"

        if "cozinha" in categoria_ia:
            link_destino = LINK_COZINHA
        elif "celular" in categoria_ia:
            link_destino = LINK_SAMSUNG
        elif "ferramenta" in categoria_ia:
            link_destino = LINK_FERRAMENTAS
        elif "informatica" in categoria_ia:
            link_destino = LINK_INFORMATICA
        elif "game" in categoria_ia:
            link_destino = LINK_GAMES
        elif "eletronico" in categoria_ia:
            link_destino = LINK_ELETRONICOS
        elif "calcado" in categoria_ia:
            link_destino = LINK_CALCADOS
        elif "relogio" in categoria_ia:
            link_destino = LINK_RELOGIOS
        elif "construcao" in categoria_ia:
            link_destino = LINK_CONSTRUCAO
        else:
            link_destino = LINK_VITRINE_SOCIAL

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🔍 *Buscando as melhores ofertas de* `{termo_busca_usuario}`...", 
        parse_mode="Markdown"
    )
    
    produto = buscar_produto_vitrine(termo_busca_usuario)
    
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
            f"👉 [CLIQUE AQUI PARA ABRIR A OFERTA NA VITRINE]({link_destino})"
        )

        if foto:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=foto,
                    caption=texto_compartilhamento,
                    parse_mode="Markdown"
                )
                return
            except Exception:
                pass

        await context.bot.send_message(
            chat_id=chat_id,
            text=texto_compartilhamento,
            parse_mode="Markdown"
        )
        return

    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"📦 **Ofertas de {termo_busca_usuario.title()}**\n\n👉 [CLIQUE AQUI PARA ABRIR A OFERTA NA VITRINE]({link_destino})",
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
