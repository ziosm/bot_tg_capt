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
from typing import Dict, List, Optional, Tuple

# ===== FOMO SYSTEM CONFIGURATION =====
PRESALE_CONFIG = {
    'target': 1500,  # TON target
    'start_date': datetime(2024, 1, 1),  # Adjust to your presale start
    'end_date': datetime(2025, 2, 1),    # Adjust to your presale end
    'current_raised': 675,  # Update this dynamically from DB
    'early_bird_bonus': 20,
    'whale_bonus': 15,
    'minimum_whale': 50,
    'token_price': 10000,  # 1 TON = 10,000 CAT
}

FOMO_MESSAGES = {
    'urgency': [
        "🚨 **URGENT**: Presale {percent}% FULL! Only {remaining} TON spots left!",
        "⏰ **TIME SENSITIVE**: {time_left} until presale closes! Don't miss out!",
        "🔥 **FILLING FAST**: {recent_buyers} buyers in the last hour! Join them!",
        "⚡ **ALERT**: At this rate, presale ends in {estimated_hours}h!"
    ],
    'social_proof': [
        "🌟 **{total_holders} HOLDERS** already secured their bags! Are you next?",
        "💎 **SMART MONEY MOVING**: {whale_count} whales joined today!",
        "🚀 **COMMUNITY EXPLODING**: {growth_rate}% growth in 24h!",
        "🏆 **TOP TRENDING** on TON ecosystem! #1 momentum!"
    ],
    'scarcity': [
        "⚠️ **ONLY {tokens_left}M CAT** tokens left in presale allocation!",
        "🎯 **FINAL {percent_left}%** of presale remaining! Act NOW!",
        "💎 **LAST CHANCE** for {bonus}% early bird bonus!",
        "🔒 **PRESALE CLOSING**: These prices will NEVER return!"
    ],
    'price_action': [
        "📈 **PRICE PREDICTION**: 10-50x after DEX listing! (NFA)",
        "💰 **PRESALE PRICE**: 1 TON = 10,000 CAT | **DEX PRICE**: 1 TON = 1,000 CAT",
        "🎯 **SMART INVESTORS** know: Presale = Best entry point!",
        "⚡ **FACT**: Every successful meme started with presale believers!"
    ]
}

