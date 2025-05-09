import streamlit as st
import pyrebase
import datetime
import json
import os
from deep_translator import GoogleTranslator

# Import from your RAG pipeline
from rag_pipeline import answer_query, retrieve_docs, llm_model

# Firebase Configuration
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

# Available languages for translation
LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Chinese (Simplified)": "zh-CN",
    "Arabic": "ar",
    "Russian": "ru",
    "Japanese": "ja",
    "Portuguese": "pt"
}

# Initialize Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()

# Authentication File Management
AUTH_FILE_PATH = '.streamlit/user_auth.json'

def save_auth_to_file(user_data):
    """Save user authentication data to a local file for session persistence"""
    try:
        # Only save necessary authentication data
        auth_data = {
            'idToken': user_data.get('idToken', ''),
            'refreshToken': user_data.get('refreshToken', ''),
            'localId': user_data.get('localId', '')
        }
        
        # Validate data before saving
        if not auth_data['idToken'] or not auth_data['refreshToken'] or not auth_data['localId']:
            st.warning("Missing critical authentication data. Session may not persist.")
            return False
            
        os.makedirs(os.path.dirname(AUTH_FILE_PATH), exist_ok=True)
        with open(AUTH_FILE_PATH, 'w') as f:
            json.dump(auth_data, f)
        return True
    except Exception as e:
        st.warning(f"Could not save session data: {e}")
        return False

def load_auth_from_file():
    """Load user authentication data from local file"""
    try:
        if os.path.exists(AUTH_FILE_PATH):
            with open(AUTH_FILE_PATH, 'r') as f:
                auth_data = json.load(f)
                
                # Validate the auth data has required fields
                if not auth_data or not all(k in auth_data for k in ['refreshToken', 'idToken', 'localId']):
                    st.warning("Invalid auth data found. Please log in again.")
                    remove_auth_file()
                    return None
                    
                return auth_data
    except Exception as e:
        st.error(f"Error loading authentication data: {e}")
        remove_auth_file()  # Remove potentially corrupted file
    return None

def remove_auth_file():
    """Remove the authentication file (used during logout)"""
    try:
        if os.path.exists(AUTH_FILE_PATH):
            os.remove(AUTH_FILE_PATH)
    except Exception as e:
        st.warning(f"Could not remove session file: {e}")

# Translation Functions
def translate_text(text, target_lang):
    """Translate text to target language"""
    if target_lang == "en" or not text:  # No translation needed for English
        return text
    
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        return translator.translate(text)
    except Exception as e:
        st.error(f"Translation error: {e}")
        return text  # Return original text if translation fails

def translate_to_english(text, source_lang):
    """Translate non-English text to English"""
    if source_lang == "en" or not text:  # No translation needed if already English
        return text
    
    try:
        translator = GoogleTranslator(source=source_lang, target='en')
        return translator.translate(text)
    except Exception as e:
        st.error(f"Translation error: {e}")
        return text  # Return original text if translation fails

# Content Processing Functions
def extract_content(message):
    """Extract content from different message formats"""
    # If it's an AIMessage object with content attribute
    if hasattr(message, 'content'):
        return message.content
    # If it's a dictionary with content key
    elif isinstance(message, dict) and 'content' in message:
        return message['content']
    # If it's already a string or convertible to string
    else:
        return str(message)

# Database Interaction Functions
def save_question(user_id, question, answer):
    """Save question and answer to user history"""
    timestamp = datetime.datetime.now().isoformat()
    answer_text = extract_content(answer)
    db.child("users").child(user_id).child("questions").push({
        "question": question,
        "answer": answer_text,
        "timestamp": timestamp
    })

def get_user_questions(user_id):
    """Get list of user's previous questions"""
    questions = db.child("users").child(user_id).child("questions").get()
    if questions.each():
        # Return list of tuples with (question, key)
        return [(q.val()["question"], q.key()) for q in questions.each()]
    return []

def get_question_answer(user_id, question_key):
    """Get full details for a specific question"""
    return db.child("users").child(user_id).child("questions").child(question_key).get().val()

# Session Initialization
def initialize_session():
    """Initialize session state variables"""
    # Define all session state variables with defaults
    if "language" not in st.session_state:
        st.session_state.language = "English"
    if "reask_query" not in st.session_state:
        st.session_state.reask_query = ""
    if "login_error" not in st.session_state:
        st.session_state.login_error = ""
    
    # Set authentication state only once to prevent overwriting during reloads
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        
        # Try to load authentication from file for persistent login
        auth_data = load_auth_from_file()
        if auth_data:
            try:
                # Directly use the refresh token to get a new ID token
                refreshed_user = auth.refresh(auth_data['refreshToken'])
                
                # Build a complete user object from refreshed data and stored data
                user_data = {
                    'idToken': refreshed_user.get('idToken', ''),
                    'refreshToken': refreshed_user.get('refreshToken', ''),
                    'localId': auth_data.get('localId', '')  # Keep original localId if not in refreshed data
                }
                
                # Validate the user data has required fields
                if not user_data['idToken'] or not user_data['refreshToken'] or not user_data['localId']:
                    st.error("Incomplete authentication data after refresh")
                    remove_auth_file()
                    return
                    
                # Save the updated tokens back to file
                save_auth_to_file(user_data)
                
                # Update session state
                st.session_state.user = user_data
                st.session_state.authenticated = True
                
            except Exception as e:
                # If token refresh fails, user needs to login again
                st.error(f"Your session has expired: {e}")
                st.session_state.authenticated = False
                st.session_state.user = None
                # Remove the auth file
                remove_auth_file()

