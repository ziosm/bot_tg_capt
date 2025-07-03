import os
import asyncio
import logging
import aiohttp
import json
import asyncpg
import time
import hashlib
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest, TimedOut, NetworkError
import random
from functools import wraps
from typing import Dict, List, Optional

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
TON_API_KEY = os.environ.get('TON_API_KEY')  # TON Center API key
TOKEN_CONTRACT_ADDRESS = os.environ.get('TOKEN_CONTRACT_ADDRESS')  # Your CAT token contract
NOTIFICATION_CHAT_ID = os.environ.get('NOTIFICATION_CHAT_ID')  # Chat ID for transaction notifications

# Anti-spam configuration
SPAM_THRESHOLD = {
    'messages_per_minute': 10,
    'messages_per_hour': 60,
    'duplicate_threshold': 3,
    'link_threshold': 5,
    'emoji_threshold': 20
}

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
                    if not is_group:
                        await update.message.reply_text("⏱️ Too fast! Try again in a minute.")
                    return
            else:
                calls[user_id] = []
            
            # Rate limiting per gruppo
            if is_group:
                if chat_id in group_calls:
                    group_calls[chat_id] = [call for call in group_calls[chat_id] if call > now - group_period]
                    if len(group_calls[chat_id]) >= group_max_calls:
                        return
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
                await self._send_game_fallback(update, context)
            elif "message is not modified" in str(e).lower():
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if "Conflict" in str(context.error):
        logger.warning("Conflict error - possibly multiple instances running")
        return
    
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "🔧 A temporary error occurred. Try again in a moment!"
            )
        except Exception:
            pass

class AntiSpamSystem:
    def __init__(self):
        self.user_messages: Dict[int, List[dict]] = {}
        self.spam_scores: Dict[int, float] = {}
        self.banned_users: Dict[int, datetime] = {}
        self.message_hashes: Dict[str, List[datetime]] = {}
        
    def clean_old_data(self):
        """Clean old data to prevent memory leaks"""
        now = datetime.now()
        cutoff = now - timedelta(hours=2)
        
        # Clean user messages
        for user_id in list(self.user_messages.keys()):
            self.user_messages[user_id] = [
                msg for msg in self.user_messages[user_id] 
                if msg['timestamp'] > cutoff
            ]
            if not self.user_messages[user_id]:
                del self.user_messages[user_id]
        
        # Clean message hashes
        for msg_hash in list(self.message_hashes.keys()):
            self.message_hashes[msg_hash] = [
                timestamp for timestamp in self.message_hashes[msg_hash]
                if timestamp > cutoff
            ]
            if not self.message_hashes[msg_hash]:
                del self.message_hashes[msg_hash]
        
        # Clean expired bans
        self.banned_users = {
            user_id: ban_time for user_id, ban_time in self.banned_users.items()
            if ban_time > now
        }
    
    def calculate_spam_score(self, message: str, user_id: int) -> float:
        """Calculate spam score for a message"""
        score = 0.0
        now = datetime.now()
        
        # Check message frequency
        if user_id in self.user_messages:
            recent_messages = [
                msg for msg in self.user_messages[user_id]
                if msg['timestamp'] > now - timedelta(minutes=1)
            ]
            if len(recent_messages) > SPAM_THRESHOLD['messages_per_minute']:
                score += 5.0
        
        # Check for duplicate messages
        msg_hash = hashlib.md5(message.encode()).hexdigest()
        if msg_hash in self.message_hashes:
            recent_duplicates = [
                timestamp for timestamp in self.message_hashes[msg_hash]
                if timestamp > now - timedelta(minutes=5)
            ]
            if len(recent_duplicates) >= SPAM_THRESHOLD['duplicate_threshold']:
                score += 3.0
        
        # Check for excessive links
        link_count = len(re.findall(r'http[s]?://|t\.me/|@\w+', message))
        if link_count > SPAM_THRESHOLD['link_threshold']:
            score += 2.0
        
        # Check for excessive emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        emoji_count = len(emoji_pattern.findall(message))
        if emoji_count > SPAM_THRESHOLD['emoji_threshold']:
            score += 1.5
        
        # Check for all caps
        if len(message) > 20 and message.isupper():
            score += 1.0
        
        # Check for repetitive characters
        if re.search(r'(.)\1{4,}', message):
            score += 1.0
        
        return score
    
    def is_spam(self, message: str, user_id: int) -> bool:
        """Check if message is spam"""
        self.clean_old_data()
        
        # Check if user is banned
        if user_id in self.banned_users:
            return True
        
        score = self.calculate_spam_score(message, user_id)
        self.spam_scores[user_id] = score
        
        # Record message
        now = datetime.now()
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        self.user_messages[user_id].append({
            'text': message,
            'timestamp': now,
            'score': score
        })
        
        # Record message hash
        msg_hash = hashlib.md5(message.encode()).hexdigest()
        if msg_hash not in self.message_hashes:
            self.message_hashes[msg_hash] = []
        self.message_hashes[msg_hash].append(now)
        
        # Ban user if score too high
        if score >= 8.0:
            self.banned_users[user_id] = now + timedelta(hours=1)
            return True
        
        return score >= 5.0
    
    def get_user_spam_info(self, user_id: int) -> dict:
        """Get spam info for user"""
        return {
            'score': self.spam_scores.get(user_id, 0.0),
            'is_banned': user_id in self.banned_users,
            'ban_expires': self.banned_users.get(user_id),
            'message_count': len(self.user_messages.get(user_id, []))
        }

