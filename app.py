import eventlet
eventlet.monkey_patch()
from flask import Flask, request, render_template
from flask_socketio import SocketIO
import os
import logging
from selenium import webdriver
import undetected_chromedriver as uc
from concurrent.futures import ThreadPoolExecutor
import gc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
socketio = SocketIO(
    app,
    async_mode='eventlet',
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=20,
    max_http_buffer_size=1e5,
    engineio_logger=False
)

executor = ThreadPoolExecutor(max_workers=1)
thread_lock = eventlet.semaphore.Semaphore()

INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD")

def safe_emit(event, message):
    with thread_lock:
        try:
            socketio.emit(event, message)
            eventlet.sleep(0)
        except Exception as e:
            logger.error(f"Emit error: {e}")

def init_chrome():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")
    options.add_argument("--memory-model=low")
    options.add_argument("--disable-software-rasterizer")
    
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.javascript": 1
    })
    
    try:
        driver = uc.Chrome(
            options=options,
            version_main=114,
            enable_cdp_events=True
        )
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logger.error(f"Chrome init failed: {e}")
        return None

def send_dm(target_username, message, delay, max_accounts):
    driver = None
    try:
        driver = init_chrome()
        if not driver:
            safe_emit('update', "Browser init failed")
            return

        # Login logic
        driver.get("https://www.instagram.com/accounts/login/")
        eventlet.sleep(2)
        
        # [Rest of your Instagram interaction logic]
        # Keep existing logic but replace time.sleep() with eventlet.sleep()
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        safe_emit('error', str(e))
    finally:
        if driver:
            driver.quit()
            gc.collect()
        safe_emit('complete', "Process finished")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        executor.submit(
            send_dm,
            request.form["username"],
            request.form["message"],
            int(request.form["delay_between_msgs"]),
            int(request.form["max_accounts"])
        )
        return render_template("index.html", started=True)
    return render_template("index.html", started=False)

@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    safe_emit('status', 'connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")

if __name__ == "__main__":
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
        use_reloader=False
    )
