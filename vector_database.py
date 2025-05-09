# File: vector_database.py

from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

# You can modify the model name or embedding settings here
embedding_model_name = "deepseek-r1:7b"
embeddings = OllamaEmbeddings(model=embedding_model_name)

# Load the vector DB (must have been created previously via main.py)
faiss_db = FAISS.load_local(
    folder_path="vectorstore/db_faiss",
    embeddings=embeddings,
    allow_dangerous_deserialization=True
)
