# Create and enter project
mkdir telegram-task-bot && cd telegram-task-bot

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install python-telegram-bot python-dotenv

# Save dependencies
pip freeze > requirements.txt

# Run bot
python task_bot.py

# Deactivate when done
deactivate
