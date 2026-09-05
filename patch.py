import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

helpers = '''
def navigate_to(page):
    if "history" not in st.session_state:
        st.session_state.history = ["overview"]
    if st.session_state.get("page") != page:
        st.session_state.history.append(st.session_state.get("page", "overview"))
        st.session_state.page = page
        st.rerun()

def navigate_back():
    if "history" in st.session_state and st.session_state.history:
        st.session_state.page = st.session_state.history.pop()
        st.rerun()
    else:
        st.session_state.page = "overview"
        st.rerun()
'''

if "def navigate_to(" not in content:
    content = content.replace('if "page" not in st.session_state:\n    st.session_state.page = "overview"',
        helpers + '\nif "page" not in st.session_state:\n    st.session_state.page = "overview"')

# Replace render_sidebar assignment
content = content.replace('st.session_state.page = new_page\n                st.rerun()', 'navigate_to(new_page)')

# Replace back buttons
content = re.sub(
    r'if st\.button\("← [^"]+", key="([^"]+)"\):\s+st\.session_state\.(?:page|audit_txn_id) = [^s]+(?:\s+st\.rerun\(\))?',
    r'if st.button("← Back", key="\1"):\n        navigate_back()',
    content
)

# And replace audit specific back button (it clears audit_txn_id)
# Actually, the user wants the back button to just say "Back" and go back.
# If they are inside audit details, we can just do navigate_back().
# But wait! If they are inside audit details, they are still on "audit" page, they just have audit_txn_id set!
# Ah! In Streamlit, "drilling down" into an evidence sets `st.session_state.audit_txn_id = ev["transaction_id"]`.
# It does NOT change `st.session_state.page`.
# So navigate_back() won't work for drill-downs unless we also track those in history!

