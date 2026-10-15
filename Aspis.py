import sys
import os
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, QAction, 
                             QLineEdit, QTabWidget, QProgressBar, QLabel, 
                             QStatusBar, QDialog, QVBoxLayout, QListWidget, QPushButton, QFileDialog)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile, QWebEngineDownloadItem

sys.argv.append("--disable-gpu")
sys.argv.append("--disable-software-rasterizer")
sys.argv.append("--num-raster-threads=4")
sys.argv.append("--no-sandbox")
sys.argv.append("--disable-features=AudioServiceSandbox")
sys.argv.append("--autoplay-policy=no-user-gesture-required")

APP_THEME = """
    QMainWindow { background-color: #f3f3f3; }
    QToolBar { background-color: #ffffff; border-bottom: 1px solid #e5e5e5; spacing: 8px; padding: 6px; }
    QToolButton { background-color: transparent; border: none; border-radius: 4px; padding: 6px 10px; font-family: "Segoe UI", sans-serif; font-size: 13px; color: #333333; }
    QToolButton:hover { background-color: #eaeaea; }
    QToolButton:pressed { background-color: #dadada; }
    QLineEdit { background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px; font-family: "Segoe UI", sans-serif; font-size: 13px; color: #333333; padding: 5px 8px; }
    QLineEdit:focus { border: 2px solid #0078d4; padding: 4px 7px; }
    QTabWidget::pane { border: none; background-color: #ffffff; }
    QTabBar::tab { background-color: #f3f3f3; border: none; border-bottom: 2px solid transparent; padding: 8px 16px; font-family: "Segoe UI", sans-serif; font-size: 12px; color: #666666; }
    QTabBar::tab:selected { background-color: #ffffff; color: #0078d4; border-bottom: 2px solid #0078d4; font-weight: 600; }
    QTabBar::tab:hover:!selected { background-color: #eaeaea; }
    QProgressBar { border: none; background-color: #e6e6e6; height: 3px; }
    QProgressBar::chunk { background-color: #0078d4; }
    QStatusBar { background-color: #ffffff; border-top: 1px solid #e5e5e5; font-family: "Segoe UI", sans-serif; font-size: 12px; color: #555555; padding: 4px; }
"""

