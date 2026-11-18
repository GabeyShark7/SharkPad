import html

SHORTCUT_GROUPS = [
    ("Files", [("Ctrl+N", "New note"), ("Ctrl+O", "Open a note"), ("Ctrl+S", "Save"),
               ("Ctrl+Shift+S", "Save As"), ("Ctrl+P", "Print"), ("Ctrl+Q", "Exit")]),
    ("Editing", [("Ctrl+Z", "Undo (text, or drawing when the pad is clicked)"),
                 ("Ctrl+Y or Ctrl+Shift+Z", "Redo"), ("Ctrl+X / Ctrl+C / Ctrl+V", "Cut / Copy / Paste"),
                 ("Ctrl+A", "Select all"), ("Ctrl+F", "Find"), ("F3 / Shift+F3", "Next / previous match"),
                 ("Ctrl+H", "Replace"), ("Ctrl+D", "Duplicate line"), ("Alt+Up / Alt+Down", "Move line up / down"),
                 ("F5", "Insert date and time")]),
    ("View", [("Ctrl+= / Ctrl+-", "Bigger / smaller text"), ("Ctrl + mouse wheel", "Bigger / smaller text"),
              ("Ctrl+0", "Reset text size"), ("F11", "Focus Mode (full screen)")]),
    ("Accessibility", [("Ctrl+Shift+R", "Read aloud / stop reading"), ("Esc", "Stop reading, close find, or leave Focus Mode")]),
    ("AI Tools", [("Ctrl+Shift+V", "Voice dictation on / off"), ("Ctrl+Shift+T", "AI Teacher explain (or follow AI-INSTRUCT blocks)"),
                  ("Ctrl+Shift+I", "Insert an AI instruction block"),
                  ("Ctrl+Shift+Q", "Ask the AI Teacher about the highlighted text")]),
    ("Drawing Pad tools", [("Ctrl+Shift+A  or  V", "Select"), ("Ctrl+Shift+D  or  P", "Pen"),
                           ("Ctrl+Shift+H  or  H", "Highlighter"), ("Ctrl+Shift+E  or  E", "Eraser"),
                           ("Ctrl+Shift+X  or  T", "Text"), ("Ctrl+Shift+U", "Add an image"),
                           ("Ctrl+Shift+C", "Pick a color")]),
    ("Drawing Pad selection (click the pad first)", [
        ("Drag on empty space", "Select everything inside the box"), ("Shift+click", "Add or remove from selection"),
        ("Ctrl+A", "Select everything"), ("Arrow keys / Shift+arrows", "Nudge 1 / 10 pixels"),
        ("Delete or Backspace", "Delete the selection"), ("Ctrl+C / Ctrl+X / Ctrl+V", "Copy / cut / paste"),
        ("Ctrl+D", "Duplicate"), ("Ctrl+Shift+] / Ctrl+Shift+[", "To front / to back"),
        ("Ctrl+] / Ctrl+[", "Forward / backward one layer"), ("Double-click text", "Edit the text")]),
    ("Help", [("F1", "Keyboard shortcuts")]),
]


def shortcuts_html(groups):
    """groups: [(group title, [(keys, description), ...]), ...]"""
    parts = ["<h2>Keyboard Shortcuts</h2>",
             "<p>On a Mac, use <b>Cmd</b> wherever this says <b>Ctrl</b>.</p>"]
    for title, rows in groups:
        parts.append(f"<h3>{html.escape(title)}</h3><table cellspacing='0' cellpadding='4' width='100%'>")
        for keys, desc in rows:
            parts.append(f"<tr><td width='42%'><b>{html.escape(keys)}</b></td><td>{html.escape(desc)}</td></tr>")
        parts.append("</table>")
    return "".join(parts)


GETTING_STARTED_HTML = """
<h2>Welcome to SharkPad</h2>
<p>SharkPad puts your notes, a drawing pad, and voice dictation in one window.</p>
<h3>Write</h3>
<ul>
<li>Type in the big box on the left. Obvious typos like "teh" fix themselves when you finish the word, and the fix flashes red for a moment. Press <b>Ctrl+Z</b> right away to keep what you typed.</li>
<li>Words SharkPad isn't sure about get a red wavy line; right-click one for suggestions. Turn either off in the <b>Edit</b> menu.</li>
<li>Made a mistake? <b>Ctrl+Z</b> undoes it and <b>Ctrl+Y</b> or <b>Ctrl+Shift+Z</b> brings it back.</li>
<li><b>Ctrl+F</b> finds words and <b>Ctrl+H</b> replaces them.</li>
<li><b>F5</b> stamps today's date and time, handy at the top of lecture notes.</li>
</ul>
<h3>Draw</h3>
<ul>
<li>Pick a tool on the drawing pad's toolbar: <b>Pen</b>, <b>Highlighter</b>, <b>Eraser</b>, <b>Text</b> or <b>Select</b>.
With the pad clicked, the keys <b>P</b>, <b>H</b>, <b>E</b>, <b>T</b> and <b>V</b> switch tools too.</li>
<li><b>Text:</b> click anywhere on the pad and type. Click away or press <b>Esc</b> when done. Double-click text to change it.</li>
<li><b>Select:</b> drag a box around things to select them, or Shift+click to add more. Drag to move, pull a corner to resize,
and use the arrow keys to nudge. <b>Delete</b> removes, <b>Ctrl+C</b>/<b>Ctrl+V</b> copy and paste, <b>Ctrl+D</b> duplicates.</li>
<li>Pick a color or size while something is selected to change it.</li>
<li>Click the pad first, then <b>Ctrl+Z</b> undoes and <b>Ctrl+Y</b> redoes.</li>
<li>The first time you press <b>Ctrl+S</b>, type a name. SharkPad makes a folder with that name and saves <b>Name_notes.txt</b> and, if you drew something, <b>Name_img.png</b> inside it.</li>
<li>Pick other file types (like .md notes or .jpg drawings) in <b>Preferences &gt; Save File Types</b>.</li>
</ul>
<h3>Listen</h3>
<ul>
<li>Press <b>Ctrl+Shift+V</b> and talk. SharkPad types what you say. Press it again to stop.</li>
<li>If it doesn't hear you, open <b>AI Tools &gt; Voice Dictation Settings</b> and use the live meter.</li>
</ul>
<h3>Learn</h3>
<ul>
<li><b>Ctrl+Shift+T</b> asks the AI Teacher to explain your notes (or just the part you selected).</li>
<li>Changed your mind? <b>Ctrl+Z</b> or <b>Restore original text</b> brings your notes back.</li>
<li>Want something specific? Put <b>AI-INSTRUCT{$your instruction$};</b> above the part you want changed and
<b>AI-INSTRUCT{END};</b> after it (or press <b>Ctrl+Shift+I</b>). The block glows red. Press <b>Ctrl+Shift+T</b> and the
AI Teacher rewrites just that part the way you asked.</li>
<li>Got a question? Highlight some notes, right-click and pick <b>Ask a Question</b> (or press <b>Ctrl+Shift+Q</b>).
The question and answer show up below that part, glowing blue.</li>
<li>In <b>AI Tools &gt; AI Teacher Settings</b>, the <b>Teacher Preset</b> box tells the AI Teacher how to act every time.</li>
<li><b>Ctrl+Shift+R</b> reads your notes out loud and highlights each word as it's spoken.</li>
</ul>
<h3>Never lose work</h3>
<ul>
<li>Tick <b>Autosave</b> in the top-right of the notes or the drawing pad to save every change automatically.</li>
<li>SharkPad also keeps a backup of unsaved notes every 30 seconds. If it closes unexpectedly,
it offers to bring them back next time.</li>
</ul>
"""

