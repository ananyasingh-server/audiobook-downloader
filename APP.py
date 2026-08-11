import streamlit as st
import speech_recognition as sr
import requests
import re
import nltk
from gtts import gTTS
from pydub import AudioSegment
import os
import math

from nlp.translation import translate_text
from nlp.sections import detect_sections
from nlp.summarizer import summarize_text
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate


# ============================================================
# 1. CORE AUDIOBOOK FUNCTIONS
# ============================================================

def create_and_combine_chunks(text, is_slow, title):
    """
    Processes the book into chunks, converts each chunk to speech,
    combines them into a single MP3, and returns the final file path.
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

            tts = gTTS(
                text=chunk_text,
                lang="en",
                slow=is_slow
            )

            chunk_file = f"chunk_{i}.mp3"

            tts.save(chunk_file)

            chunk_files.append(chunk_file)

            progress_percentage = int(
                ((i + 1) / num_chunks) * 90
            )

            progress_bar.progress(progress_percentage)

            status_text.info(
                f"Generating audio... {progress_percentage}%"
            )

        except Exception as e:

            status_text.error(
                f"Failed to create audio chunk {i + 1}. Error: {e}"
            )

            st.session_state.is_processing = False
            return

    # --------------------------------------------------------
    # Combine audio chunks
    # --------------------------------------------------------

    status_text.info("Combining audio files...")

    combined_audio = AudioSegment.empty()

    for chunk_file in chunk_files:
        combined_audio += AudioSegment.from_mp3(chunk_file)

    # --------------------------------------------------------
    # Create safe filename
    # --------------------------------------------------------

    safe_title = re.sub(
        r'[\\/*?:"<>|]',
        "",
        title
    )

    final_filename = f"{safe_title}.mp3"

    combined_audio.export(
        final_filename,
        format="mp3"
    )

    st.session_state.final_audio_path = final_filename

    progress_bar.progress(100)

    # --------------------------------------------------------
    # Cleanup temporary files
    # --------------------------------------------------------

    status_text.info("Cleaning up temporary files...")

    for chunk_file in chunk_files:

        if os.path.exists(chunk_file):
            os.remove(chunk_file)

    status_text.success(
        "Audiobook is ready for download!"
    )

    st.session_state.is_processing = False


# ============================================================
# 2. HINDI AUDIO
# ============================================================

def create_hindi_audio(text, title):
    """
    Converts Hindi text into an MP3 using gTTS.
    """

    if not text or not text.strip():
        return None

    safe_title = re.sub(
        r'[\\/*?:"<>|]',
        "",
        title
    )

    filename = f"{safe_title}_Hindi_Summary.mp3"

    try:

        tts = gTTS(
            text=text,
            lang="hi",
            slow=False
        )

        tts.save(filename)

        return filename

    except Exception as e:

        st.error(
            f"Could not create Hindi audio: {e}"
        )

        return None


# ============================================================
# 3. HINGLISH CONVERSION
# ============================================================

def convert_to_hinglish(hindi_text):
    """
    Converts Hindi Devanagari text into Roman Hindi.

    Example:

    शरलॉक होम्स एक रहस्यमय मामले की जांच करता है।

    becomes approximately:

    sharlok homes ek rahasyamay maamle ki jaanch karta hai.
    """

    if not hindi_text:
        return ""

    try:

        hinglish = transliterate(
            hindi_text,
            sanscript.DEVANAGARI,
            sanscript.ITRANS
        )

        return hinglish

    except Exception as e:

        st.error(
            f"Could not generate Hinglish: {e}"
        )

        return ""


# ============================================================
# 4. VOICE SEARCH
# ============================================================

def voice_search():
    """
    Captures audio from the microphone and converts it to text.

    Voice search is kept in English because the Gutenberg
    catalogue is searched using the original book metadata.
    """

    r = sr.Recognizer()

    try:

        with sr.Microphone() as source:

            st.info(
                "Listening... Speak the book title or author's name."
            )

            r.adjust_for_ambient_noise(source)

            try:

                audio = r.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=5
                )

                st.success(
                    "Processing your request..."
                )

                text = r.recognize_google(
                    audio,
                    language="en-IN"
                )

                st.session_state.search_query = text

                return text

            except Exception as e:

                st.warning(
                    f"Could not process audio. "
                    f"Please try again. Error: {e}"
                )

                return ""

    except AttributeError:

        st.error(
            "Microphone support is unavailable because "
            "PyAudio is not installed correctly."
        )

        return ""

    except Exception as e:

        st.error(
            f"Could not access the microphone: {e}"
        )

        return ""


# ============================================================
# 5. GUTENBERG SEARCH
# ============================================================

@st.cache_data
def search_gutenberg_api(query):
    """
    Searches the Project Gutenberg library using Gutendex.
    """

    if not query:
        return []

    search_term = requests.utils.quote(query)

    url = (
        f"https://gutendex.com/books"
        f"?search={search_term}"
    )

    try:

        response = requests.get(
            url,
            verify=False,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        return data.get("results", [])

    except requests.exceptions.RequestException as e:

        st.error(
            f"API request failed: {e}"
        )

        return []


# ============================================================
# 6. GET BOOK TEXT
# ============================================================

@st.cache_data
def get_book_text_api(book_id):
    """
    Fetches and cleans the plain text of a Project Gutenberg book.
    """

    url = (
        f"https://www.gutenberg.org/files/"
        f"{book_id}/{book_id}-0.txt"
    )

    try:

        response = requests.get(
            url,
            verify=False,
            timeout=60
        )

        # Some Gutenberg books use a different URL
        if response.status_code != 200:

            url = (
                f"https://www.gutenberg.org/files/"
                f"{book_id}/{book_id}.txt"
            )

            response = requests.get(
                url,
                verify=False,
                timeout=60
            )

        response.raise_for_status()

        text = response.content.decode(
            "utf-8",
            errors="ignore"
        )

        # ----------------------------------------------------
        # Remove Gutenberg header and footer
        # ----------------------------------------------------

        start_marker = re.search(
            r"\*\*\*\s*START OF (THIS|THE) PROJECT GUTENBERG EBOOK.*?\*\*\*",
            text,
            re.IGNORECASE
        )

        end_marker = re.search(
            r"\*\*\*\s*END OF (THIS|THE) PROJECT GUTENBERG EBOOK.*?\*\*\*",
            text,
            re.IGNORECASE
        )

        if start_marker and end_marker:

            start_pos = start_marker.end()
            end_pos = end_marker.start()

            main_text = text[
                start_pos:end_pos
            ].strip()

        else:

            main_text = text

        # ----------------------------------------------------
        # Remove Gutenberg artifacts
        # ----------------------------------------------------

        artifacts_pattern = (
            r"\[Note:.*?\]"
            r"|Note: Project Gutenberg also has an HTML version.*?"
            r"http://archive\.org/stream/.*?mode/2up"
        )

        cleaned_text = re.sub(
            artifacts_pattern,
            "",
            main_text,
            flags=re.DOTALL | re.IGNORECASE
        )

        return cleaned_text.strip()

    except requests.exceptions.RequestException as e:

        st.error(
            f"Failed to fetch book text "
            f"from Project Gutenberg: {e}"
        )

        return None


# ============================================================
# 7. STREAMLIT PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Voice Audiobook & NLP",
    layout="wide"
)

st.title(
    "📖 Voice-Powered Audiobook & NLP Analyzer"
)

st.write(
    "Search for a classic book, analyze its chapters, "
    "generate summaries, translate them into Hindi or "
    "Hinglish, and create audio."
)


# ============================================================
# 8. SESSION STATE
# ============================================================

if "search_query" not in st.session_state:
    st.session_state.search_query = ""

if "selected_book_text" not in st.session_state:
    st.session_state.selected_book_text = ""

if "selected_book_title" not in st.session_state:
    st.session_state.selected_book_title = ""

if "selected_section_text" not in st.session_state:
    st.session_state.selected_section_text = ""

if "generated_summary" not in st.session_state:
    st.session_state.generated_summary = ""

if "translated_summary" not in st.session_state:
    st.session_state.translated_summary = ""

if "hindi_audio_path" not in st.session_state:
    st.session_state.hindi_audio_path = None

if "is_slow" not in st.session_state:
    st.session_state.is_slow = True

if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if "final_audio_path" not in st.session_state:
    st.session_state.final_audio_path = None


# ============================================================
# 9. SEARCH INTERFACE
# ============================================================

st.subheader("🔎 Discover a Book")

col1, col2 = st.columns([3, 1])


with col1:

    search_query = st.text_input(
        "Type a book title or author",
        value=st.session_state.search_query
    )

    if search_query != st.session_state.search_query:

        st.session_state.search_query = search_query

        st.session_state.selected_book_text = ""
        st.session_state.selected_book_title = ""
        st.session_state.selected_section_text = ""
        st.session_state.generated_summary = ""
        st.session_state.translated_summary = ""
        st.session_state.hindi_audio_path = None
        st.session_state.final_audio_path = None
        st.session_state.is_processing = False


with col2:

    st.write("")
    st.write("")

    if st.button("🎤 Voice Search"):

        voice_search()

        st.session_state.selected_book_text = ""
        st.session_state.selected_book_title = ""
        st.session_state.selected_section_text = ""
        st.session_state.generated_summary = ""
        st.session_state.translated_summary = ""
        st.session_state.hindi_audio_path = None
        st.session_state.final_audio_path = None
        st.session_state.is_processing = False


# ============================================================
# 10. SEARCH RESULTS
# ============================================================

if (
    st.session_state.search_query
    and not st.session_state.selected_book_text
):

    st.markdown("---")

    st.subheader("📚 Search Results")

    books = search_gutenberg_api(
        st.session_state.search_query
    )

    if books:

        for book in books:

            author_names = [
                author["name"]
                for author in book.get("authors", [])
            ]

            author_str = (
                ", ".join(author_names)
                if author_names
                else "Unknown Author"
            )

            col1, col2 = st.columns([4, 1])

            with col1:

                st.write(
                    f"**{book.get('title', 'No Title')}** "
                    f"by *{author_str}*"
                )

            with col2:

                if st.button(
                    "Select Book",
                    key=f"select_{book['id']}"
                ):

                    with st.spinner(
                        f"Loading '{book.get('title')}'..."
                    ):

                        book_text = get_book_text_api(
                            book["id"]
                        )

                        if book_text:

                            st.session_state.selected_book_text = (
                                book_text
                            )

                            st.session_state.selected_book_title = (
                                book.get("title")
                            )

                            st.session_state.selected_section_text = ""
                            st.session_state.generated_summary = ""
                            st.session_state.translated_summary = ""
                            st.session_state.hindi_audio_path = None
                            st.session_state.final_audio_path = None
                            st.session_state.is_processing = False

                            st.rerun()

                        else:

                            st.error(
                                "Could not retrieve the book text."
                            )

    else:

        st.warning(
            "No books found. Try a different search."
        )


# ============================================================
# 11. BOOK ANALYSIS
# ============================================================

if st.session_state.selected_book_text:

    st.markdown("---")

    st.header(
        f"📖 {st.session_state.selected_book_title}"
    )

    # ========================================================
    # CHAPTER / SECTION DETECTION
    # ========================================================

    sections = detect_sections(
        st.session_state.selected_book_text
    )

    st.subheader(
        "📑 Book Sections"
    )

    if not sections:

        st.warning(
            "No chapters or sections were detected. "
            "The complete book will be treated as one section."
        )

        sections = [
            {
                "title": "Complete Book",
                "text": st.session_state.selected_book_text
            }
        ]

    section_titles = [
        section["title"]
        for section in sections
    ]

    selected_section_title = st.selectbox(
        "Select a chapter or section",
        section_titles
    )

    selected_section = next(
        section
        for section in sections
        if section["title"] == selected_section_title
    )

    # Clear previous results if chapter changes

    if (
        st.session_state.selected_section_text
        != selected_section["text"]
    ):

        st.session_state.generated_summary = ""
        st.session_state.translated_summary = ""
        st.session_state.hindi_audio_path = None

    st.session_state.selected_section_text = (
        selected_section["text"]
    )

    # ========================================================
    # SELECTED SECTION TEXT
    # ========================================================

    with st.expander(
        "📖 Show Selected Section",
        expanded=False
    ):

        st.text_area(
            "Section Text",
            selected_section["text"],
            height=300
        )

    # ========================================================
    # SUMMARIZATION
    # ========================================================

    st.markdown("---")

    st.subheader(
        "✨ Chapter Summary"
    )

    col1, col2 = st.columns(2)

    with col1:

        summary_length = st.radio(
            "Summary Length",
            [
                "Short",
                "Medium",
                "Detailed"
            ],
            horizontal=True
        )

    with col2:

        summary_language = st.radio(
            "Summary Language",
            [
                "English",
                "Hindi",
                "Hinglish"
            ],
            horizontal=True
        )

    if summary_length == "Short":

        summary_sentences = 3

    elif summary_length == "Medium":

        summary_sentences = 5

    else:

        summary_sentences = 8

    # ========================================================
    # GENERATE SUMMARY
    # ========================================================

    if st.button(
        "✨ Generate Summary",
        type="primary"
    ):

        with st.spinner(
            "Analyzing chapter and generating summary..."
        ):

            # -----------------------------------------------
            # English NLP summary
            # -----------------------------------------------

            summary = summarize_text(
                st.session_state.selected_section_text,
                summary_sentences
            )

            st.session_state.generated_summary = summary

            # Clear old translated result

            st.session_state.translated_summary = ""
            st.session_state.hindi_audio_path = None

            # -----------------------------------------------
            # Hindi
            # -----------------------------------------------

            if summary_language == "Hindi":

                with st.spinner(
                    "Translating summary into Hindi..."
                ):

                    try:

                        translated = translate_text(
                            summary,
                            "hi"
                        )

                        st.session_state.translated_summary = (
                            translated
                        )

                    except Exception as e:

                        st.error(
                            f"Hindi translation failed: {e}"
                        )

            # -----------------------------------------------
            # Hinglish
            # -----------------------------------------------

            elif summary_language == "Hinglish":

                with st.spinner(
                    "Generating Hinglish summary..."
                ):

                    try:

                        hindi_text = translate_text(
                            summary,
                            "hi"
                        )

                        hinglish_text = convert_to_hinglish(
                            hindi_text
                        )

                        st.session_state.translated_summary = (
                            hinglish_text
                        )

                    except Exception as e:

                        st.error(
                            f"Hinglish generation failed: {e}"
                        )

    # ========================================================
    # DISPLAY SUMMARY
    # ========================================================

    if st.session_state.generated_summary:

        st.markdown("---")

        if summary_language == "English":

            st.markdown(
                "### 🇬🇧 English Summary"
            )

            st.write(
                st.session_state.generated_summary
            )

        elif summary_language == "Hindi":

            if st.session_state.translated_summary:

                st.markdown(
                    "### 🇮🇳 Hindi Summary"
                )

                st.write(
                    st.session_state.translated_summary
                )

        elif summary_language == "Hinglish":

            if st.session_state.translated_summary:

                st.markdown(
                    "### 🇮🇳 Hinglish Summary"
                )

                st.write(
                    st.session_state.translated_summary
                )

    # ========================================================
    # HINDI AUDIO
    # ========================================================

    if (
        st.session_state.translated_summary
        and summary_language in ["Hindi", "Hinglish"]
    ):

        st.markdown("---")

        st.subheader(
            "🔊 Listen to Summary"
        )

        if summary_language == "Hindi":

            hindi_text_for_audio = (
                st.session_state.translated_summary
            )

        else:

            # For Hinglish, use the Hindi version for
            # natural Hindi speech.

            try:

                hindi_text_for_audio = translate_text(
                    st.session_state.generated_summary,
                    "hi"
                )

            except Exception:

                hindi_text_for_audio = ""

        if st.button(
            "🔊 Generate Hindi Audio"
        ):

            with st.spinner(
                "Creating Hindi audio..."
            ):

                audio_path = create_hindi_audio(
                    hindi_text_for_audio,
                    st.session_state.selected_book_title
                )

                if audio_path:

                    st.session_state.hindi_audio_path = (
                        audio_path
                    )

                    st.success(
                        "Hindi audio is ready!"
                    )

        if st.session_state.hindi_audio_path:

            with open(
                st.session_state.hindi_audio_path,
                "rb"
            ) as audio_file:

                st.audio(
                    audio_file,
                    format="audio/mp3"
                )

                st.download_button(
                    label="⬇️ Download Hindi Summary Audio",
                    data=audio_file,
                    file_name=(
                        st.session_state.hindi_audio_path
                    ),
                    mime="audio/mp3"
                )

    # ========================================================
    # FULL BOOK TEXT
    # ========================================================

    st.markdown("---")

    with st.expander(
        "📚 Show Full Book Text",
        expanded=False
    ):

        st.text_area(
            "Book Text",
            st.session_state.selected_book_text,
            height=300
        )

    # ========================================================
    # EXISTING FULL AUDIOBOOK FUNCTIONALITY
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🔊 Full English Audiobook"
    )

    speed_choice = st.radio(
        "Playback Speed",
        (
            "Slower",
            "Normal"
        ),
        index=1,
        horizontal=True
    )

    st.session_state.is_slow = (
        speed_choice == "Slower"
    )

    if st.button(
        "🚀 Create Audiobook for Download",
        disabled=st.session_state.is_processing
    ):

        create_and_combine_chunks(
            st.session_state.selected_book_text,
            st.session_state.is_slow,
            st.session_state.selected_book_title
        )

    # ========================================================
    # DOWNLOAD FULL AUDIOBOOK
    # ========================================================

    if st.session_state.final_audio_path:

        with open(
            st.session_state.final_audio_path,
            "rb"
        ) as file:

            st.download_button(
                label="✅ Download Audiobook (MP3)",
                data=file,
                file_name=st.session_state.final_audio_path,
                mime="audio/mp3"
            )