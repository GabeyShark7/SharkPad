import html
import os
import re

from PySide6.QtGui import QImageWriter, QTextDocument

NOTES_SUFFIX = "_notes"
IMAGE_SUFFIX = "_img"
NOTE_EXTENSIONS = [".txt", ".md", ".html"]
_IMAGE_CANDIDATES = [".png", ".jpg", ".bmp", ".webp", ".tiff"]
_LEGACY_IMAGE_SUFFIX = "_drawing"
_BAD_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PRE_BLOCK = re.compile(r'<pre style="white-space: pre-wrap; font-family: sans-serif;">(.*?)</pre>', re.S)


def image_extensions():
    writable = {bytes(f).decode().lower() for f in QImageWriter.supportedImageFormats()}
    return [e for e in _IMAGE_CANDIDATES if e[1:] in writable]


def clean_name(raw):
    name = os.path.basename(raw.strip())
    stem, ext = os.path.splitext(name)
    if ext.lower() in NOTE_EXTENSIONS + _IMAGE_CANDIDATES + [".pdf"]:
        name = stem
    for suffix in (NOTES_SUFFIX, IMAGE_SUFFIX):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    name = _BAD_NAME_CHARS.sub("", name).strip(" .")
    return name or "My Notes"


def project_from_choice(chosen_path):
    parent = os.path.dirname(chosen_path)
    name = clean_name(chosen_path)
    if os.path.basename(os.path.normpath(parent)) == name:
        return parent, name
    return os.path.join(parent, name), name


def is_project_notes(path):
    stem, ext = os.path.splitext(os.path.basename(path))
    return ext.lower() in NOTE_EXTENSIONS and stem.endswith(NOTES_SUFFIX)


def split_project(notes_path):
    stem = os.path.splitext(os.path.basename(notes_path))[0]
    if stem.endswith(NOTES_SUFFIX):
        stem = stem[: -len(NOTES_SUFFIX)]
    return os.path.dirname(notes_path), stem


def notes_path(folder, name, ext):
    return os.path.join(folder, f"{name}{NOTES_SUFFIX}{ext}")


def image_path(folder, name, ext):
    return os.path.join(folder, f"{name}{IMAGE_SUFFIX}{ext}")


def existing_files(folder, name):
    paths = [notes_path(folder, name, e) for e in NOTE_EXTENSIONS]
    paths += [image_path(folder, name, e) for e in _IMAGE_CANDIDATES]
    return [p for p in paths if os.path.exists(p)]


def find_image(notes_file):
    folder, name = split_project(notes_file)
    for ext in _IMAGE_CANDIDATES:
        p = image_path(folder, name, ext)
        if os.path.exists(p):
            return p
    legacy = os.path.join(folder, f"{os.path.splitext(os.path.basename(notes_file))[0]}{_LEGACY_IMAGE_SUFFIX}.png")
    return legacy if os.path.exists(legacy) else None


def remove_other_versions(folder, name, keep, images=False):
    exts = _IMAGE_CANDIDATES if images else NOTE_EXTENSIONS
    make = image_path if images else notes_path
    for ext in exts:
        p = make(folder, name, ext)
        if os.path.normcase(p) != os.path.normcase(keep or "") and os.path.exists(p):
            os.remove(p)


def _temp_path(path):
    folder, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    return os.path.join(folder, f".{stem}.saving{ext}")


def notes_to_file(text, ext, title):
    if ext == ".html":
        return ("<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
                f"<title>{html.escape(title)}</title>\n</head>\n<body>\n"
                "<pre style=\"white-space: pre-wrap; font-family: sans-serif;\">"
                f"{html.escape(text)}</pre>\n</body>\n</html>\n")
    return text


def write_notes(path, text, title):
    tmp = _temp_path(path)
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(notes_to_file(text, os.path.splitext(path)[1].lower(), title))
    os.replace(tmp, path)


def read_notes(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            raw = f.read()
    if os.path.splitext(path)[1].lower() in (".html", ".htm"):
        own = _PRE_BLOCK.search(raw)
        if own:
            return html.unescape(own.group(1))
        doc = QTextDocument()
        doc.setHtml(raw)
        return doc.toPlainText()
    return raw


def write_image(drawing_pad, path):
    tmp = _temp_path(path)
    if not drawing_pad.save_drawing(tmp):
        if os.path.exists(tmp):
            os.remove(tmp)
        raise OSError(f"Couldn't write the drawing as {os.path.splitext(path)[1]}")
    os.replace(tmp, path)