ACCESSIBILITY_HTML = """
<h2>Accessibility Features</h2>
<p>Everything here is in the <b>Accessibility</b> menu, and your choices are remembered.</p>
<h3>Reading</h3>
<ul>
<li><b>Read Aloud (Ctrl+Shift+R)</b> reads the selected text, or everything from the current paragraph.
The word being spoken is highlighted so you can follow along. Press it again or <b>Esc</b> to stop.</li>
<li><b>Reading Speed</b> and <b>Voice</b> change how it sounds.</li>
<li><b>Reading Guide</b> tints the line you're on, like a ruler under the line.</li>
</ul>
<h3>Seeing the text</h3>
<ul>
<li><b>Dyslexia Font</b> switches to OpenDyslexic, a font with weighted letter bottoms.</li>
<li><b>Text Spacing</b> adds space between letters and words, which helps many readers.</li>
<li><b>Ctrl+=</b> and <b>Ctrl+-</b> (or Ctrl + mouse wheel) make text bigger or smaller. <b>Ctrl+0</b> resets it.</li>
<li><b>Preferences &gt; Color Scheme</b> has <b>High Contrast</b> (white on black) and <b>Cream</b> (low glare).</li>
<li><b>Thick Text Cursor</b> makes the blinking cursor easier to spot.</li>
</ul>
<h3>Focus</h3>
<ul>
<li><b>Focus Mode (F11)</b> goes full screen and hides the drawing pad. Press F11 or Esc to leave.</li>
</ul>
<h3>Keyboard and screen readers</h3>
<ul>
<li>Every feature has a menu item, and most have a shortcut (see <b>Help &gt; Keyboard Shortcuts</b>).</li>
<li>Press <b>Alt</b> to reach the menus from the keyboard.</li>
<li>Controls are labeled for screen readers such as NVDA, JAWS, Narrator and VoiceOver.</li>
</ul>
"""

DICTATION_HELP_HTML = """
<h2>Voice Dictation Help</h2>
<h3>Getting started</h3>
<ol>
<li>Open <b>AI Tools &gt; Voice Dictation Settings</b>.</li>
<li>Pick your microphone, then talk normally. The bar should turn green and pass the dashed line.</li>
<li>If it doesn't, click a room preset or drag <b>Sensitivity</b> toward <b>High</b>.</li>
<li>Close the window and press <b>Ctrl+Shift+V</b>. Talk, then pause briefly: your words appear after each pause.</li>
</ol>
<h3>Speed or accuracy</h3>
<p>In the settings, <b>Fast</b> suits older computers, <b>Balanced</b> suits most, and <b>Accurate</b> makes the
fewest mistakes but needs a quick computer. Each model downloads once the first time you use it.</p>
<h3>Nothing is typed</h3>
<ul>
<li>Check the status bar at the bottom of the window for messages.</li>
<li><b>Windows:</b> Settings &gt; Privacy &amp; security &gt; Microphone: allow desktop apps.</li>
<li><b>Mac:</b> System Settings &gt; Privacy &amp; Security &gt; Microphone: allow SharkPad.</li>
<li><b>Linux:</b> install PortAudio with <code>sudo apt install libportaudio2</code>.</li>
</ul>
<p>Speech recognition runs on your own computer. Your voice is never uploaded.</p>
"""

ABOUT_HTML = """
<h2>SharkPad</h2>
<p>Notes, drawing, and voice dictation in one window. Built for students who need to type,
sketch, and listen at the same time.</p>
<p>Speech recognition by Whisper (runs offline). AI Teacher by Groq.
Dyslexia font: OpenDyslexic.</p>
<p><a href="https://github.com/GabeyShark7/SharkPad">github.com/GabeyShark7/SharkPad</a></p>
"""
