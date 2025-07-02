import os
import asyncio
import logging
import aiohttp
import json
import asyncpg
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest, TimedOut, NetworkError
import random
from functools import wraps
from translations import get_text, get_available_languages, get_language_flag, TRANSLATIONS

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database connection per il gioco
DATABASE_URL = os.environ.get('DATABASE_URL')

# Rate limiting decorator
def rate_limit(max_calls=5, period=60, group_max_calls=10, group_period=30):
    def decorator(func):
        calls = {}
        group_calls = {}
        
        @wraps(func)
        async def wrapper(self, update, context):
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            is_group = chat_id < 0
            now = time.time()
            
            # Rate limiting per utente
            if user_id in calls:
                calls[user_id] = [call for call in calls[user_id] if call > now - period]
                if len(calls[user_id]) >= max_calls:
                    if not is_group:  # Solo in privato mostra il messaggio di rate limit
                        await update.message.reply_text("⏱️ Troppo veloce! Riprova tra un minuto.")
                    return
            else:
                calls[user_id] = []
            
            # Rate limiting per gruppo
            if is_group:
                if chat_id in group_calls:
                    group_calls[chat_id] = [call for call in group_calls[chat_id] if call > now - group_period]
                    if len(group_calls[chat_id]) >= group_max_calls:
                        return  # Silenzioso nei gruppi
                else:
                    group_calls[chat_id] = []
                group_calls[chat_id].append(now)
            
            calls[user_id].append(now)
            return await func(self, update, context)
        return wrapper
    return decorator

# Error handling decorator
def handle_errors(func):
    @wraps(func)
    async def wrapper(self, update, context):
        try:
            return await func(self, update, context)
        except BadRequest as e:
            logger.error(f"BadRequest in {func.__name__}: {e}")
            if "Button_type_invalid" in str(e) or "BUTTON_TYPE_INVALID" in str(e):
                # Fallback per Web App non funzionante
                await self._send_game_fallback(update, context)
            elif "message is not modified" in str(e).lower():
                # Ignora errori di messaggio non modificato
                logger.warning("Message not modified - ignoring")
            return
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Network error in {func.__name__}: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            if update.message:
                try:
                    await update.message.reply_text("🔧 Problema temporaneo. Riprova tra poco!")
                except:
                    pass
            return
    return wrapper

# Error handler globale per l'applicazione
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log l'errore e invia un messaggio all'utente se possibile."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Se l'errore è un conflitto, ignora (istanze multiple)
    if "Conflict" in str(context.error):
        logger.warning("Conflict error - possibly multiple instances running")
        return
    
    # Se c'è un update, prova a rispondere all'utente
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "🔧 Si è verificato un errore temporaneo. Riprova tra poco!"
            )
        except Exception:
            pass

