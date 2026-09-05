def fix_indents():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # The string we accidentally inserted has 16 spaces: `                st.markdown("""`
    bad_string = "                st.markdown(\"\"\""
    good_string = "        st.markdown(\"\"\""
    
    # We also need to fix `st.markdown('</div>', unsafe_allow_html=True)` which was incorrectly unindented in the snippet?
    # Wait, the screenshot says:
    # File "C:\Users\awnns\payment_razorpay\app.py", line 1642
    #     st.markdown('</div>', unsafe_allow_html=True)
    # IndentationError: unindent does not match any outer indentation level
    # 
    # Let's just fix the bad strings
    content = content.replace(bad_string, good_string)
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    fix_indents()
