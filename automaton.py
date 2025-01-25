import sys
import os
import io
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
    QSplitter,
    QPlainTextEdit,
    QListWidget,
    QTextEdit,
    QListWidgetItem,
    QFileDialog,
    QMenuBar,
)
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QPixmap, QIcon
from PyQt5.QtCore import Qt, QRegularExpression, QSize
import os
import threading
import traceback


from helpersLib import KThread
from mouseLib import recordMouseEvents, replayMouseEvents
from screenLib import *


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code."""

    def __init__(self, document):
        super().__init__(document)
        self.keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from", "global",
            "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or",
            "pass", "raise", "return", "True", "try", "while", "with", "yield",
        ]
        self.initHighlightingRules()

    def initHighlightingRules(self):
        """Define syntax highlighting rules."""
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#ff4500"))
        keyword_format.setFontWeight(QFont.Bold)

        self.highlighting_rules = [
            (QRegularExpression(rf"\b{kw}\b"), keyword_format) for kw in self.keywords
        ]

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#008000"))
        self.highlighting_rules.append((QRegularExpression(r'".*?"|\'.*?\''), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#808080"))
        self.highlighting_rules.append((QRegularExpression(r"#.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class AutoCompleteEditor(QPlainTextEdit):
    """Python editor with auto-completion popup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Courier", 12))
        self.setPlaceholderText("Write your Python script here...")

        # Autocomplete popup
        self.popup = QListWidget(self)
        self.popup.setWindowFlags(Qt.ToolTip)
        self.popup.setFont(QFont("Courier", 12))
        self.popup.itemClicked.connect(self.insertCompletion)

        self.highlighter = PythonHighlighter(self.document())

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

        # Check for autocompletion trigger
        if event.text().strip():
            self.showCompletions()

    def showCompletions(self):
        """Show autocomplete suggestions."""
        cursor = self.textCursor()
        cursor.select(cursor.WordUnderCursor)
        current_word = cursor.selectedText()

        if not current_word:
            self.popup.hide()
            return

        # Use jedi for autocomplete
        script_source = self.toPlainText()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber()

        try:
            import jedi
            script = jedi.Script(script_source)
            completions = script.complete(line=line, column=column)
            suggestions = [c.name for c in completions]

            if suggestions:
                self.showPopup(suggestions, cursor)
            else:
                self.popup.hide()

        except Exception as e:
            print(f"Autocomplete error: {e}")
            self.popup.hide()

    def showPopup(self, suggestions, cursor):
        """Display the autocomplete popup."""
        self.popup.clear()
        for suggestion in suggestions:
            item = QListWidgetItem(suggestion)
            self.popup.addItem(item)

        # Position the popup below the cursor
        cursor_rect = self.cursorRect(cursor)
        popup_position = self.mapToGlobal(cursor_rect.bottomLeft())
        self.popup.move(popup_position)
        self.popup.setFixedWidth(300)
        self.popup.show()

    def insertCompletion(self, item):
        """Insert the selected completion."""
        cursor = self.textCursor()
        cursor.select(cursor.WordUnderCursor)
        cursor.insertText(item.text())
        self.popup.hide()

class OutputStream(io.StringIO):
    """Custom output stream to redirect stdout/stderr."""

    def __init__(self, editor):
        super().__init__()
        self.editor = editor

    def write(self, text):
        # Strip unnecessary trailing newlines and append text
        if text.strip():  # Avoid excessive empty lines
            self.editor.append(text.rstrip())
            self.editor.ensureCursorVisible()

    def flush(self):
        pass  # Required for compatibility

