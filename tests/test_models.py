from src.plugins.chatbot.models import TaskResult


class TestTaskResult:
    def test_default_error_msg_is_empty(self):
        r = TaskResult("id", "title", True)
        assert r.album_id == "id"
        assert r.title == "title"
        assert r.success is True
        assert r.error_msg == ""

    def test_failure_result(self):
        r = TaskResult("350234", "test", False, error_msg="下载失败")
        assert r.success is False
        assert r.error_msg == "下载失败"
        assert r.file_path is None
