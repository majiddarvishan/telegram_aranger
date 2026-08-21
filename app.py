import asyncio
import sqlite3

# ---------------------------------------------------------
# Python 3.14 / Pyrogram 2.0.106 compatibility
# ---------------------------------------------------------
# Pyrogram 2.0.106 uses asyncio.get_event_loop() while
# importing pyrogram.sync. Python 3.14 no longer creates
# an event loop automatically in a new thread.
#
# Streamlit executes the application in ScriptRunner.scriptThread,
# so create and register an event loop before importing Pyrogram.
# ---------------------------------------------------------
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import streamlit as st
from pyrogram import Client

# ---------------------------------------------------------
# 1. Telegram API Credentials
# ---------------------------------------------------------
# Using official Telegram for Android public credentials
# ---------------------------------------------------------API_ID = 20446742
API_ID = 20446742
API_HASH = "99124cd7544e1c93bd2c4491287e21dd"

# ---------------------------------------------------------
# 2. Local SQLite Database Setup
# ---------------------------------------------------------
# Stores custom tags for Telegram messages.
# ---------------------------------------------------------
conn = sqlite3.connect(
    "telegram_tags.db",
    check_same_thread=False,
)

cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS message_tags (
        message_id INTEGER PRIMARY KEY,
        tags TEXT
    )
    """
)

conn.commit()


def get_tags(msg_id: int) -> list[str]:
    """Retrieve saved tags for a specific message ID from SQLite."""
    cursor.execute(
        "SELECT tags FROM message_tags WHERE message_id = ?",
        (msg_id,),
    )

    row = cursor.fetchone()

    if row and row[0]:
        return row[0].split(",")

    return []


def save_tags(msg_id: int, tags_list: list[str]) -> None:
    """Save or update tags for a specific message ID."""
    tags_str = ",".join(
        tag.strip()
        for tag in tags_list
        if tag.strip()
    )

    cursor.execute(
        """
        INSERT OR REPLACE INTO message_tags
        (message_id, tags)
        VALUES (?, ?)
        """,
        (msg_id, tags_str),
    )

    conn.commit()

# ---------------------------------------------------------
# 3. Helper Function to Build Proxy Config
# ---------------------------------------------------------
def get_proxy_config() -> dict | None:
    """Read proxy settings from Streamlit session state."""

    if not st.session_state.get("use_proxy", False):
        return None

    proxy_dict = {
        "scheme": "socks5",
        "hostname": st.session_state.get(
            "proxy_host",
            "127.0.0.1",
        ),
        "port": int(
            st.session_state.get(
                "proxy_port",
                1080,
            )
        ),
    }

    username = st.session_state.get(
        "proxy_user",
        "",
    ).strip()

    password = st.session_state.get(
        "proxy_pass",
        "",
    ).strip()

    if username:
        proxy_dict["username"] = username

    if password:
        proxy_dict["password"] = password

    return proxy_dict


# ---------------------------------------------------------
# 4. Async Helper
# ---------------------------------------------------------
# def run_async(coro):
#     """
#     Run an asynchronous coroutine from Streamlit.

#     Pyrogram is used through its asynchronous API, so the
#     application does not use pyrogram.sync.
#     """
#     return asyncio.run(coro)

def run_async(coro):
    """Run a coroutine using a dedicated event loop."""
    loop = asyncio.new_event_loop()

    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()

# ---------------------------------------------------------
# 5. Asynchronous Telegram Actions
# ---------------------------------------------------------
async def fetch_saved_messages(
    limit: int = 100,
    proxy: dict | None = None,
) -> list[dict]:
    """Fetch recent messages from Telegram Saved Messages."""

    async with Client(
        "my_tele_session",
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy,
    ) as app:

        me = await app.get_me()

        messages = []

        async for message in app.get_chat_history(
            "me",
            limit=limit,
        ):
            content = (
                message.text
                or message.caption
                or "[Media / File]"
            )

            messages.append(
                {
                    "id": message.id,
                    "text": content,
                    "date": str(message.date),
                    "user_id": me.id,
                }
            )

        return messages


async def delete_telegram_message(
    message_id: int,
    proxy: dict | None = None,
) -> None:
    """Delete a specific message from Saved Messages."""

    async with Client(
        "my_tele_session",
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy,
    ) as app:

        await app.delete_messages(
            "me",
            message_id,
        )


# ---------------------------------------------------------
# 6. Streamlit Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Saved Messages Manager",
    layout="wide",
)

st.title("📂 Telegram Saved Messages Dashboard")


