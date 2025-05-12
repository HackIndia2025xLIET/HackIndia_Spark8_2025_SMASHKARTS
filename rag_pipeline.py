# File: rag_pipeline.py

from langchain_groq import ChatGroq
from vector_database import faiss_db
from langchain_core.prompts import ChatPromptTemplate

# Initialize LLM
llm_model = ChatGroq(model="deepseek-r1-distill-llama-70b", api_key="your_api_key")

# Prompt Template
custom_prompt_template = """
Use the pieces of information provided in the context to answer user's question.
If you dont know the answer, just say that you dont know, dont try to make up an answer. 
Dont provide anything out of the given context
Question: {question} 
Context: {context} 
Answer:
"""

def retrieve_docs(query):
    return faiss_db.similarity_search(query)

def get_context(documents):
    return "\n\n".join([doc.page_content for doc in documents])

def answer_query(documents, model, query):
    context = get_context(documents)
    prompt = ChatPromptTemplate.from_template(custom_prompt_template)
    chain = prompt | model
    return chain.invoke({"question": query, "context": context})
