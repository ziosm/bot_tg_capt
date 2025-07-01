import os
import asyncio
import logging
import aiohttp
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import random
from translations import get_text, get_available_languages, get_language_flag, TRANSLATIONS

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CaptainCatBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.user_languages = {}  # Memorizza la lingua di ogni utente
        self.setup_handlers()

    def get_user_language(self, user_id: int) -> str:
        """Ottiene la lingua dell'utente o usa quella di default"""
        return self.user_languages.get(user_id, 'it')  # Default: Italiano

    def set_user_language(self, user_id: int, lang_code: str):
        """Imposta la lingua dell'utente"""
        self.user_languages[user_id] = lang_code

    def t(self, user_id: int, key: str) -> str:
        """Shortcut per get_text con lingua utente"""
        lang = self.get_user_language(user_id)
        return get_text(lang, key)

    def setup_handlers(self):
        """Configura tutti gli handler del bot"""
        # Handler per comandi
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("language", self.language_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("roadmap", self.roadmap_command))
        self.app.add_handler(CommandHandler("team", self.team_command))
        self.app.add_handler(CommandHandler("utility", self.utility_command))
        self.app.add_handler(CommandHandler("presale", self.presale_command))
        self.app.add_handler(CommandHandler("community", self.community_command))
        self.app.add_handler(CommandHandler("game", self.game_command))
        self.app.add_handler(CommandHandler("staking", self.staking_command))
        self.app.add_handler(CommandHandler("nft", self.nft_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        
        # Handler per callback buttons
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Handler per messaggi di testo
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando di benvenuto"""
        user_id = update.effective_user.id
        
        keyboard = [
            [InlineKeyboardButton(self.t(user_id, 'btn_presale'), callback_data="presale"),
             InlineKeyboardButton(self.t(user_id, 'btn_roadmap'), callback_data="roadmap")],
            [InlineKeyboardButton(self.t(user_id, 'btn_gamefi'), callback_data="game"),
             InlineKeyboardButton(self.t(user_id, 'btn_team'), callback_data="team")],
            [InlineKeyboardButton(self.t(user_id, 'btn_community'), callback_data="community"),
             InlineKeyboardButton(self.t(user_id, 'btn_help'), callback_data="help")],
            [InlineKeyboardButton(self.t(user_id, 'btn_language'), callback_data="language")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = f"""
{self.t(user_id, 'welcome_title')}

{self.t(user_id, 'welcome_msg')}

{self.t(user_id, 'presale_active')}
{self.t(user_id, 'target_listing')}
{self.t(user_id, 'community_goal')}

{self.t(user_id, 'what_know')}
        """
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando per cambiare lingua"""
        user_id = update.effective_user.id
        available_langs = get_available_languages()
        
        keyboard = []
        for lang_code, lang_name in available_langs.items():
            keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_lang = self.get_user_language(user_id)
        flag = get_language_flag(current_lang)
        
        lang_msg = f"🌍 **CHOOSE YOUR LANGUAGE / SCEGLI LA TUA LINGUA**\n\n{flag} Current/Attuale: {available_langs.get(current_lang, 'Unknown')}"
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(lang_msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(lang_msg, reply_markup=reply_markup, parse_mode='Markdown')

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stato del bot"""
        user_id = update.effective_user.id
        
        status_msg = f"""
{self.t(user_id, 'status_title')}

✅ **Bot Online e Funzionante**
📡 **Server: Render.com**
⏰ **Uptime: 24/7**
🔄 **Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}**
🌍 **Lingue supportate: 5**

💪 **Pronto ad aiutare la community!**
        """
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostra il menu di aiuto"""
        user_id = update.effective_user.id
        help_text = self.t(user_id, 'help_commands')
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')

    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info su prezzo e tokenomics"""
        user_id = update.effective_user.id
        
        price_info = f"""
{self.t(user_id, 'tokenomics_title')}

🔥 **Prevendita Attiva!**
💰 **Target Listing: 1500 TON**
📊 **Supply Totale: 1,000,000,000 CAT**

📈 **Distribuzione:**
• 40% Prevendita
• 30% Liquidità DEX  
• 15% Team (locked)
• 10% Marketing
• 5% Rewards

🚀 **Prossimo step: LISTING su DEX principali!**
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Partecipa alla Prevendita", url="https://t.me/Captain_cat_Cain")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(price_info, reply_markup=reply_markup, parse_mode='Markdown')

    async def roadmap_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostra la roadmap"""
        user_id = update.effective_user.id
        
        roadmap_info = f"""
{self.t(user_id, 'roadmap_title')}

✅ **Fase 1 - Lancio** (COMPLETATO)
• Smart contract sviluppato
• Audit di sicurezza
• Community Telegram
• Website e branding

🔄 **Fase 2 - Prevendita** (IN CORSO)
• Prevendita privata
• Partnership strategiche  
• Marketing campaign
• Crescita a 10K membri

🎯 **Fase 3 - Listing** (Q1 2025)
• Listing su DEX principali
• CoinMarketCap & CoinGecko
• Influencer partnerships
• Prima fase GameFi

🚀 **Fase 4 - Ecosistema** (Q2 2025)
• CaptainCat Game
• NFT Collection
• Staking rewards
• DAO governance
        """
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(roadmap_info, parse_mode='Markdown')
        else:
            await update.message.reply_text(roadmap_info, parse_mode='Markdown')

    async def team_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info sul team"""
        user_id = update.effective_user.id
        
        team_info = f"""
{self.t(user_id, 'team_title')}

🦸‍♂️ **CZ - Founder & CEO**
Visionario crypto con anni di esperienza in DeFi e GameFi

💻 **Dr. Eliax - Lead Developer**  
Esperto in smart contracts e sicurezza blockchain

📈 **Rejane - Marketing Manager**
Specialista in crescita community e marketing virale

🔒 **Team Verificato e Doxxed**
🏆 **Track Record Comprovato**
💪 **Esperienza Combinata: 15+ anni**
        """
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(team_info, parse_mode='Markdown')
        else:
            await update.message.reply_text(team_info, parse_mode='Markdown')

    async def utility_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info sulle utility del token"""
        user_id = update.effective_user.id
        
        utility_info = f"""
{self.t(user_id, 'utility_title')}

🎮 **GameFi Ecosystem**
• CaptainCat Adventure Game
• Play-to-Earn mechanics
• In-game purchases

💎 **Staking Rewards**
• Stake CAT, earn rewards
• Lock periods: 30/90/180 giorni
• APY fino al 150%

🖼️ **NFT Collection**
• CaptainCat Heroes NFT
• Utility in-game
• Collezioni limitate

🗳️ **DAO Governance**
• Vota le decisioni
• Proponi miglioramenti  
• Guida il futuro

🔥 **Token Burn**
• Burn mensili
• Deflationary mechanics
• Aumento valore
        """
        
        await update.message.reply_text(utility_info, parse_mode='Markdown')

    async def presale_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info sulla prevendita"""
        user_id = update.effective_user.id
        
        presale_info = f"""
{self.t(user_id, 'presale_title')}

🔥 **FASE 2 ATTIVA!**

💰 **Target: 1500 TON per listing**
📊 **Progresso: 45% completato**
⏰ **Tempo rimasto: Limitato!**

🎯 **Bonus Prevendita:**
• Early Bird: +20% tokens
• Whale Bonus: +15% (>50 TON)
• Community Bonus: +10%

📱 **Come Partecipare:**
1. Unisciti al gruppo Telegram
2. Contatta gli admin
3. Invia TON
4. Ricevi CAT tokens

🚀 **Non perdere l'opportunità!**
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Unisciti alla Prevendita", url="https://t.me/Captain_cat_Cain")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(presale_info, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(presale_info, reply_markup=reply_markup, parse_mode='Markdown')

    async def community_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Links della community"""
        user_id = update.effective_user.id
        
        community_info = f"""
{self.t(user_id, 'community_title')}

🎯 **Obiettivo: 10K Membri!**
👥 **Attuali: 2.5K+ Eroi**

🔗 **Links Ufficiali:**
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Telegram Main", url="https://t.me/Captain_cat_Cain")],
            [InlineKeyboardButton("🌐 Website", url="https://captaincat.token")],
            [InlineKeyboardButton("💎 Sponsor: BLUM", url="https://www.blum.io/")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(community_info, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(community_info, reply_markup=reply_markup, parse_mode='Markdown')

    async def game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info sul GameFi"""
        user_id = update.effective_user.id
        
        game_info = f"""
{self.t(user_id, 'gamefi_title')}

🦸‍♂️ **CaptainCat Adventure**
• Action RPG game
• Play-to-Earn mechanics
• Multiplayer battles

💰 **Economia di Gioco:**
• CAT token per acquisti
• NFT equipaggiamenti
• Rewards daily/weekly

🏆 **Features:**
• Boss battles
• Guild system  
• Tournaments
• Rare item drops

🚀 **Launch: Q2 2025**
📱 **Platform: Mobile & Web**
        """
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(game_info, parse_mode='Markdown')
        else:
            await update.message.reply_text(game_info, parse_mode='Markdown')

    async def staking_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info sullo staking"""
        user_id = update.effective_user.id
        
        staking_info = f"""
{self.t(user_id, 'staking_title')}

🔒 **Stake CAT, Earn Rewards!**

📊 **Pool Disponibili:**
• 30 giorni - APY 50%
• 90 giorni - APY 100%  
• 180 giorni - APY 150%

🎁 **Bonus Features:**
• Compound automatico
• Early unstake (penale 10%)
• Staking NFT boost

💰 **Rewards Distribuiti:**
• Daily: 0.1% del pool
• Weekly: Bonus NFT
• Monthly: Token burn

🚀 **Launch: Post-Listing**
        """
        
        await update.message.reply_text(staking_info, parse_mode='Markdown')

    async def nft_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Info sugli NFT"""
        user_id = update.effective_user.id
        
        nft_info = f"""
{self.t(user_id, 'nft_title')}

🦸‍♂️ **CaptainCat Heroes**
• 10,000 NFT unici
• 100+ traits rari
• Utility in-game

🏆 **Rarità:**
• Common (60%) - Boost +10%
• Rare (25%) - Boost +25%
• Epic (10%) - Boost +50%
• Legendary (5%) - Boost +100%

⚡ **Utility NFT:**
• GameFi advantages
• Staking multipliers
• Governance votes
• Exclusive events

🎨 **Arte:** Pixel art supereroi felini
🚀 **Mint:** Q2 2025
        """
        
        await update.message.reply_text(nft_info, parse_mode='Markdown')

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler per i bottoni inline"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Gestione cambio lingua
        if query.data.startswith("lang_"):
            lang_code = query.data.split("_")[1]
            self.set_user_language(user_id, lang_code)
            
            available_langs = get_available_languages()
            lang_name = available_langs.get(lang_code, 'Unknown')
            
            await query.edit_message_text(
                f"🌍 {self.t(user_id, 'language_changed')}\n\n"
                f"Lingua impostata: {lang_name}",
                parse_mode='Markdown'
            )
            return
        
        # Altri bottoni
        if query.data == "presale":
            await self.presale_command(update, context)
        elif query.data == "roadmap":
            await self.roadmap_command(update, context)
        elif query.data == "game":
            await self.game_command(update, context)
        elif query.data == "team":
            await self.team_command(update, context)
        elif query.data == "community":
            await self.community_command(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "language":
            await self.language_command(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce i messaggi di testo libero con AI multilingua"""
        message = update.message.text.lower()
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Eroe"
        
        # Analizza il messaggio e risponde in modo intelligente
        response = self.generate_ai_response(message, user_name, user_id)
        
        await update.message.reply_text(response, parse_mode='Markdown')

    def generate_ai_response(self, message: str, user_name: str, user_id: int) -> str:
        """Genera una risposta AI multilingua basata sul messaggio"""
        
        # Parole chiave multilingua
        greetings = ['ciao', 'salve', 'buongiorno', 'buonasera', 'hey', 'hello', 'hi', 'hola', 'salut', 'hallo', 'guten tag']
        price_words = ['prezzo', 'costo', 'quanto costa', 'valore', 'price', 'cost', 'precio', 'coste', 'prix', 'preis', 'kosten']
        roadmap_words = ['roadmap', 'quando', 'timeline', 'futuro', 'piani', 'when', 'future', 'plans', 'cuándo', 'quand', 'wann', 'zukunft']
        utility_words = ['utility', 'funzioni', 'a cosa serve', 'utilità', 'gamefi', 'game', 'utilidad', 'utilité', 'nutzen', 'spiel']
        team_words = ['team', 'sviluppatori', 'fondatori', 'chi', 'who', 'equipo', 'équipe', 'entwickler', 'gründer']
        moon_words = ['moon', 'luna', 'lambo', 'ricco', 'milionario', 'rich', 'rico', 'riche', 'reich', 'mond']
        listing_words = ['listing', 'exchange', 'dex', 'trading', 'intercambio', 'échange', 'börse', 'handel']
        security_words = ['sicuro', 'scam', 'truffa', 'audit', 'sicurezza', 'safe', 'security', 'seguro', 'sûr', 'sicher', 'sicherheit']
        community_words = ['community', 'gruppo', 'telegram', 'social', 'comunidad', 'communauté', 'gemeinschaft', 'gruppe']
        
        # Saluti
        if any(word in message for word in greetings):
            responses = [self.t(user_id, 'greeting_1'), self.t(user_id, 'greeting_2'), self.t(user_id, 'greeting_3')]
            return f"🐱‍🦸 {user_name}! " + random.choice(responses)
        
        # Prezzo/Costo
        elif any(word in message for word in price_words):
            responses = [self.t(user_id, 'price_1'), self.t(user_id, 'price_2'), self.t(user_id, 'price_3')]
            return "💎 " + random.choice(responses) + "\n\n🚀 Usa /presale per tutti i dettagli!"
        
        # Roadmap/Quando
        elif any(word in message for word in roadmap_words):
            responses = [self.t(user_id, 'roadmap_1'), self.t(user_id, 'roadmap_2'), self.t(user_id, 'roadmap_3')]
            return "🗺️ " + random.choice(responses) + "\n\n📅 Usa /roadmap per la timeline completa!"
        
        # Utility/Funzioni
        elif any(word in message for word in utility_words):
            responses = [self.t(user_id, 'utility_1'), self.t(user_id, 'utility_2'), self.t(user_id, 'utility_3')]
            return "⚡ " + random.choice(responses) + "\n\n🎮 Usa /utility per tutti i dettagli!"
        
        # Team
        elif any(word in message for word in team_words):
            responses = [self.t(user_id, 'team_1'), self.t(user_id, 'team_2'), self.t(user_id, 'team_3')]
            return "👥 " + random.choice(responses) + "\n\n🦸‍♂️ Usa /team per conoscerci meglio!"
        
        # Luna/Moon
        elif any(word in message for word in moon_words):
            return f"🚀 {user_name}, {self.t(user_id, 'moon_msg')}"
        
        # Listing
        elif any(word in message for word in listing_words):
            return self.t(user_id, 'listing_msg')
        
        # Sicurezza
        elif any(word in message for word in security_words):
            return self.t(user_id, 'security_msg')
        
        # Community
        elif any(word in message for word in community_words):
            return f"{self.t(user_id, 'community_msg')}\n\n📱 Usa /community per tutti i link!"
        
        # Generale/Default
        else:
            responses = [
                self.t(user_id, 'default_1').format(user_name),
                self.t(user_id, 'default_2').format(user_name),
                self.t(user_id, 'default_3').format(user_name),
                self.t(user_id, 'default_4').format(user_name)
            ]
            return random.choice(responses) + f"\n\n❓ {self.t(user_id, 'try_commands')}"

    def run(self):
        """Avvia il bot"""
        print("🐱‍🦸 CaptainCat Multilingual Bot starting on Render...")
        self.app.run_polling(drop_pending_updates=True)

# Script principale per Render
if __name__ == "__main__":
    # Token dal environment variable di Render
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ ERRORE: Variabile BOT_TOKEN non trovata!")
        print("💡 Configura la variabile d'ambiente BOT_TOKEN su Render")
    else:
        print(f"🚀 Starting CaptainCat Multilingual Bot...")
        bot = CaptainCatBot(BOT_TOKEN)
        bot.run()