class ListDialog(QDialog):
    def __init__(self, title, data_file, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(450, 350)
        self.data_file = data_file
        
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        self.load_data()
        
        self.action_btn = QPushButton('Clear History')
        self.action_btn.clicked.connect(self.clear_history)
        layout.addWidget(self.action_btn)
        
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QDialog { background-color: #f3f3f3; font-family: 'Segoe UI', sans-serif; }
            QListWidget { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 4px; padding: 5px; font-size: 13px; color: #333333; }
            QPushButton { background-color: #0078d4; color: white; border: none; border-radius: 4px; padding: 6px 12px; font-size: 12px; font-weight: bold; }
            QPushButton:hover { background-color: #106ebe; }
        """)

    def load_data(self):
        self.list_widget.clear()
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    self.list_widget.addItem(line.strip())

    def clear_history(self):
        if os.path.exists(self.data_file):
            open(self.data_file, 'w', encoding='utf-8').close()
        self.list_widget.clear()

class Aspis(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.history_file = os.path.join(self.base_dir, 'history.txt')
        
        self.profile = QWebEngineProfile.defaultProfile()
        self.profile.setPersistentStoragePath(os.path.join(self.base_dir, 'aspis_profile'))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
        self.profile.downloadRequested.connect(self.handle_download)

        self.setStyleSheet(APP_THEME)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.setCentralWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Ready')

        self.showMaximized()

        navbar = QToolBar()
        navbar.setMovable(False)
        self.addToolBar(navbar)

        back_btn = QAction('◀', self)
        back_btn.triggered.connect(lambda: self.tabs.currentWidget().back())
        navbar.addAction(back_btn)

        forward_btn = QAction('▶', self)
        forward_btn.triggered.connect(lambda: self.tabs.currentWidget().forward())
        navbar.addAction(forward_btn)

        stop_btn = QAction('Stop', self)
        stop_btn.triggered.connect(lambda: self.tabs.currentWidget().stop())
        navbar.addAction(stop_btn)

        reload_btn = QAction('↻', self)
        reload_btn.triggered.connect(lambda: self.tabs.currentWidget().reload())
        navbar.addAction(reload_btn)

        home_btn = QAction('🏠', self)
        home_btn.triggered.connect(self.navigate_home)
        navbar.addAction(home_btn)

        new_tab_btn = QAction('＋', self)
        new_tab_btn.triggered.connect(lambda: self.add_new_tab(QUrl('https://duckduckgo.com'), 'New Tab'))
        navbar.addAction(new_tab_btn)

        history_btn = QAction('History', self)
        history_btn.triggered.connect(self.show_history)
        navbar.addAction(history_btn)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText('Enter web address or search query (F11 for Fullscreen)')
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navbar.addWidget(self.url_bar)

        self.progress = QProgressBar()
        self.progress.setMaximumHeight(3)
        self.progress.setTextVisible(False)
        self.setMenuWidget(self.progress)
        
        self.add_new_tab(QUrl('https://duckduckgo.com'), 'Home')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()

    def handle_download(self, download_item: QWebEngineDownloadItem):
        default_path = os.path.join(os.path.expanduser('~'), 'Downloads', download_item.suggestedFileName())
        path, _ = QFileDialog.getSaveFileName(self, "Save File", default_path)
        if path:
            download_item.setPath(path)
            download_item.accept()
            self.status_bar.showMessage(f"Downloading: {download_item.suggestedFileName()}")
            download_item.finished.connect(lambda: self.status_bar.showMessage("Download finished!", 5000))

    def add_new_tab(self, qurl, label):
        browser = QWebEngineView()
        browser.setUrl(qurl)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)

        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_url(qurl, browser))
        browser.loadStarted.connect(lambda: self.status_bar.showMessage('Loading page...'))
        browser.loadFinished.connect(lambda _, i=i, browser=browser: self.handle_load_finished(i, browser))
        browser.loadProgress.connect(self.progress.setValue)
        
        self.url_bar.setFocus()

    def handle_load_finished(self, i, browser):
        title = browser.page().title()
        if not title.strip():
            title = "Untitled"
        display_title = title[:17] + '...' if len(title) > 20 else title
        self.tabs.setTabText(i, display_title)
        self.status_bar.showMessage('Done')
        
        url_str = browser.url().toString()
        if url_str and not url_str.startswith('data:') and '://duckduckgo.com' not in url_str:
            entry = f"{title} ({url_str})"
            last_entry = ""
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_entry = lines[-1].strip()
            
            if entry != last_entry:
                with open(self.history_file, 'a', encoding='utf-8') as f:
                    f.write(entry + '\n')

    def close_current_tab(self, i):
        if self.tabs.count() < 2:
            return
        self.tabs.widget(i).deleteLater()
        self.tabs.removeTab(i)

    def tab_changed(self, i):
        if i != -1:
            qurl = self.tabs.widget(i).url()
            self.url_bar.setText(qurl.toString())

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl('https://duckduckgo.com'))

    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        if not url:
            return
        if not url.startswith('http://') and not url.startswith('https://'):
            if '.' in url and ' ' not in url:
                url = 'https://' + url
            else:
                url = 'https://://duckduckgo.com' + url.replace(' ', '+')
        self.tabs.currentWidget().setUrl(QUrl(url))

    def update_url(self, q, browser=None):
        if browser == self.tabs.currentWidget():
            self.url_bar.setText(q.toString())

    def show_history(self):
        dialog = ListDialog('History', self.history_file, parent=self)
        dialog.exec_()

app = QApplication(sys.argv)
QApplication.setApplicationName('Aspis')
window = Aspis()
app.exec_()
