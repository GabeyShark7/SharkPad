"""
Free API Summarization for SharkPad
Uses Groq API (OpenAI Compatible) - Fast, Free, and keeps the app tiny.
"""

import os
from openai import OpenAI

class FreeTeacherSummarizer:
    def __init__(self):
        """
        Uses Groq's free tier. 
        It uses the same 'OpenAI' library but points to a free provider.
        """
        self.client = None
        # Llama 3 is a world-class model available for free on Groq
        self.model = "llama-3.3-70b-versatile" 

    def set_token(self, token):
        """Update the client with the user's free Groq key."""
        if token and token.strip():
            self.client = OpenAI(
                api_key=token.strip(),
                base_url="https://api.groq.com/openai/v1" # This makes it free
            )
            return True
        return False

    def summarize(self, text, **kwargs):
        if not self.client:
            return "Please enter your Free API Key in Settings to use the Teacher."

        if not text or len(text.strip()) < 10:
            return "The text box is empty!"

        max_sentences = kwargs.get('max_sentences') or 5

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are a brilliant, kind teacher. "
                            "Explain the main points of the transcript provided. "
                            "Ignore speech-to-text stutters or errors completely. "
                            "Do not mention that the text is messy. "
                            f"Write a clear explanation in about {max_sentences} sentences."
                        )
                    },
                    {"role": "user", "content": text}
                ],
                temperature=0.5,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            if "rate_limit" in str(e).lower():
                return "Free tier limit reached. Please wait a minute and try again."
            return f"API Error: {str(e)}"

# Global instance for main.py
_summarizer = None

def get_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = FreeTeacherSummarizer()
    return _summarizer

def set_api_token(token):
    return get_summarizer().set_token(token)

def summarize_text(text, **kwargs):
    return get_summarizer().summarize(text, **kwargs)