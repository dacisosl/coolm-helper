# -*- coding: utf-8 -*-
"""즐겨찾기 보관함 탭 — 2분할 (왼쪽 목록 / 오른쪽 상세보기·편집)."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from store.favorites import FavStore
from ui import theme


class FavoritesTab(QWidget):
    def __init__(self, fav_store: FavStore, parent=None):
        super().__init__(parent)
        self.favs = fav_store
        self._current_id: str | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        split = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show)
        ll.addWidget(self.list)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(10, 0, 0, 0)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("제목")
        self.title_edit.setStyleSheet(
            f"QLineEdit{{font-size:14px;font-weight:bold;background:{theme.CARD};"
            f"border:1px solid {theme.BORDER};border-radius:8px;padding:8px}}"
            f"QLineEdit:focus{{border:2px solid {theme.PRIMARY}}}")
        rl.addWidget(self.title_edit)
        self.meta = QLabel()
        self.meta.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        rl.addWidget(self.meta)
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("내용")
        rl.addWidget(self.content_edit, stretch=1)

        btns = QHBoxLayout()
        del_btn = QPushButton("삭제")
        del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{theme.DANGER};"
            f"border:none;font-size:12px;padding:5px}}"
            f"QPushButton:hover{{background:#fdecea;border-radius:6px}}")
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        btns.addStretch()
        self.save_btn = QPushButton("저장")
        self.save_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.save_btn.clicked.connect(self._save)
        btns.addWidget(self.save_btn)
        rl.addLayout(btns)
        split.addWidget(right)
        split.setSizes([260, 380])
        lay.addWidget(split)

        self.refresh()
        self.favs.subscribe(lambda: QTimer.singleShot(0, self.refresh))

    def refresh(self) -> None:
        cur_id = self._current_id
        self.list.blockSignals(True)
        self.list.clear()
        for fav in self.favs.all():
            created = ""
            try:
                created = datetime.fromisoformat(fav.created).strftime("%m/%d")
            except ValueError:
                pass
            item = QListWidgetItem(f"★ {fav.title[:26]}\n     {created}")
            item.setData(Qt.ItemDataRole.UserRole, fav.id)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if not self.favs.all():
            self._current_id = None
            self.title_edit.setText("")
            self.content_edit.setPlainText("")
            self.meta.setText("즐겨찾기가 비어 있습니다 — 일정 등록 창에서 "
                              "☆ 버튼으로 저장할 수 있습니다.")
            return
        # 이전 선택 유지, 없으면 첫 항목
        row = 0
        if cur_id:
            for i in range(self.list.count()):
                if self.list.item(i).data(Qt.ItemDataRole.UserRole) == cur_id:
                    row = i
                    break
        self.list.setCurrentRow(row)
        self._show(row)

    def _show(self, row: int) -> None:
        items = self.favs.all()
        if not (0 <= row < len(items)):
            return
        fav = items[row]
        self._current_id = fav.id
        self.title_edit.setText(fav.title)
        self.content_edit.setPlainText(fav.content)
        try:
            when = datetime.fromisoformat(fav.created).strftime("%Y-%m-%d %H:%M")
            self.meta.setText(f"저장: {when}")
        except ValueError:
            self.meta.setText("")

    def _save(self) -> None:
        if self._current_id is None:
            return
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "확인", "제목을 입력하세요.")
            return
        self.favs.update(self._current_id, title,
                         self.content_edit.toPlainText())

    def _delete(self) -> None:
        if self._current_id is None:
            return
        self.favs.remove(self._current_id)
        self._current_id = None