class TONMonitor:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.api_key = TON_API_KEY
        self.contract_address = TOKEN_CONTRACT_ADDRESS
        self.notification_chat = NOTIFICATION_CHAT_ID
        self.last_transaction_lt = None
        self.monitoring = False
        
    async def get_latest_transactions(self) -> List[dict]:
        """Get latest transactions from TON blockchain"""
        if not self.api_key or not self.contract_address:
            return []
        
        try:
            url = f"https://toncenter.com/api/v2/getTransactions"
            params = {
                'address': self.contract_address,
                'limit': 10,
                'api_key': self.api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('result', [])
                    else:
                        logger.error(f"TON API error: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}")
            return []
    
    def parse_transaction(self, tx: dict) -> Optional[dict]:
        """Parse transaction data"""
        try:
            # Extract relevant transaction info
            in_msg = tx.get('in_msg', {})
            if not in_msg:
                return None
            
            amount = int(in_msg.get('value', '0'))
            from_address = in_msg.get('source', '')
            to_address = in_msg.get('destination', '')
            
            # Convert from nanotons to TON
            amount_ton = amount / 1_000_000_000
            
            if amount_ton > 0 and to_address == self.contract_address:
                return {
                    'amount': amount_ton,
                    'from_address': from_address,
                    'to_address': to_address,
                    'hash': tx.get('transaction_id', {}).get('hash', ''),
                    'timestamp': tx.get('utime', 0),
                    'lt': tx.get('transaction_id', {}).get('lt', '0')
                }
        except Exception as e:
            logger.error(f"Error parsing transaction: {e}")
        
        return None
    
    async def format_transaction_message(self, tx_data: dict) -> str:
        """Format transaction notification message"""
        amount = tx_data['amount']
        from_addr = tx_data['from_address']
        tx_hash = tx_data['hash']
        
        # Shorten address for display
        short_addr = f"{from_addr[:8]}...{from_addr[-8:]}" if len(from_addr) > 16 else from_addr
        short_hash = f"{tx_hash[:12]}..." if len(tx_hash) > 12 else tx_hash
        
        # Determine emoji based on amount
        if amount >= 100:
            emoji = "🐋"
            title = "WHALE PURCHASE"
        elif amount >= 50:
            emoji = "🦈"
            title = "BIG PURCHASE"
        elif amount >= 10:
            emoji = "🐱"
            title = "CAT PURCHASE"
        else:
            emoji = "🐾"
            title = "SMALL PURCHASE"
        
        message = f"""
{emoji} **{title}** {emoji}

💰 **Amount:** {amount:.2f} TON
🏠 **From:** `{short_addr}`
🔗 **Hash:** `{short_hash}`
⏰ **Time:** {datetime.fromtimestamp(tx_data['timestamp']).strftime('%H:%M:%S')}

🚀 **Another hero joins CaptainCat!**
💎 **Total progress towards listing!**

#CaptainCat #TON #Purchase
        """
        
        return message
    
    async def monitor_transactions(self):
        """Monitor blockchain for new transactions"""
        if not self.api_key or not self.contract_address or not self.notification_chat:
            logger.warning("TON monitoring disabled - missing configuration")
            return
        
        self.monitoring = True
        logger.info("Starting TON transaction monitoring...")
        
        while self.monitoring:
            try:
                transactions = await self.get_latest_transactions()
                
                for tx in transactions:
                    tx_data = self.parse_transaction(tx)
                    if not tx_data:
                        continue
                    
                    # Check if this is a new transaction
                    current_lt = tx_data['lt']
                    if self.last_transaction_lt and current_lt <= self.last_transaction_lt:
                        continue
                    
                    # Update last seen transaction
                    if not self.last_transaction_lt or current_lt > self.last_transaction_lt:
                        self.last_transaction_lt = current_lt
                    
                    # Send notification
                    message = await self.format_transaction_message(tx_data)
                    
                    try:
                        await self.bot.app.bot.send_message(
                            chat_id=self.notification_chat,
                            text=message,
                            parse_mode='Markdown'
                        )
                        logger.info(f"Transaction notification sent: {tx_data['amount']} TON")
                        
                        # Log transaction to database
                        await self.bot.db.log_transaction(
                            tx_data['hash'], tx_data['from_address'], 
                            tx_data['amount'], tx_data['timestamp']
                        )
                    except Exception as e:
                        logger.error(f"Error sending transaction notification: {e}")
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in transaction monitoring: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    def stop_monitoring(self):
        """Stop transaction monitoring"""
        self.monitoring = False
        logger.info("TON transaction monitoring stopped")

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
                # Game scores table
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
                ''')
                
                # Anti-spam logs table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS spam_logs (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        chat_id BIGINT NOT NULL,
                        message_text TEXT,
                        spam_score FLOAT DEFAULT 0,
                        action_taken TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
                
                # Transaction logs table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS transaction_logs (
                        id SERIAL PRIMARY KEY,
                        tx_hash TEXT UNIQUE NOT NULL,
                        from_address TEXT,
                        amount FLOAT,
                        timestamp BIGINT,
                        notified BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
                
                # Create indexes
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_user_scores ON captaincat_scores(user_id);
                    CREATE INDEX IF NOT EXISTS idx_group_scores ON captaincat_scores(group_id);
                    CREATE INDEX IF NOT EXISTS idx_score_ranking ON captaincat_scores(score DESC, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_spam_user ON spam_logs(user_id, created_at);
                    CREATE INDEX IF NOT EXISTS idx_tx_hash ON transaction_logs(tx_hash);
                ''')
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
    async def log_spam_action(self, user_id: int, chat_id: int, message: str, score: float, action: str):
        """Log spam detection action"""
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO spam_logs (user_id, chat_id, message_text, spam_score, action_taken)
                    VALUES ($1, $2, $3, $4, $5)
                ''', user_id, chat_id, message[:500], score, action)
        except Exception as e:
            logger.error(f"Error logging spam action: {e}")
    
    async def log_transaction(self, tx_hash: str, from_address: str, amount: float, timestamp: int):
        """Log transaction"""
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO transaction_logs (tx_hash, from_address, amount, timestamp, notified)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (tx_hash) DO NOTHING
                ''', tx_hash, from_address, amount, timestamp, True)
        except Exception as e:
            logger.error(f"Error logging transaction: {e}")
    
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
        self.anti_spam = AntiSpamSystem()
        self.ton_monitor = TONMonitor(self)
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
        
        # Game handlers
        self.app.add_handler(CommandHandler("game", self.game_command))
        self.app.add_handler(CommandHandler("play", self.game_command))
        self.app.add_handler(CommandHandler("mystats", self.mystats_command))
        self.app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        self.app.add_handler(CommandHandler("gametop", self.leaderboard_command))
        
        # Admin handlers
        self.app.add_handler(CommandHandler("antispam", self.antispam_command))
        self.app.add_handler(CommandHandler("tonmonitor", self.tonmonitor_command))
        self.app.add_handler(CommandHandler("spaminfo", self.spaminfo_command))
        
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self.handle_web_app_data))
        
        # Add error handler
        self.app.add_error_handler(error_handler)

    async def is_admin(self, user_id: int, chat_id: int) -> bool:
        """Check if user is admin"""
        try:
            member = await self.app.bot.get_chat_member(chat_id, user_id)
            return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except:
            return False

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

