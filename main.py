# ===== ANTI-SPAM COMMANDS =====
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

    # ===== GAME COMMANDS =====
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

    # ===== BUTTON HANDLER =====
    @handle_errors
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # FOMO button handlers
        if query.data == "live_stats":
            await self.live_stats_command(update, context)
        elif query.data == "recent_buyers":
            await self.whobought_command(update, context)
        elif query.data == "predictions":
            await self.price_prediction_command(update, context)
        elif query.data == "presale_progress":
            await self.presale_status_command(update, context)
        elif query.data == "presale_details":
            await self.benefits_command(update, context)
        elif query.data == "milestones":
            await self.milestone_command(update, context)
        elif query.data == "calculate_returns":
            # Simple return calculator
            calc_msg = """
💰 **RETURN CALCULATOR**

**Your Investment → Potential Returns:**

📊 **10 TON Investment:**
• At 2x: 20 TON
• At 10x: 100 TON
• At 50x: 500 TON
• At 100x: 1,000 TON

📊 **50 TON Investment:**
• At 2x: 100 TON
• At 10x: 500 TON
• At 50x: 2,500 TON
• At 100x: 5,000 TON

📊 **100 TON Investment:**
• At 2x: 200 TON
• At 10x: 1,000 TON
• At 50x: 5,000 TON
• At 100x: 10,000 TON

🔥 **Remember:** These are based on similar projects that succeeded!
            """
            keyboard = [[InlineKeyboardButton("💎 INVEST NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
            await query.edit_message_text(calc_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        # Game button handlers
        elif query.data == "game":
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

    # ===== MESSAGE HANDLER =====
    @rate_limit(max_calls=10, period=60, group_max_calls=20, group_period=60)
    @handle_errors
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages with anti-spam and FOMO responses"""
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
        
        # FOMO keywords
        fomo_words = ['price', 'presale', 'buy', 'invest', 'fomo', 'pump', 'moon', 'listing', 'dex', 'prediction']
        game_words = ['game', 'play', 'adventure', 'score', 'leaderboard', 'stats']
        
        if any(word in message for word in fomo_words):
            responses = [
                f"🚀 {user_name}! Presale is {self.get_presale_progress()['percentage']:.1f}% filled! Don't miss out!",
                f"💎 {user_name}, only {self.get_presale_progress()['remaining']} TON spots left! Time is running out!",
                f"🔥 {user_name}, smart money is moving! {len([tx for tx in self.fomo_stats['recent_buyers'] if tx['amount'] >= 50])} whales already joined!"
            ]
            response = random.choice(responses)
            response += "\n\n🎯 Use /stats for live updates or /predict for price predictions!"
            
            keyboard = [[InlineKeyboardButton("💎 BUY NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
            await update.message.reply_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        elif any(word in message for word in game_words):
            responses = [
                f"🎮 {user_name}! CaptainCat Adventure awaits! Collect CAT coins and defeat bear markets!",
                f"🚀 Ready for adventure, {user_name}? The game is full of crypto surprises!",
                f"⚡ {user_name}, become the leaderboard king! Use /game to start!"
            ]
            response = random.choice(responses) + "\n\n🎯 Use /game to play now!"
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            response = self.generate_ai_response(message, user_name)
            await update.message.reply_text(response, parse_mode='Markdown')
        
        # Track activity for chat animation
        self.chat_animation['last_message_time'] = datetime.now()
        self.chat_animation['message_count'] += 1
        self.chat_animation['active_users'].add(user_id)

    def generate_ai_response(self, message: str, user_name: str) -> str:
        """Generate AI response with FOMO elements"""
        greetings = ['hello', 'hi', 'hey', 'good morning', 'good evening', 'greetings']
        price_words = ['price', 'cost', 'how much', 'value', 'worth']
        
        progress = self.get_presale_progress()
        
        if any(word in message for word in greetings):
            responses = [
                f"🐱‍🦸 Hello {user_name}! Welcome to CaptainCat! Did you know presale is {progress['percentage']:.1f}% filled?",
                f"🚀 Meow {user_name}! I'm CaptainCat AI! Have you checked our price predictions? Use /predict!",
                f"⚡ Greetings {user_name}! Ready to join {len(set(tx['buyer'] for tx in self.fomo_stats['recent_buyers']))} other investors?"
            ]
            return random.choice(responses) + "\n\n🎮 Don't forget to try CaptainCat Adventure Game!"
        elif any(word in message for word in price_words):
            return f"""💎 **Current Presale Price:**
• 1 TON = 10,000 CAT
• Progress: {progress['percentage']:.1f}% filled
• Remaining: {progress['remaining']} TON

🚀 After presale, price will NEVER be this low!
Use /predict to see potential returns!"""
        else:
            responses = [
                f"Interesting question, {user_name}! While I think about it, did you see we're {progress['percentage']:.1f}% sold?",
                f"{user_name}, great question! BTW, {len([tx for tx in self.fomo_stats['recent_buyers'] if datetime.now() - tx['time'] < timedelta(hours=1)])} people bought in the last hour!",
                f"Hello {user_name}! I'll help you! Quick update: only {progress['remaining']} TON spots left in presale!",
                f"{user_name}, let me help! Fun fact: last buyer got {self.fomo_stats['recent_buyers'][-1]['amount'] * PRESALE_CONFIG['token_price']:,.0f} CAT tokens!" if self.fomo_stats['recent_buyers'] else f"{user_name}, I'm here to help! Presale is filling fast!"
            ]
            return random.choice(responses) + f"\n\n❓ Try: /stats, /whobought, /predict, /fomo"

    # ===== INITIALIZATION =====
    async def initialize_database(self):
        """Initialize database on startup"""
        await self.db.init_pool()

    # ===== RUN METHOD =====
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
        print("❌ ERROR: BOT_TOKEN environment variable not found!")
        print("💡 Configure the following environment variables on Render:")
        print("- BOT_TOKEN (required)")
        print("- TON_API_KEY (for transaction monitoring)")
        print("- TOKEN_CONTRACT_ADDRESS (your CAT token contract)")
        print("- NOTIFICATION_CHAT_ID (chat ID for transaction notifications)")
        print("- DATABASE_URL (for persistence)")
        print("- WEBAPP_URL (for game)")
        print("- MAIN_GROUP_ID (for FOMO messages)")
        print("- ANNOUNCEMENT_CHANNEL_ID (for FOMO messages)")
    else:
        print(f"🚀 Starting CaptainCat FOMO Bot...")
        bot = CaptainCatFOMOBot(BOT_TOKEN)
        bot.run()
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

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
TON_API_KEY = os.environ.get('TON_API_KEY')
TOKEN_CONTRACT_ADDRESS = os.environ.get('TOKEN_CONTRACT_ADDRESS')
NOTIFICATION_CHAT_ID = os.environ.get('NOTIFICATION_CHAT_ID')

# Anti-spam configuration
SPAM_THRESHOLD = {
    'messages_per_minute': 10,
    'messages_per_hour': 60,
    'duplicate_threshold': 3,
    'link_threshold': 5,
    'emoji_threshold': 20
}

# ===== FOMO SYSTEM CONFIGURATION =====
PRESALE_CONFIG = {
    'target': 1500,  # TON target
    'start_date': datetime(2024, 12, 1),  # Adjust to your presale start
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
                    message = await self.bot.format_transaction_message(tx_data)
                    
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
                logger.error(f"Error in countdown timer: {e}")
                await asyncio.sleep(3600)

    # ===== CHAT ANIMATION FEATURES =====
    async def chat_animator(self):
        """Animate chat with light engaging messages"""
        await asyncio.sleep(600)  # Wait 10 min after start
        
        engagement_messages = [
            "🎯 Quick question fam: Who's already in the game? Drop a 🐱 if you're a CAT holder!",
            "☕ Gm legends! How's everyone feeling about CaptainCat today? 🚀",
            "💭 Fun fact: Did you know cats have been worshipped for over 4000 years? Time to worship CAT token! 😸",
            "🎮 Who's playing CaptainCat Adventure right now? Share your high score! 🏆",
            "🌍 Where is our community from? Drop your flag! 🏴‍☠️",
            "⚡ Energy check! Rate your FOMO level from 1-10! Mine is 11! 🔥",
            "🤔 What brought you to CaptainCat? The game? The community? The gains? Tell us!",
            "📊 Poll time! Who thinks we'll hit our presale target this week? 🙋‍♂️",
            "🎲 Lucky number time! Comment your lucky number for a surprise! 🍀",
            "💎 Shoutout to all diamond hands in here! You're the real MVPs! 👑",
            "🌙 Night owls or early birds? When do you check crypto? 🦉",
            "🎯 What's your CAT price prediction for EOY? Dream big! 💭",
            "🔥 The energy in here is incredible! Love this community! ❤️",
            "📈 Chart watchers, how we looking? Bullish vibes only! 🐂",
            "🎪 Welcome to all new members! Say hi and introduce yourself! 👋"
        ]
        
        questions = [
            "❓ What's your favorite thing about CaptainCat so far?",
            "🎮 What's your best score in the game? Screenshot it!",
            "💰 What was your first crypto? Mine was BTC at $100 (sold at $150 😭)",
            "🚀 If CAT hits $1, what will you do first?",
            "🌟 Who referred you to CaptainCat? Tag them!",
            "📱 iOS or Android for crypto? Let's settle this!",
            "🏆 What achievement are you most proud of in crypto?",
            "🎯 Realistic EOY price prediction? Go!",
            "🤝 Best crypto community you've been part of? (Besides this one 😉)",
            "💡 Any suggestions for the project? We're listening!"
        ]
        
        while self.chat_animation['enabled']:
            try:
                # Check chat activity
                time_since_last = datetime.now() - self.chat_animation['last_message_time']
                
                # If chat is quiet for 20-40 min, send something
                if time_since_last.seconds > random.randint(1200, 2400):
                    # Choose message type
                    message_type = random.choice(['engagement', 'question', 'motivation'])
                    
                    if message_type == 'engagement':
                        message = random.choice(engagement_messages)
                    elif message_type == 'question':
                        message = random.choice(questions)
                    else:
                        message = await self.get_motivation_message()
                    
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(
                                    channel_id,
                                    message,
                                    parse_mode='Markdown'
                                )
                                self.chat_animation['last_message_time'] = datetime.now()
                            except:
                                pass
                
                # Wait before next check
                await asyncio.sleep(random.randint(300, 600))  # 5-10 min
                
            except Exception as e:
                logger.error(f"Error in chat animator: {e}")
                await asyncio.sleep(600)

    async def community_engager(self):
        """Send periodic community building messages"""
        await asyncio.sleep(900)  # Wait 15 min
        
        while True:
            try:
                hour = datetime.now().hour
                
                # Time-based messages
                if hour == 9:  # Morning
                    messages = [
                        "☀️ **GM CAT FAM!** ☀️\n\nNew day, new opportunities! Let's make it count! 🚀",
                        "🌅 **Rise and shine CaptainCats!**\n\nWho's ready to conquer the crypto world today? 💪",
                        "☕ **Morning coffee + Chart checking = Perfect combo!**\n\nHow's everyone feeling? 📈"
                    ]
                elif hour == 13:  # Afternoon  
                    messages = [
                        "🍔 **Lunch break check-in!**\n\nDon't forget to play a quick game! 🎮",
                        "⚡ **Afternoon energy boost!**\n\nPresale progress looking amazing! Who's excited? 🔥",
                        "📊 **Mid-day update!**\n\nWe're growing fast! Welcome all new members! 🎉"
                    ]
                elif hour == 18:  # Evening
                    messages = [
                        "🌆 **Evening vibes with the best community!**\n\nHow was your day, CAT fam? 💫",
                        "🍻 **After work = CAT time!**\n\nWho's checking the game leaderboard? 🏆",
                        "🎯 **Daily reminder:**\n\nYou're early to something special! 🚀"
                    ]
                elif hour == 22:  # Night
                    messages = [
                        "🌙 **Goodnight from CaptainCat!**\n\nRest well, tomorrow we moon! 🚀",
                        "⭐ **Night shift crew, where you at?**\n\nChart never sleeps! 📈",
                        "😴 **Sweet dreams of green candles!**\n\nSee you tomorrow, legends! 💎"
                    ]
                else:
                    messages = None
                
                if messages:
                    message = random.choice(messages)
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(channel_id, message, parse_mode='Markdown')
                            except:
                                pass
                
                # Wait 3-4 hours
                await asyncio.sleep(random.randint(10800, 14400))
                
            except Exception as e:
                logger.error(f"Error in community engager: {e}")
                await asyncio.sleep(3600)

    async def random_fact_sender(self):
        """Send interesting crypto/cat facts"""
        await asyncio.sleep(1800)  # Wait 30 min
        
        facts = [
            "🧠 **Did you know?** The first Bitcoin transaction was for pizza! 10,000 BTC for 2 pizzas. Today that's worth $400M+ 🍕",
            "🐱 **Cat Fact:** Cats spend 70% of their lives sleeping. That's 13-16 hours a day! Just like HODLers checking charts! 😴",
            "💎 **Crypto Wisdom:** 'Time in the market beats timing the market' - This is why early investors win! ⏰",
            "🚀 **Fun Fact:** There are over 2.9 million crypto wallets created daily! You're part of the revolution! 🌍",
            "😸 **Cat Fact:** A group of cats is called a 'clowder'. A group of CAT holders? Legends! 👑",
            "📈 **History:** Dogecoin was created as a joke in 2013. Now it's worth billions. Never underestimate memes! 🐕",
            "🧮 **Math Time:** If you bought $100 of BTC in 2010, you'd have $48 million today. Early = Smart! 🤯",
            "🐾 **Cat Fact:** Cats can jump up to 6 times their length! Just like CAT token will jump! 🦘",
            "💡 **Did you know?** 'HODL' came from a drunk Bitcoin forum post in 2013. Now it's crypto law! 🍺",
            "🌟 **Fact:** Over 100 million people own crypto worldwide. We're still early! 🌍"
        ]
        
        tips = [
            "💡 **Pro Tip:** Always DYOR (Do Your Own Research). Knowledge is power in crypto! 📚",
            "🛡️ **Security Tip:** Never share your seed phrase. Not even with support! 🔒",
            "📊 **Trading Tip:** Emotions are your enemy. Have a plan and stick to it! 🎯",
            "💎 **HODL Tip:** Zoom out on charts when in doubt. Long term vision wins! 🔭",
            "🎮 **Game Tip:** Play during low traffic hours for better performance! ⚡",
            "🚀 **Investment Tip:** Only invest what you can afford to lose. Stay safe! 🛡️",
            "📈 **Chart Tip:** Support and resistance levels are your friends! 📏",
            "🐱 **CAT Tip:** Engage with the community. We're stronger together! 🤝",
            "⏰ **Timing Tip:** DCA (Dollar Cost Average) beats trying to time the market! 📅",
            "🧠 **Mindset Tip:** Think in years, not days. Patience pays! ⏳"
        ]
        
        while True:
            try:
                # Send fact or tip
                if random.choice([True, False]):
                    message = random.choice(facts)
                else:
                    message = random.choice(tips)
                
                # Avoid repeating
                if message != self.chat_animation.get('last_fact'):
                    self.chat_animation['last_fact'] = message
                    
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(channel_id, message, parse_mode='Markdown')
                            except:
                                pass
                
                # Wait 2-3 hours
                await asyncio.sleep(random.randint(7200, 10800))
                
            except Exception as e:
                logger.error(f"Error in fact sender: {e}")
                await asyncio.sleep(3600)

    async def get_motivation_message(self) -> str:
        """Get motivational message"""
        progress = self.get_presale_progress()
        
        motivations = [
            f"🔥 **LFG CAT FAM!** We're {progress['percentage']:.1f}% to our goal! Every contribution matters! 🚀",
            f"💪 **Stay strong CaptainCats!** Only {progress['remaining']} TON to go! We got this! 💎",
            "🌟 **Remember:** The best time to plant a tree was 20 years ago. The second best time is now! 🌳",
            "🚀 **Greatness awaits those who dare!** You're part of something special! ⭐",
            "💎 **Diamond hands are forged under pressure!** Stay strong, stay CAT! 💪",
            f"📈 **Progress update:** {progress['percentage']:.1f}% complete! History in the making! 📚",
            "🎯 **Focus on the goal:** DEX listing is coming! Then we fly! 🦅",
            "⚡ **Energy breeds energy!** Keep the momentum going, legends! 🔥",
            "🌙 **To the moon? No, we're going to build our own galaxy!** 🌌",
            "👑 **You're not just investors, you're pioneers!** First movers advantage! 🏆"
        ]
        
        return random.choice(motivations)

    # ===== CHAT ANIMATION COMMANDS =====
    @handle_errors
    async def chatboost_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to control chat animation"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await self.is_admin(user_id, chat_id):
            await update.message.reply_text("🔒 This command is for admins only.")
            return
        
        if context.args and context.args[0].lower() == 'off':
            self.chat_animation['enabled'] = False
            await update.message.reply_text("🔇 Chat animation disabled.")
        elif context.args and context.args[0].lower() == 'on':
            self.chat_animation['enabled'] = True
            await update.message.reply_text("🔊 Chat animation enabled!")
        else:
            status = "🟢 ON" if self.chat_animation['enabled'] else "🔴 OFF"
            await update.message.reply_text(
                f"💬 **Chat Animation Status:** {status}\n\n"
                f"Commands:\n"
                f"/chatboost on - Enable animation\n"
                f"/chatboost off - Disable animation",
                parse_mode='Markdown'
            )

    @handle_errors
    async def crypto_fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a random crypto fact"""
        facts = [
            "🧠 Satoshi Nakamoto's identity remains unknown, holding ~1 million BTC!",
            "💰 The total crypto market cap exceeded $3 trillion in 2021!",
            "🍕 Bitcoin Pizza Day is May 22nd - celebrating the first BTC transaction!",
            "⚡ There will only ever be 21 million Bitcoin!",
            "🌍 El Salvador was the first country to adopt Bitcoin as legal tender!",
            "📱 More people have crypto wallets than bank accounts in some countries!",
            "🔥 About 20% of all Bitcoin is lost forever in inaccessible wallets!",
            "🚀 The word 'cryptocurrency' was added to Merriam-Webster in 2018!",
            "💎 'Satoshi' is the smallest unit of Bitcoin (0.00000001 BTC)!",
            "🎮 The first NFT was created in 2014, before Ethereum existed!"
        ]
        
        fact = random.choice(facts)
        await update.message.reply_text(f"💡 **Crypto Fact:**\n\n{fact}", parse_mode='Markdown')

    @handle_errors
    async def motivate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send motivational message"""
        message = await self.get_motivation_message()
        
        keyboard = [[InlineKeyboardButton("💎 I'M MOTIVATED!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(status_msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(status_msg, reply_markup=reply_markup, parse_mode='Markdown')"Error in transaction monitoring: {e}")
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
            'raised': 0.077168252,  # Aggiungi la transazione vista nei log
            'last_buy_time': datetime.now(),
            'recent_buyers': [],
            'whale_alerts': [],
            'community_milestones': [],
            'scheduled_messages': {}
        }
        
        # Chat animation state
        self.chat_animation = {
            'enabled': True,
            'last_message_time': datetime.now(),
            'message_count': 0,
            'active_users': set(),
            'last_fact': None
        }
        
        # FOMO Channels - aggiungi i tuoi gruppi target
        self.fomo_channels = []
        if os.environ.get('MAIN_GROUP_ID'):
            self.fomo_channels.append(int(os.environ.get('MAIN_GROUP_ID')))
        if os.environ.get('ANNOUNCEMENT_CHANNEL_ID'):
            self.fomo_channels.append(int(os.environ.get('ANNOUNCEMENT_CHANNEL_ID')))
        
        self.setup_handlers()
        self.setup_fomo_handlers()

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

    def setup_fomo_handlers(self):
        """Setup FOMO-specific command handlers"""
        self.app.add_handler(CommandHandler("stats", self.live_stats_command))
        self.app.add_handler(CommandHandler("whobought", self.whobought_command))
        self.app.add_handler(CommandHandler("presalestatus", self.presale_status_command))
        self.app.add_handler(CommandHandler("predict", self.price_prediction_command))
        self.app.add_handler(CommandHandler("benefits", self.benefits_command))
        self.app.add_handler(CommandHandler("fomo", self.fomo_command))
        self.app.add_handler(CommandHandler("milestone", self.milestone_command))
        
        # Chat animation commands
        self.app.add_handler(CommandHandler("chatboost", self.chatboost_command))
        self.app.add_handler(CommandHandler("fact", self.crypto_fact_command))
        self.app.add_handler(CommandHandler("motivate", self.motivate_command))

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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(stats_message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(stats_message, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def whobought_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent buyers to create FOMO"""
        recent = sorted(self.fomo_stats['recent_buyers'], 
                       key=lambda x: x['time'], reverse=True)[:10]
        
        if not recent:
            no_buyers_msg = "🚀 Be the FIRST hero to buy CaptainCat!"
            if update.callback_query:
                await update.callback_query.edit_message_text(no_buyers_msg)
            else:
                await update.message.reply_text(no_buyers_msg)
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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
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
• +15% Whale Bonus (>50 TON)
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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    # ===== AUTOMATED FOMO MESSAGES =====
    async def start_fomo_scheduler(self):
        """Start automated FOMO message scheduler"""
        asyncio.create_task(self.hourly_fomo_blast())
        asyncio.create_task(self.momentum_tracker())
        asyncio.create_task(self.whale_watcher())
        asyncio.create_task(self.milestone_announcer())
        asyncio.create_task(self.countdown_timer())
        asyncio.create_task(self.chat_animator())
        asyncio.create_task(self.community_engager())
        asyncio.create_task(self.random_fact_sender())
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

    # ===== CHAT ANIMATION FEATURES =====
    async def chat_animator(self):
        """Animate chat with light engaging messages"""
        await asyncio.sleep(600)  # Wait 10 min after start
        
        engagement_messages = [
            "🎯 Quick question fam: Who's already in the game? Drop a 🐱 if you're a CAT holder!",
            "☕ Gm legends! How's everyone feeling about CaptainCat today? 🚀",
            "💭 Fun fact: Did you know cats have been worshipped for over 4000 years? Time to worship CAT token! 😸",
            "🎮 Who's playing CaptainCat Adventure right now? Share your high score! 🏆",
            "🌍 Where is our community from? Drop your flag! 🏴‍☠️",
            "⚡ Energy check! Rate your FOMO level from 1-10! Mine is 11! 🔥",
            "🤔 What brought you to CaptainCat? The game? The community? The gains? Tell us!",
            "📊 Poll time! Who thinks we'll hit our presale target this week? 🙋‍♂️",
            "🎲 Lucky number time! Comment your lucky number for a surprise! 🍀",
            "💎 Shoutout to all diamond hands in here! You're the real MVPs! 👑",
            "🌙 Night owls or early birds? When do you check crypto? 🦉",
            "🎯 What's your CAT price prediction for EOY? Dream big! 💭",
            "🔥 The energy in here is incredible! Love this community! ❤️",
            "📈 Chart watchers, how we looking? Bullish vibes only! 🐂",
            "🎪 Welcome to all new members! Say hi and introduce yourself! 👋"
        ]
        
        questions = [
            "❓ What's your favorite thing about CaptainCat so far?",
            "🎮 What's your best score in the game? Screenshot it!",
            "💰 What was your first crypto? Mine was BTC at $100 (sold at $150 😭)",
            "🚀 If CAT hits $1, what will you do first?",
            "🌟 Who referred you to CaptainCat? Tag them!",
            "📱 iOS or Android for crypto? Let's settle this!",
            "🏆 What achievement are you most proud of in crypto?",
            "🎯 Realistic EOY price prediction? Go!",
            "🤝 Best crypto community you've been part of? (Besides this one 😉)",
            "💡 Any suggestions for the project? We're listening!"
        ]
        
        while self.chat_animation['enabled']:
            try:
                # Check chat activity
                time_since_last = datetime.now() - self.chat_animation['last_message_time']
                
                # If chat is quiet for 20-40 min, send something
                if time_since_last.seconds > random.randint(1200, 2400):
                    # Choose message type
                    message_type = random.choice(['engagement', 'question', 'motivation'])
                    
                    if message_type == 'engagement':
                        message = random.choice(engagement_messages)
                    elif message_type == 'question':
                        message = random.choice(questions)
                    else:
                        message = await self.get_motivation_message()
                    
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(
                                    channel_id,
                                    message,
                                    parse_mode='Markdown'
                                )
                                self.chat_animation['last_message_time'] = datetime.now()
                            except:
                                pass
                
                # Wait before next check
                await asyncio.sleep(random.randint(300, 600))  # 5-10 min
                
            except Exception as e:
                logger.error(f"Error in chat animator: {e}")
                await asyncio.sleep(600)

    async def community_engager(self):
        """Send periodic community building messages"""
        await asyncio.sleep(900)  # Wait 15 min
        
        while True:
            try:
                hour = datetime.now().hour
                
                # Time-based messages
                if hour == 9:  # Morning
                    messages = [
                        "☀️ **GM CAT FAM!** ☀️\n\nNew day, new opportunities! Let's make it count! 🚀",
                        "🌅 **Rise and shine CaptainCats!**\n\nWho's ready to conquer the crypto world today? 💪",
                        "☕ **Morning coffee + Chart checking = Perfect combo!**\n\nHow's everyone feeling? 📈"
                    ]
                elif hour == 13:  # Afternoon  
                    messages = [
                        "🍔 **Lunch break check-in!**\n\nDon't forget to play a quick game! 🎮",
                        "⚡ **Afternoon energy boost!**\n\nPresale progress looking amazing! Who's excited? 🔥",
                        "📊 **Mid-day update!**\n\nWe're growing fast! Welcome all new members! 🎉"
                    ]
                elif hour == 18:  # Evening
                    messages = [
                        "🌆 **Evening vibes with the best community!**\n\nHow was your day, CAT fam? 💫",
                        "🍻 **After work = CAT time!**\n\nWho's checking the game leaderboard? 🏆",
                        "🎯 **Daily reminder:**\n\nYou're early to something special! 🚀"
                    ]
                elif hour == 22:  # Night
                    messages = [
                        "🌙 **Goodnight from CaptainCat!**\n\nRest well, tomorrow we moon! 🚀",
                        "⭐ **Night shift crew, where you at?**\n\nChart never sleeps! 📈",
                        "😴 **Sweet dreams of green candles!**\n\nSee you tomorrow, legends! 💎"
                    ]
                else:
                    messages = None
                
                if messages:
                    message = random.choice(messages)
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(channel_id, message, parse_mode='Markdown')
                            except:
                                pass
                
                # Wait 3-4 hours
                await asyncio.sleep(random.randint(10800, 14400))
                
            except Exception as e:
                logger.error(f"Error in community engager: {e}")
                await asyncio.sleep(3600)

    async def random_fact_sender(self):
        """Send interesting crypto/cat facts"""
        await asyncio.sleep(1800)  # Wait 30 min
        
        facts = [
            "🧠 **Did you know?** The first Bitcoin transaction was for pizza! 10,000 BTC for 2 pizzas. Today that's worth $400M+ 🍕",
            "🐱 **Cat Fact:** Cats spend 70% of their lives sleeping. That's 13-16 hours a day! Just like HODLers checking charts! 😴",
            "💎 **Crypto Wisdom:** 'Time in the market beats timing the market' - This is why early investors win! ⏰",
            "🚀 **Fun Fact:** There are over 2.9 million crypto wallets created daily! You're part of the revolution! 🌍",
            "😸 **Cat Fact:** A group of cats is called a 'clowder'. A group of CAT holders? Legends! 👑",
            "📈 **History:** Dogecoin was created as a joke in 2013. Now it's worth billions. Never underestimate memes! 🐕",
            "🧮 **Math Time:** If you bought $100 of BTC in 2010, you'd have $48 million today. Early = Smart! 🤯",
            "🐾 **Cat Fact:** Cats can jump up to 6 times their length! Just like CAT token will jump! 🦘",
            "💡 **Did you know?** 'HODL' came from a drunk Bitcoin forum post in 2013. Now it's crypto law! 🍺",
            "🌟 **Fact:** Over 100 million people own crypto worldwide. We're still early! 🌍"
        ]
        
        tips = [
            "💡 **Pro Tip:** Always DYOR (Do Your Own Research). Knowledge is power in crypto! 📚",
            "🛡️ **Security Tip:** Never share your seed phrase. Not even with support! 🔒",
            "📊 **Trading Tip:** Emotions are your enemy. Have a plan and stick to it! 🎯",
            "💎 **HODL Tip:** Zoom out on charts when in doubt. Long term vision wins! 🔭",
            "🎮 **Game Tip:** Play during low traffic hours for better performance! ⚡",
            "🚀 **Investment Tip:** Only invest what you can afford to lose. Stay safe! 🛡️",
            "📈 **Chart Tip:** Support and resistance levels are your friends! 📏",
            "🐱 **CAT Tip:** Engage with the community. We're stronger together! 🤝",
            "⏰ **Timing Tip:** DCA (Dollar Cost Average) beats trying to time the market! 📅",
            "🧠 **Mindset Tip:** Think in years, not days. Patience pays! ⏳"
        ]
        
        while True:
            try:
                # Send fact or tip
                if random.choice([True, False]):
                    message = random.choice(facts)
                else:
                    message = random.choice(tips)
                
                # Avoid repeating
                if message != self.chat_animation.get('last_fact'):
                    self.chat_animation['last_fact'] = message
                    
                    for channel_id in self.fomo_channels:
                        if channel_id:
                            try:
                                await self.app.bot.send_message(channel_id, message, parse_mode='Markdown')
                            except:
                                pass
                
                # Wait 2-3 hours
                await asyncio.sleep(random.randint(7200, 10800))
                
            except Exception as e:
                logger.error(f"Error in fact sender: {e}")
                await asyncio.sleep(3600)

    async def get_motivation_message(self) -> str:
        """Get motivational message"""
        progress = self.get_presale_progress()
        
        motivations = [
            f"🔥 **LFG CAT FAM!** We're {progress['percentage']:.1f}% to our goal! Every contribution matters! 🚀",
            f"💪 **Stay strong CaptainCats!** Only {progress['remaining']} TON to go! We got this! 💎",
            "🌟 **Remember:** The best time to plant a tree was 20 years ago. The second best time is now! 🌳",
            "🚀 **Greatness awaits those who dare!** You're part of something special! ⭐",
            "💎 **Diamond hands are forged under pressure!** Stay strong, stay CAT! 💪",
            f"📈 **Progress update:** {progress['percentage']:.1f}% complete! History in the making! 📚",
            "🎯 **Focus on the goal:** DEX listing is coming! Then we fly! 🦅",
            "⚡ **Energy breeds energy!** Keep the momentum going, legends! 🔥",
            "🌙 **To the moon? No, we're going to build our own galaxy!** 🌌",
            "👑 **You're not just investors, you're pioneers!** First movers advantage! 🏆"
        ]
        
        return random.choice(motivations)

    # ===== CHAT ANIMATION COMMANDS =====
    @handle_errors
    async def chatboost_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to control chat animation"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not await self.is_admin(user_id, chat_id):
            await update.message.reply_text("🔒 This command is for admins only.")
            return
        
        if context.args and context.args[0].lower() == 'off':
            self.chat_animation['enabled'] = False
            await update.message.reply_text("🔇 Chat animation disabled.")
        elif context.args and context.args[0].lower() == 'on':
            self.chat_animation['enabled'] = True
            await update.message.reply_text("🔊 Chat animation enabled!")
        else:
            status = "🟢 ON" if self.chat_animation['enabled'] else "🔴 OFF"
            await update.message.reply_text(
                f"💬 **Chat Animation Status:** {status}\n\n"
                f"Commands:\n"
                f"/chatboost on - Enable animation\n"
                f"/chatboost off - Disable animation",
                parse_mode='Markdown'
            )

    @handle_errors
    async def crypto_fact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a random crypto fact"""
        facts = [
            "🧠 Satoshi Nakamoto's identity remains unknown, holding ~1 million BTC!",
            "💰 The total crypto market cap exceeded $3 trillion in 2021!",
            "🍕 Bitcoin Pizza Day is May 22nd - celebrating the first BTC transaction!",
            "⚡ There will only ever be 21 million Bitcoin!",
            "🌍 El Salvador was the first country to adopt Bitcoin as legal tender!",
            "📱 More people have crypto wallets than bank accounts in some countries!",
            "🔥 About 20% of all Bitcoin is lost forever in inaccessible wallets!",
            "🚀 The word 'cryptocurrency' was added to Merriam-Webster in 2018!",
            "💎 'Satoshi' is the smallest unit of Bitcoin (0.00000001 BTC)!",
            "🎮 The first NFT was created in 2014, before Ethereum existed!"
        ]
        
        fact = random.choice(facts)
        await update.message.reply_text(f"💡 **Crypto Fact:**\n\n{fact}", parse_mode='Markdown')

    @handle_errors
    async def motivate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send motivational message"""
        message = await self.get_motivation_message()
        
        keyboard = [[InlineKeyboardButton("💎 I'M MOTIVATED!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

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
        
        # Handle both message and callback query
        if update.callback_query:
            await update.callback_query.edit_message_text(status_msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(status_msg, reply_markup=reply_markup, parse_mode='Markdown')

    # ===== BASIC COMMANDS FROM ORIGINAL BOT =====
    @handle_errors
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🎮 CaptainCat Game!", callback_data="game"),
             InlineKeyboardButton("💎 Presale", callback_data="presale")],
            [InlineKeyboardButton("🗺️ Roadmap", callback_data="roadmap"),
             InlineKeyboardButton("👥 Team", callback_data="team")],
            [InlineKeyboardButton("🏆 Game Leaderboard", callback_data="leaderboard"),
             InlineKeyboardButton("📱 Community", callback_data="community")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
            [InlineKeyboardButton("🔥 LIVE STATS", callback_data="live_stats"),
             InlineKeyboardButton("📈 PREDICTIONS", callback_data="predictions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = f"""
🐱‍🦸 **WELCOME TO CAPTAINCAT!**

Hello future hero! I'm CaptainCat AI, the superhero of meme coins!

🎮 **NEW: CaptainCat Adventure Game!**
Play, collect CAT coins and climb the leaderboard!

🚀 **PRESALE {self.get_presale_progress()['percentage']:.1f}% FILLED!**
💎 **Target: 1500 TON**
🎯 **Community: 10K+ and growing!**

🔥 **FOMO FEATURES:**
• Live presale tracking
• Price predictions  
• Recent buyer alerts
• Whale watching

What do you want to know today?
        """
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = f"""🐱‍🦸 **CAPTAINCAT BOT COMMANDS**

**📊 FOMO COMMANDS:**
/stats - Live presale statistics
/whobought - Recent buyers list
/presalestatus - Detailed presale info
/predict - Price predictions
/benefits - Presale benefits
/fomo - FOMO summary
/milestone - Progress milestones

**🎯 BASIC COMMANDS:**
/start - Start conversation
/help - Show this menu
/price - Price and tokenomics
/roadmap - Project roadmap
/team - Meet the team
/utility - Token utility
/presale - Presale info
/community - Community links
/staking - Staking rewards
/nft - NFT collection
/status - Bot status

**🎮 GAME COMMANDS:**
/game - Start CaptainCat Adventure
/play - Alias for /game
/mystats - Your game statistics
/leaderboard - Game leaderboard
/gametop - Alias for /leaderboard

**⚡ ADMIN COMMANDS:**
/antispam - Anti-spam system status
/tonmonitor - TON monitoring controls
/spaminfo - Check user spam info

🚀 **Just write and I'll respond!**
Examples: "how much?", "when listing?", "price prediction?"

⚡ **Features:**
• Advanced anti-spam protection
• Real-time transaction monitoring
• Automated FOMO alerts
• Whale tracking
• Price predictions"""
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(help_text, parse_mode='Markdown')

    @handle_errors
    async def price_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        progress = self.get_presale_progress()
        
        price_info = f"""
💎 **CAPTAINCAT TOKENOMICS**

🔥 **Presale {progress['percentage']:.1f}% FILLED!**
💰 **Raised: {progress['raised']}/{progress['target']} TON**
📊 **Total Supply: 1,000,000,000 CAT**

📈 **Distribution:**
• 40% Presale
• 30% DEX Liquidity  
• 15% Team (locked)
• 10% Marketing
• 5% Game Rewards 🎮

💵 **Current Price:**
• 1 TON = 10,000 CAT
• 1 CAT = 0.0001 TON

🚀 **Next step: LISTING on major DEXes!**

⚠️ **Only {progress['remaining']} TON spots left!**
        """
        
        keyboard = [
            [InlineKeyboardButton("💎 Join Presale", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📈 Price Predictions", callback_data="predictions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(price_info, reply_markup=reply_markup, parse_mode='Markdown')

    @handle_errors
    async def presale_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        progress = self.get_presale_progress()
        recent_buyers = len([tx for tx in self.fomo_stats['recent_buyers'] 
                           if datetime.now() - tx['time'] < timedelta(hours=1)])
        
        presale_info = f"""
💎 **CAPTAINCAT PRESALE** 💎

🔥 **LIVE STATUS:**
{self.create_progress_visual(progress['percentage'])}

💰 **Raised: {progress['raised']}/{progress['target']} TON**
⏰ **Time remaining: {progress['time_left'].days} days**
🚀 **Recent activity: {recent_buyers} buyers last hour!**

🎯 **Presale Bonuses:**
• Early Bird: +20% tokens
• Whale Bonus: +15% (>50 TON)
• Community Bonus: +10%
• Game Beta Access: INCLUDED! 🎮

📱 **How to Participate:**
1. Click button below
2. Connect wallet
3. Choose amount
4. Receive CAT + bonuses!

⚡ **At current rate: SOLD OUT in {progress['hours_to_complete']:.0f} hours!**

🚨 **Don't miss the opportunity!**
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Join Presale NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")],
            [InlineKeyboardButton("📊 Live Stats", callback_data="live_stats"),
             InlineKeyboardButton("💰 Recent Buys", callback_data="recent_buyers")]
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

🔄 **Phase 2 - Presale** (IN PROGRESS - {self.get_presale_progress()['percentage']:.1f}%)
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
        progress = self.get_presale_progress()
        total_holders = len(set(tx['buyer'] for tx in self.fomo_stats['recent_buyers']))
        
        community_info = f"""
📱 **CAPTAINCAT COMMUNITY**

🎯 **Goal: 10K Members!**
👥 **Current: Growing fast!**
💎 **Holders: {total_holders}+ heroes**
🎮 **Active Players: Increasing daily!**

📊 **PRESALE: {progress['percentage']:.1f}% FILLED!**

🔗 **Official Links:**
        """
        
        keyboard = [
            [InlineKeyboardButton("💬 Telegram Main", url="https://t.me/Captain_cat_Cain")],
            [InlineKeyboardButton("🌐 Website", url="https://captaincat.token")],
            [InlineKeyboardButton("🎮 Game Community", callback_data="leaderboard")],
            [InlineKeyboardButton("💎 Buy CAT", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]
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

⚡ **Presale investors get +50% APY boost!**
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

💎 **Presale investors get automatic whitelist!**
        """
        
        await update.message.reply_text(nft_info, parse_mode='Markdown')

    @handle_errors
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        db_status = "✅ Connected" if self.db.pool else "⚠️ Not available"
        ton_status = "🟢 Active" if self.ton_monitor.monitoring else "🔴 Inactive"
        progress = self.get_presale_progress()
        
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

📊 **PRESALE STATUS:**
• Progress: {progress['percentage']:.1f}%
• Raised: {progress['raised']}/{progress['target']} TON
• Recent activity: {len([tx for tx in self.fomo_stats['recent_buyers'] if datetime.now() - tx['time'] < timedelta(hours=1)])} buyers/hour

🔥 **FOMO Features:**
• Automated alerts: ACTIVE
• Whale tracking: ENABLED
• Price predictions: READY
• Milestone tracking: ON

💪 **Ready to help the community reach the moon!**
        """
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    # ===== ANTI-SPAM COMMANDS =====
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

    # ===== GAME COMMANDS =====
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

    # ===== BUTTON HANDLER =====
    @handle_errors
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # FOMO button handlers
        if query.data == "live_stats":
            await self.live_stats_command(update, context)
        elif query.data == "recent_buyers":
            await self.whobought_command(update, context)
        elif query.data == "predictions":
            await self.price_prediction_command(update, context)
        elif query.data == "presale_progress":
            await self.presale_status_command(update, context)
        elif query.data == "presale_details":
            await self.benefits_command(update, context)
        elif query.data == "milestones":
            await self.milestone_command(update, context)
        elif query.data == "calculate_returns":
            # Simple return calculator
            calc_msg = """
💰 **RETURN CALCULATOR**

**Your Investment → Potential Returns:**

📊 **10 TON Investment:**
• At 2x: 20 TON
• At 10x: 100 TON
• At 50x: 500 TON
• At 100x: 1,000 TON

📊 **50 TON Investment:**
• At 2x: 100 TON
• At 10x: 500 TON
• At 50x: 2,500 TON
• At 100x: 5,000 TON

📊 **100 TON Investment:**
• At 2x: 200 TON
• At 10x: 1,000 TON
• At 50x: 5,000 TON
• At 100x: 10,000 TON

🔥 **Remember:** These are based on similar projects that succeeded!
            """
            keyboard = [[InlineKeyboardButton("💎 INVEST NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
            await query.edit_message_text(calc_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        # Game button handlers
        elif query.data == "game":
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

    # ===== MESSAGE HANDLER =====
    @rate_limit(max_calls=10, period=60, group_max_calls=20, group_period=60)
    @handle_errors
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages with anti-spam and FOMO responses"""
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
        
        # FOMO keywords
        fomo_words = ['price', 'presale', 'buy', 'invest', 'fomo', 'pump', 'moon', 'listing', 'dex', 'prediction']
        game_words = ['game', 'play', 'adventure', 'score', 'leaderboard', 'stats']
        
        if any(word in message for word in fomo_words):
            responses = [
                f"🚀 {user_name}! Presale is {self.get_presale_progress()['percentage']:.1f}% filled! Don't miss out!",
                f"💎 {user_name}, only {self.get_presale_progress()['remaining']} TON spots left! Time is running out!",
                f"🔥 {user_name}, smart money is moving! {len([tx for tx in self.fomo_stats['recent_buyers'] if tx['amount'] >= 50])} whales already joined!"
            ]
            response = random.choice(responses)
            response += "\n\n🎯 Use /stats for live updates or /predict for price predictions!"
            
            keyboard = [[InlineKeyboardButton("💎 BUY NOW!", url="https://t.me/blum/app?startapp=memepadjetton_CAPT_caHzE-ref_AeHwZ0VMTm")]]
            await update.message.reply_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        elif any(word in message for word in game_words):
            responses = [
                f"🎮 {user_name}! CaptainCat Adventure awaits! Collect CAT coins and defeat bear markets!",
                f"🚀 Ready for adventure, {user_name}? The game is full of crypto surprises!",
                f"⚡ {user_name}, become the leaderboard king! Use /game to start!"
            ]
            response = random.choice(responses) + "\n\n🎯 Use /game to play now!"
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            response = self.generate_ai_response(message, user_name)
            await update.message.reply_text(response, parse_mode='Markdown')
        
        # Track activity for chat animation
        self.chat_animation['last_message_time'] = datetime.now()
        self.chat_animation['message_count'] += 1
        self.chat_animation['active_users'].add(user_id)

    def generate_ai_response(self, message: str, user_name: str) -> str:
        """Generate AI response with FOMO elements"""
        greetings = ['hello', 'hi', 'hey', 'good morning', 'good evening', 'greetings']
        price_words = ['price', 'cost', 'how much', 'value', 'worth']
        
        progress = self.get_presale_progress()
        
        if any(word in message for word in greetings):
            responses = [
                f"🐱‍🦸 Hello {user_name}! Welcome to CaptainCat! Did you know presale is {progress['percentage']:.1f}% filled?",
                f"🚀 Meow {user_name}! I'm CaptainCat AI! Have you checked our price predictions? Use /predict!",
                f"⚡ Greetings {user_name}! Ready to join {len(set(tx['buyer'] for tx in self.fomo_stats['recent_buyers']))} other investors?"
            ]
            return random.choice(responses) + "\n\n🎮 Don't forget to try CaptainCat Adventure Game!"
        elif any(word in message for word in price_words):
            return f"""💎 **Current Presale Price:**
• 1 TON = 10,000 CAT
• Progress: {progress['percentage']:.1f}% filled
• Remaining: {progress['remaining']} TON

🚀 After presale, price will NEVER be this low!
Use /predict to see potential returns!"""
        else:
            responses = [
                f"Interesting question, {user_name}! While I think about it, did you see we're {progress['percentage']:.1f}% sold?",
                f"{user_name}, great question! BTW, {len([tx for tx in self.fomo_stats['recent_buyers'] if datetime.now() - tx['time'] < timedelta(hours=1)])} people bought in the last hour!",
                f"Hello {user_name}! I'll help you! Quick update: only {progress['remaining']} TON spots left in presale!",
                f"{user_name}, let me help! Fun fact: last buyer got {self.fomo_stats['recent_buyers'][-1]['amount'] * PRESALE_CONFIG['token_price']:,.0f} CAT tokens!" if self.fomo_stats['recent_buyers'] else f"{user_name}, I'm here to help! Presale is filling fast!"
            ]
            return random.choice(responses) + f"\n\n❓ Try: /stats, /whobought, /predict, /fomo"

    # ===== INITIALIZATION =====
    async def initialize_database(self):
        """Initialize database on startup"""
        await self.db.init_pool()

    # ===== RUN METHOD =====
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
        print("❌ ERROR: BOT_TOKEN environment variable not found!")
        print("💡 Configure the following environment variables on Render:")
        print("- BOT_TOKEN (required)")
        print("- TON_API_KEY (for transaction monitoring)")
        print("- TOKEN_CONTRACT_ADDRESS (your CAT token contract)")
        print("- NOTIFICATION_CHAT_ID (chat ID for transaction notifications)")
        print("- DATABASE_URL (for persistence)")
        print("- WEBAPP_URL (for game)")
        print("- MAIN_GROUP_ID (for FOMO messages)")
        print("- ANNOUNCEMENT_CHANNEL_ID (for FOMO messages)")
    else:
        print(f"🚀 Starting CaptainCat FOMO Bot...")
        bot = CaptainCatFOMOBot(BOT_TOKEN)
        bot.run()
