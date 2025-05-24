import logging
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Set base level to INFO
)
# Set debug level only for your application code
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Set higher levels for third-party libraries to reduce noise
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Bot token from environment variable
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables. Please create a .env file with BOT_TOKEN=your_token_here")

# File to store tasks
TASKS_FILE = "tasks.json"

last_forwarded_user_id = None
pending_forwarded_messages = {}  # Dictionary to store pending messages by user_id

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
    
    def add_task(self, user_id, task_text, message_link=None, message_id=None, media_info=None):
        """Add a new task for user"""
        user_id_str = str(user_id)
        if user_id_str not in self.tasks:
            self.tasks[user_id_str] = []
        
        # Add debug logging
        logger.info(f"Adding task with media_info: {media_info}")
        
        task = {
            'id': len(self.tasks[user_id_str]) + 1,
            'text': task_text,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'completed_at': None,
            'message_link': message_link,
            'message_id': message_id,
            'media_info': media_info
        }
        
        # More debug logging
        logger.info(f"Task created: {task}")
        
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
/view &lt;task_id&gt; - View task details
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
<code>/view 1</code>
<code>/complete 1</code>
<code>/archive 1</code>
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

async def create_task_list_message(user_id, page=0):
    """Create a formatted task list message with navigation buttons
    
    Args:
        user_id: The user ID to get tasks for
        page: The page number (0-based) to display
        
    Returns:
        tuple: (message_text, reply_markup) for the task list
    """
    tasks = task_bot.get_user_tasks(user_id)
    
    if not tasks:
        return "📝 You have no tasks yet. Use /add to create one!", None
    
    # Calculate pagination
    tasks_per_page = 8
    total_pages = (len(tasks) + tasks_per_page - 1) // tasks_per_page
    page = max(0, min(page, total_pages - 1))  # Ensure page is in valid range
    
    start_idx = page * tasks_per_page
    end_idx = min(start_idx + tasks_per_page, len(tasks))
    current_tasks = tasks[start_idx:end_idx]
    
    # Create task list text
    task_text = f"📋 *Your Tasks* (Page {page+1}/{total_pages}):\n\n"
    
    for task in current_tasks:
        status_emoji = "✅" if task['status'] == 'completed' else "⏳"
        created_date = datetime.fromisoformat(task['created_at']).strftime('%m/%d')
        
        # Get a short preview of the task text (first line or first 120 chars) (TODO: use contant variable instead)
        task_preview = task['text'].split('\n')[0][:120] + ('...' if len(task['text'].split('\n')[0]) > 120 else '')
        
        # Add task header with ID and preview
        task_text += f"{status_emoji} *#{task['id']}* {task_preview}\n"
        
        # Add date info and attachment indicator
        attachment_indicator = ""
        if task.get('media_info') or task.get('message_link'):
            attachment_indicator = " 📎"
        
        task_text += f"   📅 {created_date}{attachment_indicator}"
        
        if task['status'] == 'completed' and task['completed_at']:
            completed_date = datetime.fromisoformat(task['completed_at']).strftime('%m/%d')
            task_text += f" → ✅ {completed_date}"
        
        task_text += "\n\n"
    
    # Create navigation keyboard
    keyboard = []
    
    # Add view buttons for each task
    task_buttons = []
    for task in current_tasks:
        task_buttons.append(
            InlineKeyboardButton(f"🔍{task['id']}", callback_data=f"view_{task['id']}")
        )
        
        # Create rows with 8 buttons each TODO use constant instead
        if len(task_buttons) == 8:
            keyboard.append(task_buttons)
            task_buttons = []
    
    # Add any remaining buttons
    if task_buttons:
        keyboard.append(task_buttons)
    
    # Add navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"list_page_{page-1}"))
    
    nav_row.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"list_page_{page}"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"list_page_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return task_text, reply_markup

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List tasks command handler"""
    user_id = update.effective_user.id
    page = 0  # Start with first page
    
    task_text, reply_markup = await create_task_list_message(user_id, page)
    
    await update.message.reply_text(
        task_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

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
    
    # Handle paginated list
    if data.startswith("list_page_"):
        page = int(data.split("_")[-1])
        task_text, reply_markup = await create_task_list_message(user_id, page)
        
        try:
            await query.edit_message_text(
                task_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except error.BadRequest as e:
            # Handle "message is not modified" error silently
            if "message is not modified" in str(e).lower():
                # Just answer the callback query to show some response to the user
                await query.answer("List is already up to date!")
            else:
                # Re-raise other BadRequest errors
                raise
    
    # Handle list tasks button (back to first page)
    elif data == "list_tasks":
        task_text, reply_markup = await create_task_list_message(user_id, 0)
        
        try:
            await query.edit_message_text(
                task_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except error.BadRequest as e:
            # Handle "message is not modified" error silently
            if "message is not modified" in str(e).lower():
                await query.answer("List is already up to date!")
            else:
                raise
    
    # Handle view task details
    if data.startswith('view_'):
        task_id = int(data.split('_')[1])
        user_id_str = str(user_id)
        
        # Find the task
        task = None
        if user_id_str in task_bot.tasks:
            for t in task_bot.tasks[user_id_str]:
                if t['id'] == task_id:
                    task = t
                    break
        
        if not task:
            await query.edit_message_text(f"❌ Task #{task_id} not found.")
            return
        
        # Format task details
        status_emoji = "✅" if task['status'] == 'completed' else "⏳"
        created_date = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')
        completed_date = "N/A"
        if task['status'] == 'completed' and task['completed_at']:
            completed_date = datetime.fromisoformat(task['completed_at']).strftime('%Y-%m-%d %H:%M')
        
        details_text = f"""
{status_emoji} <b>Task #{task['id']}</b>

