import sys

def patch_app():
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()

        # Update Intents Empty State
        empty_intents = '''        st.markdown("""
        <div style="text-align:center;padding:48px 24px;border:1px dashed #d1d5db;border-radius:8px;background:#f9fafb;margin-top:16px;">
            <div style="font-size:24px;color:#9ca3af;margin-bottom:8px">📝</div>
            <div style="font-size:14px;font-weight:600;color:#374151">No Authorizations Found</div>
            <div style="font-size:13px;color:#6b7280;margin-top:4px">Create a natural language authorization above to get started.</div>
        </div>
        """, unsafe_allow_html=True)'''
        content = content.replace('st.info("No authorizations found.")', empty_intents)

        # Update Transactions Empty State
        empty_txns = '''        st.markdown("""
        <div style="text-align:center;padding:48px 24px;border:1px dashed #d1d5db;border-radius:8px;background:#f9fafb;margin-top:16px;">
            <div style="font-size:24px;color:#9ca3af;margin-bottom:8px">💳</div>
            <div style="font-size:14px;font-weight:600;color:#374151">No Transactions Found</div>
            <div style="font-size:13px;color:#6b7280;margin-top:4px">Run a simulation on the Overview page to generate transactions.</div>
        </div>
        """, unsafe_allow_html=True)'''
        content = content.replace('st.info("No transactions found.")', empty_txns)

        # Update Audit Empty State
        empty_audit = '''        st.markdown("""
        <div style="text-align:center;padding:48px 24px;border:1px dashed #d1d5db;border-radius:8px;background:#f9fafb;margin-top:16px;">
            <div style="font-size:24px;color:#9ca3af;margin-bottom:8px">🔒</div>
            <div style="font-size:14px;font-weight:600;color:#374151">No Evidence Records</div>
            <div style="font-size:13px;color:#6b7280;margin-top:4px">A cryptographic chain of custody will appear here once an agent initiates a transaction.</div>
        </div>
        """, unsafe_allow_html=True)'''
        content = content.replace('st.info("No audit evidence available yet. Run a transaction first.")', empty_audit)

        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    patch_app()
