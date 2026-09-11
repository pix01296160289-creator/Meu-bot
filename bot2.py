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
# GERADOR DE LINK COM COMISSÃO
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    separador = "&" if "?" in url_produto else "?"
    return f"{url_produto}{separador}matt_tool={AFFILIATE_ID}"

# =========================
# LIMPEZA DE TEXTO (REMOVE EMOJIS)
# =========================
def limpar_termo(texto):
    # Remove emojis e caracteres especiais para a busca não falhar
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    # Remove espaços extras
    return ' '.join(texto_limpo.split()).strip()

# =========================
# INTELIGÊNCIA ARTIFICIAL (GROQ)
# =========================
def interpretar_com_ia(texto_usuario):
    """Usa a IA da Groq para extrair o produto da busca ou gerar uma resposta amigável."""
    prompt_sistema = (
        "Você é o Merlim, um assistente de inteligência artificial especialista em e-commerce e caça a ofertas no Mercado Livre. "
        "O usuário vai digitar algo para você. Sua tarefa é analisar o texto e extrair APENAS o nome limpo do produto ou termo principal "
        "que ele deseja buscar (ex: se ele disse 'preciso de uma parafusadeira boa', você retorna apenas 'parafusadeira'). "
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
        # Retorna a resposta da IA já limpa de emojis
        return limpar_termo(resposta)
    except Exception as e:
        print(f"Erro na API da Groq: {e}")
        # Fallback: se a IA falhar, limpa o texto original do usuário
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
    
    # --- AQUI ESTÁ A SUA IMAGEM PERSONALIZADA ---
    banner_url = "https://i.ibb.co/pr5XpyL8/image-1789089291368.jpg"
    
    legenda_boas_vindas = (
        "🧙‍♂️ **MERLIM DAS OFERTAS** | *Seu Assistente Inteligente*\n\n"
        "Seja muito bem-vindo! Agora sou impulsionado por Inteligência Artificial e trago as melhores ofertas do Mercado Livre para você.\n\n"
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
        # Fallback caso a foto dê erro, envia só o texto
        await update.message.reply_text(legenda_boas_vindas, reply_markup=teclado_menu, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    # Tratamento para os botões fixos
    if "Cupons" in texto_usuario:
        link_cupons = gerar_link_afiliado("https://www.mercadolivre.com.br/cupons")
        await update.message.reply_text(
            f"🎟️ **Central de Cupons do Mercado Livre**\n\nAcesse o link abaixo para resgatar seus descontos:\n\n{link_cupons}",
            parse_mode="Markdown"
        )
        return
    elif "Ofertas" in texto_usuario:
        texto_usuario = "ofertas imperdíveis"

    # Captura o nome se ainda não estiver definido
    if "nome" not in context.user_data:
        nome_limpo = limpar_termo(texto_usuario)
        if len(nome_limpo) < 2 or "Ofertas" in texto_usuario or "Cupons" in texto_usuario:
            await update.message.reply_text("⚠️ Por favor, digite um nome ou apelido válido:")
            return
        
        context.user_data["nome"] = nome_limpo
        nome_usuario = context.user_data["nome"]

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ **Tudo pronto, {nome_usuario}!**\n\nAgora você pode conversar comigo naturalmente. **O que você está procurando hoje?** (ex: *quero um tênis esportivo, celular barato, etc*):",
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

    # IA interpreta e limpa o pedido do usuário
    termo_inteligente = interpretar_com_ia(texto_usuario)
    
    # Se a IA não encontrar produto, trata como busca normal limpa
    if termo_inteligente == "CONVERSA" or not termo_inteligente:
        termo_inteligente = limpar_termo(texto_usuario)

    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🧙‍♂️ *Merlim (IA) analisando e garimpando:* `{termo_inteligente}`...", 
        parse_mode="Markdown"
    )
    
    # Busca produtos no ML
    produtos = buscar_produtos_mercadolivre(termo_inteligente)
    
    # Apaga a mensagem de "aguarde"
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except Exception:
        pass

    # Link base para busca geral
    link_busca_geral = gerar_link_afiliado(f"https://lista.mercadolivre.com.br/{requests.utils.quote(termo_inteligente)}")

    teclado = [
        [InlineKeyboardButton("🔗 VER VITRINE COMPLETA NO SITE", url=link_busca_geral)],
        [InlineKeyboardButton("🎟️ RESGATAR CUPONS", url=gerar_link_afiliado("https://www.mercadolivre.com.br/cupons"))]
    ]

    # Se encontrou produtos, mostra o melhor destaque com foto
    if produtos:
        primeiro_produto = produtos[0]
        titulo = primeiro_produto.get("title")
        preco_atual = primeiro_produto.get("price", 0)
        
        # Pega a foto real do Mercado Livre e converte para alta resolução trocando de I.jpg para O.jpg
        foto_url = primeiro_produto.get("thumbnail", "")
        if foto_url:
            foto_url = foto_url.replace("-I.jpg", "-O.jpg") # Tenta obter a imagem maior

        texto_oferta = (
            f"🏆 **IA ENCONTROU A MELHOR OFERTA!**\n\n"
            f"🛒 *{titulo}*\n"
            f"🟢 **Menor preço:** R$ {preco_atual:,.2f}\n\n"
            f"👇 *Veja todas as opções na vitrine oficial:*"
        )

        # Se encontrou a foto, manda como foto com a legenda do produto
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
                print("❌ Erro ao enviar foto do ML, enviando texto.")
                pass # Se der falha ao carregar a foto do ML, cai para o envio de texto abaixo

    # Mensagem de fallback caso não venha foto ou dê erro
    texto_catalogo = (
        f"📦 **Catálogo Completo: {termo_inteligente.title()}**\n\n"
        f"Olá, {nome_usuario}! Usei minha inteligência para buscar as melhores opções no Mercado Livre.\n\n"
        f"👇 *Clique no botão abaixo para ver a vitrine completa com segurança:*"
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
    print("🧙‍♂️ Iniciando o Merlim com IA, Fotos do ML e Banner Personalizado...", flush=True)
    
    # Configuração de timeout para evitar travamentos
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim 100% operacional!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
