# SharkPad
SharkPad is an open-source, versatile notepad and drawing environment designed for students, teachers, and anyone looking to organize their work efficiently. Whether you're jotting down notes, managing school assignments, sketching ideas, or planning projects, SharkPad combines text editing and drawing in a single intuitive interface.

Features Include

Text Editing: Create, edit, and save notes or documents quickly.

Drawing Tools: Sketch diagrams, illustrations, or annotations directly within your workspace.

Multi-purpose: Perfect for school work, teaching materials, brainstorming, or general productivity.

AI: Capture voice and sounds simultaneously and summarize your text with a click of a button.

Open Source: Fully open-source and customizable, making it easy to adapt to your workflow.

SharkPad aims to be a lightweight, user-friendly tool for organizing your ideas, tasks, and creative work being one app for everything you need to do.


## Download

Prebuilt Windows, macOS, and Linux builds are on [sharkpad.net](https://sharkpad.net) and the [Releases](https://github.com/GabeyShark7/sharkpad/releases) page.

## Built With

- **PySide6 (Qt)**: UI, text editor, and drawing canvas
- **faster-whisper**: local, offline speech-to-text for voice dictation (Whisper `base` model, CPU, int8)
- **SpeechRecognition + PyAudio**: microphone capture
- **NumPy**: audio conversion and silence detection
- **openai** client pointed at **Groq**: AI Teacher summarization (`llama-3.1-8b-instant`)
- **pyspellchecker**: spell checking
- **OpenDyslexic**: optional dyslexia-friendly font

## Run From Source

```bash
git clone https://github.com/GabeyShark7/sharkpad
cd sharkpad
pip install -r requirements.txt
python main.py
```

The AI Teacher needs a free Groq API key (`gsk_...`) from [console.groq.com/keys](https://console.groq.com/keys). Enter it under **AI Tools → AI Teacher Settings**. It's saved locally.

## Build an Executable

```bash
python build.py
```

The standalone app is written to `dist/`. Build on each OS you want to ship for.
