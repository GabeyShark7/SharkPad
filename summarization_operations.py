# AI Teacher summarization for SharkPad.
# Uses Groq's OpenAI-compatible API through the official `openai` client.

from openai import OpenAI


class FreeTeacherSummarizer:
    def __init__(self):
        """
        Uses Groq's free tier.
        """
        self.client = None
        self.model = "llama-3.1-8b-instant"

    def set_token(self, token):
        # Groq keys always start with "gsk_"; reject anything else up front.
        token = token.strip()
        if not token.startswith("gsk_"):
            return False
        self.client = OpenAI(
            api_key=token,
            base_url="https://api.groq.com/openai/v1",
        )
        return True

    def summarize(self, text, **kwargs):
        if not self.client:
            return "Please enter your Groq API Key in Settings."

        if not text or len(text.strip()) < 10:
            return "The text box is too short for me to explain!"

        max_sentences = kwargs.get("max_sentences", 5)

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
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.5,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            msg = str(e).lower()
            if "authentication" in msg or "invalid api key" in msg or "401" in msg:
                return "API Error: Invalid Groq Key. Make sure it starts with 'gsk_'."
            if "rate limit" in msg or "429" in msg:
                return "Free tier limit reached. Please wait a minute and try again."
            return f"API Error: {str(e)}"


# Global instance for main.py
global _summarizer
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
