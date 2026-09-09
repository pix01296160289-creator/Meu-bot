import os
import sys
import asyncio
from dotenv import load_dotenv
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest

# =========================
# CONFIGURAÇÃO E CHAVES
# =========================
print("🔄 Carregando variáveis de ambiente...", flush=True)
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Pega automaticamente o ID de afiliado configurado no Railway (.env)
AFFILIATE_ID = os.getenv("AFFILIATE_ID", "")

if not TOKEN or not GROQ_API_KEY:
    print("❌ ERRO: Verifique suas chaves TOKEN e GROQ_API_KEY", flush=True)
    sys.exit(1)

# =========================
# TRATADOR DE ERROS GLOBAL
# =========================
async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"❌ ERRO CAPTURADO NO BOT: {context.error}", flush=True)

# =========================
# INTERPRETAÇÃO COM IA (GROQ)
# =========================
def interpretar_pedido_com_ia(pergunta_usuario, nome_usuario="Amigo"):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    instrucao_sistema = (
        f"Você é o Merlim das Ofertas, especialista em cupons e descontos reais. "
        f"O usuário se chama {nome_usuario}. "
        f"Extraia o produto principal que ele quer buscar (ex: se ele disser 'celular samsung com promoção', retorne 'celular samsung'). Não use pontuação."
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
# GERADOR DE LINK COM COMISSÃO AUTOMÁTICA
# =========================
def gerar_link_afiliado(url_produto):
    if not AFFILIATE_ID:
        return url_produto
    
    # Adiciona o parâmetro de rastreio de afiliado de forma automática na URL do produto
    separador = "&" if "?" in url_produto else "?"
    return f"{url_produto}{separador}matt_tool={AFFILIATE_ID}"

# =========================
# BUSCA DE PROMOÇÕES NO MERCADO LIVRE
# =========================
def buscar_cupons_e_promocoes(termo_busca):
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={requests.utils.quote(termo_busca + ' ofertas')}&sort=price_asc&limit=10"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            resultados = response.json().get("results", [])
            
            produtos_com_desconto_real = []
            for p in resultados:
                preco_atual = p.get("price", 0)
                preco_antigo = p.get("original_price")
                
                if preco_antigo and preco_antigo > preco_atual:
                    produtos_com_desconto_real.append(p)
            
            if produtos_com_desconto_real:
                return produtos_com_desconto_real[:3]
            return resultados[:3]
            
    except Exception as e:
        print(f"Erro na busca: {e}")
        
    return []

# =========================
# COMANDOS E INTERFACE DO TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    legenda_boas_vindas = (
        "🧙‍♂️ **OLÁ! EU SOU O MERLIM DAS OFERTAS** 🎟️🔥\n\n"
        "O seu mago especialista em caçar **cupons ativos, descontos reais e menor preço**!\n\n"
        "Para iniciarmos, por favor:\n"
        "👉 **DIGITE SEU NOME OU APELIDO:**"
    )
    await update.message.reply_text(legenda_boas_vindas, parse_mode="Markdown")

