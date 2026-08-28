from datetime import date, timedelta
import streamlit as st
from db.telegram_accounts import get_account
from db.tags import get_tags, save_tags, all_tags
from services.telegram_service import get_dialogs, history, delete_message
from utils.date_range import bounds, normalize_range


def _chat_label(c):
    prefix={"private":"👤","group":"👥","supergroup":"👥","channel":"📢"}.get(c["type"],"💬")
    return f"{prefix} {c['title']}" + (f" (@{c['username']})" if c.get('username') else "")


def render_main(settings):
    if not st.session_state.telegram_user or not st.session_state.selected_telegram_account_id:
        st.title("📂 Telegram Saved Messages Manager"); st.info("Add or select a Telegram account from the sidebar."); return

    st.title("📂 Telegram Message Manager")
    if not st.session_state.dialogs:
        try: st.session_state.dialogs=get_dialogs()
        except Exception as e: st.error(f"Failed to load chats: {e}"); return
    dialogs=st.session_state.dialogs
    options={c["id"]:_chat_label(c) for c in dialogs}
    current=st.session_state.selected_chat_id
    if current not in options: current=next(iter(options),None); st.session_state.selected_chat_id=current
    if not current: st.warning("No chats were returned by Telegram."); return

    selected=st.selectbox("💬 Chat / Group / Channel",list(options),index=list(options).index(current),format_func=lambda x:options[x],key="chat_selector")
    if selected!=st.session_state.selected_chat_id:
        st.session_state.selected_chat_id=selected; st.session_state.messages=[]; st.rerun()

    today=date.today(); default=(today-timedelta(days=6),today)
    current_range=normalize_range(st.session_state.get("message_date_range"),default)
    picked=st.sidebar.date_input("Message Date Range",value=current_range,max_value=today,key="message_date_range_picker")
    if isinstance(picked,(list,tuple)) and len(picked)==2:
        st.session_state.message_date_range=(picked[0],picked[1])
    else:
        st.session_state.message_date_range=(picked,picked)
    start_date,end_date=st.session_state.message_date_range

    st.sidebar.caption(f"Showing: {start_date.isoformat()} → {end_date.isoformat()}")
    col1,col2=st.columns([1,1]);
    with col1: search=st.text_input("🔍 Search message text")
    tags=all_tags(settings.db_file,st.session_state.selected_telegram_account_id)
    with col2: tag=st.selectbox("🏷️ Tag",["All"]+tags)

    if not st.session_state.messages or st.button("🔄 Refresh Messages"):
        with st.spinner("Fetching messages..."):
            try:
                start_dt,end_dt=bounds(start_date,end_date)
                st.session_state.messages=history(selected,start_dt,end_dt,settings.default_message_limit)
            except Exception as e: st.error(f"Failed to fetch messages: {e}"); st.session_state.messages=[]

    messages=[]
    for m in st.session_state.messages:
        ts=m["date"].date()
        if not (start_date<=ts<=end_date): continue
        if search and search.lower() not in m["text"].lower(): continue
        mt=get_tags(settings.db_file,st.session_state.selected_telegram_account_id,m["id"])
        if tag!="All" and tag not in mt: continue
        messages.append((m,mt))

    st.caption(f"{len(messages)} message(s) in selected range")
    for m,current_tags in messages:
        with st.container(border=True):
            left,right=st.columns([4,1])
            with left:
                st.write(m["text"]); st.caption(f"📅 {m['date'].strftime('%Y-%m-%d %H:%M:%S')} | ID: {m['id']}")
            with right:
                value=st.text_input("Tags",", ".join(current_tags),key=f"tags_{m['id']}")
                if st.button("Save Tags",key=f"save_{m['id']}"): save_tags(settings.db_file,st.session_state.selected_telegram_account_id,m["id"],value.split(",")); st.rerun()
                if st.button("🗑️ Delete",key=f"del_{m['id']}",type="primary"):
                    try: delete_message(selected,m["id"]); st.session_state.messages=[x for x in st.session_state.messages if x["id"]!=m["id"]]; st.rerun()
                    except Exception as e: st.error(f"Failed to delete message: {e}")

    st.markdown("""<style>
    .message-nav{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:999;background:var(--background-color);padding:10px 16px;border-radius:12px;border:1px solid rgba(128,128,128,.35);box-shadow:0 4px 18px rgba(0,0,0,.15)}
    </style>""",unsafe_allow_html=True)
    st.markdown('<div class="message-nav">',unsafe_allow_html=True)
    a,b,c=st.columns([1,2,1])
    with a:
        if st.button("◀ Previous Day",use_container_width=True):
            st.session_state.message_date_range=(start_date-timedelta(days=1),end_date-timedelta(days=1)); st.rerun()
    with b: st.markdown(f"<div style='text-align:center;padding:7px 0'><b>{start_date.isoformat()} → {end_date.isoformat()}</b></div>",unsafe_allow_html=True)
    with c:
        if st.button("Next Day ▶",use_container_width=True):
            if end_date<today:
                st.session_state.message_date_range=(start_date+timedelta(days=1),end_date+timedelta(days=1)); st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
