import os
import sys
import asyncio
from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# =========================
# CONFIGURAÇÃO E CHAVES (.env)
# =========================
print("🔄 Carregando variáveis do .env...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print(f"🔑 Token do Telegram encontrado? {'Sim' if TOKEN else 'Não'}", flush=True)
print(f"🔑 Groq Key encontrada? {'Sim' if GROQ_API_KEY else 'Não'}", flush=True)

if not TOKEN:
    print("❌ ERRO: O token do Telegram não foi encontrado!", flush=True)
    sys.exit(1)

if not GROQ_API_KEY:
    print("❌ ERRO: A chave GROQ_API_KEY não foi encontrada!", flush=True)
    sys.exit(1)

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# CHAMADA À API DA GROQ (IA)
# =========================
def interpretar_pedido_com_ia(pergunta_usuario, nome_usuario="Amigo"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    instrucao_sistema = (
        f"Você é o Merlim das Ofertas, um assistente virtual especialista em compras, cupons e ofertas no e-commerce. "
        f"O usuário se chama {nome_usuario}. "
        f"Sua função:\n"
        f"1. Se o usuário estiver procurando um produto, responda APENAS com o termo exato e limpo que deve ser pesquisado na API de e-commerce (ex: se ele disser 'quero um celular samsung bom', você responde apenas 'smartphone samsung').\n"
        f"2. Se for uma conversa normal, dúvida sobre compras ou pedidos de cupom, dê uma resposta amigável, prestativa e curta dando dicas de economia."
    )

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": instrucao_sistema},
            {"role": "user", "content": pergunta_usuario}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            return pergunta_usuario
    except Exception as e:
        return pergunta_usuario

# =========================
# FUNÇÃO DE BUSCA (MERCADO LIVRE)
# =========================
def buscar_produtos_mercado_livre(termo_busca):
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo_busca}&limit=3"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            return dados.get("results", [])
        return []
    except Exception as e:
        print(f"Erro na busca: {e}")
        return []

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("nome", None)
    legenda_boas_vindas = (
        "🧙‍♂️ **OLÁ! EU SOU O MERLIM DAS OFERTAS** 🛍️\n\n"
        "O seu mago particular para encontrar os melhores preços, descontos e cupons da internet!\n\n"
        "Para iniciarmos, por favor:\n"
        "👉 **DIGITE SEU NOME OU APELIDO:**"
    )

    try:
        await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")
    except Exception as e:
        print(f"Erro no start: {e}")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    # Se o usuário ainda não informou o nome
    if "nome" not in context.user_data:
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        # Vinheta de carregamento charmosa
        msg_vinheta = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ *Preparando a varinha mágica para {nome_usuario.upper()}...*\n⏳ Carregando feitiços de desconto [ 1/3 ]", 
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_vinheta.message_id,
            text=f"✨ *Portal aberto para:* **{nome_usuario.upper()}**\n⏳ Sincronizando com as melhores lojas [ 2/3 ]",
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_vinheta.message_id,
            text=f"✨ *Portal aberto para:* **{nome_usuario.upper()}**\n✅ Merlim pronto para caçar ofertas! [ 3/3 ]",
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_vinheta.message_id)
        except:
            pass

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🪄 **Tudo pronto, {nome_usuario}!**\n\nO que você quer comprar hoje ou qual produto está procurando?", 
            parse_mode="Markdown"
        )
        return

    nome_usuario = context.user_data.get("nome", "Cliente")

    # Ação de digitação para parecer natural
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # 1. A IA interpreta o pedido do usuário
    resposta_ia = interpretar_pedido_com_ia(texto_usuario, nome_usuario)
    palavras_resposta = resposta_ia.split()

    # 2. Se a IA indicar que é um produto (respostas curtas), fazemos a busca no Mercado Livre
    if len(palavras_resposta) <= 4 and "cupom" not in texto_usuario.lower() and "olá" not in texto_usuario.lower():
        termo_busca = resposta_ia
        msg_aguarde = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🔮 *Merlim interpretou:* `{termo_busca}`\n🔍 Buscando os menores preços...", 
            parse_mode="Markdown"
        )
        
        produtos = buscar_produtos_mercado_livre(termo_busca)
        
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
        except:
            pass

        if not produtos:
            await context.bot.send_message(chat_id=chat_id, text="❌ O feitiço não encontrou ofertas exatas para isso. Tente descrever de outro modo!")
            return

        for p in produtos:
            titulo = p.get("title")
            preco = p.get("price")
            link = p.get("permalink")
            thumbnail = p.get("thumbnail")
            
            texto_oferta = (
                f"🛒 **{titulo}**\n\n"
                f"💰 **Preço:** R$ {preco:,.2f}\n"
                f"✨ *Oferta encontrada pelo Merlim*"
            )
            
            teclado = [[InlineKeyboardButton("🔗 VER PROMOÇÃO NO SITE", url=link)]]
            reply_markup = InlineKeyboardMarkup(teclado)

            try:
                await context.bot.send_photo(chat_id=chat_id, photo=thumbnail, caption=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")
            except:
                await context.bot.send_message(chat_id=chat_id, text=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Se for uma dica ou conversa geral, a IA responde diretamente
        await context.bot.send_message(chat_id=chat_id, text=resposta_ia, parse_mode="Markdown")

# =========================
# INICIALIZAÇÃO DO BOT
# =========================
def main():
    print("🧙‍♂️ Iniciando o Merlim das Ofertas...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim configurado e pronto para caçar descontos!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
            
