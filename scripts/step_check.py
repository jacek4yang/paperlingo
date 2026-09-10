import sys

print("step1: import PyQt6", flush=True)
from PyQt6.QtWidgets import QApplication

print("step2: create app", flush=True)
app = QApplication(sys.argv)

print("step3: import database", flush=True)
from paperlingo.database.db import Database

print("step4: create db", flush=True)
db = Database(":memory:")

print("step5: import main_window", flush=True)
from paperlingo.ui.main_window import MainWindow

print("step6: create window", flush=True)
from paperlingo.database.repository import Repository
from paperlingo.services.settings import AppSettings

repo = Repository(db)
win = MainWindow(db, repo, AppSettings())

print("step7: show", flush=True)
win.show()

print("ALL OK", flush=True)