🛡️ **Protected by advanced anti-spam**
💎 **Real-time TON transaction monitoring**

What do you want to know today?
        """
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

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
/staking - Staking rewards info
/nft - NFT collection info
/status - Bot status

🎮 **GAME COMMANDS:**
/game - Start CaptainCat Adventure
/play - Alias for /game
/mystats - Your game statistics
/leaderboard - Game leaderboard
/gametop - Alias for /leaderboard

⚡ **ADMIN COMMANDS:**
/antispam - Anti-spam system status
/tonmonitor - TON monitoring controls
/spaminfo - Check user spam info

🚀 **Just write and I'll respond!**
Examples: "how much?", "when listing?", "how it works?"

⚡ **Features:**
• Advanced anti-spam protection
• Real-time transaction monitoring
• Automatic spam detection & filtering
• Admin controls and logging"""
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')

    @handle_errors
    async def antispam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Anti-spam control command (admin only)"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await self.is_admin(user_id, chat_id):
            await update.message.reply_text("🔒 This command is for admins only.")
            return
        
        antispam_info = f"""
🛡️ **CAPTAINCAT ANTI-SPAM SYSTEM**

📊 **Current Status:**
• Active Users Monitored: {len(self.anti_spam.user_messages)}
• Banned Users: {len(self.anti_spam.banned_users)}
• Message Hashes Tracked: {len(self.anti_spam.message_hashes)}
• Spam Scores Calculated: {len(self.anti_spam.spam_scores)}

⚙️ **Thresholds:**
• Messages per minute: {SPAM_THRESHOLD['messages_per_minute']}
• Duplicate threshold: {SPAM_THRESHOLD['duplicate_threshold']}
• Link threshold: {SPAM_THRESHOLD['link_threshold']}
• Emoji threshold: {SPAM_THRESHOLD['emoji_threshold']}

🎯 **Actions:**
• Score 5.0+: Message filtered
• Score 8.0+: User temporarily banned (1 hour)

Use /spaminfo @username to check user spam info.
        """
        
        await update.message.reply_text(antispam_info, parse_mode='Markdown')

    @handle_errors
    async def tonmonitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """TON monitoring control command (admin only)"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await self.is_admin(user_id, chat_id):
            await update.message.reply_text("🔒 This command is for admins only.")
            return
        
        args = context.args
        if args and args[0].lower() == 'start':
            if not self.ton_monitor.monitoring:
                # Start monitoring in background
                asyncio.create_task(self.ton_monitor.monitor_transactions())
                await update.message.reply_text("🚀 TON transaction monitoring started!")
            else:
                await update.message.reply_text("⚠️ TON monitoring is already running.")
        elif args and args[0].lower() == 'stop':
            self.ton_monitor.stop_monitoring()
            await update.message.reply_text("⏹️ TON transaction monitoring stopped.")
        else:
            status = "🟢 Running" if self.ton_monitor.monitoring else "🔴 Stopped"
            monitor_info = f"""
