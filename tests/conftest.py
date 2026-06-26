import os
import sys
import tempfile
import yaml
import atexit
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import pytest

import nonebot

os.environ.setdefault("NONEBOT_LOG_LEVEL", "ERROR")

_test_tmp_dir = tempfile.mkdtemp(prefix="jmbot_test_")

config = {
    "jm_download_dir": f"{_test_tmp_dir}/data/jm_temp",
    "jm_option_path": f"{_test_tmp_dir}/option.yml",
    "books_folder": f"{_test_tmp_dir}/books",
    "font_path": "C:\\Windows\\Fonts\\msyh.ttc",
    "superusers": ["123456", "789012"]
}
with open(f"{_test_tmp_dir}/config_bot_base.yaml", "w", encoding="utf-8") as f:
    yaml.dump(config, f, allow_unicode=True)

option_config = {
    "client": {
        "postman": {
            "meta_data": {
                "proxies": {
                    "http": "http://127.0.0.1:7890",
                    "https": "http://127.0.0.1:7890"
                }
            }
        },
        "impl": "html",
        "retry_times": 3,
    },
    "dir_rule": {
        "base_dir": f"{_test_tmp_dir}/downloads",
        "rule": "Bd_Aid"
    },
    "download": {
        "image": {"suffix": ".jpg", "quality": 100},
        "threading": {"image": 10, "photo": 3}
    }
}
with open(f"{_test_tmp_dir}/option.yml", "w", encoding="utf-8") as f:
    yaml.dump(option_config, f, allow_unicode=True)

os.makedirs(f"{_test_tmp_dir}/books", exist_ok=True)
os.makedirs(f"{_test_tmp_dir}/data/jm_temp", exist_ok=True)
os.makedirs(f"{_test_tmp_dir}/downloads", exist_ok=True)

_old_cwd = os.getcwd()
os.chdir(_test_tmp_dir)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with open(f"{_test_tmp_dir}/.env", "w", encoding="utf-8") as f:
    f.write("DRIVER=~fastapi\nHOST=127.0.0.1\nPORT=18080\n")

nonebot.init()

def _cleanup():
    os.chdir(_old_cwd)
    print(f"\n[Conftest] Temp dir: {_test_tmp_dir}")

atexit.register(_cleanup)


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.send_group_msg = AsyncMock()
    bot.send_private_msg = AsyncMock()
    bot.call_api = AsyncMock(return_value=None)
    return bot
