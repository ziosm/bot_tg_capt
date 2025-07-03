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
                        await update.message.reply_text("⏱️ Too fast! Try again in a minute.")
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
                    await update.message.reply_text("🔧 Temporary issue. Try again in a moment!")
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
                "🔧 A temporary error occurred. Try again in a moment!"
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
        self.db = GameDatabase()
        self._web_app_url = os.environ.get('WEBAPP_URL', 'https://captaincat-game.onrender.com')
        self.setup_handlers()

    def setup_handlers(self):
        # Basic handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("price", self.price_command))
        self.app.add_handler(CommandHandler("roadmap", self.roadmap_command))
        self.app.add_handler(CommandHandler("team", self.team_command))
        self.app.add_handler(CommandHandler("utility", self.utility_command))
        self.app.add_handler(CommandHandler("presale", self.presale_command))
        self.app.add_handler(CommandHandler("community", self.community_command))
        self.app.add_handler(CommandHandler("staking", self.staking_command))
        self.app.add_handler(CommandHandler("nft", self.nft_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        
        # Game handlers with rate limiting
        self.app.add_handler(CommandHandler("game", self.game_command))
        self.app.add_handler(CommandHandler("play", self.game_command))
        self.app.add_handler(CommandHandler("mystats", self.mystats_command))
        self.app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        self.app.add_handler(CommandHandler("gametop", self.leaderboard_command))
        
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Web App data handler
        self.app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_web_app_data))
        
        # Add error handler
        self.app.add_error_handler(error_handler)

    async def _send_game_fallback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fallback when Web App doesn't work"""
        user = update.effective_user
        
        fallback_text = f"""
🎮 **CaptainCat Adventure** 🦸‍♂️

{user.first_name}, the game is temporarily under maintenance.

🎯 **How to play:**
1. Click "Direct Link" below
2. Or use Private Chat
3. Have fun and climb the leaderboard!

🏆 Scores will be saved for this group!
        """
        
        keyboard = [
            [InlineKeyboardButton("🤖 Private Chat", url=f"https://t.me/{context.bot.username}")],
            [InlineKeyboardButton("🔗 Direct Link", url=self._web_app_url)]
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
        keyboard = [
            [InlineKeyboardButton("🎮 CaptainCat Game!", callback_data="game"),
             InlineKeyboardButton("💎 Presale", callback_data="presale")],
            [InlineKeyboardButton("🗺️ Roadmap", callback_data="roadmap"),
             InlineKeyboardButton("👥 Team", callback_data="team")],
            [InlineKeyboardButton("🏆 Game Leaderboard", callback_data="leaderboard"),
             InlineKeyboardButton("📱 Community", callback_data="community")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = f"""
🐱‍🦸 **WELCOME TO CAPTAINCAT!**

Hello future hero! I'm CaptainCat AI, the superhero of meme coins!

🎮 **NEW: CaptainCat Adventure Game!**
Play, collect CAT coins and climb the leaderboard!

🚀 **We're in PRESALE!**
💎 **1500 TON for listing**
🎯 **Goal: 10K community members**

What do you want to know today?
        """
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

    @rate_limit(max_calls=3, period=60, group_max_calls=15, group_period=60)
    @handle_errors
    async def game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main game command optimized for groups"""
        user_id = update.effective_user.id
        user = update.effective_user
        chat_id = update.effective_chat.id
        is_group = chat_id < 0
        
        logger.info(f"Game command from user {user_id} in {'group' if is_group else 'private'} {chat_id}")
        
        # Game text customized for group/private
        if is_group:
            game_text = f"""
🎮 **{user.first_name} is about to play CaptainCat Adventure!** 🦸‍♂️

🌟 **The Most Fun Crypto Game:**
• Collect golden CAT coins (100 pts)
• Defeat bear markets (200 pts) 
• Progressive crypto-themed levels
• Climb the group leaderboard!

🏆 **Compete in the group for:**
• Being #1 on the leaderboard
• Getting special recognition
• Winning weekly tournaments
• Earning CAT rewards!

🎯 **Direct link for better experience:**
            """
        else:
            game_text = f"""
🎮 **CaptainCat Adventure** 🦸‍♂️

Hello {user.first_name}! Ready for the crypto adventure?

🌟 **Game Objectives:**
• Collect golden CAT coins (100 points)
• Defeat bear markets (200 points)
• Complete all levels (500 bonus)
• Become #1 on the leaderboard!

🚀 **Special Mechanics:**
• Bull market power-ups for boost
• Combo multiplier for high scores
• Crypto-themed enemies
• Progressive levels getting harder

💎 **Community Rewards:**
• Top players get special recognition
• Weekly tournaments with prizes
• CAT token integration

🎯 **Tip:** Use touch controls for mobile or arrows for desktop!
            """
        
        # Different buttons for group vs private - using only normal links to avoid Web App issues
        try:
            if is_group:
                keyboard = [
                    [InlineKeyboardButton("🎮 Play Now! 🦸‍♂️", url=self._web_app_url)],
                    [InlineKeyboardButton("🤖 Private Chat", url=f"https://t.me/{context.bot.username}"),
                     InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
                ]
            else:
                # In private chat, try Web App first then fallback
                try:
                    keyboard = [
                        [InlineKeyboardButton("🎮 Play CaptainCat Adventure! 🦸‍♂️", web_app=WebAppInfo(url=self._web_app_url))],
                        [InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
                         InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
                    ]
                except Exception:
                    # Fallback if Web App not supported
                    keyboard = [
                        [InlineKeyboardButton("🎮 Play Now! 🦸‍♂️", url=self._web_app_url)],
                        [InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
                         InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
                    ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Handle both messages and callbacks
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
        """Player personal statistics"""
        user_id = update.effective_user.id
        user = update.effective_user
        
        stats = await self.db.get_user_best_score(user_id)
        
        if not stats or stats['best_score'] is None:
            no_stats_text = f"""
🎮 **{user.first_name}, you haven't played yet!**

🚀 **Start your crypto adventure now:**
• Collect CAT coins
• Defeat bear markets  
• Climb the leaderboard
• Become a legend!

🎯 Click "Play Now" to start!
            """
            
            keyboard = [[InlineKeyboardButton("🎮 Play Now!", callback_data="game")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Handle both messages and callbacks
            if update.callback_query:
                await update.callback_query.edit_message_text(no_stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(no_stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Calculate player grade
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
📊 **{user.first_name}'s Statistics** {grade_emoji}

🏆 **Grade:** {grade}
⭐ **Best Score:** {stats['best_score']:,} points
🎯 **Max Level:** {stats['max_level']}
🪙 **CAT Coins Collected:** {stats['total_coins']:,}
💀 **Bear Markets Defeated:** {stats['total_enemies']:,}
🎮 **Games Played:** {stats['games_played']}

🔥 **Next Goal:**
{self._get_next_goal(stats['best_score'])}
        """
        
        keyboard = [
            [InlineKeyboardButton("🎮 Play Again!", callback_data="game")],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Handle both messages and callbacks
        if update.callback_query:
            await update.callback_query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

    def _get_next_goal(self, current_score):
        """Calculate player's next goal"""
        if current_score < 1000:
            return "Reach 1,000 points to become CAT HERO! 🐱"
        elif current_score < 5000:
            return "Reach 5,000 points to become BULL RUNNER! ⚡"
        elif current_score < 10000:
            return "Reach 10,000 points to become MOON WALKER! 🚀"
        elif current_score < 25000:
            return "Reach 25,000 points for DIAMOND HANDS! 💎"
        elif current_score < 50000:
            return "Reach 50,000 points for CRYPTO LEGEND! 👑"
        else:
            return "You're already a LEGEND! Keep the first place! 🏆"

    @rate_limit(max_calls=3, period=60, group_max_calls=10, group_period=60)
    @handle_errors
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Optimized game leaderboard"""
        chat_id = update.effective_chat.id
        is_group = chat_id < 0
        
        # Get leaderboard (group-specific if in a group)
        leaderboard = await self.db.get_group_leaderboard(chat_id if is_group else None, 10)
        
        if not leaderboard:
            no_players_text = f"""
🏆 **CaptainCat Game Leaderboard** 🏆

🎮 **No one has played yet!**

Be the first hero to:
• Start the adventure
• Set the record
• Become a legend
• Conquer the leaderboard!

🚀 **Glory awaits you!**
            """
            
            keyboard = [[InlineKeyboardButton("🎮 Be the First!", callback_data="game")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Handle both messages and callbacks
            if update.callback_query:
                await update.callback_query.edit_message_text(no_players_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(no_players_text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Create leaderboard
        leaderboard_text = "🏆 **CAPTAINCAT GAME LEADERBOARD** 🏆\n\n"
        
        if is_group:
            leaderboard_text += "🎯 **Group Leaderboard** 🎯\n\n"
        else:
            leaderboard_text += "🌍 **Global Leaderboard** 🌍\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, player in enumerate(leaderboard):
            if i < 3:
                medal = medals[i]
            else:
                medal = f"**{i+1}.**"
            
            name = player['first_name'] or player['username'] or "Anonymous Hero"
            score = player['score']
            level = player['level']
            
            # Grade emoji
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
        
        leaderboard_text += f"\n🎮 **Want to join the leaderboard? Play now!**"
        leaderboard_text += f"\n🏆 **{len(leaderboard)} heroes have already played!**"
        
        keyboard = [
            [InlineKeyboardButton("🎮 Play Now!", callback_data="game")],
            [InlineKeyboardButton("📊 My Stats", callback_data="mystats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Handle both messages and callbacks
        if update.callback_query:
            await update.callback_query.edit_message_text(leaderboard_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(leaderboard_text, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def handle_web_app_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle data from Web App game"""
        if update.message and update.message.web_app_data:
            try:
                # Parse game results
                data = json.loads(update.message.web_app_data.data)
                
                user = update.effective_user
                chat_id = update.effective_chat.id
                is_group = chat_id < 0
                
                # Save score to database
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
                
                # Congratulations message
                score = data.get('score', 0)
                level = data.get('level', 1)
                coins = data.get('coins', 0)
                enemies = data.get('enemies', 0)
                
                # Determine message type based on score
                if score >= 50000:
                    message = f"👑 **ABSOLUTE LEGEND!** 👑\n{user.first_name} reached {score:,} points! 🏆✨"
                    celebration = "🎊🎊🎊"
                elif score >= 25000:
                    message = f"💎 **DIAMOND HANDS ACHIEVED!** 💎\n{user.first_name} scored {score:,} points! 🚀🌙"
                    celebration = "🔥🔥🔥"
                elif score >= 10000:
                    message = f"🚀 **MOON WALKER!** 🚀\n{user.first_name} got {score:,} points! 🌙⭐"
                    celebration = "⚡⚡⚡"
                elif score >= 5000:
                    message = f"⚡ **BULL RUNNER!** ⚡\n{user.first_name} reached {score:,} points! 📈💪"
                    celebration = "🎯🎯🎯"
                elif score >= 1000:
                    message = f"🐱 **CAT HERO!** 🐱\n{user.first_name} scored {score:,} points! 🎮💫"
                    celebration = "🎉🎉🎉"
                else:
                    message = f"🌱 **Great start!** 🌱\n{user.first_name} got {score:,} points! 💪🎮"
                    celebration = "👏👏👏"
                
                # Detailed statistics
                stats_detail = f"\n\n📊 **Game Statistics:**\n"
                stats_detail += f"🪙 CAT Coins: {coins}\n"
                stats_detail += f"💀 Bear Markets defeated: {enemies}\n"
                stats_detail += f"🎯 Level reached: {level}\n"
                
                if not saved:
                    stats_detail += "\n⚠️ *Score not saved - database temporarily unavailable*"
                
                # Check if it's a new group record
                if is_group and saved:
                    leaderboard = await self.db.get_group_leaderboard(chat_id, 1)
                    if leaderboard and leaderboard[0]['score'] <= score and leaderboard[0]['user_id'] == user.id:
                        message += f"\n\n🏆 **NEW GROUP RECORD!** 🏆 {celebration}"
                
                message += stats_detail
                
                keyboard = [
                    [InlineKeyboardButton("🎮 Play Again!", callback_data="game")],
                    [InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
                     InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                
            except json.JSONDecodeError:
                await update.message.reply_text("❌ Error saving game results. Try again!")
            except Exception as e:
                logger.error(f"Error handling web app data: {e}")
                await update.message.reply_text("⚠️ Temporary issue saving data. The game still works!")

    @handle_errors
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # Game button handlers
        if query.data == "game":
            await self.game_command(update, context)
        elif query.data == "mystats":
            await self.mystats_command(update, context)
        elif query.data == "leaderboard":
            await self.leaderboard_command(update, context)
        # Other existing buttons
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

    @handle_errors
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db_status = "✅ Connected" if self.db.pool else "⚠️ Not available"
        
        status_msg = f"""
🤖 **CAPTAINCAT BOT STATUS**

✅ **Bot Online and Working**
🎮 **CaptainCat Game: ACTIVE**
📡 **Server: Render.com**
⏰ **Uptime: 24/7**
🔄 **Last update: {datetime.now().strftime('%d/%m/%Y %H:%M')}**
🗃️ **Database: {db_status}**
🛡️ **Rate Limiting: ACTIVE**
🔧 **Error Handling: OPTIMIZED**

💪 **Ready to help the community and host game tournaments!**
        """
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    @handle_errors
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = f"""🐱‍🦸 **CAPTAINCAT BOT COMMANDS**

/start - Start conversation
/help - Show this menu
/price - Price and tokenomics info
/roadmap - Project roadmap
/team - Meet the team
/utility - Token utility
/presale - Presale info
/community - Community links
/game - GameFi info
/staking - Staking rewards info
/nft - NFT collection info
/status - Bot status

🚀 **Just write and I'll respond!**
Examples: "how much?", "when listing?", "how it works?"

🎮 **GAME COMMANDS:**
/game - Start CaptainCat Adventure
/play - Alias for /game
/mystats - Your game statistics
/leaderboard - Game leaderboard
/gametop - Alias for /leaderboard

⚡ **OPTIMIZATIONS:**
• Rate limiting for groups
• Automatic fallback
• Advanced error handling
• Improved performance"""
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')

    @handle_errors
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        price_info = f"""
💎 **CAPTAINCAT TOKENOMICS**

🔥 **Presale Active!**
💰 **Listing Target: 1500 TON**
📊 **Total Supply: 1,000,000,000 CAT**

📈 **Distribution:**
• 40% Presale
• 30% DEX Liquidity  
• 15% Team (locked)
• 10% Marketing
• 5% Game Rewards 🎮

🚀 **Next step: LISTING on major DEXes!**
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Join Presale", url="https://t.me/Captain_cat_Cain")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(price_info, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def presale_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        presale_info = f"""
💎 **CAPTAINCAT PRESALE**

🔥 **PHASE 2 ACTIVE!**

💰 **Target: 1500 TON for listing**
📊 **Progress: 45% completed**
⏰ **Time remaining: Limited!**

🎯 **Presale Bonuses:**
• Early Bird: +20% tokens
• Whale Bonus: +15% (>50 TON)
• Community Bonus: +10%
• Game Beta Access: INCLUDED! 🎮

📱 **How to Participate:**
1. Join Telegram group
2. Contact admins
3. Send TON
4. Receive CAT tokens + Game Access

🚀 **Don't miss the opportunity!**
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Join Presale", url="https://t.me/Captain_cat_Cain")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(presale_info, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(presale_info, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def roadmap_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        roadmap_info = f"""
🗺️ **CAPTAINCAT ROADMAP**

✅ **Phase 1 - Launch** (COMPLETED)
• Smart contract developed
• Security audit
• Telegram community
• Website and branding

🔄 **Phase 2 - Presale** (IN PROGRESS)
• Private presale
• Strategic partnerships  
• Marketing campaign
• CaptainCat Game LIVE! 🎮

🎯 **Phase 3 - Listing** (Q1 2025)
• Listing on major DEXes
• CoinMarketCap & CoinGecko
• Influencer partnerships
• Game tournaments

🚀 **Phase 4 - Ecosystem** (Q2 2025)
• Game expansion
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
        team_info = f"""
👥 **CAPTAINCAT TEAM**

🦸‍♂️ **CZ - Founder & CEO**
Crypto visionary with years of DeFi and GameFi experience

💻 **Dr. Eliax - Lead Developer**  
Expert in smart contracts and blockchain security

📈 **Rejane - Marketing Manager**
Specialist in community growth and viral marketing

🎮 **Game Team - CaptainCat Studios**
Developers specialized in Web3 gaming

🔒 **Verified and Doxxed Team**
🏆 **Proven Track Record**
💪 **Combined Experience: 20+ years**
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(team_info, parse_mode='Markdown')
        else:
            await update.message.reply_text(team_info, parse_mode='Markdown')

    @handle_errors
    async def utility_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        utility_info = f"""
⚡ **CAPTAINCAT UTILITY**

🎮 **CaptainCat Adventure Game**
• Play-to-Earn mechanics
• Competitive leaderboard
• Weekly tournaments
• CAT rewards for top players

💎 **Staking Rewards**
• Stake CAT, earn rewards
• Lock periods: 30/90/180 days
• APY up to 150%

🖼️ **NFT Collection**
• CaptainCat Heroes NFT
• In-game utility
• Limited collections

🗳️ **DAO Governance**
• Vote on decisions
• Propose improvements  
• Guide the future

🔥 **Token Burn**
• Monthly burns
• Deflationary mechanics
• Value increase
        """
        
        await update.message.reply_text(utility_info, parse_mode='Markdown')

    @handle_errors
    async def community_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        community_info = f"""
📱 **CAPTAINCAT COMMUNITY**

🎯 **Goal: 10K Members!**
👥 **Current: 2.5K+ Heroes**
🎮 **Active Players: Growing!**

🔗 **Official Links:**
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
        staking_info = f"""
💎 **CAPTAINCAT STAKING**

🔒 **Stake CAT, Earn Rewards!**

📊 **Available Pools:**
• 30 days - APY 50%
• 90 days - APY 100%  
• 180 days - APY 150%

🎁 **Bonus Features:**
• Automatic compound
• Early unstake (10% penalty)
• Game boost for stakers
• Exclusive tournaments

💰 **Rewards Distributed:**
• Daily: 0.1% of pool
• Weekly: Bonus NFT
• Monthly: Token burn

🚀 **Launch: Post-Listing**
        """
        
        await update.message.reply_text(staking_info, parse_mode='Markdown')

    @handle_errors
    async def nft_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nft_info = f"""
🖼️ **CAPTAINCAT NFT COLLECTION**

🦸‍♂️ **CaptainCat Heroes**
• 10,000 unique NFTs
• 100+ rare traits
• In-game utility

🏆 **Rarity:**
• Common (60%) - Boost +10%
• Rare (25%) - Boost +25%
• Epic (10%) - Boost +50%
• Legendary (5%) - Boost +100%

⚡ **NFT Utility:**
• Game advantages
• Staking multipliers
• Governance votes
• Exclusive tournaments

🎨 **Art:** Pixel art superhero cats
🚀 **Mint:** Q2 2025
        """
        
        await update.message.reply_text(nft_info, parse_mode='Markdown')

    @rate_limit(max_calls=10, period=60, group_max_calls=20, group_period=60)
    @handle_errors
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message.text.lower()
        user_name = update.effective_user.first_name or "Hero"
        
        # Game keywords
        game_words = ['game', 'play', 'adventure', 'score', 'leaderboard', 'stats']
        
        if any(word in message for word in game_words):
            responses = [
                f"🎮 {user_name}! CaptainCat Adventure awaits! Collect CAT coins and defeat bear markets!",
                f"🚀 Ready for adventure, {user_name}? The game is full of crypto surprises!",
                f"⚡ {user_name}, become the leaderboard king! Use /game to start!"
            ]
            response = random.choice(responses) + "\n\n🎯 Use /game to play now!"
        else:
            response = self.generate_ai_response(message, user_name)
        
        await update.message.reply_text(response, parse_mode='Markdown')

    def generate_ai_response(self, message: str, user_name: str) -> str:
        # AI response logic + game responses
        greetings = ['hello', 'hi', 'hey', 'good morning', 'good evening', 'greetings']
        price_words = ['price', 'cost', 'how much', 'value', 'worth']
        
        if any(word in message for word in greetings):
            responses = [
                "🐱‍🦸 Hello hero! Welcome to CaptainCat community! How can I help you today?",
                "🚀 Meow! I'm CaptainCat AI, your feline crypto assistant! What do you want to know?",
                "⚡ Greetings, future millionaire! CaptainCat is here to guide you to the moon! 🌙"
            ]
            return f"🐱‍🦸 {user_name}! " + random.choice(responses) + "\n\n🎮 Don't forget to try CaptainCat Adventure Game!"
        elif any(word in message for word in price_words):
            responses = [
                "💎 CaptainCat price is constantly evolving! We're still in presale phase.",
                "📈 During presale, every token is worth gold! Get ready for takeoff! 🚀",
                "🎯 The real value of CaptainCat will be seen after DEX listing!"
            ]
            return "💎 " + random.choice(responses) + "\n\n🚀 Use /presale for all details!"
        else:
            responses = [
                f"Interesting question, {user_name}! I'm here to help you with everything about CaptainCat!",
                f"{user_name}, use /help to see all available commands!",
                f"Hello {user_name}! Tell me what you want to know about CaptainCat and I'll answer right away!",
                f"{user_name}, I'm CaptainCat AI! I can answer any question about the project!"
            ]
            return random.choice(responses) + f"\n\n❓ Try commands like: /price, /roadmap, /presale"

    async def initialize_database(self):
        """Initialize database on startup"""
        await self.db.init_pool()

    def run(self):
        print("🐱‍🦸 CaptainCat Bot (English Only) starting on Render...")
        
        # Initialize database
        async def startup():
            await self.initialize_database()
            logger.info("Database initialized for game features")
        
        # Run startup with modern asyncio handling
        try:
            # Use new_event_loop to avoid deprecation warning
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(startup())
        except Exception as e:
            logger.error(f"Startup error: {e}")
        
        # Stability configurations
        self.app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=1.0,
            timeout=10,
            close_loop=False  # Avoid issues with multiple instances
        )

# Main script
if __name__ == "__main__":
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not found!")
        print("💡 Configure BOT_TOKEN environment variable on Render")
    else:
        print(f"🚀 Starting CaptainCat Bot (English Only)...")
        bot = CaptainCatBot(BOT_TOKEN)
        bot.run()
