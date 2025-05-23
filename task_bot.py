import logging
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables. Please create a .env file with BOT_TOKEN=your_token_here")

# File to store tasks
TASKS_FILE = "tasks.json"

class TaskBot:
    def __init__(self):
        self.tasks = self.load_tasks()
        self.archived_tasks = self.load_archived_tasks()
    
    def load_tasks(self):
        """Load tasks from file"""
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_tasks(self):
        """Save tasks to file"""
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)
    
    def load_archived_tasks(self):
        """Load archived tasks from file"""
        if os.path.exists("archived_tasks.json"):
            try:
                with open("archived_tasks.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_archived_tasks(self):
        """Save archived tasks to file"""
        with open("archived_tasks.json", 'w', encoding='utf-8') as f:
            json.dump(self.archived_tasks, f, ensure_ascii=False, indent=2)
    
    def get_user_tasks(self, user_id):
        """Get tasks for a specific user"""
        return self.tasks.get(str(user_id), [])
    
    def add_task(self, user_id, task_text, message_link=None):
        """Add a new task for user"""
        user_id_str = str(user_id)
        if user_id_str not in self.tasks:
            self.tasks[user_id_str] = []
        
        task = {
            'id': len(self.tasks[user_id_str]) + 1,
            'text': task_text,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'completed_at': None,
            'message_link': message_link
        }
        
        self.tasks[user_id_str].append(task)
        self.save_tasks()
        return task
    
    def complete_task(self, user_id, task_id):
        """Mark task as completed"""
        user_tasks = self.get_user_tasks(user_id)
        for task in user_tasks:
            if task['id'] == task_id:
                task['status'] = 'completed'
                task['completed_at'] = datetime.now().isoformat()
                self.save_tasks()
                return True
        return False
    
    def delete_task(self, user_id, task_id):
        """Delete a task"""
        user_id_str = str(user_id)
        if user_id_str in self.tasks:
            self.tasks[user_id_str] = [
                task for task in self.tasks[user_id_str] 
                if task['id'] != task_id
            ]
            self.save_tasks()
            return True
        return False
    
    def archive_task(self, user_id, task_id):
        """Archive a completed task"""
        user_id_str = str(user_id)
        if user_id_str not in self.tasks:
            return False
            
        task_to_archive = None
        for task in self.tasks[user_id_str]:
            if task['id'] == task_id and task['status'] == 'completed':
                task_to_archive = task
                break
                
        if not task_to_archive:
            return False
            
        # Remove from active tasks
        self.tasks[user_id_str] = [
            task for task in self.tasks[user_id_str] 
            if task['id'] != task_id
        ]
        self.save_tasks()
        
        # Add to archived tasks
        if user_id_str not in self.archived_tasks:
            self.archived_tasks[user_id_str] = []
        
        task_to_archive['archived_at'] = datetime.now().isoformat()
        self.archived_tasks[user_id_str].append(task_to_archive)
        self.save_archived_tasks()
        
        return True

    def permanently_delete_archived_task(self, user_id, task_id):
        """Permanently delete an archived task"""
        user_id_str = str(user_id)
        if user_id_str not in self.archived_tasks:
            return False
        
        # Check if task exists
        task_exists = any(task['id'] == task_id for task in self.archived_tasks[user_id_str])
        if not task_exists:
            return False
    
        # Remove from archived tasks
        self.archived_tasks[user_id_str] = [
            task for task in self.archived_tasks[user_id_str] 
            if task['id'] != task_id
        ]
        self.save_archived_tasks()
        
        return True

# Initialize task bot
task_bot = TaskBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_text = """
🤖 <b>Task Recording Bot</b>

Welcome! I can help you manage your tasks.

<b>Available commands:</b>
/add &lt;task&gt; - Add a new task
/list - Show all your tasks
/complete &lt;task_id&gt; - Mark task as completed
/delete &lt;task_id&gt; - Delete a task
/archive &lt;task_id&gt; - Archive a completed task
/archived - List all archived tasks
/archived &lt;task_id&gt; - View specific archived task
/stats - Show task statistics
/help - Show this help message

<b>Smart Features:</b>
📨 Forward any message to convert it to a task
📎 Send photos, documents, or media to create tasks
💬 Send regular text messages to create tasks

<b>Example:</b>
<code>/add Buy groceries</code>
<code>/complete 1</code>
<code>/archive 1</code>

<b>Forward Examples:</b>
- Forward a message from a colleague → Task with sender info
- Forward a photo with caption → Task with image description
- Forward a document → Task with file details
    """
    await update.message.reply_text(welcome_text, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    await start(update, context)

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add task command handler"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a task description.\n"
            "Example: `/add Buy groceries`",
            parse_mode='Markdown'
        )
        return
    
    task_text = ' '.join(context.args)
    user_id = update.effective_user.id
    
    task = task_bot.add_task(user_id, task_text)
    
    await update.message.reply_text(
        f"✅ Task added successfully!\n"
        f"*Task #{task['id']}:* {task['text']}\n"
        f"*Status:* {task['status']}\n"
        f"*Created:* {datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')}",
        parse_mode='Markdown'
    )

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List tasks command handler"""
    user_id = update.effective_user.id
    tasks = task_bot.get_user_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("📝 You have no tasks yet. Use /add to create one!")
        return
    
    # Create inline keyboard for task actions
    keyboard = []
    task_text = "📋 *Your Tasks:*\n\n"
    
    for task in tasks:
        status_emoji = "✅" if task['status'] == 'completed' else "⏳"
        created_date = datetime.fromisoformat(task['created_at']).strftime('%m/%d')
        
        task_text += f"{status_emoji} *#{task['id']}* {task['text']}\n"
        
        # Add message link if available
        if task.get('message_link'):
            task_text += f"   🔗 [Original Message]({task['message_link']})\n"
            
        task_text += f"   📅 {created_date}"
        
        if task['status'] == 'completed' and task['completed_at']:
            completed_date = datetime.fromisoformat(task['completed_at']).strftime('%m/%d')
            task_text += f" → ✅ {completed_date}"
        
        task_text += "\n\n"
        
        # Add buttons for tasks
        if task['status'] == 'pending':
            keyboard.append([
                InlineKeyboardButton(f"✅ Complete #{task['id']}", callback_data=f"complete_{task['id']}"),
                InlineKeyboardButton(f"🗑 Delete #{task['id']}", callback_data=f"delete_{task['id']}")
            ])
        else:
            # For completed tasks, add archive option
            keyboard.append([
                InlineKeyboardButton(f"📦 Archive #{task['id']}", callback_data=f"archive_{task['id']}"),
                InlineKeyboardButton(f"🗑 Delete #{task['id']}", callback_data=f"delete_{task['id']}")
            ])
    
    # Send the message with the inline keyboard
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(task_text, parse_mode='Markdown', reply_markup=reply_markup, disable_web_page_preview=True)

async def complete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Complete task command handler"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a task ID.\n"
            "Example: `/complete 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        task_id = int(context.args[0])
        user_id = update.effective_user.id
        
        if task_bot.complete_task(user_id, task_id):
            await update.message.reply_text(f"✅ Task #{task_id} marked as completed!")
        else:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
    except ValueError:
        await update.message.reply_text("Please provide a valid task ID number.")

async def delete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete task command handler"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a task ID.\n"
            "Example: `/delete 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        task_id = int(context.args[0])
        user_id = update.effective_user.id
        
        if task_bot.delete_task(user_id, task_id):
            await update.message.reply_text(f"🗑 Task #{task_id} deleted successfully!")
        else:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
    except ValueError:
        await update.message.reply_text("Please provide a valid task ID number.")

async def archive_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Archive completed task command handler"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a task ID.\n"
            "Example: `/archive 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        task_id = int(context.args[0])
        user_id = update.effective_user.id
        
        if task_bot.archive_task(user_id, task_id):
            await update.message.reply_text(f"📦 Task #{task_id} archived successfully!")
        else:
            await update.message.reply_text(f"❌ Task #{task_id} not found or not completed.")
    except ValueError:
        await update.message.reply_text("Please provide a valid task ID number.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show task statistics"""
    user_id = update.effective_user.id
    tasks = task_bot.get_user_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("📊 No tasks to show statistics for.")
        return
    
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t['status'] == 'completed'])
    pending_tasks = total_tasks - completed_tasks
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    stats_text = f"""
📊 **Task Statistics**

📝 Total tasks: {total_tasks}
✅ Completed: {completed_tasks}
⏳ Pending: {pending_tasks}
📈 Completion rate: {completion_rate:.1f}%
    """
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Handle task completion
    if data.startswith('complete_'):
        task_id = int(data.split('_')[1])
        if task_bot.complete_task(user_id, task_id):
            await query.edit_message_text(f"✅ Task #{task_id} marked as completed!")
        else:
            await query.edit_message_text(f"❌ Task #{task_id} not found.")
    
    # Handle task deletion
    elif data.startswith('delete_'):
        task_id = int(data.split('_')[1])
        if task_bot.delete_task(user_id, task_id):
            await query.edit_message_text(f"🗑 Task #{task_id} deleted successfully!")
        else:
            await query.edit_message_text(f"❌ Task #{task_id} not found.")
    
    # Handle task archiving
    elif data.startswith('archive_'):
        task_id = int(data.split('_')[1])
        if task_bot.archive_task(user_id, task_id):
            await query.edit_message_text(f"📦 Task #{task_id} archived successfully!")
        else:
            await query.edit_message_text(f"❌ Task #{task_id} not found or not completed.")
    
    # Handle forwarded message task creation
    elif data == "add_forwarded_task":
        if 'forwarded_task_content' in context.user_data:
            task_text = context.user_data['forwarded_task_content']
            message_link = context.user_data.get('forwarded_task_link')
            
            task = task_bot.add_task(user_id, task_text, message_link)
            
            response_text = f"✅ Task added successfully!\n*Task #{task['id']}:* {task['text'][:50]}{'...' if len(task['text']) > 50 else ''}"
            if message_link:
                response_text += f"\n\n🔗 [Original Message]({message_link})"
            
            # Clear the stored content
            del context.user_data['forwarded_task_content']
            if 'forwarded_task_link' in context.user_data:
                del context.user_data['forwarded_task_link']
                
            await query.edit_message_text(response_text, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            await query.edit_message_text("❌ Task content not found.")
    
    # Handle regular text message task creation
    elif data == "add_regular_task":
        if 'regular_task_content' in context.user_data:
            task_text = context.user_data['regular_task_content']
            task = task_bot.add_task(user_id, task_text)
            
            await query.edit_message_text(
                f"✅ Task added successfully!\n"
                f"*Task #{task['id']}:* {task['text']}",
                parse_mode='Markdown'
            )
            # Clear the stored content
            del context.user_data['regular_task_content']
        else:
            await query.edit_message_text("❌ Task content not found.")
    
    # Handle media message task creation
    elif data == "add_media_task":
        if 'media_task_content' in context.user_data:
            task_text = context.user_data['media_task_content']
            task = task_bot.add_task(user_id, task_text)
            
            await query.edit_message_text(
                f"✅ Task added successfully!\n"
                f"*Task #{task['id']}:* {task['text'][:50]}{'...' if len(task['text']) > 50 else ''}",
                parse_mode='Markdown'
            )
            # Clear the stored content
            del context.user_data['media_task_content']
        else:
            await query.edit_message_text("❌ Task content not found.")
    
    # Handle cancel button
    elif data == "cancel":
        await query.edit_message_text("❌ Task creation cancelled.")
        # Clear any stored content
        for key in ['forwarded_task_content', 'regular_task_content', 'media_task_content']:
            if key in context.user_data:
                del context.user_data[key]
    
    # Keep the permanent delete action for archived tasks
    elif data.startswith('perm_delete_'):
        task_id = int(data.split('_')[1])
        if task_bot.permanently_delete_archived_task(user_id, task_id):
            await query.edit_message_text(f"🗑 Task #{task_id} permanently deleted!")
        else:
            await query.edit_message_text(f"❌ Task #{task_id} not found in archived tasks.")

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle forwarded messages and convert to tasks"""
    message = update.message
    
    # Extract task content from forwarded message
    task_data = extract_task_from_message(message)
    
    if not task_data["content"]:
        await update.message.reply_text("❌ Could not extract task content from forwarded message.")
        return
    
    # Create inline keyboard for forwarded message
    keyboard = [[
        InlineKeyboardButton("✅ Add as Task", callback_data=f"add_forwarded_task"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store the forwarded content and link in context for later use
    context.user_data['forwarded_task_content'] = task_data["content"]
    if task_data["link"]:
        context.user_data['forwarded_task_link'] = task_data["link"]
    
    preview_text = task_data["content"][:100] + "..." if len(task_data["content"]) > 100 else task_data["content"]
    link_text = f"\n\n🔗 [Original Message]({task_data['link']})" if task_data["link"] else ""
    
    await update.message.reply_text(
        f"📨 *Forwarded Message Detected*\n\n"
        f"*Content Preview:*\n{preview_text}{link_text}\n\n"
        f"Do you want to add this as a task?",
        parse_mode='Markdown',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

def extract_task_from_message(message):
    """Extract task content from various message types"""
    task_parts = []
    message_link = None
    
    # Check if message is forwarded using the origin property (new API)
    if hasattr(message, 'forward_origin') and message.forward_origin:
        origin = message.forward_origin
        
        # Handle different origin types
        if hasattr(origin, 'sender_user') and origin.sender_user:
            task_parts.append(f"From: {origin.sender_user.first_name}")
        elif hasattr(origin, 'sender_user_name') and origin.sender_user_name:
            task_parts.append(f"From: {origin.sender_user_name}")
        elif hasattr(origin, 'chat') and origin.chat:
            chat_name = origin.chat.title or origin.chat.first_name or "Unknown"
            task_parts.append(f"From: {chat_name}")
            
            # Try to create a link to the original message if it's from a public channel
            if hasattr(origin, 'message_id') and hasattr(origin.chat, 'username') and origin.chat.username:
                message_link = f"https://t.me/{origin.chat.username}/{origin.message_id}"
        elif hasattr(origin, 'sender_chat') and origin.sender_chat:
            chat_name = origin.sender_chat.title or "Unknown"
            task_parts.append(f"From: {chat_name}")
            
            # Try to create a link to the original message if it's from a public channel
            if hasattr(origin, 'message_id') and hasattr(origin.sender_chat, 'username') and origin.sender_chat.username:
                message_link = f"https://t.me/{origin.sender_chat.username}/{origin.message_id}"
        
        # Add forwarded date
        if hasattr(origin, 'date') and origin.date:
            forward_date = origin.date.strftime('%Y-%m-%d %H:%M')
            task_parts.append(f"Date: {forward_date}")
    
    # Fallback for older API (if still available)
    elif hasattr(message, 'forward_from') and message.forward_from:
        task_parts.append(f"From: {message.forward_from.first_name}")
        if message.forward_date:
            forward_date = message.forward_date.strftime('%Y-%m-%d %H:%M')
            task_parts.append(f"Date: {forward_date}")
    elif hasattr(message, 'forward_from_chat') and message.forward_from_chat:
        task_parts.append(f"From: {message.forward_from_chat.title}")
        
        # Try to create a link to the original message if it's from a public channel
        if hasattr(message, 'forward_from_message_id') and message.forward_from_chat.username:
            message_link = f"https://t.me/{message.forward_from_chat.username}/{message.forward_from_message_id}"
            
        if message.forward_date:
            forward_date = message.forward_date.strftime('%Y-%m-%d %H:%M')
            task_parts.append(f"Date: {forward_date}")
    elif hasattr(message, 'forward_sender_name') and message.forward_sender_name:
        task_parts.append(f"From: {message.forward_sender_name}")
        if message.forward_date:
            forward_date = message.forward_date.strftime('%Y-%m-%d %H:%M')
            task_parts.append(f"Date: {forward_date}")
    
    # Extract main content
    if message.text:
        task_parts.append(f"Text: {message.text}")
    elif message.caption:
        task_parts.append(f"Caption: {message.caption}")
    
    # Handle different media types
    if message.photo:
        task_parts.append("📷 Photo attached")
    elif message.document:
        doc_name = message.document.file_name or "Unknown file"
        task_parts.append(f"📎 Document: {doc_name}")
    elif message.video:
        task_parts.append("🎥 Video attached")
    elif message.audio:
        title = message.audio.title or "Unknown audio"
        task_parts.append(f"🎵 Audio: {title}")
    elif message.voice:
        duration = message.voice.duration
        task_parts.append(f"🎤 Voice message ({duration}s)")
    elif message.video_note:
        task_parts.append("🎬 Video note attached")
    elif message.sticker:
        task_parts.append(f"🎭 Sticker: {message.sticker.emoji or 'N/A'}")
    elif message.location:
        lat, lon = message.location.latitude, message.location.longitude
        task_parts.append(f"📍 Location: {lat:.4f}, {lon:.4f}")
    elif message.contact:
        contact_name = f"{message.contact.first_name} {message.contact.last_name or ''}".strip()
        task_parts.append(f"👤 Contact: {contact_name} ({message.contact.phone_number})")
    elif message.poll:
        task_parts.append(f"📊 Poll: {message.poll.question}")
    
    # Add message link if available
    result = " | ".join(task_parts) if task_parts else None
    
    # Return both the task content and the message link
    return {"content": result, "link": message_link}

def is_forwarded_message(message):
    """Check if message is forwarded using both new and old API"""
    # New API (v20+)
    if hasattr(message, 'forward_origin') and message.forward_origin:
        return True
    
    # Old API (fallback)
    if (hasattr(message, 'forward_from') and message.forward_from) or \
       (hasattr(message, 'forward_from_chat') and message.forward_from_chat) or \
       (hasattr(message, 'forward_sender_name') and message.forward_sender_name):
        return True
    
    return False

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages as potential tasks"""
    if update.message.text and update.message.text.startswith('/'):
        return  # Ignore commands
    
    # Check if this is a forwarded message
    if is_forwarded_message(update.message):
        await handle_forwarded_message(update, context)
        return
    
    # Handle regular text messages
    if update.message.text:
        # Ask user if they want to add this as a task
        keyboard = [[
            InlineKeyboardButton("✅ Add as Task", callback_data=f"add_regular_task"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store the text content in context
        context.user_data['regular_task_content'] = update.message.text
        
        await update.message.reply_text(
            f"Do you want to add this as a task?\n\n**\"{update.message.text}\"**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media messages (photos, documents, etc.) as potential tasks"""
    message = update.message
    
    # Check if this is a forwarded media message
    if is_forwarded_message(message):
        await handle_forwarded_message(update, context)
        return
    
    # Handle regular media messages
    task_content = extract_task_from_message(message)
    
    if task_content:
        keyboard = [[
            InlineKeyboardButton("✅ Add as Task", callback_data=f"add_media_task"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store the media content in context
        context.user_data['media_task_content'] = task_content
        
        preview_text = task_content[:100] + "..." if len(task_content) > 100 else task_content
        
        await update.message.reply_text(
            f"📎 **Media Message Detected**\n\n"
            f"**Content:** {preview_text}\n\n"
            f"Do you want to add this as a task?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def view_archived_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific archived task command handler"""
    if not context.args:
        # If no arguments, show all archived tasks
        await list_archived_tasks(update, context)
        return
    
    try:
        task_id = int(context.args[0])
        user_id = update.effective_user.id
        user_id_str = str(user_id)
        
        # Get archived tasks for the user
        archived_tasks = task_bot.archived_tasks.get(user_id_str, [])
        
        # Find the specific task
        task = None
        for t in archived_tasks:
            if t['id'] == task_id:
                task = t
                break
        
        if not task:
            await update.message.reply_text(f"❌ Archived task #{task_id} not found.")
            return
        
        # Format detailed task view
        created_date = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')
        completed_date = datetime.fromisoformat(task['completed_at']).strftime('%Y-%m-%d %H:%M') if task['completed_at'] else "N/A"
        archived_date = datetime.fromisoformat(task['archived_at']).strftime('%Y-%m-%d %H:%M')
        
        task_details = f"""
📦 <b>Archived Task #{task['id']}</b>

<b>Task:</b> {task['text']}
<b>Status:</b> {task['status']}
<b>Created:</b> {created_date}
<b>Completed:</b> {completed_date}
<b>Archived:</b> {archived_date}
"""
        
        # Add button to permanently delete only
        keyboard = [[
            InlineKeyboardButton("🗑 Delete Permanently", callback_data=f"perm_delete_{task['id']}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(task_details, parse_mode='HTML', reply_markup=reply_markup)
        
    except ValueError:
        await update.message.reply_text("Please provide a valid task ID number.")

async def list_archived_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List archived tasks command handler"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    # Get archived tasks for the user
    archived_tasks = task_bot.archived_tasks.get(user_id_str, [])
    
    if not archived_tasks:
        await update.message.reply_text("📦 You have no archived tasks.")
        return
    
    # Create message with archived tasks
    archived_text = "📦 <b>Your Archived Tasks:</b>\n\n"
    
    for task in archived_tasks:
        created_date = datetime.fromisoformat(task['created_at']).strftime('%m/%d')
        completed_date = datetime.fromisoformat(task['completed_at']).strftime('%m/%d') if task['completed_at'] else "N/A"
        archived_date = datetime.fromisoformat(task['archived_at']).strftime('%m/%d')
        
        archived_text += f"✅ <b>#{task['id']}</b> {task['text']}\n"
        archived_text += f"   📅 Created: {created_date} | Completed: {completed_date} | Archived: {archived_date}\n\n"
    
    archived_text += "\nUse /archived &lt;task_id&gt; to view details of a specific archived task."
    
    await update.message.reply_text(archived_text, parse_mode='HTML')

def main():
    """Main function to run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("complete", complete_task_command))
    application.add_handler(CommandHandler("delete", delete_task_command))
    application.add_handler(CommandHandler("archive", archive_task_command))
    application.add_handler(CommandHandler("archived", view_archived_task))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle different types of messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Handle media messages with more specific filters
    application.add_handler(MessageHandler(filters.PHOTO, handle_media))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_media))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media))
    application.add_handler(MessageHandler(filters.AUDIO, handle_media))
    application.add_handler(MessageHandler(filters.VOICE, handle_media))
    application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_media))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_media))
    application.add_handler(MessageHandler(filters.LOCATION, handle_media))
    application.add_handler(MessageHandler(filters.CONTACT, handle_media))
    application.add_handler(MessageHandler(filters.POLL, handle_media))
    
    # Start the bot
    print("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
