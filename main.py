# File: main.py

import streamlit as st
import pyrebase
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq

# Firebase Configuration
firebaseConfig = {
  "apiKey": "AIzaSyBHjPkKWCaO-W6Mw6gASb0b8eg1evvzdXw",
  "authDomain": "jurisrag.firebaseapp.com",
  "databaseURL": "https://jurisrag-default-rtdb.asia-southeast1.firebasedatabase.app",
  "projectId": "jurisrag",
  "storageBucket": "jurisrag.firebasestorage.app",
  "messagingSenderId": "803233703815",
  "appId": "1:803233703815:web:229221682448b863d91522",
  "measurementId": "G-G8HGLSQJXZ"
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

def login_ui():
    st.title("Login to JurisRag")
    choice = st.selectbox('Login/Signup', ['Login', 'Sign up'])
    email = st.text_input('Email')
    password = st.text_input('Password', type='password')

    if choice == 'Sign up':
        if st.button('Create Account'):
            try:
                user = auth.create_user_with_email_and_password(email, password)
                st.success('Account created! Please log in.')
            except Exception as e:
                st.error(f'Error: {e}')
    else:
        if st.button('Login'):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state['user'] = user
                st.success('Logged in successfully!')
            except Exception as e:
                st.error(f'Login failed: {e}')

if 'user' not in st.session_state:
    login_ui()
    st.stop()

# ---- JurisRag RAG Code Starts Here ----
ollama_model_name = "deepseek-r1:14b"
embeddings = OllamaEmbeddings(model=ollama_model_name)
FAISS_DB_PATH = "vectorstore/db_faiss"
pdfs_directory = 'pdfs/'
llm_model = ChatGroq(model="deepseek-r1-distill-llama-70b")

custom_prompt_template = """
Use the pieces of information provided in the context to answer user's question.
If you dont know the answer, just say that you dont know, dont try to make up an answer. 
Dont provide anything out of the given context
Question: {question} 
Context: {context} 
Answer:
"""

def upload_pdf(file):
    with open(pdfs_directory + file.name, "wb") as f:
        f.write(file.getbuffer())

def load_pdf(file_path):
    loader = PDFPlumberLoader(file_path)
    documents = loader.load()
    return documents

def create_chunks(documents): 
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 1000,
        chunk_overlap = 200,
        add_start_index = True
    )
    text_chunks = text_splitter.split_documents(documents)
    return text_chunks

def get_embedding_model(ollama_model_name):
    embeddings = OllamaEmbeddings(model=ollama_model_name)
    return embeddings

def create_vector_store(db_faiss_path, text_chunks, ollama_model_name):
    faiss_db = FAISS.from_documents(text_chunks, get_embedding_model(ollama_model_name))
    faiss_db.save_local(db_faiss_path)
    return faiss_db

def retrieve_docs(faiss_db, query):
    return faiss_db.similarity_search(query)

def get_context(documents):
    context = "\n\n".join([doc.page_content for doc in documents])
    return context

def answer_query(documents, model, query):
    context = get_context(documents)
    prompt = ChatPromptTemplate.from_template(custom_prompt_template)
    chain = prompt | model
    return chain.invoke({"question": query, "context": context})

# UI
st.title("JurisRag: AI Legal Assistant")
uploaded_file = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=False)
user_query = st.text_area("Enter your prompt: ", height=150 , placeholder= "Ask Anything!")
ask_question = st.button("Ask AI Lawyer")

if ask_question:
    if uploaded_file and user_query:
        upload_pdf(uploaded_file)
        documents = load_pdf(pdfs_directory + uploaded_file.name)
        text_chunks = create_chunks(documents)
        faiss_db = create_vector_store(FAISS_DB_PATH, text_chunks, ollama_model_name)

        retrieved_docs = retrieve_docs(faiss_db, user_query)
        response = answer_query(documents=retrieved_docs, model=llm_model, query=user_query)

        st.chat_message("user").write(user_query)
        st.chat_message("AI Lawyer").write(response)
    else:
        st.error("Kindly upload a valid PDF file and/or ask a valid Question!")

if st.button("Logout"):
    st.session_state.clear()
    st.success("You have been logged out.")
    st.stop()