class GameDatabase:
    def __init__(self):
        self.pool = None
        self._connection_attempts = 0
        self._max_attempts = 3
    
    async def init_pool(self):
        if DATABASE_URL and self._connection_attempts < self._max_attempts:
            try:
                self.pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    command_timeout=60,
                    server_settings={'jit': 'off'}
                )
                await self.create_tables()
                logger.info("Database pool created successfully")
            except Exception as e:
                self._connection_attempts += 1
                logger.error(f"Database connection failed (attempt {self._connection_attempts}): {e}")
                if self._connection_attempts >= self._max_attempts:
                    logger.error("Max database connection attempts reached. Running without database.")
    
    async def create_tables(self):
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS captaincat_scores (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        score INTEGER NOT NULL,
                        level INTEGER DEFAULT 1,
                        coins_collected INTEGER DEFAULT 0,
                        enemies_defeated INTEGER DEFAULT 0,
                        play_time INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        group_id BIGINT
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_user_scores ON captaincat_scores(user_id);
                    CREATE INDEX IF NOT EXISTS idx_group_scores ON captaincat_scores(group_id);
                    CREATE INDEX IF NOT EXISTS idx_score_ranking ON captaincat_scores(score DESC, created_at DESC);
                ''')
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
    async def save_score(self, user_id, username, first_name, score, level, 
                        coins, enemies, play_time, group_id=None):
        if not self.pool:
            logger.warning("Database not available, score not saved")
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO captaincat_scores 
                    (user_id, username, first_name, score, level, coins_collected, 
                     enemies_defeated, play_time, group_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ''', user_id, username, first_name, score, level, coins, enemies, play_time, group_id)
                return True
        except Exception as e:
            logger.error(f"Error saving score: {e}")
            return False
    
    async def get_user_best_score(self, user_id):
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow('''
                    SELECT MAX(score) as best_score, MAX(level) as max_level,
                           SUM(coins_collected) as total_coins, SUM(enemies_defeated) as total_enemies,
                           COUNT(*) as games_played
                    FROM captaincat_scores WHERE user_id = $1
                ''', user_id)
                return result
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None
    
    async def get_group_leaderboard(self, group_id=None, limit=10):
        if not self.pool:
            return []
        try:
            async with self.pool.acquire() as conn:
                if group_id:
                    query = '''
                        WITH ranked_scores AS (
                            SELECT user_id, username, first_name, score, level, created_at,
                                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY score DESC, created_at DESC) as rn
                            FROM captaincat_scores 
                            WHERE group_id = $1
                        )
                        SELECT user_id, username, first_name, score, level, created_at
                        FROM ranked_scores 
                        WHERE rn = 1
                        ORDER BY score DESC, created_at ASC
                        LIMIT $2
                    '''
                    results = await conn.fetch(query, group_id, limit)
                else:
                    query = '''
                        WITH ranked_scores AS (
                            SELECT user_id, username, first_name, score, level, created_at,
                                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY score DESC, created_at DESC) as rn
                            FROM captaincat_scores
                        )
                        SELECT user_id, username, first_name, score, level, created_at
                        FROM ranked_scores 
                        WHERE rn = 1
                        ORDER BY score DESC, created_at ASC
                        LIMIT $1
                    '''
                    results = await conn.fetch(query, limit)
                
                return list(results)
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []

class CaptainCatBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.user_languages = {}
        self.db = GameDatabase()
        self._web_app_url = os.environ.get('WEBAPP_URL', 'https://captaincat-game.onrender.com')
        self.setup_handlers()

    def get_user_language(self, user_id: int) -> str:
        return self.user_languages.get(user_id, 'it')

    def set_user_language(self, user_id: int, lang_code: str):
        self.user_languages[user_id] = lang_code

    def t(self, user_id: int, key: str) -> str:
        lang = self.get_user_language(user_id)
        return get_text(lang, key)

    def setup_handlers(self):
        # Handler esistenti
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("language", self.language_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("roadmap", self.roadmap_command))
        self.app.add_handler(CommandHandler("team", self.team_command))
        self.app.add_handler(CommandHandler("utility", self.utility_command))
        self.app.add_handler(CommandHandler("presale", self.presale_command))
        self.app.add_handler(CommandHandler("community", self.community_command))
        self.app.add_handler(CommandHandler("staking", self.staking_command))
        self.app.add_handler(CommandHandler("nft", self.nft_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        
        # Nuovi handler per il gioco con rate limiting
        self.app.add_handler(CommandHandler("game", self.game_command))
        self.app.add_handler(CommandHandler("play", self.game_command))
        self.app.add_handler(CommandHandler("mystats", self.mystats_command))
        self.app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        self.app.add_handler(CommandHandler("gametop", self.leaderboard_command))
        
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Handler per dati Web App
        self.app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_web_app_data))
        
        # Aggiungi error handler
        self.app.add_error_handler(error_handler)

    async def _send_game_fallback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fallback quando Web App non funziona"""
        user = update.effective_user
        
        fallback_text = f"""
🎮 **CaptainCat Adventure** 🦸‍♂️

{user.first_name}, il gioco è temporaneamente in manutenzione.

🎯 **Come giocare:**
1. Clicca "Link Diretto" qui sotto
2. Oppure usa la Chat Privata
3. Divertiti e scala la classifica!

