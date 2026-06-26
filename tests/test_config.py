import os
import yaml
import tempfile
from pathlib import Path
from src.plugins.chatbot.config import Config, ConfigManager


class TestConfigModel:
    def test_default_values(self):
        cfg = Config()
        assert cfg.jm_download_dir == "data/jm_temp"
        assert isinstance(cfg.superusers, set)

    def test_set_values(self):
        cfg = Config(jm_download_dir="/tmp/test", superusers={"123"})
        assert cfg.jm_download_dir == "/tmp/test"
        assert cfg.superusers == {"123"}


class TestConfigManager:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cfg_test_"))
        (self.tmp / "data").mkdir(exist_ok=True)
        self.old_cwd = os.getcwd()

    def teardown_method(self):
        os.chdir(self.old_cwd)

    def _write_config(self, data: dict):
        with open(self.tmp / "config_bot_base.yaml", "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    def test_loads_yaml(self):
        self._write_config({
            "jm_download_dir": "data/custom",
            "superusers": ["111", "222"]
        })
        os.chdir(self.tmp)
        mgr = ConfigManager()
        assert mgr.jm_download_dir == "data/custom"
        assert mgr.superusers == {"111", "222"}

    def test_handles_missing_file(self):
        os.chdir(self.tmp)
        mgr = ConfigManager()
        assert mgr.books_folder is not None

    def test_type_coercion_list_to_set(self):
        self._write_config({"superusers": ["a", "b", "a"]})
        os.chdir(self.tmp)
        mgr = ConfigManager()
        assert mgr.superusers == {"a", "b"}

    def test_type_coercion_str_to_set(self):
        self._write_config({"superusers": "a, b, c"})
        os.chdir(self.tmp)
        mgr = ConfigManager()
        assert mgr.superusers == {"a", "b", "c"}

    def test_ignores_unknown_fields(self):
        self._write_config({"unknown_field": "value", "jm_download_dir": "/tmp/test"})
        os.chdir(self.tmp)
        mgr = ConfigManager()
        assert mgr.jm_download_dir == "/tmp/test"
        assert not hasattr(mgr, "unknown_field")

    def test_setattr_works(self):
        self._write_config({"jm_download_dir": "original"})
        os.chdir(self.tmp)
        mgr = ConfigManager()
        mgr.jm_download_dir = "changed"
        assert mgr.jm_download_dir == "changed"

    def test_generates_default_yaml(self):
        os.chdir(self.tmp)
        config_path = self.tmp / "config_bot_base.yaml"
        assert not config_path.exists()
        ConfigManager()
        assert config_path.exists()
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "jm_download_dir" in data

    def test_reload_after_modify(self):
        self._write_config({"jm_download_dir": "v1"})
        os.chdir(self.tmp)
        mgr = ConfigManager()
        assert mgr.jm_download_dir == "v1"
        self._write_config({"jm_download_dir": "v2"})
        mgr.load_config()
        assert mgr.jm_download_dir == "v2"
