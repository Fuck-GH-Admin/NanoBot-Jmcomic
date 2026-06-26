from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import zipfile


def make_temp_zip(path: Path, size: int = 10240) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("001.jpg", "x" * size)
    return path


class TestPDFConverter:
    def test_returns_input_if_already_pdf(self):
        from src.plugins.chatbot.services.converter import PDFConverter
        p = Path("test.pdf")
        p.write_text("dummy")
        result = PDFConverter.convert_zip(p, Path("/tmp"))
        assert result == p
        p.unlink()

    @patch("src.plugins.chatbot.services.converter.PDFUtils.convert_zip_to_pdf")
    def test_converts_zip(self, mock_conv):
        from src.plugins.chatbot.services.converter import PDFConverter
        inp = Path("/tmp/test/123.zip")
        out = Path("/tmp/output/123.pdf")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("pdf content")
        mock_conv.return_value = str(out)
        result = PDFConverter.convert_zip(inp, Path("/tmp/output"))
        assert result is not None
        assert result.suffix == ".pdf"
        assert "123" in result.stem or result.stem.endswith("123")
        if out.exists():
            out.unlink()
        if result and result.exists() and result != out:
            result.unlink()

    @patch("src.plugins.chatbot.services.converter.PDFUtils.convert_zip_to_pdf")
    def test_returns_none_on_failure(self, mock_conv):
        from src.plugins.chatbot.services.converter import PDFConverter
        mock_conv.return_value = None
        result = PDFConverter.convert_zip(Path("/tmp/test.zip"), Path("/tmp/out"))
        assert result is None


class TestPDFEncryptor:
    def test_returns_none_without_pypdf2(self):
        with patch("src.plugins.chatbot.services.converter.PdfWriter", None):
            from src.plugins.chatbot.services.converter import PDFEncryptor
            result = PDFEncryptor.encrypt(Path("in.pdf"), Path("/tmp"))
            assert result is None

    @patch("src.plugins.chatbot.services.converter.PdfWriter")
    @patch("src.plugins.chatbot.services.converter.PdfReader")
    def test_encrypts_pdf(self, mock_reader_cls, mock_writer_cls):
        from src.plugins.chatbot.services.converter import PDFEncryptor
        mock_writer = MagicMock()
        mock_writer_cls.return_value = mock_writer
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock()]
        mock_reader.metadata = {"/Title": "T"}
        mock_reader_cls.return_value = mock_reader
        result = PDFEncryptor.encrypt(Path("in.pdf"), Path("/tmp/out"))
        assert result is not None
        assert result.name.startswith("enc_")
        assert mock_writer.encrypt.called


class TestJmDownloader:
    def test_downloads_album(self):
        from src.plugins.chatbot.services.downloader import JmDownloader, JmOptionCache
        JmOptionCache.invalidate()
        stale = Path("/tmp/350234_テスト.zip")
        if stale.exists():
            stale.unlink()
        with (
            patch("jmcomic.JmOption.from_file") as mock_from_file,
            patch("jmcomic.JmDownloader") as mock_dler_cls,
        ):
            mock_album = MagicMock()
            mock_album.title = "テスト"
            mock_album.episode_list = [("350234", 1, "ch1")]
            mock_client = MagicMock()
            mock_client.get_album_detail.return_value = mock_album
            mock_option = MagicMock()
            mock_option.dir_rule.base_dir = "/tmp"
            mock_from_file.return_value = mock_option
            mock_dler = MagicMock()
            mock_dler.client = mock_client
            mock_dler_cls.return_value = mock_dler

            ch_dir = Path("/tmp/350234_テスト")
            ch_dir.mkdir(parents=True, exist_ok=True)

            dl = JmDownloader(Path("/tmp"), Path("option.yml"), Path("/tmp"))
            result = dl.download_album("350234")

            assert len(result) > 0
            assert result[0]["title"] == "テスト"


class TestBookServiceProcess:
    @patch("src.plugins.chatbot.services.book_service.BookService._check_env", return_value=False)
    async def test_returns_error_when_env_incomplete(self, mock_check):
        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        results = await svc.process_download(["111"])
        assert len(results) == 1
        assert results[0].success is False
        assert "环境配置不完整" in results[0].error_msg

    async def test_returns_error_for_empty_ids(self):
        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        results = await svc.process_download([])
        assert len(results) == 1
        assert results[0].success is False

    @patch("src.plugins.chatbot.services.converter.PDFEncryptor.encrypt")
    @patch("src.plugins.chatbot.services.converter.PDFConverter.convert_zip")
    @patch("src.plugins.chatbot.services.book_service.BookService.check_network", return_value="")
    @patch("src.plugins.chatbot.services.book_service.JmDownloader.download_album")
    async def test_successful_download(self, mock_dl, mock_net, mock_conv, mock_enc):
        from src.plugins.chatbot.services.book_service import BookService
        tmp_zip = Path("data/jm_temp/test_350234.zip")
        tmp_zip.parent.mkdir(parents=True, exist_ok=True)
        make_temp_zip(tmp_zip)
        pdf_path = tmp_zip.with_suffix(".pdf")
        pdf_path.write_text("pdf content")

        mock_dl.return_value = [{
            "id": "350234", "title": "テスト",
            "path": tmp_zip, "series_ids": []
        }]
        mock_conv.return_value = pdf_path
        mock_enc.return_value = pdf_path

        svc = BookService()
        results = await svc.process_download(["350234"])
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].title == "テスト"

    @patch("src.plugins.chatbot.services.book_service.BookService.check_network", return_value="")
    @patch("src.plugins.chatbot.services.book_service.JmDownloader.download_album")
    async def test_reports_failure_when_no_content(self, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        mock_dl.return_value = []
        svc = BookService()
        results = await svc.process_download(["350234"])
        assert len(results) == 1
        assert results[0].success is False

    @patch("src.plugins.chatbot.services.book_service.BookService.check_network", return_value="")
    @patch("src.plugins.chatbot.services.book_service.JmDownloader.download_album")
    async def test_removes_duplicate_ids(self, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        mock_dl.return_value = []
        svc = BookService()
        results = await svc.process_download(["350234", "350234", "350235"])
        assert mock_dl.call_count == 2

    @patch("src.plugins.chatbot.services.book_service.BookService.check_network", return_value="")
    @patch("src.plugins.chatbot.services.book_service.JmDownloader.download_album")
    async def test_progress_callback_called(self, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        mock_dl.return_value = []
        progress = AsyncMock()
        svc = BookService()
        await svc.process_download(["350234"], progress=progress)
        assert progress.await_count > 0

    @patch("src.plugins.chatbot.services.book_service.BookService.check_network", return_value="")
    @patch("src.plugins.chatbot.services.book_service.JmDownloader.download_album")
    async def test_bitter_lovebirds(self, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        mock_dl.return_value = []
        svc = BookService()
        results = await svc.process_bitter_lovebirds()
        assert len(results) == 2