🏆 I punteggi saranno salvati per questo gruppo!
        """
        
        keyboard = [
            [InlineKeyboardButton("🤖 Chat Privata", url=f"https://t.me/{context.bot.username}")],
            [InlineKeyboardButton("🔗 Link Diretto", url=self._web_app_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(fallback_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(fallback_text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error sending fallback: {e}")

    @handle_errors
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        keyboard = [
            [InlineKeyboardButton("🎮 CaptainCat Game!", callback_data="game"),
             InlineKeyboardButton(self.t(user_id, 'btn_presale'), callback_data="presale")],
            [InlineKeyboardButton(self.t(user_id, 'btn_roadmap'), callback_data="roadmap"),
             InlineKeyboardButton(self.t(user_id, 'btn_team'), callback_data="team")],
            [InlineKeyboardButton("🏆 Game Leaderboard", callback_data="leaderboard"),
             InlineKeyboardButton(self.t(user_id, 'btn_community'), callback_data="community")],
            [InlineKeyboardButton(self.t(user_id, 'btn_help'), callback_data="help"),
             InlineKeyboardButton(self.t(user_id, 'btn_language'), callback_data="language")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = f"""
{self.t(user_id, 'welcome_title')}

{self.t(user_id, 'welcome_msg')}

🎮 **NOVITÀ: CaptainCat Adventure Game!**
Gioca, raccogli CAT coin e scala la classifica!

{self.t(user_id, 'presale_active')}
{self.t(user_id, 'target_listing')}
{self.t(user_id, 'community_goal')}

