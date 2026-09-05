import re

def patch_app():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    helpers = '''
def navigate_to(page, **kwargs):
    if "history" not in st.session_state:
        st.session_state.history = [{"page": "overview"}]
    
    current_state = {"page": st.session_state.get("page", "overview")}
    for k in ["detail_txn_id", "audit_txn_id"]:
        if k in st.session_state:
            current_state[k] = st.session_state[k]
            
    st.session_state.history.append(current_state)
    
    st.session_state.page = page
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()

def navigate_back():
    if "history" in st.session_state and st.session_state.history:
        prev_state = st.session_state.history.pop()
        
        st.session_state.page = prev_state.get("page", "overview")
        
        for k in ["detail_txn_id", "audit_txn_id"]:
            if k in prev_state:
                st.session_state[k] = prev_state[k]
            elif k in st.session_state:
                st.session_state[k] = None
        
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

    # Replace specific page assignments with navigate_to
    content = re.sub(r'st\.session_state\.page\s*=\s*"([^"]+)"\n\s*st\.rerun\(\)', r'navigate_to("\1")', content)

    # Replace back buttons
    content = re.sub(
        r'if st\.button\("← [^"]+", key="([^"]+)"\):\n\s+st\.session_state\.page = "[^"]+"\n\s+st\.rerun\(\)',
        r'if st.button("← Back", key="\1"):\n        navigate_back()',
        content
    )
    
    # Audit back button is special: clears audit_txn_id
    content = re.sub(
        r'if st\.button\("← Back to Evidence List", key="back_aud"\):\n\s+st\.session_state\.audit_txn_id = None\n\s+st\.rerun\(\)',
        r'if st.button("← Back", key="back_aud"):\n        navigate_back()',
        content
    )
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Success")

if __name__ == "__main__":
    patch_app()
