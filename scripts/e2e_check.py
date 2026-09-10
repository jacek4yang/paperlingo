"""临时 E2E 验证脚本（跑完即删）。"""
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)

from paperlingo.database.db import Database
from paperlingo.database.repository import Repository
from paperlingo.services.settings import AppSettings
from paperlingo.ui.main_window import MainWindow

db = Database(":memory:")
repo = Repository(db)
win = MainWindow(db, repo, AppSettings())
win.show()

rp = win.reading_page

# 1. 加载示例
rp._load_example()
src = rp.source_edit.toPlainText()
assert "curated corpus" in src, "example not loaded"
print("1. example loaded")

# 2. 生成 Prompt
rp._generate_prompt()
prompt = rp._prompt.text
assert "curated corpus" in prompt
for ph in ("{domain_role}", "{schema_description}", "{depth_instruction}", "{source_text}"):
    assert ph not in prompt, f"leftover {ph}"
print("2. prompt generated, no leftover placeholders")

# 3. fixture 模拟 AI Response 解析
raw = Path("tests/fixtures/clean.json").read_text(encoding="utf-8")
rp.response_edit.setPlainText(raw)
rp._do_parse(raw)
assert rp._last_analysis_id and rp._last_analysis_id > 0, "analysis not saved"
print("3. parsed & saved, analysis_id =", rp._last_analysis_id)

# 4. 知识库沉淀
stats = repo.knowledge_stats()
assert stats["words"] > 0, f"no words ingested: {stats}"
lemmas = {w.lemma for w in repo.list_words()}
assert any("curat" in x for x in lemmas), f"curate missing: {lemmas}"
assert stats["phrases"] > 0 and stats["grammar"] > 0, f"ingest incomplete: {stats}"
print("4. ingest OK:", stats)

# 5. 标记不熟 -> 复习队列
from paperlingo.domain.learning import MasteryStatus

wid = repo.list_words()[0].word_id
repo.set_mastery("word", wid, MasteryStatus.UNFAMILIAR)
due = repo.due_items()
assert len(due) == 1, f"due items: {len(due)}"
print("5. mastery -> due queue OK")

# 6. 复习评分 -> review_logs
from paperlingo.domain.learning import Rating
from paperlingo.learning.review import review_item

assert review_item(repo, due[0].item_id, Rating.GOOD)
logs = repo.db.conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0]
assert logs == 1, f"review_logs: {logs}"
row = repo.db.conn.execute(
    "SELECT due_at, reps FROM learning_items WHERE id=?", (due[0].item_id,)
).fetchone()
assert row["reps"] == 1 and row["due_at"], f"not updated: {dict(row)}"
print("6. review log + reschedule OK, due_at =", row["due_at"])

# 7. 历史恢复
loaded = repo.load_parsed_analysis(rp._last_analysis_id)
assert loaded is not None, "restore failed"
win.switch_page("history")
win.switch_page("knowledge")
win.switch_page("review")
print("7. history restore + page switches OK")
print("E2E PASS")
