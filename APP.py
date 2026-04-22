import streamlit as st
import speech_recognition as sr
import requests
import re
import nltk
from gtts import gTTS
from pydub import AudioSegment
import os
import math

# --- 1. CORE FUNCTIONS ---

def create_and_combine_chunks(text, is_slow, title):
    """
    Processes the book into chunks, combines them into a single MP3,
    and returns the path to the final file.
    """
    st.session_state.is_processing = True
    st.session_state.final_audio_path = None
    
    sentences = nltk.sent_tokenize(text)
    chunk_size = 10
    num_chunks = math.ceil(len(sentences) / chunk_size)
    chunk_files = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.info("Starting audio creation...")

    for i in range(num_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk_text = " ".join(sentences[start:end])
        
        if not chunk_text.strip():
            continue

        try:
            tts = gTTS(text=chunk_text, lang='en', slow=is_slow)
            chunk_file = f"chunk_{i}.mp3"
            tts.save(chunk_file)
            chunk_files.append(chunk_file)
            
            progress_percentage = int(((i + 1) / num_chunks) * 90) # Go up to 90%
            progress_bar.progress(progress_percentage)
            status_text.info(f"Generating audio... {progress_percentage}%")

        except Exception as e:
            status_text.error(f"Failed to create audio chunk {i+1}. Error: {e}")
            st.session_state.is_processing = False
            return

    # --- Combine Chunks ---
    status_text.info("Combining audio files...")
    combined_audio = AudioSegment.empty()
    for chunk_file in chunk_files:
        combined_audio += AudioSegment.from_mp3(chunk_file)
    
    # Sanitize title for filename
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    final_filename = f"{safe_title}.mp3"
    combined_audio.export(final_filename, format="mp3")
    st.session_state.final_audio_path = final_filename
    progress_bar.progress(100)

    # --- Cleanup ---
    status_text.info("Cleaning up temporary files...")
    for chunk_file in chunk_files:
        if os.path.exists(chunk_file):
            os.remove(chunk_file)
            
    status_text.success("Audiobook is ready for download!")
    st.session_state.is_processing = False


def voice_search():
    """Captures audio from the microphone and converts it to text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Listening... Speak the book title or author's name.")
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
            st.success("Processing your request...")
            text = r.recognize_google(audio)
            st.session_state.search_query = text
            return text
        except Exception as e:
            st.warning(f"Could not process audio. Please try again. Error: {e}")
            return ""

@st.cache_data
def search_gutenberg_api(query):
    """Searches for books using the Gutendex API."""
    if not query:
        return []
    search_term = requests.utils.quote(query)
    url = f"https://gutendex.com/books?search={search_term}"
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        return []

@st.cache_data
def get_book_text_api(book_id):
    """
    Fetches and cleans the plain text of a book to remove Gutenberg headers/footers.
    """
    url = f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt"
    try:
        response = requests.get(url, verify=False)
        if response.status_code != 200:
             url = f"https://www.gutenberg.org/files/{book_id}/{book_id}.txt"
             response = requests.get(url, verify=False)
        response.raise_for_status()
        text = response.content.decode('utf-8', errors='ignore')
        start_marker = re.search(r'\*\*\*\s*START OF (THIS|THE) PROJECT GUTENBERG EBOOK.*\*\*\*', text, re.IGNORECASE)
        end_marker = re.search(r'\*\*\*\s*END OF (THIS|THE) PROJECT GUTENBERG EBOOK.*\*\*\*', text, re.IGNORECASE)
        if start_marker and end_marker:
            start_pos = start_marker.end()
            end_pos = end_marker.start()
            main_text = text[start_pos:end_pos].strip()
        else:
            main_text = text
        artifacts_pattern = r'\[Note:.*?\]|Note: Project Gutenberg also has an HTML version.*?http://archive\.org/stream/.*?mode/2up'
        cleaned_text = re.sub(artifacts_pattern, '', main_text, flags=re.DOTALL | re.IGNORECASE)
        return cleaned_text.strip()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch book text from Project Gutenberg: {e}")
        return None

# --- 2. STREAMLIT UI AND STATE MANAGEMENT ---

st.set_page_config(page_title="Voice Audiobook Player", layout="wide")
st.title("📖 Voice-Powered Audiobook Downloader")
st.write("Search for a classic book, then create and download it as a single MP3 file.")

# Initialize session state variables
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'selected_book_text' not in st.session_state:
    st.session_state.selected_book_text = ""
if 'selected_book_title' not in st.session_state:
    st.session_state.selected_book_title = ""
if 'is_slow' not in st.session_state:
    st.session_state.is_slow = True
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'final_audio_path' not in st.session_state:
    st.session_state.final_audio_path = None

col1, col2 = st.columns([3, 1])
with col1:
    search_query = st.text_input("Type a book title or author", value=st.session_state.search_query)
    if search_query != st.session_state.search_query:
        st.session_state.search_query = search_query
        st.session_state.selected_book_text = ""
        st.session_state.selected_book_title = ""
        st.session_state.is_processing = False
        st.session_state.final_audio_path = None

with col2:
    st.write("")
    st.write("")
    if st.button("🎤 Use Voice Search"):
        voice_search()
        st.session_state.selected_book_text = ""
        st.session_state.selected_book_title = ""
        st.session_state.is_processing = False
        st.session_state.final_audio_path = None

if st.session_state.search_query and not st.session_state.selected_book_text:
    st.markdown("---")
    st.subheader("Search Results")
    books = search_gutenberg_api(st.session_state.search_query)
    if books:
        for book in books:
            author_names = [author['name'] for author in book.get('authors', [])]
            author_str = ", ".join(author_names) if author_names else "Unknown Author"
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{book.get('title', 'No Title')}** by *{author_str}*")
            with col2:
                if st.button("Select Book", key=f"select_{book['id']}"):
                    with st.spinner(f"Loading '{book.get('title')}'..."):
                        st.session_state.selected_book_text = get_book_text_api(book['id'])
                        st.session_state.selected_book_title = book.get('title')
                        st.session_state.is_processing = False
                        st.session_state.final_audio_path = None
                        st.rerun()
    else:
        st.warning("No books found. Try a different search.")

if st.session_state.selected_book_text:
    st.markdown("---")
    st.header(f"Selected Book: {st.session_state.selected_book_title}")
    
    with st.expander("Show Full Text", expanded=False):
        st.text_area("Book Text", st.session_state.selected_book_text, height=300)

    st.subheader("Download Audiobook")
    
    speed_choice = st.radio(
        "Playback Speed",
        ("Slower", "Normal"),
        index=1,
        horizontal=True,
    )
    st.session_state.is_slow = (speed_choice == "Slower")

    if st.button("Create Audiobook for Download", disabled=st.session_state.is_processing):
        create_and_combine_chunks(
            st.session_state.selected_book_text, 
            st.session_state.is_slow,
            st.session_state.selected_book_title
        )
    
    # Show the download button only when the file is ready
    if st.session_state.final_audio_path:
        with open(st.session_state.final_audio_path, "rb") as file:
            st.download_button(
                label="✅ Download Audiobook (MP3)",
                data=file,
                file_name=st.session_state.final_audio_path,
                mime="audio/mp3"
            )
            