💎 **TON TRANSACTION MONITOR**

📊 **Status:** {status}
🏠 **Contract:** `{self.ton_monitor.contract_address or 'Not configured'}`
📢 **Notification Chat:** `{self.ton_monitor.notification_chat or 'Not configured'}`
🔑 **API Key:** {'✅ Set' if self.ton_monitor.api_key else '❌ Missing'}
📈 **Last TX LT:** {self.ton_monitor.last_transaction_lt or 'None'}

**Commands:**
/tonmonitor start - Start monitoring
/tonmonitor stop - Stop monitoring
            """
            await update.message.reply_text(monitor_info, parse_mode='Markdown')

    @handle_errors
    async def spaminfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get spam info for a user (admin only)"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await self.is_admin(user_id, chat_id):
            await update.message.reply_text("🔒 This command is for admins only.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Usage: /spaminfo user_id")
            return
        
        target_user = context.args[0]
        try:
            target_user_id = int(target_user)
            
            spam_info = self.anti_spam.get_user_spam_info(target_user_id)
            
            status = "🔴 BANNED" if spam_info['is_banned'] else "🟢 CLEAN"
            ban_info = ""
            if spam_info['is_banned'] and spam_info['ban_expires']:
                ban_info = f"\n⏰ **Ban expires:** {spam_info['ban_expires'].strftime('%H:%M:%S')}"
            
            info_msg = f"""
📊 **SPAM INFO FOR USER {target_user_id}**

🛡️ **Status:** {status}
⚡ **Spam Score:** {spam_info['score']:.2f}
📱 **Messages Tracked:** {spam_info['message_count']}{ban_info}