# UI Components
def login_ui():
    """Login and signup user interface"""
    st.title("🔐 JurisRAG Login")
    
    # Language selector in login page
    if "temp_language" not in st.session_state:
        st.session_state.temp_language = st.session_state.language
        
    lang_name = st.selectbox(
        "Select Language", 
        list(LANGUAGES.keys()), 
        index=list(LANGUAGES.keys()).index(st.session_state.temp_language),
        key="login_lang_selector"
    )
    
    # Update language in session if changed
    if lang_name != st.session_state.temp_language:
        st.session_state.language = lang_name
        st.session_state.temp_language = lang_name
    
    lang_code = LANGUAGES[lang_name]
    
    # Translate UI elements
    login_text = translate_text("Login or Sign up", lang_code)
    email_text = translate_text("Email", lang_code)
    password_text = translate_text("Password", lang_code)
    signup_text = translate_text("Sign up", lang_code)
    login_button_text = translate_text("Login", lang_code)
    create_account_text = translate_text("Create Account", lang_code)
    
    option = st.selectbox(
        login_text, 
        [translate_text("Login", lang_code), translate_text("Sign up", lang_code)]
    )
    
    with st.form("auth_form"):
        email = st.text_input(email_text)
        password = st.text_input(password_text, type="password")
        
        submitted = st.form_submit_button(
            login_button_text if option == translate_text("Login", lang_code) else create_account_text
        )
        
        if submitted:
            if option == translate_text("Sign up", lang_code):
                try:
                    auth.create_user_with_email_and_password(email, password)
                    st.success(translate_text("✅ Account created. Please log in.", lang_code))
                except Exception as e:
                    error_message = str(e)
                    if "EMAIL_EXISTS" in error_message:
                        st.error("❌ Email already exists. Please use a different email or try logging in.")
                    elif "WEAK_PASSWORD" in error_message:
                        st.error("❌ Password should be at least 6 characters long.")
                    elif "INVALID_EMAIL" in error_message:
                        st.error("❌ Please enter a valid email address.")
                    else:
                        st.error(f"❌ Registration error: {error_message}")
            else:
                try:
                    user = auth.sign_in_with_email_and_password(email, password)
                    
                    # Ensure we have the required fields
                    if not user.get('idToken') or not user.get('refreshToken') or not user.get('localId'):
                        st.error("Incomplete authentication data received")
                        return
                    
                    # Save only necessary authentication data
                    auth_data = {
                        'idToken': user.get('idToken', ''),
                        'refreshToken': user.get('refreshToken', ''),
                        'localId': user.get('localId', '')
                    }
                    
                    # Save authentication data to file for persistence
                    if save_auth_to_file(auth_data):
                        # Update session state with auth data
                        st.session_state.user = auth_data
                        st.session_state.authenticated = True
                        
                        # Force page rerun to show the main app
                        st.rerun()
                    else:
                        st.error("Failed to save authentication data")
                        
                except Exception as e:
                    # Convert Firebase error to user-friendly message
                    error_message = str(e)
                    if "INVALID_LOGIN_CREDENTIALS" in error_message:
                        st.error(f"❌ Invalid email or password. Please try again.")
                    elif "TOO_MANY_ATTEMPTS_TRY_LATER" in error_message:
                        st.error("❌ Too many failed login attempts. Please try again later.")
                    elif "USER_DISABLED" in error_message:
                        st.error("❌ This account has been disabled. Please contact support.")
                    else:
                        st.error(f"❌ Login error: {error_message}")