# ---------------------------------------------------------
# 7. Sidebar: Proxy Settings
# ---------------------------------------------------------
st.sidebar.header("⚙️ Network Settings")

st.session_state.use_proxy = st.sidebar.checkbox(
    "Enable SOCKS5 Proxy",
    value=True,
)

if st.session_state.use_proxy:

    st.session_state.proxy_host = st.sidebar.text_input(
        "Proxy Host/IP",
        value="127.0.0.1",
    )

    st.session_state.proxy_port = st.sidebar.number_input(
        "Proxy Port",
        value=1080,
        min_value=1,
        max_value=65535,
    )

    st.session_state.proxy_user = st.sidebar.text_input(
        "Username (Optional)",
        value="",
    )

    st.session_state.proxy_pass = st.sidebar.text_input(
        "Password (Optional)",
        type="password",
        value="",
    )


st.sidebar.markdown("---")


# ---------------------------------------------------------
# 8. Message Fetching
# ---------------------------------------------------------
proxy_config = get_proxy_config()


if (
    "messages" not in st.session_state
    or st.button("🔄 Refresh Messages")
):
    with st.spinner(
        "Fetching messages from Telegram..."
    ):
        try:
            st.session_state.messages = run_async(
                fetch_saved_messages(
                    limit=100,
                    proxy=proxy_config,
                )
            )

        except Exception as e:
            st.error(
                f"Error connecting to Telegram: {e}"
            )

            st.session_state.messages = []


# ---------------------------------------------------------
# 9. Sidebar: Tag Filter
# ---------------------------------------------------------
all_tags = set()

cursor.execute(
    "SELECT tags FROM message_tags"
)

for row in cursor.fetchall():
    if row[0]:
        all_tags.update(
            row[0].split(",")
        )


selected_tag = st.sidebar.selectbox(
    "Filter by Tag:",
    ["All"] + sorted(all_tags),
)


# ---------------------------------------------------------
# 10. Search
# ---------------------------------------------------------
search_query = st.text_input(
    "🔍 Search message text:"
)


# ---------------------------------------------------------
# 11. Render Message Cards
# ---------------------------------------------------------
if "messages" in st.session_state:

    for msg in st.session_state.messages:

        msg_id = msg["id"]
        text = msg["text"]

        current_tags = get_tags(msg_id)

        # -------------------------------------------------
        # Filter by tag
        # -------------------------------------------------
        if (
            selected_tag != "All"
            and selected_tag not in current_tags
        ):
            continue

        # -------------------------------------------------
        # Filter by text
        # -------------------------------------------------
        if (
            search_query
            and search_query.lower()
            not in text.lower()
        ):
            continue

        # -------------------------------------------------
        # Message container
        # -------------------------------------------------
        with st.container():

            st.markdown("---")

            col_content, col_actions = st.columns(
                [3, 1]
            )

            # ---------------------------------------------
            # Message content
            # ---------------------------------------------
            with col_content:

                st.write(text)

                st.caption(
                    f"📅 Date: {msg['date']} | "
                    f"ID: {msg_id}"
                )

                tg_deep_link = (
                    f"https://t.me/c/"
                    f"{msg['user_id']}/"
                    f"{msg_id}"
                )

                st.markdown(
                    f"[🔗 Open in Telegram Client]"
                    f"({tg_deep_link})"
                )

            # ---------------------------------------------
            # Actions
            # ---------------------------------------------
            with col_actions:

                tags_input = st.text_input(
                    "Tags (comma separated):",
                    value=", ".join(
                        current_tags
                    ),
                    key=f"tag_{msg_id}",
                )

                # -----------------------------------------
                # Save Tags
                # -----------------------------------------
                if st.button(
                    "Save Tags",
                    key=f"save_{msg_id}",
                ):

                    save_tags(
                        msg_id,
                        tags_input.split(","),
                    )

                    st.success(
                        "Tags updated!"
                    )

                    st.rerun()

                # -----------------------------------------
                # Delete Message
                # -----------------------------------------
                if st.button(
                    "🗑️ Delete Message",
                    key=f"del_{msg_id}",
                    type="primary",
                ):
                    try:

                        run_async(
                            delete_telegram_message(
                                msg_id,
                                proxy=proxy_config,
                            )
                        )

                        st.session_state.messages = [
                            message
                            for message
                            in st.session_state.messages
                            if message["id"] != msg_id
                        ]

                        st.success(
                            "Message deleted from Telegram!"
                        )

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Failed to delete message: {e}"
                        )
