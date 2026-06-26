import os
from pathlib import Path
from src.plugins.chatbot.repositories.book_repo import BookRepository


class TestBookRepository:
    def test_init_creates_dirs(self):
        repo = BookRepository()
        assert repo.books_dir.exists()
        assert repo.output_dir.exists()

    def test_get_all_books_empty(self, tmp_path):
        repo = BookRepository()
        assert repo.get_all_books() == []

    def test_get_all_books_with_files(self):
        repo = BookRepository()
        test_file = repo.books_dir / "test_12345.zip"
        test_file.write_text("fake content")
        books = repo.get_all_books()
        assert len(books) == 1
        assert books[0].name == "test_12345.zip"

    def test_get_all_books_skips_unsupported(self):
        repo = BookRepository()
        test_file = repo.books_dir / "test.txt"
        test_file.write_text("fake")
        test_exe = repo.books_dir / "test.exe"
        test_exe.write_text("fake")
        books = repo.get_all_books()
        assert "test.txt" in [b.name for b in books]
        assert "test.exe" not in [b.name for b in books]

    def test_find_book_by_id(self):
        repo = BookRepository()
        test_file = repo.books_dir / "350234_测试本子.zip"
        test_file.write_text("fake")
        found = repo.find_book_by_id_or_name("350234")
        assert found is not None
        assert found.name == "350234_测试本子.zip"

    def test_find_book_case_insensitive(self):
        repo = BookRepository()
        test_file = repo.books_dir / "HELLO.zip"
        test_file.write_text("fake")
        found = repo.find_book_by_id_or_name("hello")
        assert found is not None

    def test_find_book_exact_id_without_title(self):
        repo = BookRepository()
        f = repo.books_dir / "350234.zip"
        f.write_text("fake")
        assert repo.find_book_by_id_or_name("350234") is not None

    def test_find_book_does_not_match_substring(self):
        repo = BookRepository()
        (repo.books_dir / "350234_测试本子.zip").write_text("fake")
        (repo.books_dir / "3502345_其他本子.zip").write_text("fake")
        found = repo.find_book_by_id_or_name("350234")
        assert found is not None
        assert "3502345" not in found.name

    def test_find_book_edge_id_1_does_not_match_all(self):
        repo = BookRepository()
        (repo.books_dir / "350234_测试本子.zip").write_text("fake")
        (repo.books_dir / "12345_其他本子.zip").write_text("fake")
        assert repo.find_book_by_id_or_name("1") is None

    def test_find_book_not_found(self):
        repo = BookRepository()
        found = repo.find_book_by_id_or_name("nonexistent")
        assert found is None

    def test_get_random_book(self):
        repo = BookRepository()
        # clean any files left by earlier tests
        for f in repo.books_dir.iterdir():
            if f.is_file():
                f.unlink()
        assert repo.get_random_book() is None
        test_file = repo.books_dir / "test.zip"
        test_file.write_text("fake")
        assert repo.get_random_book() is not None

    def test_get_pdf_output_path(self):
        repo = BookRepository()
        source = repo.books_dir / "test.zip"
        pdf = repo.get_pdf_output_path(source)
        assert pdf.name == "test.pdf"
        assert pdf.parent == repo.output_dir

    def test_get_encrypted_output_path(self):
        repo = BookRepository()
        source = repo.output_dir / "test.pdf"
        enc = repo.get_encrypted_output_path(source)
        assert enc.name == "test_enc.pdf"

    def test_get_zip_save_path(self):
        repo = BookRepository()
        path = repo.get_zip_save_path("测试本子 Title")
        assert "测试本子 Title" in path.name
        assert path.suffix == ".zip"

    def test_get_zip_save_path_sanitizes(self):
        repo = BookRepository()
        path = repo.get_zip_save_path('bad:chars/here"')
        assert "bad" in path.name
        assert "/" not in path.name
