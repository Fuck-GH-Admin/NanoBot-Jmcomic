from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Callable, Awaitable


@dataclass
class TaskResult:
    album_id: str
    title: str
    success: bool
    file_path: Optional[Path] = None
    series_ids: List[str] = field(default_factory=list)
    error_msg: str = ""


ProgressCallback = Callable[[str], Awaitable[None]]