<b>Content:</b> {task['text']}
<b>Status:</b> {task['status']}
<b>Created:</b> {created_date}
<b>Completed:</b> {completed_date}
"""
        
        # Add message link if available
        if task.get('message_link'):
            details_text += f"\n<b>Original Message:</b> <a href='{task['message_link']}'>Link</a>"
        
        # Create keyboard with actions
        keyboard = []
        
        # Add reply button if the task has a message_id
        if task.get('message_id'):
            keyboard.append([
                InlineKeyboardButton("📩 Reply to Original", callback_data=f"reply_{task['id']}")
            ])
        
        # Add action buttons based on task status
        action_row = []
        if task['status'] == 'pending':
            action_row.extend([
                InlineKeyboardButton("✅ Complete", callback_data=f"complete_{task['id']}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{task['id']}")
            ])
        else:
            action_row.extend([
                InlineKeyboardButton("📦 Archive", callback_data=f"archive_{task['id']}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{task['id']}")
            ])
        
        keyboard.append(action_row)
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to List", callback_data="list_tasks")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update the message with detailed view
        await query.edit_message_text(
            details_text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            disable_web_page_preview=False  # Enable preview to show media if there's a link
        )
        
        # IMPORTANT: After editing the message, check for media and send it separately
        logger.info(f"Checking for media in task #{task_id}")
        
        # If the task has media info, send the media as a separate message
        if task.get('media_info'):
            media_info = task['media_info']
            logger.info(f"Found media_info in task #{task_id}: {media_info}")
            
            # Send debug message
            await query.message.reply_text(f"DEBUG: Found media: {media_info['type']}")
            
            # Handle multiple media items
            if media_info.get('type') == 'multiple' and media_info.get('items'):
                logger.info(f"Processing multiple media items: {len(media_info['items'])} items")
                
                # Send debug message
                await query.message.reply_text(f"DEBUG: Found {len(media_info['items'])} media items")
                
                # Process each item
                for i, item in enumerate(media_info['items'][:5]):
                    logger.info(f"Processing item {i+1}: {item}")
                    
                    try:
                        # Try to send the media directly
                        if item.get('type') == 'photo' and item.get('file_id'):
                            logger.info(f"Sending photo with file_id: {item['file_id'][:15]}...")
                            await query.message.reply_photo(
                                photo=item['file_id'],
                                caption=f"Attachment {i+1} for Task #{task_id}"
                            )
                            logger.info("Photo sent successfully")
                        else:
                            # Use the helper function for other types
                            await send_media_item(query.message, item, f"Attachment {i+1} for Task #{task_id}")
                    except Exception as e:
                        error_msg = f"Error sending media item {i+1}: {str(e)}"
                        logger.error(error_msg)
                        await query.message.reply_text(f"❌ {error_msg}")
            else:
                # Handle single media item
                logger.info(f"Processing single media item: {media_info}")
                try:
                    await send_media_item(query.message, media_info, f"Attachment for Task #{task_id}")
                    logger.info("Media sent successfully")
                except Exception as e:
                    error_msg = f"Error sending media: {str(e)}"
                    logger.error(error_msg)
                    await query.message.reply_text(f"❌ {error_msg}")
        
        # If the task has a message_id, send a new message as a reply to the original
        elif task.get('message_id'):
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📎 <b>Original message content:</b>",
                parse_mode='HTML',
                reply_to_message_id=task['message_id']
            )
    
    # Handle reply to original message
    if data.startswith('reply_'):
        task_id = int(data.split('_')[1])
        user_id_str = str(user_id)
        
        # Find the task
        task = None
        if user_id_str in task_bot.tasks:
            for t in task_bot.tasks[user_id_str]:
                if t['id'] == task_id:
                    task = t
                    break
        
        if task and task.get('message_id'):
            # Reply to the original message
            await query.message.reply_text(
                f"🔍 *Replying to original message for Task #{task_id}*\n\n"
                f"To find the original message, look for message ID: {task['message_id']} in your chat history.",
                parse_mode='Markdown',
                reply_to_message_id=task['message_id']
            )
        else:
            await query.message.reply_text(f"❌ Could not find message ID for Task #{task_id}.")
    
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
    if data == "add_forwarded_task":
        if 'forwarded_task_content' in context.user_data:
            task_text = context.user_data['forwarded_task_content']
            message_link = context.user_data.get('forwarded_task_link')
            message_id = context.user_data.get('forwarded_message_id')
            media_info = context.user_data.get('forwarded_media_info')
            
            task = task_bot.add_task(user_id, task_text, message_link, message_id, media_info)
            
            response_text = f"✅ Task added successfully!\n*Task #{task['id']}:* {task['text'][:50]}{'...' if len(task['text']) > 50 else ''}"
            
            # Add link to original message if available
            if message_link:
                response_text += f"\n\n🔗 [Original Message]({message_link})"
            
            # Add reference to the forwarded message
            if message_id:
                response_text += f"\n\n📩 Reference to forwarded message ID: {message_id}"
            
            # Clear the stored content
            del context.user_data['forwarded_task_content']
            if 'forwarded_task_link' in context.user_data:
                del context.user_data['forwarded_task_link']
            if 'forwarded_message_id' in context.user_data:
                del context.user_data['forwarded_message_id']
            if 'forwarded_media_info' in context.user_data:
                del context.user_data['forwarded_media_info']
                
            # Reply to the original message when showing the task
            await query.edit_message_text(response_text, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            await query.edit_message_text("❌ Task content not found.")
    
    # Handle media message task creation
    elif data == "add_media_task":
        if 'media_task_content' in context.user_data:
            task_text = context.user_data['media_task_content']
            message_id = context.user_data.get('media_task_message_id')
            media_info = context.user_data.get('media_task_media_info')
            
            task = task_bot.add_task(user_id, task_text, None, message_id, media_info)
            
            await query.edit_message_text(
                f"✅ Task added successfully!\n"
                f"*Task #{task['id']}:* {task['text'][:50]}{'...' if len(task['text']) > 50 else ''}",
                parse_mode='Markdown'
            )
            # Clear the stored content
            del context.user_data['media_task_content']
            if 'media_task_message_id' in context.user_data:
                del context.user_data['media_task_message_id']
            if 'media_task_media_info' in context.user_data:
                del context.user_data['media_task_media_info']
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
    global last_forwarded_user_id, pending_forwarded_messages
    
    message = update.message
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    # Initialize user's pending messages if not exists
    if user_id_str not in pending_forwarded_messages:
        pending_forwarded_messages[user_id_str] = {
            "messages": [],
            "last_time": None
        }
    
    # Extract task content from forwarded message
    task_data = extract_task_from_message(message)
    
    # Check if this is a continuation of previous forwarded messages (within 30 seconds)
    current_time = datetime.now()
    is_continuation = False
    
    if pending_forwarded_messages[user_id_str]["last_time"]:
        time_diff = (current_time - pending_forwarded_messages[user_id_str]["last_time"]).total_seconds()
        is_continuation = time_diff < 30  # Consider messages within 30 seconds as a batch
    
    # Update the last time
    pending_forwarded_messages[user_id_str]["last_time"] = current_time
    
    # Add current message to pending messages
    pending_forwarded_messages[user_id_str]["messages"].append(task_data)
    
    # If this is not a continuation or we have too many messages, process the batch
    if not is_continuation or len(pending_forwarded_messages[user_id_str]["messages"]) >= 10:
        await process_forwarded_messages_batch(update, context, user_id_str)
    else:
        # If it's a continuation, just acknowledge receipt
        await update.message.reply_text(
            "📨 *Message added to batch*\n"
            "Forward more messages within 30 seconds to combine them, or wait to create a task.",
            parse_mode='Markdown'
        )

async def process_forwarded_messages_batch(update, context, user_id_str):
    """Process a batch of forwarded messages as a single task"""
    global pending_forwarded_messages
    
    # Get all pending messages for this user
    messages = pending_forwarded_messages[user_id_str]["messages"]
    
    if not messages:
        return
    
    # Combine all message contents
    combined_content = []
    message_ids = []
    media_infos = []
    links = []
    debug_info = []
    
    for msg_data in messages:
        if msg_data["content"]:
            combined_content.append(msg_data["content"])
        if msg_data["message_id"]:
            message_ids.append(msg_data["message_id"])
        if msg_data["media_info"]:
            media_infos.append(msg_data["media_info"])
        if msg_data["link"]:
            links.append(msg_data["link"])
        if msg_data["debug"]:
            debug_info.extend(msg_data["debug"])
    
    # Create combined task content
    task_content = "\n---\n".join(combined_content)
    
    # Store only the first message ID as the reference
    first_message_id = message_ids[0] if message_ids else None
    
    # Store only the first link
    first_link = links[0] if links else None
    
    # Store all media info in a list
    combined_media_info = None
    if media_infos:
        combined_media_info = {
            "type": "multiple",
            "items": media_infos
        }
    
    # Create inline keyboard for forwarded message batch
    keyboard = [[
        InlineKeyboardButton("✅ Add as Task", callback_data=f"add_forwarded_task"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store the combined content in context
    context.user_data['forwarded_task_content'] = task_content
    if first_link:
        context.user_data['forwarded_task_link'] = first_link
    if first_message_id:
        context.user_data['forwarded_message_id'] = first_message_id
    if combined_media_info:
        context.user_data['forwarded_media_info'] = combined_media_info
    
    # Debug info
    debug_text = "\n".join(debug_info[:10]) + (f"\n... and {len(debug_info) - 10} more" if len(debug_info) > 10 else "")
    
    # Preview text
    preview_text = task_content[:200] + "..." if len(task_content) > 200 else task_content
    
    # Send the combined message
    await update.message.reply_text(
        f"📨 *{len(messages)} Forwarded Messages Detected*\n\n"
        f"*Content Preview:*\n{preview_text}\n\n"
        f"Do you want to add these as a single task?",
        parse_mode='Markdown',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )
    
    # Clear the pending messages for this user
    pending_forwarded_messages[user_id_str]["messages"] = []

def extract_task_from_message(message):
    """Extract task content from various message types and save media file_ids"""
    task_parts = []
    message_link = None
    debug_info = []
    source_type = "unknown"
    media_info = {}
    
    # Store the message ID of the forwarded message
    forwarded_message_id = message.message_id
    debug_info.append(f"Current message ID: {forwarded_message_id}")
    
    # Extract sender and date information from forwarded messages
    if is_forwarded_message(message):
        # Try to get sender info
        sender_name = None
        forward_date = None
        
        # New API (v20+)
        if hasattr(message, 'forward_origin'):
            origin = message.forward_origin
            if hasattr(origin, 'sender_user') and origin.sender_user:
                sender_name = origin.sender_user.first_name
                if origin.sender_user.last_name:
                    sender_name += f" {origin.sender_user.last_name}"
                source_type = "user"
            elif hasattr(origin, 'sender_chat') and origin.sender_chat:
                sender_name = origin.sender_chat.title
                source_type = "chat"
            elif hasattr(origin, 'sender_name') and origin.sender_name:
                sender_name = origin.sender_name
                source_type = "hidden"
            
            if hasattr(origin, 'date'):
                forward_date = origin.date
        
        # Old API (fallback)
        else:
            if message.forward_from:
                sender_name = message.forward_from.first_name
                if message.forward_from.last_name:
                    sender_name += f" {message.forward_from.last_name}"
                source_type = "user"
            elif message.forward_from_chat:
                sender_name = message.forward_from_chat.title
                source_type = "chat"
            elif message.forward_sender_name:
                sender_name = message.forward_sender_name
                source_type = "hidden"
            
            forward_date = message.forward_date
        
        # Format date if available
        date_str = ""
        if forward_date:
            date_str = forward_date.strftime("%Y-%m-%d %H:%M")
        
        # Add sender and date to task parts
        if sender_name:
            task_parts.append(f"From: {sender_name}")
        if date_str:
            task_parts.append(f"Date: {date_str}")
        
        # Try to get message link for forwarded messages
        if hasattr(message, 'forward_origin'):
            origin = message.forward_origin
            if hasattr(origin, 'chat') and origin.chat and hasattr(origin, 'message_id') and origin.message_id:
                chat_id = origin.chat.id
                message_id = origin.message_id
                if str(chat_id).startswith('-100'):
                    chat_id_str = str(chat_id)[4:]
                    message_link = f"https://t.me/c/{chat_id_str}/{message_id}"
                    debug_info.append(f"Generated link from origin: {message_link}")
        
        # Old API fallback for message link
        elif message.forward_from_chat and message.forward_from_message_id:
            chat_id = message.forward_from_chat.id
            message_id = message.forward_from_message_id
            if str(chat_id).startswith('-100'):
                chat_id_str = str(chat_id)[4:]
                message_link = f"https://t.me/c/{chat_id_str}/{message_id}"
                debug_info.append(f"Generated link from forward_from_chat: {message_link}")
    
    # Extract main content
    if message.text:
        task_parts.append(f"T: {message.text}")
    elif message.caption:
        task_parts.append(f"C: {message.caption}")
    
    # Handle different media types and store file_ids
    if message.photo:
        # Get the largest photo (last item in the list)
        photo_file_id = message.photo[-1].file_id
        media_info['type'] = 'photo'
        media_info['file_id'] = photo_file_id
        task_parts.append("📷 Photo attached")
    elif message.document:
        doc_name = message.document.file_name or "Unknown file"
        media_info['type'] = 'document'
        media_info['file_id'] = message.document.file_id
        media_info['file_name'] = doc_name
        task_parts.append(f"📎 Document: {doc_name}")
    elif message.video:
        media_info['type'] = 'video'
        media_info['file_id'] = message.video.file_id
        task_parts.append("🎥 Video attached")
    elif message.audio:
        title = message.audio.title or "Unknown audio"
        media_info['type'] = 'audio'
        media_info['file_id'] = message.audio.file_id
        media_info['title'] = title
        task_parts.append(f"🎵 Audio: {title}")
    elif message.voice:
        duration = message.voice.duration
        media_info['type'] = 'voice'
        media_info['file_id'] = message.voice.file_id
        media_info['duration'] = duration
        task_parts.append(f"🎤 Voice message ({duration}s)")
    elif message.video_note:
        media_info['type'] = 'video_note'
        media_info['file_id'] = message.video_note.file_id
        task_parts.append("🎬 Video note attached")
    elif message.sticker:
        media_info['type'] = 'sticker'
        media_info['file_id'] = message.sticker.file_id
        media_info['emoji'] = message.sticker.emoji
        task_parts.append(f"🎭 Sticker: {message.sticker.emoji or 'N/A'}")
    elif message.location:
        lat, lon = message.location.latitude, message.location.longitude
        media_info['type'] = 'location'
        media_info['latitude'] = lat
        media_info['longitude'] = lon
        task_parts.append(f"📍 Location: {lat:.4f}, {lon:.4f}")
    elif message.contact:
        name = message.contact.first_name
        if message.contact.last_name:
            name += f" {message.contact.last_name}"
        phone = message.contact.phone_number
        media_info['type'] = 'contact'
        media_info['name'] = name
        media_info['phone_number'] = phone
        task_parts.append(f"👤 Contact: {name} ({phone})")
    elif message.poll:
        question = message.poll.question
        media_info['type'] = 'poll'
        media_info['question'] = question
        task_parts.append(f"📊 Poll: {question}")
    
    # Add message link if available
    result = " | ".join(task_parts) if task_parts else None
    
    # Return both the task content and the message link
    return {
        "content": result, 
        "link": message_link, 
        "debug": debug_info, 
        "source_type": source_type,
        "message_id": forwarded_message_id,
        "media_info": media_info if media_info else None
    }

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
    task_data = extract_task_from_message(message)  # Remove the await keyword
    
    if task_data["content"]:
        keyboard = [[
            InlineKeyboardButton("✅ Add as Task", callback_data=f"add_media_task"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store the media content and media info in context
        context.user_data['media_task_content'] = task_data["content"]
        if task_data.get("media_info"):
            context.user_data['media_task_media_info'] = task_data["media_info"]
        
        # Store the message ID
        context.user_data['media_task_message_id'] = task_data["message_id"]
        
        preview_text = task_data["content"][:100] + "..." if len(task_data["content"]) > 100 else task_data["content"]
        
        await update.message.reply_text(
            f"📎 **Media Message Detected**\n\n"
            f"**Content:** {preview_text}\n\n"
            f"Do you want to add this as a task?",
            parse_mode='Markdown',
            reply_markup=reply_markup,
            reply_to_message_id=message.message_id  # Reply to the original media message
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
        
        # Find the archived task
        task = None
        if user_id_str in task_bot.archived_tasks:
            for t in task_bot.archived_tasks[user_id_str]:
                if t['id'] == task_id:
                    task = t
                    break
        
        if not task:
            await update.message.reply_text(f"❌ Archived task #{task_id} not found.")
            return
        
        # Format task details
        created_date = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')
        completed_date = "N/A"
        if task['completed_at']:
            completed_date = datetime.fromisoformat(task['completed_at']).strftime('%Y-%m-%d %H:%M')
        
        archived_date = "N/A"
        if task.get('archived_at'):
            archived_date = datetime.fromisoformat(task['archived_at']).strftime('%Y-%m-%d %H:%M')
        
        task_details = f"""
