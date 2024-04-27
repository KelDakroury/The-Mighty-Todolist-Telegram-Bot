import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from threading import Event, Thread

from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CallbackContext, CommandHandler

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = 'task.db'
DAILY_REMINDER_START = "09:00:00"

# Database setup


def init_db():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            description TEXT, 
            category TEXT, 
            deadline TEXT, 
            completed BOOLEAN DEFAULT 0
        )
    """
    )

    conn.commit()
    conn.close()


# Command handlers


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome to your personal To-Do List Bot!")


async def add_task(update: Update, context: CallbackContext):
    """
    Adds a new task to the database.
    Command format: /add <description>; <category>; <deadline: YYYY-MM-DD HH:MM>
    Example: /add Prepare presentation; work; 2023-10-15
    """
    try:
        args = " ".join(context.args).split(";")
        if len(args) < 1:
            await update.message.reply_text(
                "Usage: /add <description>; <category>; <deadline: YYYY-MM-DD HH:MM>"
            )
            return

        description = args[0].strip()
        category = args[1].strip() if len(args) > 1 else "general"
        deadline = args[2].strip() if len(args) > 2 else None

        try:
            deadline = datetime.strptime(deadline, '%Y-%m-%d %H:%M').isoformat(
                ' '
            )
        except ValueError:
            await update.message.reply_text(
                "Invalid date format. Use YYYY-MM-DD HH:MM."
            )
            return

        user_id = update.effective_user.id

        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            """
        INSERT INTO tasks (user_id, description, category, deadline, completed)
        VALUES (?, ?, ?, ?, 0)
        """,
            (user_id, description, category, deadline),
        )
        conn.commit()
        conn.close()

        await update.message.reply_text("Task added successfully!")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await update.message.reply_text(
            "Failed to add task due to a database error."
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await update.message.reply_text(
            "Failed to add task due to an unexpected error."
        )


async def delete_task(update: Update, context: CallbackContext):
    """
    Deletes a task from the database.
    Command format: /delete <task_id>
    Example: /delete 3
    """
    try:
        # Extracting the task ID from the command
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: /delete <task_id>")
            return

        task_id = int(args[0])
        user_id = update.effective_user.id

        # Database connection and deletion
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Check if the task belongs to the user
        cursor.execute(
            "SELECT id FROM tasks WHERE user_id = ? AND id = ?",
            (user_id, task_id),
        )
        task = cursor.fetchone()
        if not task:
            await update.message.reply_text(
                "Task not found or does not belong to you."
            )
            conn.close()
            return

        # If task found, delete it
        cursor.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        conn.commit()
        conn.close()

        await update.message.reply_text("Task deleted successfully!")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await update.message.reply_text(
            "Failed to delete task due to a database error."
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await update.message.reply_text(
            "Failed to delete task due to an unexpected error."
        )


async def mark_completed(update: Update, context: CallbackContext):
    """
    Marks a specified task as completed in the database.
    Command format: /complete <task_id>
    Example: /complete 42
    """
    try:
        # Extracting the task ID from the command
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: /complete <task_id>")
            return

        task_id = int(args[0])
        user_id = update.effective_user.id

        # Database connection and update
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Check if the task exists and belongs to the user
        cursor.execute(
            """
            SELECT id FROM tasks WHERE user_id = ? AND
            id = ? AND completed = FALSE
            """,
            (user_id, task_id),
        )
        task = cursor.fetchone()
        if not task:
            await update.message.reply_text(
                "Task not found or already completed."
            )
            conn.close()
            return

        # If task found and not completed, mark it as completed
        cursor.execute(
            "UPDATE tasks SET completed = TRUE WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        conn.commit()
        conn.close()

        await update.message.reply_text(
            "Task marked as completed successfully!"
        )
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await update.message.reply_text(
            "Failed to complete task due to a database error."
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await update.message.reply_text(
            "Failed to complete task due to an unexpected error."
        )


async def list_tasks(update: Update, context: CallbackContext):
    """
    Lists the non-completed tasks of the user from the SQLite database.
    Command format: /list
    Example: /list
    """
    try:
        user_id = update.effective_user.id
        conn = sqlite3.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute(
            """
            SELECT description, category, deadline FROM tasks WHERE user_id=?
            AND completed=FALSE
            """,
            (user_id,),
        )
        tasks = c.fetchall()
        message = "\n".join(
            f"{desc} - {cat} - due by {deadline}"
            for desc, cat, deadline in tasks
        )
        await update.message.reply_text(
            message if message else "No tasks found."
        )
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        await update.message.reply_text(
            "Failed to add task due to a database error."
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await update.message.reply_text(
            "Failed to add task due to an unexpected error."
        )


bot = Bot(token=TOKEN)


async def notify_due_tasks():
    """Check for tasks that are due and notify the respective users."""
    try:
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, description
            FROM tasks
            WHERE deadline >= datetime('now', 'localtime')
            AND deadline < datetime('now', 'localtime', '+24 hours')
            AND completed = 0
            """
        )
        due_tasks = cursor.fetchall()

        for task_id, user_id, description in due_tasks:
            message = f"""
                Reminder: Task '{description}' is due in 24 hours!
                """
            await bot.send_message(chat_id=user_id, text=message)
            logging.info(f"Notified user {user_id} about task {task_id}")

        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error during notification: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during notification: {e}")


shutdown_event = Event()


def run_notifiers():
    """Run the scheduler loop to check for due tasks."""
    last_reminder = datetime.now() + timedelta(minutes=-10)

    while not shutdown_event.is_set():
        now = datetime.now()
        reminder_start = datetime.strptime(
            f"{now.date()} {DAILY_REMINDER_START}", "%Y-%m-%d %H:%M:%S"
        )

        if reminder_start <= now and now > last_reminder + timedelta(
            minutes=10
        ):
            last_reminder = datetime.now()
            asyncio.run(notify_due_tasks())

        shutdown_event.wait(timeout=10)


# Main function


def main():
    """Run bot."""
    try:
        init_db()
        application = Application.builder().token(TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("add", add_task))
        application.add_handler(CommandHandler("list", list_tasks))
        application.add_handler(CommandHandler("delete", delete_task))
        application.add_handler(CommandHandler("complete", mark_completed))

        # Start the notifiers in a separate thread or as part of your main bot loop
        thread = Thread(target=run_notifiers)
        thread.start()

        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=Update.ALL_TYPES)

        # Shut down
        logging.info("Shutting down. This might take a moment.")
        shutdown_event.set()
        thread.join()
        logging.info("done.")
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")


if __name__ == "__main__":
    main()