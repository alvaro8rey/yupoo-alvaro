"""
main.py — Entry point: runs Flask admin (port 8080) + Telegram bot together.
"""

import threading
import db

db.init_db()
db.seed_demo_if_empty()

import admin
import bot


def run_flask():
    admin.app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.main()