**Score Meaning:**
• 0.0-2.0: Clean user
• 2.0-5.0: Suspicious activity
• 5.0+: Spam detected
• 8.0+: Auto-banned
            """
            
            await update.message.reply_text(info_msg, parse_mode='Markdown')
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user_id format.")

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
        
        # Different buttons for group vs private
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
            [InlineKeyboardButton("💎 Join Presale", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]
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
            [InlineKeyboardButton("🚀 Join Presale", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]
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

    @handle_errors
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db_status = "✅ Connected" if self.db.pool else "⚠️ Not available"
        ton_status = "🟢 Active" if self.ton_monitor.monitoring else "🔴 Inactive"
        
        status_msg = f"""
🤖 **CAPTAINCAT BOT STATUS**

✅ **Bot Online and Working**
🎮 **CaptainCat Game: ACTIVE**
📡 **Server: Render.com**
⏰ **Uptime: 24/7**
🔄 **Last update: {datetime.now().strftime('%d/%m/%Y %H:%M')}**
🗃️ **Database: {db_status}**
🛡️ **Anti-Spam: ACTIVE**
💎 **TON Monitor: {ton_status}**
🔧 **Error Handling: OPTIMIZED**

🛡️ **Security Features:**
• Advanced anti-spam protection
• Real-time transaction monitoring
• Automated spam detection & filtering
• Admin controls and logging

💪 **Ready to help the community and host game tournaments!**
        """
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    @rate_limit(max_calls=10, period=60, group_max_calls=20, group_period=60)
    @handle_errors
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages with anti-spam"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_text = update.message.text
        user_name = update.effective_user.first_name or "Hero"
        
        # Check for spam
        if self.anti_spam.is_spam(message_text, user_id):
            spam_info = self.anti_spam.get_user_spam_info(user_id)
            
            # Log spam action
            action = "BANNED" if spam_info['is_banned'] else "FILTERED"
            await self.db.log_spam_action(user_id, chat_id, message_text, spam_info['score'], action)
            
            # Delete message if possible (in groups)
            if chat_id < 0:  # Group chat
                try:
                    await update.message.delete()
                    
                    # Notify admins about spam
                    if spam_info['is_banned']:
                        warning_msg = f"🛡️ **SPAM DETECTED & USER BANNED**\n\n"
                        warning_msg += f"👤 **User:** {user_name} ({user_id})\n"
                        warning_msg += f"⚡ **Score:** {spam_info['score']:.2f}\n"
                        warning_msg += f"⏰ **Ban duration:** 1 hour\n"
                        warning_msg += f"📝 **Message:** {message_text[:100]}..."
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=warning_msg,
                            parse_mode='Markdown'
                        )
                    
                    logger.info(f"Spam message deleted from user {user_id}, score: {spam_info['score']}")
                    return
                except:
                    pass
            else:
                # In private chat, just warn
                await update.message.reply_text(
                    f"⚠️ Your message appears to be spam (score: {spam_info['score']:.1f}). Please moderate your messaging."
                )
                return
        
        # Process normal message
        message = message_text.lower()
        
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
        """Generate AI response"""
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
        print("🐱‍🦸 CaptainCat Bot with TON Monitoring & Anti-Spam starting...")
        
        # Initialize database
        async def startup():
            await self.initialize_database()
            logger.info("Database initialized for all features")
            
            # Start TON monitoring if configured
            if self.ton_monitor.api_key and self.ton_monitor.contract_address:
                asyncio.create_task(self.ton_monitor.monitor_transactions())
                logger.info("TON transaction monitoring started")
            else:
                logger.warning("TON monitoring not started - missing configuration")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(startup())
        except Exception as e:
            logger.error(f"Startup error: {e}")
        
        # Run bot
        self.app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=1.0,
            timeout=10,
            close_loop=False
        )

# Main script
if __name__ == "__main__":
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not found!")
        print("💡 Configure the following environment variables on Render:")
        print("- BOT_TOKEN (required)")
        print("- TON_API_KEY (for transaction monitoring)")
        print("- TOKEN_CONTRACT_ADDRESS (your CAT token contract)")
        print("- NOTIFICATION_CHAT_ID (chat ID for transaction notifications)")
        print("- DATABASE_URL (for persistence)")
        print("- WEBAPP_URL (for game)")
    else:
        print(f"🚀 Starting CaptainCat Bot with TON Monitoring & Anti-Spam...")
        bot = CaptainCatBot(BOT_TOKEN)
        bot.run()