📦 <b>Archived Task #{task['id']}</b>

<b>Task:</b> {task['text']}
<b>Status:</b> {task['status']}
<b>Created:</b> {created_date}
<b>Completed:</b> {completed_date}
<b>Archived:</b> {archived_date}
"""
        
        # Add message link if available
        if task.get('message_link'):
            task_details += f"\n<b>Original Message:</b> <a href='{task['message_link']}'>Link</a>"
        
        # Add button to permanently delete only
        keyboard = [[
            InlineKeyboardButton("🗑 Delete Permanently", callback_data=f"perm_delete_{task['id']}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(task_details, parse_mode='HTML', reply_markup=reply_markup)
        
        # If the task has media info, send the media
        if task.get('media_info'):
            media_info = task['media_info']
            
            # Handle multiple media items
            if media_info.get('type') == 'multiple' and media_info.get('items'):
                # Send up to 5 media items to avoid flooding
                for i, item in enumerate(media_info['items'][:5]):
                    if i >= 5:  # Limit to 5 attachments
                        await update.message.reply_text(f"... and {len(media_info['items']) - 5} more attachments")
                        break
                    
                    await send_media_item(update.message, item, f"Attachment {i+1} for Archived Task #{task['id']}")
            else:
                # Send single media item
                await send_media_item(update.message, media_info, f"Attachment for Archived Task #{task['id']}")
        
        # If the task has a message_id but no media info, reply to that message to show the original content
        elif task.get('message_id'):
            try:
                await update.message.reply_text(
                    "📎 <b>Original message content:</b>",
                    parse_mode='HTML',
                    reply_to_message_id=task['message_id']
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Could not reference original message: {str(e)}")
        
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

async def view_task_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View detailed information about a specific task"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a task ID.\n"
            "Example: `/view 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        task_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Get the task
        user_tasks = task_bot.get_user_tasks(user_id)
        task = None
        
        for t in user_tasks:
            if t['id'] == task_id:
                task = t
                break
        
        if not task:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
            return
        
        # Format task details
        status_emoji = "✅" if task['status'] == 'completed' else "⏳"
        created_date = datetime.fromisoformat(task['created_at']).strftime('%Y-%m-%d %H:%M')
        completed_date = "N/A"
        if task['status'] == 'completed' and task['completed_at']:
            completed_date = datetime.fromisoformat(task['completed_at']).strftime('%Y-%m-%d %H:%M')
        
        details_text = f"""
{status_emoji} <b>Task #{task['id']}</b>

