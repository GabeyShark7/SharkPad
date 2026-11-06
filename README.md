<p align="center">
  <img src="shark_pad_icon.png" alt="SharkPad icon" width="120">
</p>

<h1 align="center">SharkPad</h1>

<p align="center">
  Notes, drawing, and voice dictation in one window. Built for students who need to type, sketch, and listen at the same time.
</p>

<p align="center">
  <a href="https://sharkpad.net"><b>Download at sharkpad.net</b></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/GabeyShark7/sharkpad/releases">Releases</a>
  &nbsp;·&nbsp;
  <a href="#run-from-source">Run from source</a>
</p>

<p align="center">
  <img src="docs/screenshots/dark.png" alt="SharkPad in dark mode with lecture notes and a benzene ring sketch" width="820">
</p>

## Why SharkPad

Some lectures don't fit in a text box. In organic chemistry you're writing notes, drawing structures, and trying to catch what the professor just said, all at once. Most note apps make you switch between tools to do that. SharkPad puts a text editor, a drawing pad, and live voice dictation side by side, so nothing gets missed.

## Features

**Write**
- Fast plain-text editor with spell check
- Adjustable font size, word wrap, and an optional dyslexia-friendly font (OpenDyslexic)
- Notes and drawings save together as a project

**Draw**
- Freehand drawing with a color picker and recent colors
- Upload images, then move, resize, and layer them
- Eraser and clear-all

**Listen**
- Voice dictation that types into your notes as you talk
- Runs locally on your computer with Whisper, so it works offline
- Adjustable microphone sensitivity for quiet or noisy rooms

**Understand**
- **AI Teacher** explains your notes in plain language with one click
- Uses Groq's free API tier, so all you need is a free key

**Make it yours**
- Light, Dark, and Solarized themes, applied to the whole app
- Show or hide keyboard shortcut hints
- Your theme, font size, and API key are remembered between launches

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/light.png" alt="SharkPad in light mode"></td>
    <td width="50%"><img src="docs/screenshots/ai-teacher-setup.png" alt="AI Teacher setup dialog"></td>
  </tr>
  <tr>
    <td align="center">Light mode</td>
    <td align="center">AI Teacher setup</td>
  </tr>
</table>

## Keyboard Shortcuts

| Action | Shortcut |
| --- | --- |
| Open | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Voice dictation on/off | `Ctrl+Shift+V` |
| AI Teacher explain | `Ctrl+Shift+T` |
| Draw mode | `Ctrl+Shift+D` |
| Select mode | `Ctrl+Shift+A` |
| Eraser | `Ctrl+Shift+E` |
| Pick color | `Ctrl+Shift+C` |
| Upload image | `Ctrl+Shift+U` |
| Bring to front / send to back | `Ctrl+Shift+]` / `Ctrl+Shift+[` |
| Forward / backward one layer | `Ctrl+]` / `Ctrl+[` |
| Delete selected image | `Ctrl+Shift+Del` |

## Setting Up the AI Teacher

1. Get a free API key at [console.groq.com/keys](https://console.groq.com/keys). It starts with `gsk_`.
2. In SharkPad, open **AI Tools → AI Teacher Settings** and paste it in.
3. Write or dictate some notes, then press `Ctrl+Shift+T`.

Your key is stored locally on your computer and is only sent to Groq.

## Run From Source

Requires Python 3.12.

```bash
git clone https://github.com/GabeyShark7/sharkpad
cd sharkpad
pip install -r requirements.txt
python main.py
```

On Linux, microphone capture needs PortAudio installed first (`sudo apt install libportaudio2`). Windows and macOS need nothing extra.

The first time you use voice dictation, the Whisper model downloads automatically.

## Build an Executable

```bash
python build.py
```

The standalone app is written to `dist/`. Build on each OS you want to ship for.

## Built With

| Library | Used for |
| --- | --- |
| [PySide6](https://doc.qt.io/qtforpython-6/) (Qt) | The whole interface: editor, drawing canvas, menus, dialogs |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Offline speech-to-text (Whisper `base` model on CPU) |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | Microphone capture |
| [NumPy](https://numpy.org/) | Audio processing and silence detection |
| [openai](https://github.com/openai/openai-python) client with [Groq](https://groq.com/) | AI Teacher (`openai/gpt-oss-20b`) |
| [pyspellchecker](https://github.com/barrust/pyspellchecker) | Spell checking |
| [OpenDyslexic](https://opendyslexic.org/) | Dyslexia-friendly font option |
| [PyInstaller](https://pyinstaller.org/) | Packaging into standalone apps |

## License

SharkPad is released under the [MIT License](LICENSE). The bundled OpenDyslexic fonts are under their own license, the [SIL Open Font License](https://opendyslexic.org/).

## Author

Built by [Gabe Alvarado](https://gabealvarado.org).
