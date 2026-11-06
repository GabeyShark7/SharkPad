from PySide6.QtCore import QObject, QThread, Signal, Slot


class FreeTeacherSummarizer:
    def __init__(self):
        """
        Uses Groq's free tier.
        """
        self.client = None
        self.token = None
        self.model = "openai/gpt-oss-20b"

    def set_token(self, token):
        token = token.strip()
        if not token.startswith("gsk_"):
            return False
        self.token = token
        self.client = None
        return True

    def _get_client(self):
        if self.client is None and self.token:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.token, base_url="https://api.groq.com/openai/v1")
        return self.client

    def summarize(self, text, **kwargs):
        """Returns (ok, text). On failure, text is a message to show the user."""
        if not self.token:
            return False, "Please enter your Groq API Key in AI Tools > AI Teacher Settings."

        if not text or len(text.strip()) < 10:
            return False, "There isn't enough text for me to explain yet. Write a bit more first!"

        max_sentences = kwargs.get("max_sentences", 5)

        try:
            response = self._get_client().chat.completions.create(
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
            return True, response.choices[0].message.content.strip()

        except Exception as e:
            msg = str(e).lower()
            if "authentication" in msg or "invalid api key" in msg or "401" in msg:
                return False, "Your Groq key was rejected. Check it in AI Tools > AI Teacher Settings."
            if "rate limit" in msg or "429" in msg:
                return False, "Free tier limit reached. Please wait a minute and try again."
            if "connection" in msg or "timed out" in msg or "timeout" in msg:
                return False, "Couldn't reach the AI Teacher. Check your internet connection."
            return False, f"AI Teacher error: {e}"


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


class _ExplainWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, text, max_sentences):
        super().__init__()
        self.text = text
        self.max_sentences = max_sentences

    def run(self):
        ok, result = summarize_text(self.text, max_sentences=self.max_sentences)
        self.done.emit(ok, result)


class _Receiver(QObject):
    """Delivers the result on the UI thread and keeps the worker alive until it ends."""

    def __init__(self, worker, callback):
        super().__init__()
        self.worker = worker
        self.callback = callback

    @Slot(bool, str)
    def receive(self, ok, text):
        self.callback(ok, text)

    @Slot()
    def finished(self):
        _jobs.discard(self)


_jobs = set()


def explain_async(text, callback, max_sentences=5):
    """Explain `text` in the background, then call callback(ok, text) on the UI thread."""
    worker = _ExplainWorker(text, max_sentences)
    receiver = _Receiver(worker, callback)
    worker.done.connect(receiver.receive)
    worker.finished.connect(receiver.finished)
    _jobs.add(receiver)
    worker.start()
    return worker


def is_busy():
    return any(r.worker.isRunning() for r in _jobs)