# ===== ENHANCED FOMO BOT CLASS =====
class CaptainCatFOMOBot:
    def __init__(self, token: str):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.db = GameDatabase()
        self.anti_spam = AntiSpamSystem()
        self.ton_monitor = TONMonitor(self)
        self._web_app_url = os.environ.get('WEBAPP_URL', 'https://captaincat-game.onrender.com')
        
        # FOMO System State
        self.fomo_stats = {
            'raised': PRESALE_CONFIG['current_raised'],
            'last_buy_time': datetime.now(),
            'recent_buyers': [],
            'whale_alerts': [],
            'community_milestones': [],
            'scheduled_messages': {}
        }
        
        # FOMO Channels - aggiungi i tuoi gruppi target
        self.fomo_channels = [
            int(os.environ.get('MAIN_GROUP_ID', '0')),
            int(os.environ.get('ANNOUNCEMENT_CHANNEL_ID', '0')),
        ]
        
        self.setup_handlers()
        self.setup_fomo_handlers()

    def setup_fomo_handlers(self):
        """Setup FOMO-specific command handlers"""
        self.app.add_handler(CommandHandler("stats", self.live_stats_command))
        self.app.add_handler(CommandHandler("whobought", self.whobought_command))
        self.app.add_handler(CommandHandler("presalestatus", self.presale_status_command))
        self.app.add_handler(CommandHandler("predict", self.price_prediction_command))
        self.app.add_handler(CommandHandler("benefits", self.benefits_command))
        self.app.add_handler(CommandHandler("fomo", self.fomo_command))
        self.app.add_handler(CommandHandler("milestone", self.milestone_command))

    # ===== PRESALE TRACKING =====
    def get_presale_progress(self) -> dict:
        """Calculate current presale progress"""
        raised = self.fomo_stats['raised']
        target = PRESALE_CONFIG['target']
        percentage = (raised / target) * 100
        remaining = target - raised
        
        # Calculate time left
        now = datetime.now()
        time_left = PRESALE_CONFIG['end_date'] - now
        
        # Estimate completion time based on recent rate
        recent_rate = self.calculate_recent_rate()
        if recent_rate > 0:
            hours_to_complete = remaining / recent_rate
            estimated_completion = now + timedelta(hours=hours_to_complete)
        else:
            hours_to_complete = float('inf')
            estimated_completion = PRESALE_CONFIG['end_date']
        
        return {
            'raised': raised,
            'target': target,
            'percentage': round(percentage, 1),
            'remaining': remaining,
            'time_left': time_left,
            'hours_to_complete': hours_to_complete,
            'estimated_completion': estimated_completion,
            'recent_rate': recent_rate,
            'tokens_sold': raised * PRESALE_CONFIG['token_price'],
            'tokens_remaining': remaining * PRESALE_CONFIG['token_price']
        }

    def calculate_recent_rate(self) -> float:
        """Calculate TON/hour rate from recent transactions"""
        # Get transactions from last 24h
        recent = [tx for tx in self.fomo_stats['recent_buyers'] 
                 if datetime.now() - tx['time'] < timedelta(hours=24)]
        
        if not recent:
            return 0.0
        
        total_amount = sum(tx['amount'] for tx in recent)
        hours_elapsed = 24
        return total_amount / hours_elapsed

    def create_progress_visual(self, percentage: float) -> str:
        """Create visual progress bar"""
        filled = int(percentage / 5)  # 20 segments
        
        if percentage >= 90:
            emoji = "🔴"
            empty = "⬜"
        elif percentage >= 70:
            emoji = "🟠"
            empty = "⬜"
        elif percentage >= 50:
            emoji = "🟡"
            empty = "⬜"
        else:
            emoji = "🟢"
            empty = "⬜"
        
        bar = emoji * filled + empty * (20 - filled)
        return f"{bar}\n{percentage}% FILLED | {100-percentage}% REMAINING"

    # ===== FOMO COMMANDS =====
    @handle_errors
    async def live_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show live presale statistics with FOMO elements"""
        progress = self.get_presale_progress()
        recent_buyers = len([tx for tx in self.fomo_stats['recent_buyers'] 
                           if datetime.now() - tx['time'] < timedelta(hours=1)])
        
        # Get whale count
        whale_count = len([tx for tx in self.fomo_stats['recent_buyers']
                         if tx['amount'] >= PRESALE_CONFIG['minimum_whale']])
        
        stats_message = f"""
🔥 **CAPTAINCAT PRESALE LIVE STATS** 🔥

{self.create_progress_visual(progress['percentage'])}