{self.t(user_id, 'what_know')}
        """
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

    @rate_limit(max_calls=3, period=60, group_max_calls=15, group_period=60)
    @handle_errors
    async def game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando principale per il gioco ottimizzato per gruppi"""
        user_id = update.effective_user.id
        user = update.effective_user
        chat_id = update.effective_chat.id
        is_group = chat_id < 0
        
        logger.info(f"Game command from user {user_id} in {'group' if is_group else 'private'} {chat_id}")
        
        # Testo del gioco personalizzato per gruppo/privato
        if is_group:
            game_text = f"""
🎮 **{user.first_name} sta per giocare a CaptainCat Adventure!** 🦸‍♂️

🌟 **Il Gioco Crypto più Divertente:**
• Raccogli CAT coin d'oro (100 pts)
• Sconfiggi bear market (200 pts) 
• Livelli progressivi crypto-themed
• Scala la classifica del gruppo!

🏆 **Compete nel gruppo per:**
• Essere il #1 della leaderboard
• Ottenere riconoscimenti speciali
• Vincere tornei settimanali
• Guadagnare CAT rewards!

🎯 **Link diretto per una migliore esperienza:**
            """
        else:
            game_text = f"""
🎮 **CaptainCat Adventure** 🦸‍♂️

Ciao {user.first_name}! Pronto per l'avventura crypto?

🌟 **Obiettivi del Gioco:**
• Raccogli CAT coin d'oro (100 punti)
• Sconfiggi i bear market (200 punti)
• Supera tutti i livelli (500 bonus)
• Diventa il #1 della classifica!

🚀 **Meccaniche Speciali:**
• Power-up bull market per boost
• Combo multiplier per punteggi alti
• Nemici a tema crypto
• Livelli progressivi sempre più difficili

💎 **Premi Community:**
• Top player ottengono riconoscimenti speciali
• Tornei settimanali con premi
• Integrazione con il token CAT

🎯 **Tip:** Usa i controlli touch per mobile o le frecce per desktop!
            """
        
        # Pulsanti diversi per gruppo vs privato - usando solo link normali per evitare Web App issues
        try:
            if is_group:
                keyboard = [
                    [InlineKeyboardButton("🎮 Gioca Ora! 🦸‍♂️", url=self._web_app_url)],
                    [InlineKeyboardButton("🤖 Chat Privata", url=f"https://t.me/{context.bot.username}"),
                     InlineKeyboardButton("🏆 Classifica", callback_data="leaderboard")]
                ]
            else:
                # In chat privata, prova prima Web App poi fallback
                try:
                    keyboard = [
                        [InlineKeyboardButton("🎮 Gioca a CaptainCat Adventure! 🦸‍♂️", web_app=WebAppInfo(url=self._web_app_url))],
                        [InlineKeyboardButton("📊 Le Mie Stats", callback_data="mystats"),
                         InlineKeyboardButton("🏆 Classifica", callback_data="leaderboard")]
                    ]
                except Exception:
                    # Fallback se Web App non supportato
                    keyboard = [
                        [InlineKeyboardButton("🎮 Gioca Ora! 🦸‍♂️", url=self._web_app_url)],
                        [InlineKeyboardButton("📊 Le Mie Stats", callback_data="mystats"),
                         InlineKeyboardButton("🏆 Classifica", callback_data="leaderboard")]
                    ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Gestisce sia messaggi che callback
            if update.callback_query:
                await update.callback_query.edit_message_text(game_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(game_text, reply_markup=reply_markup, parse_mode='Markdown')
                
        except BadRequest as e:
            if "Button_type_invalid" in str(e) or "BUTTON_TYPE_INVALID" in str(e):
                logger.warning("Web App button failed, sending fallback")
                await self._send_game_fallback(update, context)
            else:
                raise e

    @rate_limit(max_calls=5, period=60)
    @handle_errors
    async def mystats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Statistiche personali del giocatore"""
        user_id = update.effective_user.id
        user = update.effective_user
        
        stats = await self.db.get_user_best_score(user_id)
        
        if not stats or stats['best_score'] is None:
            no_stats_text = f"""
🎮 **{user.first_name}, non hai ancora giocato!**

🚀 **Inizia subito la tua avventura crypto:**
• Raccogli CAT coin
• Sconfiggi i bear market  
• Scala la classifica
• Diventa una leggenda!

🎯 Clicca "Gioca Ora" per iniziare!
            """
            
            keyboard = [[InlineKeyboardButton("🎮 Gioca Ora!", callback_data="game")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Gestisce sia messaggi che callback
            if update.callback_query:
                await update.callback_query.edit_message_text(no_stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(no_stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Calcola il grado del giocatore
        if stats['best_score'] >= 50000:
            grade = "🏆 CRYPTO LEGEND"
            grade_emoji = "👑"
        elif stats['best_score'] >= 25000:
            grade = "💎 DIAMOND HANDS"
            grade_emoji = "💎"
        elif stats['best_score'] >= 10000:
            grade = "🚀 MOON WALKER"
            grade_emoji = "🚀"
        elif stats['best_score'] >= 5000:
            grade = "⚡ BULL RUNNER"
            grade_emoji = "⚡"
        elif stats['best_score'] >= 1000:
            grade = "🐱 CAT HERO"
            grade_emoji = "🐱"
        else:
            grade = "🌱 ROOKIE TRADER"
            grade_emoji = "🌱"
        
        stats_text = f"""
📊 **Statistiche di {user.first_name}** {grade_emoji}

🏆 **Grado:** {grade}
⭐ **Miglior Punteggio:** {stats['best_score']:,} punti
🎯 **Livello Massimo:** {stats['max_level']}
🪙 **CAT Coin Raccolte:** {stats['total_coins']:,}
💀 **Bear Market Sconfitti:** {stats['total_enemies']:,}
🎮 **Partite Giocate:** {stats['games_played']}

🔥 **Prossimo Obiettivo:**
{self._get_next_goal(stats['best_score'])}
        """
        
        keyboard = [
            [InlineKeyboardButton("🎮 Gioca Ancora!", callback_data="game")],
            [InlineKeyboardButton("🏆 Classifica", callback_data="leaderboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

    def _get_next_goal(self, current_score):
        """Calcola il prossimo obiettivo del giocatore"""
        if current_score < 1000:
            return "Raggiungi 1,000 punti per diventare CAT HERO! 🐱"
        elif current_score < 5000:
            return "Raggiungi 5,000 punti per diventare BULL RUNNER! ⚡"
        elif current_score < 10000:
            return "Raggiungi 10,000 punti per diventare MOON WALKER! 🚀"
        elif current_score < 25000:
            return "Raggiungi 25,000 punti per DIAMOND HANDS! 💎"
        elif current_score < 50000:
            return "Raggiungi 50,000 punti per CRYPTO LEGEND! 👑"
        else:
            return "Sei già una LEGGENDA! Mantieni il primo posto! 🏆"

    @rate_limit(max_calls=3, period=60, group_max_calls=10, group_period=60)
    @handle_errors
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Classifica del gioco ottimizzata"""
        chat_id = update.effective_chat.id
        is_group = chat_id < 0
        
        # Ottieni classifica (specifica del gruppo se in un gruppo)
        leaderboard = await self.db.get_group_leaderboard(chat_id if is_group else None, 10)
        
        if not leaderboard:
            no_players_text = f"""
🏆 **CaptainCat Game Leaderboard** 🏆

🎮 **Nessuno ha ancora giocato!**

Sii il primo eroe a:
• Iniziare l'avventura
• Stabilire il record
• Diventare una leggenda
• Conquistare la classifica!

🚀 **La gloria ti aspetta!**
            """
            
            keyboard = [[InlineKeyboardButton("🎮 Sii il Primo!", callback_data="game")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Gestisce sia messaggi che callback
            if update.callback_query:
                await update.callback_query.edit_message_text(no_players_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(no_players_text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Crea la classifica
        leaderboard_text = "🏆 **CAPTAINCAT GAME LEADERBOARD** 🏆\n\n"
        
        if is_group:
            leaderboard_text += "🎯 **Classifica del Gruppo** 🎯\n\n"
        else:
            leaderboard_text += "🌍 **Classifica Globale** 🌍\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, player in enumerate(leaderboard):
            if i < 3:
                medal = medals[i]
            else:
                medal = f"**{i+1}.**"
            
            name = player['first_name'] or player['username'] or "Anonymous Hero"
            score = player['score']
            level = player['level']
            
            # Emoji per il grado
            if score >= 50000:
                grade_emoji = "👑"
            elif score >= 25000:
                grade_emoji = "💎"
            elif score >= 10000:
                grade_emoji = "🚀"
            elif score >= 5000:
                grade_emoji = "⚡"
            elif score >= 1000:
                grade_emoji = "🐱"
            else:
                grade_emoji = "🌱"
            
            leaderboard_text += f"{medal} {grade_emoji} **{name}** - {score:,} pts (Lv.{level})\n"
        
        leaderboard_text += f"\n🎮 **Vuoi entrare in classifica? Gioca ora!**"
        leaderboard_text += f"\n🏆 **{len(leaderboard)} eroi hanno già giocato!**"
        
        keyboard = [
            [InlineKeyboardButton("🎮 Gioca Ora!", callback_data="game")],
            [InlineKeyboardButton("📊 Le Mie Stats", callback_data="mystats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Gestisce sia messaggi che callback
        if update.callback_query:
            await update.callback_query.edit_message_text(leaderboard_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(leaderboard_text, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def handle_web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce i dati dal gioco Web App"""
        if update.message and update.message.web_app_data:
            try:
                # Parse risultati dal gioco
                data = json.loads(update.message.web_app_data.data)
                
                user = update.effective_user
                chat_id = update.effective_chat.id
                is_group = chat_id < 0
                
                # Salva punteggio nel database
                saved = await self.db.save_score(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    score=data.get('score', 0),
                    level=data.get('level', 1),
                    coins=data.get('coins', 0),
                    enemies=data.get('enemies', 0),
                    play_time=data.get('playTime', 0),
                    group_id=chat_id if is_group else None
                )
                
                # Messaggio di congratulazioni
                score = data.get('score', 0)
                level = data.get('level', 1)
                coins = data.get('coins', 0)
                enemies = data.get('enemies', 0)
                
                # Determina il tipo di messaggio basato sul punteggio
                if score >= 50000:
                    message = f"👑 **LEGGENDA ASSOLUTA!** 👑\n{user.first_name} ha raggiunto {score:,} punti! 🏆✨"
                    celebration = "🎊🎊🎊"
                elif score >= 25000:
                    message = f"💎 **DIAMOND HANDS ACHIEVED!** 💎\n{user.first_name} ha totalizzato {score:,} punti! 🚀🌙"
                    celebration = "🔥🔥🔥"
                elif score >= 10000:
                    message = f"🚀 **MOON WALKER!** 🚀\n{user.first_name} ha fatto {score:,} punti! 🌙⭐"
                    celebration = "⚡⚡⚡"
                elif score >= 5000:
                    message = f"⚡ **BULL RUNNER!** ⚡\n{user.first_name} ha raggiunto {score:,} punti! 📈💪"
                    celebration = "🎯🎯🎯"
                elif score >= 1000:
                    message = f"🐱 **CAT HERO!** 🐱\n{user.first_name} ha totalizzato {score:,} punti! 🎮💫"
                    celebration = "🎉🎉🎉"
                else:
                    message = f"🌱 **Ottimo inizio!** 🌱\n{user.first_name} ha fatto {score:,} punti! 💪🎮"
                    celebration = "👏👏👏"
                
                # Statistiche dettagliate
                stats_detail = f"\n\n📊 **Statistiche Partita:**\n"
                stats_detail += f"🪙 CAT Coin: {coins}\n"
                stats_detail += f"💀 Bear Market sconfitti: {enemies}\n"
                stats_detail += f"🎯 Livello raggiunto: {level}\n"
                
                if not saved:
                    stats_detail += "\n⚠️ *Punteggio non salvato - database temporaneamente non disponibile*"
                
                # Controlla se è un nuovo record del gruppo
                if is_group and saved:
                    leaderboard = await self.db.get_group_leaderboard(chat_id, 1)
                    if leaderboard and leaderboard[0]['score'] <= score and leaderboard[0]['user_id'] == user.id:
                        message += f"\n\n🏆 **NUOVO RECORD DEL GRUPPO!** 🏆 {celebration}"
                
                message += stats_detail
                
                keyboard = [
                    [InlineKeyboardButton("🎮 Gioca Ancora!", callback_data="game")],
                    [InlineKeyboardButton("📊 Le Mie Stats", callback_data="mystats"),
                     InlineKeyboardButton("🏆 Classifica", callback_data="leaderboard")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                
            except json.JSONDecodeError:
                await update.message.reply_text("❌ Errore nel salvare i risultati del gioco. Riprova!")
            except Exception as e:
                logger.error(f"Errore handling web app data: {e}")
                await update.message.reply_text("⚠️ Problema temporaneo nel salvare i dati. Il gioco funziona comunque!")

    # Altri metodi esistenti rimangono identici ma con handle_errors...
    @handle_errors
    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        available_langs = get_available_languages()
        
        keyboard = []
        for lang_code, lang_name in available_langs.items():
            keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        current_lang = self.get_user_language(user_id)
        flag = get_language_flag(current_lang)
        
        lang_msg = f"🌍 **CHOOSE YOUR LANGUAGE / SCEGLI LA TUA LINGUA**\n\n{flag} Current/Attuale: {available_langs.get(current_lang, 'Unknown')}"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(lang_msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(lang_msg, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                f"🌍 {self.t(user_id, 'language_changed')}\n\nLingua impostata: {lang_name}",
                parse_mode='Markdown'
            )
            return
        
        # Handler per i bottoni del gioco
        if query.data == "game":
            await self.game_command(update, context)
        elif query.data == "mystats":
            await self.mystats_command(update, context)
        elif query.data == "leaderboard":
            await self.leaderboard_command(update, context)
        # Altri bottoni esistenti
        elif query.data == "presale":
            await self.presale_command(update, context)
        elif query.data == "roadmap":
            await self.roadmap_command(update, context)
        elif query.data == "team":
            await self.team_command(update, context)
        elif query.data == "community":
            await self.community_command(update, context)
        elif query.data == "help":
            await self.help_command(update, context)
        elif query.data == "language":
            await self.language_command(update, context)

    # Metodi esistenti per tutti gli altri comandi con handle_errors...
    @handle_errors
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        db_status = "✅ Connesso" if self.db.pool else "⚠️ Non disponibile"
        
        status_msg = f"""
{self.t(user_id, 'status_title')}

✅ **Bot Online e Funzionante**
🎮 **CaptainCat Game: ATTIVO**
📡 **Server: Render.com**
⏰ **Uptime: 24/7**
🔄 **Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}**
🌍 **Lingue supportate: 5**
🗃️ **Database: {db_status}**
🛡️ **Rate Limiting: ATTIVO**
🔧 **Error Handling: OTTIMIZZATO**

💪 **Pronto ad aiutare la community e ospitare tornei di gioco!**
        """
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    @handle_errors
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        help_text = f"""{self.t(user_id, 'help_commands')}

🎮 **COMANDI GIOCO:**
/game - Avvia CaptainCat Adventure
/play - Alias per /game
/mystats - Le tue statistiche di gioco
/leaderboard - Classifica del gioco
/gametop - Alias per /leaderboard

⚡ **OTTIMIZZAZIONI:**
• Rate limiting per gruppi
• Fallback automatico
• Error handling avanzato
• Performance migliorate"""
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')

    @handle_errors
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• 5% Game Rewards 🎮

🚀 **Prossimo step: LISTING su DEX principali!**
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Partecipa alla Prevendita", url="https://t.me/Captain_cat_Cain")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(price_info, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def presale_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• Game Beta Access: INCLUSO! 🎮

📱 **Come Partecipare:**
1. Unisciti al gruppo Telegram
2. Contatta gli admin
3. Invia TON
4. Ricevi CAT tokens + Game Access

🚀 **Non perdere l'opportunità!**
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Unisciti alla Prevendita", url="https://t.me/Captain_cat_Cain")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(presale_info, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(presale_info, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def roadmap_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• CaptainCat Game LIVE! 🎮

🎯 **Fase 3 - Listing** (Q1 2025)
• Listing su DEX principali
• CoinMarketCap & CoinGecko
• Influencer partnerships
• Tornei di gioco

🚀 **Fase 4 - Ecosistema** (Q2 2025)
• Game espansione
• NFT Collection
• Staking rewards
• DAO governance
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(roadmap_info, parse_mode='Markdown')
        else:
            await update.message.reply_text(roadmap_info, parse_mode='Markdown')

    @handle_errors
    async def team_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        team_info = f"""
{self.t(user_id, 'team_title')}

🦸‍♂️ **CZ - Founder & CEO**
Visionario crypto con anni di esperienza in DeFi e GameFi

💻 **Dr. Eliax - Lead Developer**  
Esperto in smart contracts e sicurezza blockchain

📈 **Rejane - Marketing Manager**
Specialista in crescita community e marketing virale

🎮 **Game Team - CaptainCat Studios**
Sviluppatori specializzati in Web3 gaming

🔒 **Team Verificato e Doxxed**
🏆 **Track Record Comprovato**
💪 **Esperienza Combinata: 20+ anni**
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(team_info, parse_mode='Markdown')
        else:
            await update.message.reply_text(team_info, parse_mode='Markdown')

    @handle_errors
    async def utility_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        utility_info = f"""
{self.t(user_id, 'utility_title')}

🎮 **CaptainCat Adventure Game**
• Play-to-Earn mechanics
• Classifica competitiva
• Tornei settimanali
• CAT rewards per top player

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

    @handle_errors
    async def community_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        community_info = f"""
{self.t(user_id, 'community_title')}

🎯 **Obiettivo: 10K Membri!**
👥 **Attuali: 2.5K+ Eroi**
🎮 **Giocatori Attivi: In Crescita!**

🔗 **Links Ufficiali:**
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Telegram Main", url="https://t.me/Captain_cat_Cain")],
            [InlineKeyboardButton("🌐 Website", url="https://captaincat.token")],
            [InlineKeyboardButton("🎮 Game Community", callback_data="leaderboard")],
            [InlineKeyboardButton("💎 Sponsor: BLUM", url="https://www.blum.io/")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(community_info, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(community_info, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def staking_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• Game boost per staker
• Tornei esclusivi

💰 **Rewards Distribuiti:**
• Daily: 0.1% del pool
• Weekly: Bonus NFT
• Monthly: Token burn

🚀 **Launch: Post-Listing**
        """
        
        await update.message.reply_text(staking_info, parse_mode='Markdown')

    @handle_errors
    async def nft_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• Game advantages
• Staking multipliers
• Governance votes
• Exclusive tournaments

🎨 **Arte:** Pixel art supereroi felini
🚀 **Mint:** Q2 2025
        """
        
        await update.message.reply_text(nft_info, parse_mode='Markdown')

    @rate_limit(max_calls=10, period=60, group_max_calls=20, group_period=60)
    @handle_errors
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message.text.lower()
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Eroe"
        
        # Parole chiave per il gioco
        game_words = ['gioco', 'game', 'play', 'giocare', 'gioca', 'adventure', 'avventura', 'punteggio', 'score', 'classifica', 'leaderboard', 'stats']
        
        if any(word in message for word in game_words):
            responses = [
                f"🎮 {user_name}! CaptainCat Adventure ti aspetta! Raccogli CAT coin e sconfiggi i bear market!",
                f"🚀 Pronto per l'avventura, {user_name}? Il gioco è pieno di sorprese crypto!",
                f"⚡ {user_name}, diventa il re della classifica! Usa /game per iniziare!"
            ]
            response = random.choice(responses) + "\n\n🎯 Usa /game per giocare subito!"
        else:
            response = self.generate_ai_response(message, user_name, user_id)
        
        await update.message.reply_text(response, parse_mode='Markdown')

    def generate_ai_response(self, message: str, user_name: str, user_id: int) -> str:
        # Logica esistente per le risposte AI + aggiunta delle risposte per il gioco
        greetings = ['ciao', 'salve', 'buongiorno', 'buonasera', 'hey', 'hello', 'hi', 'hola', 'salut', 'hallo', 'guten tag']
        price_words = ['prezzo', 'costo', 'quanto costa', 'valore', 'price', 'cost', 'precio', 'coste', 'prix', 'preis', 'kosten']
        
        if any(word in message for word in greetings):
            responses = [self.t(user_id, 'greeting_1'), self.t(user_id, 'greeting_2'), self.t(user_id, 'greeting_3')]
            return f"🐱‍🦸 {user_name}! " + random.choice(responses) + "\n\n🎮 Non dimenticare di provare CaptainCat Adventure Game!"
        elif any(word in message for word in price_words):
            responses = [self.t(user_id, 'price_1'), self.t(user_id, 'price_2'), self.t(user_id, 'price_3')]
            return "💎 " + random.choice(responses) + "\n\n🚀 Usa /presale per tutti i dettagli!"
        else:
            responses = [
                self.t(user_id, 'default_1').format(user_name),
                self.t(user_id, 'default_2').format(user_name),
                self.t(user_id, 'default_3').format(user_name),
                self.t(user_id, 'default_4').format(user_name)
            ]
            return random.choice(responses) + f"\n\n❓ {self.t(user_id, 'try_commands')}"

    async def initialize_database(self):
        """Inizializza il database all'avvio"""
        await self.db.init_pool()

    def run(self):
        print("🐱‍🦸 CaptainCat Bot with Fixed Error Handling starting on Render...")
        
        # Inizializza database
        async def startup():
            await self.initialize_database()
            logger.info("Database initialized for game features")
        
        # Esegui startup con gestione moderna di asyncio
        try:
            # Usa new_event_loop per evitare deprecation warning
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(startup())
        except Exception as e:
            logger.error(f"Startup error: {e}")
        
        # Configurazioni per stabilità
        self.app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=1.0,
            timeout=10,
            close_loop=False  # Evita problemi con multiple instances
        )

# Script principale
if __name__ == "__main__":
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ ERRORE: Variabile BOT_TOKEN non trovata!")
        print("💡 Configura la variabile d'ambiente BOT_TOKEN su Render")
    else:
        print(f"🚀 Starting CaptainCat Bot with Fixed Error Handling...")
        bot = CaptainCatBot(BOT_TOKEN)
        bot.run()
