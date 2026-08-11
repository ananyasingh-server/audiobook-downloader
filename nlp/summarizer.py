import re
import nltk
from collections import Counter


def summarize_text(text, sentence_count=3):
    """
    Extractive NLP summarizer.

    sentence_count:
        Maximum number of sentences in the summary.
    """

    if not text or not text.strip():
        return ""

    # Split text into sentences
    sentences = nltk.sent_tokenize(text)

    if len(sentences) <= sentence_count:
        return " ".join(sentences)

    # Remove very short sentences
    valid_sentences = [
        sentence.strip()
        for sentence in sentences
        if len(sentence.split()) >= 5
    ]

    if not valid_sentences:
        valid_sentences = sentences

    # Basic stopword removal
    stop_words = set(
        nltk.corpus.stopwords.words("english")
    )

    # Build word frequency table
    words = []

    for sentence in valid_sentences:

        tokens = re.findall(
            r"\b[a-zA-Z]+\b",
            sentence.lower()
        )

        for word in tokens:

            if word not in stop_words and len(word) > 2:
                words.append(word)

    word_frequency = Counter(words)

    if not word_frequency:
        return " ".join(
            valid_sentences[:sentence_count]
        )

    # Normalize frequencies
    max_frequency = max(
        word_frequency.values()
    )

    for word in word_frequency:
        word_frequency[word] /= max_frequency

    # Score each sentence
    sentence_scores = {}

    for index, sentence in enumerate(valid_sentences):

        tokens = re.findall(
            r"\b[a-zA-Z]+\b",
            sentence.lower()
        )

        score = 0

        for word in tokens:

            if word in word_frequency:
                score += word_frequency[word]

        sentence_scores[index] = score

    # Pick highest scoring sentences
    ranked_sentences = sorted(
        sentence_scores,
        key=sentence_scores.get,
        reverse=True
    )

    selected_indexes = ranked_sentences[
        :sentence_count
    ]

    # Restore original order
    selected_indexes.sort()

    summary = [
        valid_sentences[index]
        for index in selected_indexes
    ]

    return " ".join(summary)