💰 **Raised:** {progress['raised']}/{progress['target']} TON
📊 **Progress:** {progress['percentage']}%
⏰ **Time Left:** {progress['time_left'].days}d {progress['time_left'].seconds//3600}h

📈 **MOMENTUM INDICATORS:**
• **Last Hour:** {recent_buyers} new investors
• **24h Rate:** {progress['recent_rate']:.2f} TON/hour
• **Whales:** {whale_count} joined ({whale_count * PRESALE_CONFIG['minimum_whale']}+ TON)
• **Completion ETA:** {progress['hours_to_complete']:.1f} hours

🚨 **CRITICAL LEVELS:**
{"⚡ FOMO ZONE - Filling rapidly!" if progress['percentage'] > 70 else ""}
{"🔥 MOMENTUM BUILDING!" if recent_buyers > 5 else ""}
{"🐋 WHALE ALERT ACTIVE!" if whale_count > 0 else ""}

💎 **Tokens Sold:** {progress['tokens_sold']:,.0f} CAT
🎯 **Still Available:** {progress['tokens_remaining']:,.0f} CAT

⚠️ **WARNING:** At current rate, presale ends in {progress['hours_to_complete']:.0f} hours!
"""
        
        keyboard = [
            [InlineKeyboardButton("💎 BUY NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Check Progress", callback_data="presale_progress"),
             InlineKeyboardButton("🔥 Recent Buys", callback_data="recent_buyers")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(stats_message, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def whobought_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent buyers to create FOMO"""
        recent = sorted(self.fomo_stats['recent_buyers'], 
                       key=lambda x: x['time'], reverse=True)[:10]
        
        if not recent:
            await update.message.reply_text("🚀 Be the FIRST hero to buy CaptainCat!")
            return
        
        message = "🔥 **LATEST CAPTAINCAT INVESTORS** 🔥\n\n"
        
        for tx in recent:
            time_ago = datetime.now() - tx['time']
            if time_ago.seconds < 3600:
                time_str = f"{time_ago.seconds // 60}m ago"
            else:
                time_str = f"{time_ago.seconds // 3600}h ago"
            
            # Whale indicator
            whale = "🐋" if tx['amount'] >= PRESALE_CONFIG['minimum_whale'] else "🐱"
            
            # Format amount
            if tx['amount'] >= 100:
                amount_str = f"{tx['amount']:.0f} TON"
            else:
                amount_str = f"{tx['amount']:.1f} TON"
            
            message += f"{whale} **{amount_str}** - {time_str}\n"
        
        # Add FOMO elements
        total_recent = sum(tx['amount'] for tx in recent)
        message += f"\n💰 **Total last 10:** {total_recent:.1f} TON"
        message += f"\n🚀 **That's {total_recent * PRESALE_CONFIG['token_price']:,.0f} CAT tokens!**"
        
        # Add psychological triggers
        if any(tx['amount'] >= PRESALE_CONFIG['minimum_whale'] for tx in recent):
            message += "\n\n🐋 **WHALE ALERT: Smart money is accumulating!**"
        
        message += "\n\n⚡ **Don't be left watching from sidelines!**"
        message += "\n🎯 **Join these legends NOW!**"
        
        keyboard = [
            [InlineKeyboardButton("🚀 I'M IN!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Live Stats", callback_data="live_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def price_prediction_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show price predictions to create FOMO"""
        current_price = 1 / PRESALE_CONFIG['token_price']  # Price per CAT in TON
        
        message = f"""
📈 **CAPTAINCAT PRICE PREDICTION** 📈

**Current Presale Price:**
• 1 TON = {PRESALE_CONFIG['token_price']:,} CAT
• 1 CAT = {current_price:.8f} TON

🎯 **REALISTIC TARGETS (Based on similar projects):**

**🚀 Launch Day (DEX Listing):**
• Conservative: 2-3x ({current_price * 2:.8f} - {current_price * 3:.8f} TON)
• Realistic: 5-10x ({current_price * 5:.8f} - {current_price * 10:.8f} TON)
• Optimistic: 15-20x ({current_price * 15:.8f} - {current_price * 20:.8f} TON)

**📅 Week 1:**
• 10-50x potential ({current_price * 10:.8f} - {current_price * 50:.8f} TON)

**📅 Month 1 (with CEX listings):**
• 50-100x possible ({current_price * 50:.8f} - {current_price * 100:.8f} TON)

**🌙 Long Term (6 months):**
• 100-1000x if we reach top memecoins

💡 **COMPARISON:**
• DOGS: Did 87x from presale
• HMSTR: Did 45x from presale  
• NOT: Did 156x from presale

⚠️ **REMEMBER:**
• Presale = LOWEST price EVER
• After launch = NEVER this cheap
• Early believers = Biggest winners

🔥 **YOUR POTENTIAL:**
• Invest 10 TON = Get 100,000 CAT
• At 10x = Worth 100 TON
• At 100x = Worth 1,000 TON!

*Not Financial Advice - DYOR*
"""
        
        keyboard = [
            [InlineKeyboardButton("💎 SECURE MY BAG!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Calculate Returns", callback_data="calculate_returns")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors  
    async def benefits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show presale benefits to create FOMO"""
        message = f"""
🎁 **PRESALE EXCLUSIVE BENEFITS** 🎁

**🔥 ONLY FOR PRESALE INVESTORS:**

✅ **Lowest Price EVER**
• Presale: 1 TON = 10,000 CAT
• After: 1 TON = 1,000 CAT (10x higher!)

✅ **Bonus Tokens**
• +20% Early Bird Bonus
• +15% Whale Bonus (50+ TON)
• +10% Community Bonus

✅ **NFT Whitelist**
• Automatic WL for CaptainCat NFTs
• Free mint for 100+ TON investors
• NFT = Game boosts + Staking multiplier

✅ **DAO Power**
• 2x voting power vs regular holders
• Decide project future
• Revenue sharing rights

✅ **Staking Benefits**
• +50% APY boost
• Early access to staking
• No lock period for presalers

✅ **Game Perks**
• Lifetime premium access
• Exclusive skins & power-ups
• Double rewards in tournaments

✅ **Airdrops**
• Weekly CAT airdrops
• Partner token airdrops
• NFT airdrops

❌ **AFTER PRESALE: NONE OF THESE!**

⏰ **Time Remaining:** {(PRESALE_CONFIG['end_date'] - datetime.now()).days} days

⚡ **These benefits = Worth 100x more than investment!**
"""
        
        keyboard = [
            [InlineKeyboardButton("🎁 CLAIM BENEFITS NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📋 Full Details", callback_data="presale_details")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def fomo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ultimate FOMO summary message"""
        progress = self.get_presale_progress()
        recent_buyers = len([tx for tx in self.fomo_stats['recent_buyers'] 
                           if datetime.now() - tx['time'] < timedelta(hours=1)])
        
        # Random FOMO facts
        fomo_facts = [
            f"🔥 {recent_buyers} people bought in the last hour!",
            f"⚡ Only {progress['remaining']} TON spots left!",
            f"🚀 {progress['percentage']:.1f}% already sold!",
            f"💎 Last buyer got {random.randint(100000, 150000)} CAT!",
            f"⏰ Presale ends in {progress['time_left'].days} days!",
            f"🐋 Biggest buy today: {max([tx['amount'] for tx in self.fomo_stats['recent_buyers']] or [0])} TON!"
        ]
        
        message = f"""
🚨🔥 **CAPTAINCAT FOMO ALERT** 🔥🚨

{random.choice(fomo_facts)}

**❓ WHY EVERYONE'S BUYING:**

1️⃣ **MASSIVE POTENTIAL**
• Similar projects did 50-150x
• We have better fundamentals
• Stronger community growth

2️⃣ **LIMITED SUPPLY**
• Only {progress['remaining']} TON spots left
• {progress['percentage']:.1f}% already gone
• These prices = NEVER AGAIN

3️⃣ **SMART MONEY MOVING**
• {len([tx for tx in self.fomo_stats['recent_buyers'] if tx['amount'] >= 50])} whales joined
• Top traders accumulating
• Influencers coming onboard

4️⃣ **UPCOMING CATALYSTS**
• DEX listing confirmed
• Major partnership announcement
• Game launch with rewards
• CEX talks ongoing

5️⃣ **COMMUNITY EXPLODING**
• 1000+ new members daily
• Organic growth (no bots)
• Active 24/7 community

**⚠️ FINAL WARNING:**
This is your LAST CHANCE at presale prices!

**💭 IMAGINE:**
• Missing 100x gains
• Watching others get rich
• Saying "I wish I bought"

**🎯 BE SMART: BUY NOW!**
"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 FOMO BUY NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Check Stats", callback_data="live_stats"),
             InlineKeyboardButton("💰 Recent Buys", callback_data="recent_buyers")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def milestone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show upcoming milestones"""
        progress = self.get_presale_progress()
        
        milestones = [
            {'percent': 50, 'reward': 'Unlock Game Beta', 'emoji': '🎮'},
            {'percent': 60, 'reward': 'Partnership Reveal', 'emoji': '🤝'},
            {'percent': 70, 'reward': 'CEX Announcement', 'emoji': '📱'},
            {'percent': 80, 'reward': 'NFT Preview', 'emoji': '🖼️'},
            {'percent': 90, 'reward': 'Staking Launch', 'emoji': '💎'},
            {'percent': 100, 'reward': 'DEX LISTING!', 'emoji': '🚀'}
        ]
        
        message = "🏆 **PRESALE MILESTONES** 🏆\n\n"
        
        for milestone in milestones:
            if progress['percentage'] >= milestone['percent']:
                status = "✅ UNLOCKED"
                style = "**"
            else:
                status = "🔒 LOCKED"
                style = ""
            
            message += f"{milestone['emoji']} {style}{milestone['percent']}% - {milestone['reward']}{style} {status}\n"
        
        message += f"\n📊 **Current Progress:** {progress['percentage']:.1f}%"
        message += f"\n🎯 **Next Milestone:** {next((m['percent'] for m in milestones if m['percent'] > progress['percentage']), 100)}%"
        message += "\n\n⚡ **Help us reach next milestone!**"
        
        keyboard = [
            [InlineKeyboardButton("🚀 Contribute Now!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Live Progress", callback_data="live_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    # ===== AUTOMATED FOMO MESSAGES =====
    async def start_fomo_scheduler(self):
        """Start automated FOMO message scheduler"""
        asyncio.create_task(self.hourly_fomo_blast())
        asyncio.create_task(self.momentum_tracker())
        asyncio.create_task(self.whale_watcher())
        asyncio.create_task(self.milestone_announcer())
        asyncio.create_task(self.countdown_timer())
        logger.info("FOMO scheduler started!")

    async def hourly_fomo_blast(self):
        """Send hourly FOMO updates"""
        while True:
            try:
                await asyncio.sleep(3600)  # 1 hour
                
                progress = self.get_presale_progress()
                message_type = random.choice(['urgency', 'social_proof', 'scarcity', 'price_action'])
                
                # Select and format message
                template = random.choice(FOMO_MESSAGES[message_type])
                
                # Format with real data
                message = template.format(
                    percent=progress['percentage'],
                    remaining=progress['remaining'],
                    time_left=f"{progress['time_left'].days}d {progress['time_left'].seconds//3600}h",
                    recent_buyers=len([tx for tx in self.fomo_stats['recent_buyers'] 
                                     if datetime.now() - tx['time'] < timedelta(hours=1)]),
                    estimated_hours=progress['hours_to_complete'],
                    total_holders=len(set(tx['buyer'] for tx in self.fomo_stats['recent_buyers'])),
                    whale_count=len([tx for tx in self.fomo_stats['recent_buyers'] 
                                   if tx['amount'] >= PRESALE_CONFIG['minimum_whale']]),
                    growth_rate=random.randint(20, 50),
                    tokens_left=(progress['remaining'] * PRESALE_CONFIG['token_price']) / 1_000_000,
                    percent_left=100 - progress['percentage'],
                    bonus=PRESALE_CONFIG['early_bird_bonus']
                )
                
                # Add call to action
                message += "\n\n🔥 **Don't miss out!**"
                message += f"\n👉 @Captain_cat_Cain"
                
                # Send to all FOMO channels
                for channel_id in self.fomo_channels:
                    if channel_id:
                        try:
                            keyboard = [[InlineKeyboardButton("💎 BUY NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
                            await self.app.bot.send_message(
                                channel_id, 
                                message, 
                                reply_markup=InlineKeyboardMarkup(keyboard),
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Error sending FOMO blast to {channel_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in hourly FOMO blast: {e}")
                await asyncio.sleep(60)

    async def momentum_tracker(self):
        """Track and announce momentum changes"""
        last_rate = 0
        
        while True:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                
                current_rate = self.calculate_recent_rate()
                
                if current_rate > last_rate * 1.5 and current_rate > 1:  # 50% increase in rate
                    message = f"""
🚀 **MOMENTUM ALERT** 🚀

📈 **Buying rate EXPLODED!**
• Previous: {last_rate:.2f} TON/hour
• Current: {current_rate:.2f} TON/hour
• Increase: {((current_rate/last_rate - 1) * 100):.0f}%!

🔥 **FOMO is building! Join the wave!**
                    """
                    
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(channel_id, message, parse_mode='Markdown')
                            except:
                                pass
                
                last_rate = current_rate
                
            except Exception as e:
                logger.error(f"Error in momentum tracker: {e}")
                await asyncio.sleep(60)

    async def whale_watcher(self):
        """Special alerts for whale purchases"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check for new whales in recent buyers
                for tx in self.fomo_stats['recent_buyers']:
                    if tx['amount'] >= PRESALE_CONFIG['minimum_whale'] and not tx.get('announced'):
                        tx['announced'] = True
                        
                        # Create whale alert
                        if tx['amount'] >= 200:
                            emoji = "🐋🐋🐋"
                            title = "MEGA WHALE ALERT"
                        elif tx['amount'] >= 100:
                            emoji = "🐋🐋"
                            title = "WHALE ALERT"
                        else:
                            emoji = "🐋"
                            title = "WHALE SPOTTED"
                        
                        message = f"""
{emoji} **{title}** {emoji}

💰 **Amount:** {tx['amount']} TON
💎 **Got:** {tx['amount'] * PRESALE_CONFIG['token_price']:,.0f} CAT
🔥 **Worth at 10x:** {tx['amount'] * 10} TON
🚀 **Worth at 100x:** {tx['amount'] * 100} TON

⚠️ **Smart money is moving!**
🎯 **Whales know something...**

Don't let them buy it all!
                        """
                        
                        keyboard = [[InlineKeyboardButton("🐋 Join the Whales!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
                        
                        for channel_id in self.fomo_channels:
                            if channel_id:
                                try:
                                    await self.app.bot.send_message(
                                        channel_id, 
                                        message,
                                        reply_markup=InlineKeyboardMarkup(keyboard),
                                        parse_mode='Markdown'
                                    )
                                except:
                                    pass
                
            except Exception as e:
                logger.error(f"Error in whale watcher: {e}")
                await asyncio.sleep(60)

    async def milestone_announcer(self):
        """Announce when milestones are reached"""
        announced_milestones = set()
        
        milestones = [25, 50, 60, 70, 75, 80, 85, 90, 95, 98, 99]
        
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                progress = self.get_presale_progress()
                current_percent = progress['percentage']
                
                for milestone in milestones:
                    if current_percent >= milestone and milestone not in announced_milestones:
                        announced_milestones.add(milestone)
                        
                        # Special messages for different milestones
                        if milestone >= 90:
                            urgency = "🚨🚨🚨 FINAL HOURS 🚨🚨🚨"
                            action = "LAST CHANCE - BUY NOW OR CRY LATER!"
                        elif milestone >= 75:
                            urgency = "⚡⚡ ALMOST GONE ⚡⚡"
                            action = "Hurry! Only few spots left!"
                        else:
                            urgency = "🎯 MILESTONE REACHED 🎯"
                            action = "Join before it's too late!"
                        
                        message = f"""
{urgency}

🏆 **PRESALE {milestone}% COMPLETE!** 🏆

📊 **Stats:**
• Raised: {progress['raised']}/{progress['target']} TON
• Remaining: Only {progress['remaining']} TON!
• Investors: {len(set(tx['buyer'] for tx in self.fomo_stats['recent_buyers']))}+

{action}

#CaptainCat #Presale #TON
                        """
                        
                        keyboard = [[InlineKeyboardButton("🚀 GET IN NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
                        
                        for channel_id in self.fomo_channels:
                            if channel_id:
                                try:
                                    await self.app.bot.send_message(
                                        channel_id,
                                        message,
                                        reply_markup=InlineKeyboardMarkup(keyboard),
                                        parse_mode='Markdown'
                                    )
                                except:
                                    pass
                
            except Exception as e:
                logger.error(f"Error in milestone announcer: {e}")
                await asyncio.sleep(60)

    async def countdown_timer(self):
        """Special countdown messages for final days"""
        while True:
            try:
                time_left = PRESALE_CONFIG['end_date'] - datetime.now()
                days_left = time_left.days
                
                # Special messages for final countdown
                if days_left <= 7 and days_left > 0:
                    if datetime.now().hour == 12:  # Once per day at noon
                        
                        if days_left == 1:
                            message = "🚨 **24 HOURS LEFT!** 🚨\n\nThis is your FINAL CHANCE!"
                        elif days_left <= 3:
                            message = f"⏰ **ONLY {days_left} DAYS LEFT!** ⏰\n\nTime is running out!"
                        else:
                            message = f"📅 **{days_left} DAYS REMAINING** 📅\n\nDon't procrastinate!"
                        
                        progress = self.get_presale_progress()
                        message += f"\n\n💎 Still available: {progress['remaining']} TON"
                        message += f"\n🔥 Current progress: {progress['percentage']:.1f}%"
                        message += "\n\n⚡ **Every second counts now!**"
                        
                        keyboard = [[InlineKeyboardButton("⏰ BUY BEFORE TIME RUNS OUT!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
                        
                        for channel_id in self.fomo_channels:
                            if channel_id:
                                try:
                                    await self.app.bot.send_message(
                                        channel_id,
                                        message,
                                        reply_markup=InlineKeyboardMarkup(keyboard),
                                        parse_mode='Markdown'
                                    )
                                except:
                                    pass
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in countdown timer: {e}")
                await asyncio.sleep(3600)

    # ===== ENHANCED TRANSACTION MONITOR =====
    async def format_transaction_message(self, tx_data: dict) -> str:
        """Enhanced transaction notification with FOMO"""
        amount = tx_data['amount']
        from_addr = tx_data['from_address']
        tx_hash = tx_data['hash']
        
        # Update stats
        self.fomo_stats['raised'] += amount
        self.fomo_stats['last_buy_time'] = datetime.now()
        self.fomo_stats['recent_buyers'].append({
            'amount': amount,
            'buyer': from_addr,
            'time': datetime.now(),
            'announced': False
        })
        
        # Keep only last 100 transactions
        if len(self.fomo_stats['recent_buyers']) > 100:
            self.fomo_stats['recent_buyers'] = self.fomo_stats['recent_buyers'][-100:]
        
        progress = self.get_presale_progress()
        
        # Shorten address for display
        short_addr = f"{from_addr[:8]}...{from_addr[-8:]}" if len(from_addr) > 16 else from_addr
        short_hash = f"{tx_hash[:12]}..." if len(tx_hash) > 12 else tx_hash
        
        # Determine message based on amount
        if amount >= 200:
            emoji = "🐋🐋🐋"
            title = "MEGA WHALE PURCHASE"
            fomo_msg = "🚨 **PRESALE FILLING RAPIDLY!**"
        elif amount >= 100:
            emoji = "🐋🐋"
            title = "WHALE PURCHASE"
            fomo_msg = "⚡ **Smart money is accumulating!**"
        elif amount >= 50:
            emoji = "🦈"
            title = "SHARK PURCHASE"
            fomo_msg = "🔥 **Another big investor joined!**"
        elif amount >= 10:
            emoji = "🐱"
            title = "CAT PURCHASE"
            fomo_msg = "💎 **Community growing strong!**"
        else:
            emoji = "🐾"
            title = "NEW INVESTOR"
            fomo_msg = "🚀 **Every buy counts!**"
        
        tokens_received = amount * PRESALE_CONFIG['token_price']
        
        message = f"""
{emoji} **{title}** {emoji}

💰 **Investment:** {amount:.2f} TON
💎 **Received:** {tokens_received:,.0f} CAT
🏠 **Investor:** `{short_addr}`
🔗 **TX:** `{short_hash}`
⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}

📊 **PRESALE STATUS:**
• Progress: {progress['percentage']:.1f}% FILLED!
• Remaining: Only {progress['remaining']:.0f} TON left!
• Recent buyers: {len([tx for tx in self.fomo_stats['recent_buyers'] if datetime.now() - tx['time'] < timedelta(hours=1)])} in last hour

{fomo_msg}
🎯 **Don't miss your chance!**

#CaptainCat #NewInvestor #TON
        """
        
        return message

    # ===== PRESALE STATUS COMMAND =====
    @handle_errors
    async def presale_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detailed presale status for groups"""
        progress = self.get_presale_progress()
        
        # Calculate various stats
        total_investors = len(set(tx['buyer'] for tx in self.fomo_stats['recent_buyers']))
        avg_investment = progress['raised'] / max(total_investors, 1)
        
        recent_24h = [tx for tx in self.fomo_stats['recent_buyers'] 
                     if datetime.now() - tx['time'] < timedelta(hours=24)]
        volume_24h = sum(tx['amount'] for tx in recent_24h)
        
        status_msg = f"""
📊 **CAPTAINCAT PRESALE DETAILED STATUS** 📊

{self.create_progress_visual(progress['percentage'])}

**💰 FINANCIAL METRICS:**
• Total Raised: {progress['raised']:.1f}/{progress['target']} TON
• USD Value: ${progress['raised'] * 5.5:,.0f} (at $5.5/TON)
• Tokens Sold: {progress['tokens_sold']:,.0f} CAT
• Avg Investment: {avg_investment:.1f} TON

**📈 MOMENTUM METRICS:**
• 24h Volume: {volume_24h:.1f} TON
• 24h Investors: {len(recent_24h)}
• Hourly Rate: {progress['recent_rate']:.2f} TON/h
• Completion ETA: {progress['hours_to_complete']:.0f} hours

**👥 COMMUNITY METRICS:**
• Total Investors: {total_investors}
• Whale Count (50+ TON): {len([tx for tx in self.fomo_stats['recent_buyers'] if tx['amount'] >= 50])}
• Shark Count (25+ TON): {len([tx for tx in self.fomo_stats['recent_buyers'] if tx['amount'] >= 25])}

**⏰ TIME METRICS:**
• Started: {PRESALE_CONFIG['start_date'].strftime('%d %b %Y')}
• Ends: {PRESALE_CONFIG['end_date'].strftime('%d %b %Y')}
• Time Left: {progress['time_left'].days}d {progress['time_left'].seconds//3600}h

**🎯 NEXT TARGETS:**
• 80% - NFT Collection Preview
• 90% - Staking Platform Launch
• 100% - Immediate DEX Listing!

⚡ **Be part of history in the making!**
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Invest Now!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Live Updates", callback_data="live_stats"),
             InlineKeyboardButton("🏆 Milestones", callback_data="milestones")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(status_msg, reply_markup=reply_markup, parse_mode='Markdown')

    # ===== RUN METHOD WITH FOMO =====
    def run(self):
        print("🐱‍🦸 CaptainCat FOMO Bot starting...")
        
        # Initialize everything including FOMO scheduler
        async def startup():
            await self.initialize_database()
            logger.info("Database initialized")
            
            # Start FOMO automation
            await self.start_fomo_scheduler()
            logger.info("FOMO automation started")
            
            # Start TON monitoring if configured
            if self.ton_monitor.api_key and self.ton_monitor.contract_address:
                asyncio.create_task(self.ton_monitor.monitor_transactions())
                logger.info("TON monitoring started")
        
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

# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN not found!")
    else:
        print("🚀 Starting CaptainCat FOMO Bot...")
        bot = CaptainCatFOMOBot(BOT_TOKEN)
        bot.run()
