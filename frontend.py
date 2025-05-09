import streamlit as st
import pyrebase
from rag_pipeline import answer_query, retrieve_docs, llm_model

# Firebase config
firebaseConfig = {
    "apiKey": "AIzaSyBHjPkKWCaO-W6Mw6gASb0b8eg1evvzdXw",
    "authDomain": "jurisrag.firebaseapp.com",
    "databaseURL": "https://jurisrag-default-rtdb.asia-southeast1.firebasedatabase.app",
    "projectId": "jurisrag",
    "storageBucket": "jurisrag.appspot.com",
    "messagingSenderId": "803233703815",
    "appId": "1:803233703815:web:229221682448b863d91522",
    "measurementId": "G-G8HGLSQJXZ"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

# Session defaults
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Login UI
def login_ui():
    st.title("🔐 JurisRAG Login")
    option = st.selectbox("Login or Sign up", ["Login", "Sign up"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if option == "Sign up":
        if st.button("Create Account"):
            try:
                auth.create_user_with_email_and_password(email, password)
                st.success("✅ Account created. Please log in.")
            except Exception as e:
                st.error(f"❌ {e}")
    else:
        if st.button("Login"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state.user = user
                st.session_state.authenticated = True
            except Exception as e:
                st.error(f"❌ {e}")

# Main App
def main_app():
    st.title("⚖️ JurisRAG: AI Legal Assistant")

    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    user_query = st.text_area("Ask your legal question:")

    if st.button("Ask JurisRAG"):
        if uploaded_file and user_query:
            st.chat_message("user").write(user_query)
            with st.spinner("Thinking..."):
                docs = retrieve_docs(user_query)
                answer = answer_query(documents=docs, model=llm_model, query=user_query)
            st.chat_message("JurisRag").write(answer)
        else:
            st.error("📂 Please upload a file and enter a question.")

    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user = None

# Control flow
if st.session_state.authenticated:
    main_app()
else:
    login_ui()