async def responder_texto_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    texto_usuario = update.message.text.strip()

    if "nome" not in context.user_data:
        context.user_data["nome"] = texto_usuario
        nome_usuario = context.user_data["nome"]

        msg_vinheta = await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✨ *Preparando os pergaminhos de cupons para {nome_usuario.upper()}...*\n⏳ Buscando descontos verificados [ 1/3 ]", 
            parse_mode="Markdown"
        )
        await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_vinheta.message_id, text=f"✨ *Portal aberto para:* **{nome_usuario.upper()}**\n⏳ Varrendo cupons e ofertas relâmpago [ 2/3 ]", parse_mode="Markdown")
        await asyncio.sleep(1)
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_vinheta.message_id, text=f"✨ *Portal aberto para:* **{nome_usuario.upper()}**\n✅ Merlim pronto para economizar de verdade! [ 3/3 ]", parse_mode="Markdown")
        await asyncio.sleep(1)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_vinheta.message_id)
        except:
            pass

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🪄 **Tudo pronto, {nome_usuario}!**\n\nQual produto você quer encontrar com **cupom ou promoção real** hoje?", 
            parse_mode="Markdown"
        )
        return

    if context.user_data.get("ultima_mensagem") == texto_usuario:
        return
    context.user_data["ultima_mensagem"] = texto_usuario

    nome_usuario = context.user_data.get("nome", "Cliente")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    termo_ia = interpretar_pedido_com_ia(texto_usuario, nome_usuario)
    
    msg_aguarde = await context.bot.send_message(
        chat_id=chat_id, 
        text=f"🎟️ *Merlim caçando cupons e descontos para:* `{texto_usuario}`...", 
        parse_mode="Markdown"
    )
    
    produtos = buscar_cupons_e_promocoes(termo_ia)
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_aguarde.message_id)
    except:
        pass

    link_cupons_oficial = gerar_link_afiliado("https://www.mercadolivre.com.br/cupons")
    link_busca_ofertas = gerar_link_afiliado(f"https://lista.mercadolivre.com.br/ofertas/{requests.utils.quote(texto_usuario)}")

    if not produtos:
        texto_fallback = (
            f"🎟️ **Central de Cupons, {nome_usuario}!**\n\n"
            f"Não achei um item isolado com desconto imediato para essa busca específica, mas você pode resgatar **cupons ativos na página oficial** ou ver as **ofertas relâmpago** abaixo:"
        )
        teclado = [
            [InlineKeyboardButton("🎟️ RESGATAR CUPONS NO SITE", url=link_cupons_oficial)],
            [InlineKeyboardButton("🔥 VER OFERTAS DO PRODUTO", url=link_busca_ofertas)]
        ]
        await context.bot.send_message(chat_id=chat_id, text=texto_fallback, reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")
        return

    for p in produtos:
        titulo = p.get("title")
        preco_atual = p.get("price", 0)
        preco_antigo = p.get("original_price")
        link_original = p.get("permalink")
        thumbnail = p.get("thumbnail")
        
        # 🔗 Converte o link do produto no seu link monetizado de afiliado automaticamente
        link_monetizado = gerar_link_afiliado(link_original)
        
        if preco_antigo and preco_antigo > preco_atual:
            desconto_pct = int(100 - (preco_atual * 100 / preco_antigo))
            info_preco = (
                f"❌ ~~R$ {preco_antigo:,.2f}~~ | 🟢 **R$ {preco_atual:,.2f}**\n"
                f"🔥 **DESCONTO REAL: {desconto_pct}% OFF!**"
            )
        else:
            info_preco = f"💰 **Preço Encontrado:** R$ {preco_atual:,.2f}\n✨ *Preço competitivo*"

        texto_oferta = (
            f"🛒 **{titulo}**\n\n"
            f"{info_preco}\n\n"
            f"🎟️ *Dica do Merlim: Verifique se há cupons extras aplicáveis!*"
        )
        
        teclado = [
            [InlineKeyboardButton("🔗 APROVEITAR DESCONTO NO SITE", url=link_monetizado)],
            [InlineKeyboardButton("🎟️ RESGATAR CUPONS", url=link_cupons_oficial)]
        ]
        reply_markup = InlineKeyboardMarkup(teclado)

        try:
            await context.bot.send_photo(chat_id=chat_id, photo=thumbnail, caption=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")
        except:
            await context.bot.send_message(chat_id=chat_id, text=texto_oferta, reply_markup=reply_markup, parse_mode="Markdown")

# =========================
# MAIN
# =========================
def main():
    print("🧙‍♂️ Iniciando o Merlim das Ofertas...", flush=True)
    request = HTTPXRequest(connection_pool_size=20, connect_timeout=60, read_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    app.add_error_handler(erro_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_texto_livre))

    print("✅ Merlim configurado e pronto para faturar!", flush=True)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
