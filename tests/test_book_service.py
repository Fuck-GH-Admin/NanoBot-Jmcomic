import os
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call
import pytest
import zipfile


@pytest.fixture(autouse=True)
def reset_service():
    from src.plugins.chatbot.services.book_service import BookService
    svc = BookService()
    svc._network_checked = False
    svc._need_proxy = False
    yield
    del svc


def make_temp_zip(path: Path, content: str = "fake_image_data") -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("001.jpg", content)
    return path


class TestCheckEnv:
    def test_env_ok(self):
        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        assert svc._check_env() is True

    def test_missing_jmcomic(self):
        with patch("src.plugins.chatbot.services.book_service.jmcomic", None):
            from src.plugins.chatbot.services.book_service import BookService
            svc = BookService()
            assert svc._check_env() is False

    def test_missing_option_yml(self):
        from src.plugins.chatbot.services.book_service import BookService
        broken = Path("option_broken.yml")
        svc = BookService()
        svc.option_yaml_path = broken
        assert svc._check_env() is False


NETWORK_PATCH = patch("src.plugins.chatbot.services.book_service.BookService._check_and_update_network", return_value="")


@pytest.mark.asyncio
class TestHandleJmDownload:

    @NETWORK_PATCH
    @patch("src.plugins.chatbot.services.book_service.BookService._check_env", return_value=False)
    async def test_returns_error_when_env_incomplete(self, mock_check, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        result = await svc.handle_jm_download(MagicMock(), 123, "group", ["111"])
        assert "环境配置不完整" in result

    @NETWORK_PATCH
    async def test_returns_error_for_empty_ids(self, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        result = await svc.handle_jm_download(MagicMock(), 123, "group", [])
        assert "请提供 ID" in result

    @NETWORK_PATCH
    @patch("src.plugins.chatbot.services.book_service.BookService._sync_download_single")
    @patch("src.plugins.chatbot.services.book_service.BookService._encrypt_pdf_task")
    async def test_sends_processing_message(self, mock_enc, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        bot = MagicMock()
        bot.send_group_msg = AsyncMock()
        bot.call_api = AsyncMock(return_value=None)

        mock_dl.return_value = []
        svc = BookService()
        await svc.handle_jm_download(bot, 999, "group", ["350234"])

        bot.send_group_msg.assert_awaited_once()
        call_args = bot.send_group_msg.call_args
        assert "开始处理" in str(call_args)
        assert call_args[1]["group_id"] == 999

    @NETWORK_PATCH
    @patch("src.plugins.chatbot.services.book_service.BookService._sync_download_single")
    @patch("src.plugins.chatbot.services.book_service.PDFUtils.convert_zip_to_pdf")
    @patch("src.plugins.chatbot.services.book_service.BookService._encrypt_pdf_task")
    async def test_full_flow_success(self, mock_enc, mock_conv, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        bot = MagicMock()
        bot.send_group_msg = AsyncMock()
        bot.call_api = AsyncMock(return_value=None)

        tmp_zip = Path("data/jm_temp/test_350234.zip")
        tmp_zip.parent.mkdir(parents=True, exist_ok=True)
        make_temp_zip(tmp_zip)

        pdf_path = tmp_zip.with_suffix(".pdf")
        pdf_path.write_text("fake pdf content")

        mock_dl.return_value = [{
            "id": "350234",
            "title": "テスト本子",
            "path": tmp_zip,
            "series_ids": []
        }]
        mock_conv.return_value = str(pdf_path)
        mock_enc.return_value = pdf_path

        svc = BookService()
        result = await svc.handle_jm_download(bot, 999, "group", ["350234"])

        assert "成功" in result or "完成" in result
        mock_dl.assert_called_once_with("350234")

    @NETWORK_PATCH
    @patch("src.plugins.chatbot.services.book_service.BookService._sync_download_single")
    async def test_reports_failures(self, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        bot = MagicMock()
        bot.send_group_msg = AsyncMock()
        bot.call_api = AsyncMock(return_value=None)

        mock_dl.return_value = []
        svc = BookService()
        result = await svc.handle_jm_download(bot, 999, "group", ["350234"])
        assert "失败" in result

    @NETWORK_PATCH
    @patch("src.plugins.chatbot.services.book_service.BookService._sync_download_single")
    @patch("src.plugins.chatbot.services.book_service.BookService._encrypt_pdf_task")
    async def test_removes_duplicate_ids(self, mock_enc, mock_dl, mock_net):
        from src.plugins.chatbot.services.book_service import BookService
        bot = MagicMock()
        bot.send_group_msg = AsyncMock()
        bot.call_api = AsyncMock(return_value=None)

        mock_dl.return_value = [{
            "id": "350234",
            "title": "test",
            "path": Path("data/jm_temp/test.zip"),
            "series_ids": []
        }]
        mock_enc.return_value = None

        svc = BookService()
        await svc.handle_jm_download(bot, 999, "group", ["350234", "350234", "350235"])
        all_calls = mock_dl.call_args_list
        assert len(all_calls) == 2
        assert call("350234") in all_calls
        assert call("350235") in all_calls


@pytest.mark.asyncio
class TestHandleBitterLovebirds:

    @patch("src.plugins.chatbot.services.book_service.BookService.handle_jm_download")
    async def test_triggers_download(self, mock_handle):
        from src.plugins.chatbot.services.book_service import BookService
        mock_handle.return_value = "ok"
        bot = MagicMock()
        svc = BookService()
        result = await svc.handle_bitter_lovebirds(bot, 999)
        assert "苦命鸳鸯" in result
        mock_handle.assert_awaited_once_with(bot, 999, "group", ["350234", "350235"])

    @patch("src.plugins.chatbot.services.book_service.BookService._check_env", return_value=False)
    async def test_fails_without_env(self, mock_check):
        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        result = await svc.handle_bitter_lovebirds(MagicMock(), 999)
        assert "不支持" in result


class TestSyncDownloadSingle:

    @patch("src.plugins.chatbot.services.book_service.jmcomic")
    def test_downloads_album(self, mock_jm):
        mock_option = MagicMock()
        mock_client = MagicMock()
        mock_album = MagicMock()
        mock_album.title = "テスト本子"
        mock_album.episode_list = [("350234", 1, "ch1")]
        mock_client.get_album_detail.return_value = mock_album
        mock_option.dir_rule.base_dir = "data/jm_temp"
        mock_jm.JmOption.from_file.return_value = mock_option
        mock_jm.JmDownloader.return_value.client = mock_client
        mock_jm.JmDownloader.return_value.download_album = MagicMock()

        from src.plugins.chatbot.services.book_service import BookService

        ch_dir = Path("data/jm_temp/350234_测试本子")
        ch_dir.mkdir(parents=True, exist_ok=True)

        svc = BookService()
        result = svc._sync_download_single("350234")

        assert len(result) > 0
        assert result[0]["title"] == "テスト本子"

    def test_returns_empty_when_no_content(self):
        with patch("src.plugins.chatbot.services.book_service.jmcomic") as mock_jm:
            mock_option = MagicMock()
            mock_client = MagicMock()
            mock_album = MagicMock()
            mock_album.title = "test"
            mock_album.episode_list = [("111", 1, "ch1")]
            mock_client.get_album_detail.return_value = mock_album
            mock_option.dir_rule.base_dir = "data/jm_temp"
            mock_jm.JmOption.from_file.return_value = mock_option
            mock_jm.JmDownloader.return_value.client = mock_client
            mock_jm.JmDownloader.return_value.download_album = MagicMock()

            from src.plugins.chatbot.services.book_service import BookService

            svc = BookService()
            result = svc._sync_download_single("111")

            assert len(result) == 0

    @patch("src.plugins.chatbot.services.book_service.jmcomic")
    def test_detects_series(self, mock_jm):
        mock_option = MagicMock()
        mock_client = MagicMock()
        mock_album = MagicMock()
        mock_album.title = "系列本"
        mock_album.episode_list = [("350234", 1, "ch1"), ("350235", 2, "ch2"), ("350236", 3, "ch3")]
        mock_client.get_album_detail.return_value = mock_album
        mock_option.dir_rule.base_dir = "data/jm_temp"
        mock_jm.JmOption.from_file.return_value = mock_option
        mock_jm.JmDownloader.return_value.client = mock_client
        mock_jm.JmDownloader.return_value.download_album = MagicMock()

        from src.plugins.chatbot.services.book_service import BookService

        ch_dir = Path("data/jm_temp/350234_系列本")
        ch_dir.mkdir(parents=True, exist_ok=True)

        svc = BookService()
        result = svc._sync_download_single("350234")

        assert len(result) > 0
        assert result[0]["series_ids"] == ["350235", "350236"]


class TestEncryptPdfTask:

    def test_returns_none_without_pypdf2(self):
        with patch("src.plugins.chatbot.services.book_service.PdfWriter", None):
            from src.plugins.chatbot.services.book_service import BookService
            svc = BookService()
            result = svc._encrypt_pdf_task(Path("input.pdf"), Path("output.pdf"), "pw")
            assert result is None

    @patch("src.plugins.chatbot.services.book_service.PdfWriter")
    @patch("src.plugins.chatbot.services.book_service.PdfReader")
    def test_encrypts_with_uuid_metadata(self, mock_reader_cls, mock_writer_cls):
        mock_writer = MagicMock()
        mock_writer_cls.return_value = mock_writer
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock()]
        mock_reader.metadata = {"/Title": "Test"}
        mock_reader_cls.return_value = mock_reader

        from src.plugins.chatbot.services.book_service import BookService
        svc = BookService()
        inp = Path("test_in.pdf")
        outp = Path("test_out.pdf")

        result = svc._encrypt_pdf_task(inp, outp, "114514")

        assert result == outp
        mock_writer.add_metadata.assert_called_once()
        mock_writer.encrypt.assert_called_once_with("114514")
        assert mock_writer.add_page.called