<b>Content:</b> {task['text']}
<b>Status:</b> {task['status']}
<b>Created:</b> {created_date}
<b>Completed:</b> {completed_date}
"""
        
        # Add message link if available
        if task.get('message_link'):
            details_text += f"\n<b>Original Message:</b> <a href='{task['message_link']}'>Link</a>"
        
        # Create keyboard with actions
        keyboard = []
        
        # Add reply button if the task has a message_id
        if task.get('message_id'):
            keyboard.append([
                InlineKeyboardButton("📩 Reply to Original", callback_data=f"reply_{task['id']}")
            ])
        
        # Add action buttons based on task status
        action_row = []
        if task['status'] == 'pending':
            action_row.extend([
                InlineKeyboardButton("✅ Complete", callback_data=f"complete_{task['id']}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{task['id']}")
            ])
        else:
            action_row.extend([
                InlineKeyboardButton("📦 Archive", callback_data=f"archive_{task['id']}"),
                InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{task['id']}")
            ])
        
        keyboard.append(action_row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the detailed view
        await update.message.reply_text(
            details_text,
            parse_mode='HTML',
            reply_markup=reply_markup,
            disable_web_page_preview=False  # Enable preview to show media if there's a link
        )
        
        # Debug prints
        logger.info(f"DEBUG: Task #{task['id']} details sent, now checking for media")
        logger.info(f"DEBUG: Task has media_info: {bool(task.get('media_info'))}")
        if task.get('media_info'):
            logger.info(f"DEBUG: Media info content: {task['media_info']}")
        
        # Add explicit debug for media handling
        logger.info(f"Checking for media in task #{task['id']}")
        
        # If the task has media info, send the media
        if task.get('media_info'):
            media_info = task['media_info']
            logger.info(f"Found media_info in task #{task['id']}: {media_info}")
            
            # Send debug message to user
            await update.message.reply_text(f"DEBUG: Found media: {media_info['type']}")
            
            # Handle multiple media items
            if media_info.get('type') == 'multiple' and media_info.get('items'):
                logger.info(f"Processing multiple media items: {len(media_info['items'])} items")
                
                # Send debug message to user
                await update.message.reply_text(f"DEBUG: Found {len(media_info['items'])} media items")
                
                # Process each item
                for i, item in enumerate(media_info['items'][:5]):
                    logger.info(f"Processing item {i+1}: {item}")
                    
                    try:
                        # Try to send the media directly
                        if item.get('type') == 'photo' and item.get('file_id'):
                            logger.info(f"Sending photo with file_id: {item['file_id'][:15]}...")
                            await update.message.reply_photo(
                                photo=item['file_id'],
                                caption=f"Attachment {i+1} for Task #{task['id']}"
                            )
                            logger.info("Photo sent successfully")
                        else:
                            # Use the helper function for other types
                            await send_media_item(update.message, item, f"Attachment {i+1} for Task #{task['id']}")
                    except Exception as e:
                        error_msg = f"Error sending media item {i+1}: {str(e)}"
                        logger.error(error_msg)
                        await update.message.reply_text(f"❌ {error_msg}")
            else:
                # Handle single media item
                logger.info(f"Processing single media item: {media_info}")
                try:
                    await send_media_item(update.message, media_info, f"Attachment for Task #{task['id']}")
                    logger.info("Media sent successfully")
                except Exception as e:
                    error_msg = f"Error sending media: {str(e)}"
                    logger.error(error_msg)
                    await update.message.reply_text(f"❌ {error_msg}")
        
        # If the task has a message_id, reply to that message to show the original content
        elif task.get('message_id'):
            await update.message.reply_text(
                "📎 <b>Original message content:</b>",
                parse_mode='HTML',
                reply_to_message_id=task['message_id']
            )
        
    except ValueError:
        await update.message.reply_text("Please provide a valid task ID number.")

async def send_media_item(message, media_info, caption_prefix=""):
    """Helper function to send a media item"""
    media_type = media_info.get('type')
    file_id = media_info.get('file_id')
    
    logger.info(f"Attempting to send media: type={media_type}, file_id={file_id[:15] if file_id else None}")
    
    if not media_type or not file_id:
        logger.error(f"Media information is incomplete: {media_info}")
        await message.reply_text(f"❌ Media information is incomplete: {media_info}")
        return
    
    try:
        if media_type == 'photo':
            logger.info(f"Sending photo with file_id: {file_id[:15]}...")
            await message.reply_photo(
                photo=file_id,
                caption=f"{caption_prefix}"
            )
        elif media_type == 'document':
            # Other media types with logging
            file_name = media_info.get('file_name', 'Unknown file')
            logger.info(f"Sending document: {file_name} with file_id: {file_id[:15]}...")
            await message.reply_document(
                document=file_id,
                caption=f"{caption_prefix}: {file_name}"
            )
        # Add logging to other media types similarly
    except Exception as e:
        error_msg = f"Error sending media: {str(e)}\nType: {media_type}, File ID: {file_id[:15]}..."
        logger.error(error_msg)
        await message.reply_text(f"❌ {error_msg}")

async def send_media_item_bot(bot, chat_id, media_info, caption_prefix=""):
    """Helper function to send a media item using the bot object
    
    Args:
        bot: The bot object
        chat_id: The chat ID to send the media to
        media_info: The media info dictionary
        caption_prefix: Optional prefix for the caption
    """
    media_type = media_info.get('type')
    file_id = media_info.get('file_id')
    
    if not media_type or not file_id:
        await bot.send_message(chat_id=chat_id, text="❌ Media information is incomplete")
        return
    
    try:
        if media_type == 'photo':
            await bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=f"{caption_prefix}"
            )
        elif media_type == 'document':
            file_name = media_info.get('file_name', 'Unknown file')
            await bot.send_document(
                chat_id=chat_id,
                document=file_id,
                caption=f"{caption_prefix}: {file_name}"
            )
        elif media_type == 'video':
            await bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=f"{caption_prefix}"
            )
        elif media_type == 'audio':
            title = media_info.get('title', 'Unknown audio')
            await bot.send_audio(
                chat_id=chat_id,
                audio=file_id,
                caption=f"{caption_prefix}: {title}"
            )
        elif media_type == 'voice':
            await bot.send_voice(
                chat_id=chat_id,
                voice=file_id,
                caption=f"{caption_prefix}"
            )
        elif media_type == 'video_note':
            await bot.send_video_note(
                chat_id=chat_id,
                video_note=file_id
            )
        elif media_type == 'sticker':
            await bot.send_sticker(
                chat_id=chat_id,
                sticker=file_id
            )
        elif media_type == 'location':
            lat = media_info.get('latitude')
            lon = media_info.get('longitude')
            if lat and lon:
                await bot.send_location(
                    chat_id=chat_id,
                    latitude=lat,
                    longitude=lon
                )
        elif media_type == 'contact':
            name = media_info.get('name')
            phone = media_info.get('phone_number')
            if name and phone:
                await bot.send_contact(
                    chat_id=chat_id,
                    phone_number=phone,
                    first_name=name
                )
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"❌ Error sending media: {str(e)}")

def main():
    """Main function to run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("view", view_task_details))
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
