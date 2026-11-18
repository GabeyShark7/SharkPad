from PySide6.QtCore import QObject, QThread, Signal, Slot

MODEL = "openai/gpt-oss-20b"
MAX_SENTENCES = 5

EXPLAIN_TASK = (
    "You are a brilliant, kind teacher inside of SharkPad, a student's notepad. "
    "Explain the main points of the transcript provided. "
    "Ignore speech-to-text stutters or errors completely. "
    "Do not mention that the text is messy. "
    f"Write a clear explanation in about {MAX_SENTENCES} sentences. "
    "Use simple words a student understands, and give a short example when it helps. "
    "Only use facts you are sure of. If something in the notes looks wrong, gently point it out."
)

INSTRUCT_TASK = (
    "You are the AI Teacher inside SharkPad, a student's notepad. "
    "The student wrote an instruction and marked a part of their notes for you to work on. "
    "Follow the instruction exactly and completely, including any exact counts, lengths or formats it asks for. "
    "If no text was marked, write new text that follows the instruction. "
    "Reply with only the finished text that will replace the marked part. "
    "Do not add an introduction, a closing remark, quotes around the text, or notes about what you changed."
)

ASK_TASK = (
    "You are the AI Teacher inside SharkPad, a student's notepad. "
    "The student highlighted part of their notes and asked a question about it. "
    "Answer the question directly, using the highlighted notes as context. "
    "Keep it to a few clear sentences unless the question needs more. "
    "Do not repeat the question, and do not add an introduction."
)

PLAIN_TEXT_RULE = (
    "Your reply goes straight into a plain text notepad, so never use Markdown: "
    "no #, **, backticks or tables. Use plain sentences, and simple dashes for lists. "
    "Reply in the same language as the student's notes."
)

_token = None
_client = None
_preset = ""


def set_api_token(token):
    global _token, _client
    token = token.strip()
    if token.startswith("gsk_"):
        _token = token
        _client = None


def set_preset(text):
    global _preset
    _preset = (text or "").strip()


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=_token, base_url="https://api.groq.com/openai/v1")
    return _client


def _system_prompt(task):
    parts = [task, PLAIN_TEXT_RULE]
    if _preset:
        parts.append("The student set these rules for how you act. Always follow them:\n" + _preset)
    return "\n\n".join(parts)


def _ask(task, user_text):
    if not _token:
        return False, "Please enter your Groq API Key in AI Tools > AI Teacher Settings."
    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _system_prompt(task)},
                {"role": "user", "content": user_text},
            ],
            temperature=0.5,
        )
        return True, (response.choices[0].message.content or "").strip()

    except Exception as e:
        msg = str(e).lower()
        if "authentication" in msg or "invalid api key" in msg or "401" in msg:
            return False, "Your Groq key was rejected. Check it in AI Tools > AI Teacher Settings."
        if "rate limit" in msg or "429" in msg:
            return False, "Free tier limit reached. Please wait a minute and try again."
        if "connection" in msg or "timed out" in msg or "timeout" in msg:
            return False, "Couldn't reach the AI Teacher. Check your internet connection."
        return False, f"AI Teacher error: {e}"


def explain(text):
    """Returns (ok, text). On failure, text is a message to show the user."""
    if not text or len(text.strip()) < 10:
        return False, "There isn't enough text for me to explain yet. Write a bit more first!"
    return _ask(EXPLAIN_TASK, text)


def follow_instruction(instruction, text):
    if not instruction.strip():
        return False, "One of your AI-INSTRUCT blocks is empty. Write what you want inside the { }."
    marked = text if text.strip() else "(nothing marked, write new text)"
    return _ask(INSTRUCT_TASK, f"Instruction:\n{instruction.strip()}\n\nMarked text:\n{marked}")


def answer_question(question, notes):
    if not question.strip():
        return False, "Type a question first."
    return _ask(ASK_TASK, f"Highlighted notes:\n{notes.strip()}\n\nQuestion:\n{question.strip()}")


def follow_all(blocks):
    results = []
    for block in blocks:
        ok, result = follow_instruction(block.instruction, block.body)
        if not ok:
            return False, result
        results.append(result)
    return True, results


class _Worker(QThread):
    done = Signal(bool, object)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        self.done.emit(*self.job())


class _Receiver(QObject):
    """Delivers the result on the UI thread and keeps the worker alive until it ends."""

    def __init__(self, worker, callback):
        super().__init__()
        self.worker = worker
        self.callback = callback

    @Slot(bool, object)
    def receive(self, ok, result):
        self.callback(ok, result)

    @Slot()
    def finished(self):
        _jobs.discard(self)


_jobs = set()


def run_async(job, callback):
    """Run job() in the background, then call callback(ok, result) on the UI thread."""
    worker = _Worker(job)
    receiver = _Receiver(worker, callback)
    worker.done.connect(receiver.receive)
    worker.finished.connect(receiver.finished)
    _jobs.add(receiver)
    worker.start()


def is_busy():
    return any(r.worker.isRunning() for r in _jobs)