def sidebar_ui(user_id, lang_name, lang_code):
    """Sidebar UI with settings and history"""
    with st.sidebar:
        st.title(translate_text("🌐 Settings", lang_code))
        
        # Language selector
        lang_selector = st.selectbox(
            translate_text("Select Language", lang_code),
            list(LANGUAGES.keys()),
            index=list(LANGUAGES.keys()).index(lang_name),
            key="sidebar_lang_selector"
        )
        
        # Apply button for language change
        if lang_selector != lang_name:
            if st.button(translate_text("Apply Language Change", lang_code)):
                st.session_state.language = lang_selector
                st.rerun()
        
        # History section in sidebar
        st.markdown("---")
        st.title(translate_text("📚 Your Question History", lang_code))
        question_history = get_user_questions(user_id)
        
        if question_history:
            # Display questions - use only the question text for display
            question_texts = [q[0] for q in question_history]
            
            selected_index = st.selectbox(
                translate_text("Previous Questions", lang_code),
                range(len(question_texts)),
                format_func=lambda i: question_texts[i],
                key="history_selector"
            )
            
            selected_question, selected_key = question_history[selected_index]
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(translate_text("View Details", lang_code)):
                    question_data = get_question_answer(user_id, selected_key)
                    st.subheader(translate_text("Question:", lang_code))
                    st.write(translate_text(question_data["question"], lang_code))
                    st.subheader(translate_text("Answer:", lang_code))
                    st.write(translate_text(question_data["answer"], lang_code))
            
            with col2:
                if st.button(translate_text("Re-ask Selected", lang_code)):
                    st.session_state.reask_query = selected_question
                    st.rerun()
        else:
            st.write(translate_text("No previous questions found.", lang_code))

        # Logout button in sidebar
        st.markdown("---")
        if st.button(translate_text("Logout", lang_code), type="primary"):
            st.session_state.authenticated = False
            st.session_state.user = None
            
            # Remove authentication file
            remove_auth_file()
                
            # Force page rerun to show login screen
            st.rerun()

def main_content_ui(user_id, lang_code):
    """Main content area with question input and response"""
    upload_text = translate_text("Upload PDF", lang_code)
    ask_text = translate_text("Ask your legal question:", lang_code)
    button_text = translate_text("Ask JurisRAG", lang_code)
    
    # File uploader for PDF documents
    uploaded_file = st.file_uploader(upload_text, type="pdf")

    # Get reask_query from session if available
    default_query = ""
    if st.session_state.reask_query:
        default_query = st.session_state.reask_query
        # Clear it after using
        st.session_state.reask_query = ""
    
    # Question input area    
    user_query = st.text_area(ask_text, value=default_query, height=100)

    # Submit button
    if st.button(button_text, type="primary", use_container_width=True):
        if uploaded_file and user_query:
            # Save the original query (in selected language)
            original_query = user_query
            
            # Translate query to English for processing if not already in English
            if lang_code != "en":
                query_for_processing = translate_to_english(user_query, lang_code)
            else:
                query_for_processing = user_query
            
            # Display user query in chat format    
            st.chat_message("user").write(original_query)
            
            with st.spinner(translate_text("Thinking...", lang_code)):
                # Process query with RAG pipeline
                docs = retrieve_docs(query_for_processing)
                answer_in_english = answer_query(documents=docs, model=llm_model, query=query_for_processing)
                
                # Extract text content from the response
                answer_text = extract_content(answer_in_english)
                
                # Translate answer back to user's language if needed
                if lang_code != "en":
                    answer = translate_text(answer_text, lang_code)
                else:
                    answer = answer_text
                
            # Display assistant response in chat format    
            st.chat_message("assistant", avatar="⚖️").write(answer)
            
            # Save both question and answer to history
            save_question(user_id, original_query, answer)
        else:
            error_msg = translate_text("📂 Please upload a file and enter a question.", lang_code)
            st.error(error_msg)

def main_app():
    """Main application UI when user is authenticated"""
    # Get language settings
    lang_name = st.session_state.language
    lang_code = LANGUAGES[lang_name]
    
    # Translate title
    title_text = translate_text("⚖️ JurisRAG: AI Legal Assistant", lang_code)
    st.title(title_text)

    # Get user ID from session - with error checking
    try:
        if 'user' in st.session_state and st.session_state.user and 'localId' in st.session_state.user:
            user_id = st.session_state.user['localId']
        else:
            st.error("Session data is incomplete. Please log in again.")
            st.session_state.authenticated = False
            remove_auth_file()
            st.rerun()
            return
    except Exception as e:
        st.error(f"Error accessing user data: {e}")
        st.session_state.authenticated = False
        remove_auth_file()
        st.rerun()
        return

    # Initialize sidebar with settings and history
    sidebar_ui(user_id, lang_name, lang_code)
    
    # Initialize main content area
    main_content_ui(user_id, lang_code)

# Application entry point
def run_app():
    """Main application entry point"""
    # Set page configuration
    st.set_page_config(
        page_title="JurisRAG",
        page_icon="⚖️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Add custom CSS for better error styling
    st.markdown("""
    <style>
    .stAlert {
        padding: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state - this preserves the state across reruns
    initialize_session()

    # Determine which UI to show based on authentication state
    if st.session_state.authenticated:
        try:
            # The main_app function now handles its own error checking
            main_app()
        except Exception as e:
            # Global error handler for unexpected errors
            error_msg = str(e)
            st.error(f"An unexpected error occurred: {error_msg}")
            
            # Log more details for debugging
            import traceback
            st.error(traceback.format_exc())
            
            # Specific handling for authentication errors
            if "INVALID_ID_TOKEN" in error_msg or "Token expired" in error_msg:
                st.error("Your session has expired. Please log in again.")
                st.session_state.authenticated = False
                st.session_state.user = None
                remove_auth_file()
                st.rerun()
    else:
        login_ui()

if __name__ == "__main__":
    run_app()