class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Automaton")
        self.setGeometry(100, 100, 1200, 800)

        # Autosave file
        self.latest_script_path = os.path.join(os.getcwd(), "latest_script.py")

        # Initialize threading attributes
        self.script_thread = None
        self.stop_thread_event = threading.Event()

        # Capture folder
        self.capture_folder = os.path.join(os.getcwd(), "captures")
        os.makedirs(self.capture_folder, exist_ok=True)

        # Create Menu Bar
        self.createMenuBar()

        # Main Layout
        main_layout = QVBoxLayout()

        # Top bar
        top_bar = self.createTopBar()
        main_layout.addLayout(top_bar)

        # Horizontal Splitter for Editor, Help, and Thumbnails
        horizontal_splitter = QSplitter(Qt.Horizontal)

        # Editor and Help Section
        editor_splitter = QSplitter(Qt.Horizontal)

        # Script Editor
        self.editor = AutoCompleteEditor()
        editor_splitter.addWidget(self.editor)
        self.editor.textChanged.connect(self.autosaveScript)

        # Help Section
        self.help_list = QListWidget()
        editor_splitter.addWidget(self.help_list)
        editor_splitter.setStretchFactor(0, 3)
        editor_splitter.setStretchFactor(1, 1)

        horizontal_splitter.addWidget(editor_splitter)

        # Thumbnails Section (Rightmost)
        self.thumbnail_view = QListWidget()
        self.thumbnail_view.setIconSize(QSize(100, 100))  # Thumbnail size
        self.thumbnail_view.itemClicked.connect(self.insertImagePathToEditor)
        horizontal_splitter.addWidget(self.thumbnail_view)
        horizontal_splitter.setStretchFactor(0, 2)  # Editor + Help
        horizontal_splitter.setStretchFactor(1, 1)  # Thumbnails

        self.updateThumbnails()

        # Vertical Splitter for Horizontal Content and Output Window
        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.addWidget(horizontal_splitter)

        # Output Window
        self.output_window = QTextEdit()
        self.output_window.setFont(QFont("Courier", 10))
        self.output_window.setReadOnly(True)

        # Remove extra padding and set minimal margins
        self.output_window.setStyleSheet("QTextEdit { padding: 2px; }")
        self.output_window.setContentsMargins(0, 0, 0, 0)

        vertical_splitter.addWidget(self.output_window)
        vertical_splitter.setStretchFactor(0, 4)  # More space for horizontal content
        vertical_splitter.setStretchFactor(1, 1)  # Less space for output window

        # Add vertical splitter to main layout
        main_layout.addWidget(vertical_splitter)

        # Central Widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Populate help
        self.populateHelp()

        # Redirect stdout/stderr to the output window
        sys.stdout = OutputStream(self.output_window)
        sys.stderr = OutputStream(self.output_window)

        # Autoload the latest script
        self.autoloadScript()

    def insertImagePathToEditor(self, item):
        """Insert the clicked image's path into the editor."""
        file_path = os.path.join(self.capture_folder, item.text())
        cursor = self.editor.textCursor()
        cursor.insertText(f'"{file_path}"')

    def updateThumbnails(self):
        """Populate the thumbnails view with images from the captures folder."""
        self.thumbnail_view.clear()
        for file_name in os.listdir(self.capture_folder):
            if file_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                file_path = os.path.join(self.capture_folder, file_name)
                item = QListWidgetItem()
                pixmap = QPixmap(file_path)
                icon = QIcon(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                item.setIcon(icon)
                item.setText(file_name)
                item.setToolTip(file_path)
                self.thumbnail_view.addItem(item)

    def createTopBar(self):
        top_bar_layout = QHBoxLayout()

        # Screen Capture button
        btn_screen_capture = QPushButton("Screen Capture")
        btn_screen_capture.clicked.connect(self.screenCapture)
        top_bar_layout.addWidget(btn_screen_capture)

        # Record Mouse button
        btn_record_mouse = QPushButton("Record Mouse")
        btn_record_mouse.clicked.connect(self.recordMouse)
        top_bar_layout.addWidget(btn_record_mouse)

        # Playback button
        btn_playback = QPushButton("Playback")
        btn_playback.clicked.connect(self.playback)
        top_bar_layout.addWidget(btn_playback)

        # Play Script button
        btn_play_script = QPushButton("Play Script")
        btn_play_script.clicked.connect(self.runScript)
        top_bar_layout.addWidget(btn_play_script)

        # Stop script button
        btn_stop_script = QPushButton("Stop Script")
        btn_stop_script.clicked.connect(self.stopScript)
        top_bar_layout.addWidget(btn_stop_script)


        return top_bar_layout

    def createMenuBar(self):
        """Create the menu bar with File menu."""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # File Menu
        file_menu = menu_bar.addMenu("File")

        # Save Script Action
        save_action = file_menu.addAction("Save Script")
        save_action.triggered.connect(self.saveScript)

        # Load Script Action
        load_action = file_menu.addAction("Load Script")
        load_action.triggered.connect(self.loadScript)

    def autosaveScript(self):
        """Automatically save the script in the editor to the latest script file."""
        try:
            with open(self.latest_script_path, "w") as file:
                file.write(self.editor.toPlainText())
            # print(f"Autosaved to {self.latest_script_path}")
        except Exception as e:
            print(f"Error during autosave: {e}")

    def autoloadScript(self):
        """Automatically load the latest script into the editor on startup."""
        if os.path.exists(self.latest_script_path):
            try:
                with open(self.latest_script_path, "r") as file:
                    self.editor.setPlainText(file.read())
                print(f"Autoloaded script from {self.latest_script_path}")
            except Exception as e:
                print(f"Error during autoload: {e}")

    def saveScript(self):
        """Save the current script in the editor to a file."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Script", "", "Python Files (*.py);;All Files (*)", options=options
        )
        if file_path:
            try:
                with open(file_path, "w") as file:
                    file.write(self.editor.toPlainText())
                print(f"Script saved to: {file_path}")
            except Exception as e:
                print(f"Error saving script: {e}")

    def loadScript(self):
        """Load a script from a file into the editor."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Script", "", "Python Files (*.py);;All Files (*)", options=options
        )
        if file_path:
            try:
                with open(file_path, "r") as file:
                    self.editor.setPlainText(file.read())
                print(f"Script loaded from: {file_path}")
            except Exception as e:
                print(f"Error loading script: {e}")

    def populateHelp(self):
        """Populate the help section with function details."""
        functions = {
            "screenCapture": "Capture a region of the screen and save it.",
            "recordMouse": "Record mouse actions and save them.",
            "playback": "Replay recorded mouse actions.",
            "runScript": "Run the Python script written in the editor.",
            "detectImage": "Detect an image on the screen.",
            "clickOnImage": "Click on the specified part of the screen.",
            "waitForImage": "Wait for an image to appear on the screen.",
        }
        for name, desc in functions.items():
            self.help_list.addItem(f"{name} - {desc}")

    def screenCapture(self):
        print("Select a region of the screen...")
        region = selectScreenRegion()

        if region:
            # Check if file exists
            output_path = "captures/captured_region.png"
            if not os.path.exists("captures"):
                os.makedirs("captures")
            
            # If file exists, rename it and increment the number
            if os.path.exists(output_path):
                i = 1
                while os.path.exists(f"captures/captured_region_{i}.png"):
                    i += 1
                output_path = f"captures/captured_region_{i}.png"
            
            captureScreenRegion(region, output_path)
            print(f"Region captured and saved to {output_path}")
            self.updateThumbnails()


    def recordMouse(self):        
        recordMouseEvents("mouse_events.json")

    def playback(self):
        replayMouseEvents("mouse_events.json")

    def runScript(self):
        # Minimize the main window
        self.showMinimized()
        """Run the script from the editor in a separate thread."""
        script = self.editor.toPlainText()

        def script_execution():
            # Reset the stop thread event
            self.stop_thread_event.clear()
            try:
                exec(script, {
                    'screenCapture': self.screenCapture,
                    'recordMouse': self.recordMouse,
                    'playback': self.playback,
                    'detectImage': detectImage,
                    'clickOnImage': clickOnImage,
                    'waitForImage': waitForImage,
                    'stop_thread_event': self.stop_thread_event,
                })
            except Exception:
                traceback.print_exc(file=sys.stdout)

        # Ensure only one script thread runs at a time
        if self.script_thread is None or not self.script_thread.is_alive():
            self.script_thread = KThread(target=script_execution, daemon=True)
            self.script_thread.start()
            print("Script execution started.")
        else:
            print("A script is already running.")

    
    def stopScript(self):
        try:
            """Stop the currently running script."""
            if self.script_thread and self.script_thread.is_alive():
                self.stop_thread_event.set()  # Signal the thread to stop
                self.script_thread.join(timeout=1)
                print("Script execution stopped.")
                # Kill the thread if it's still running
                if self.script_thread.is_alive():
                    self.script_thread.kill()
            else:
                print("No script is currently running.")
        except Exception as e:
            print(f"Error stopping script: {e}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
