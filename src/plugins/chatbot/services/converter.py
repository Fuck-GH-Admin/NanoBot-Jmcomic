import uuid
from pathlib import Path
from typing import Optional
from nonebot.log import logger

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    PdfReader = None
    PdfWriter = None

from ..utils.pdf_utils import PDFUtils


class PDFConverter:
    @staticmethod
    def convert_zip(input_zip: Path, output_dir: Path) -> Optional[Path]:
        if input_zip.suffix.lower() == '.pdf':
            return input_zip
        safe_name = f"{uuid.uuid4().hex[:8]}_{input_zip.stem}"
        result = PDFUtils.convert_zip_to_pdf(str(input_zip), str(output_dir))
        if result and Path(result).exists():
            actual = Path(result)
            if actual.name != f"{safe_name}.pdf":
                renamed = actual.with_name(f"{safe_name}.pdf")
                renamed.parent.mkdir(parents=True, exist_ok=True)
                actual.rename(renamed)
                return renamed
            return actual
        return None


class PDFEncryptor:
    @staticmethod
    def encrypt(input_pdf: Path, output_dir: Path, password: str = "114514") -> Optional[Path]:
        if not PdfWriter:
            return None
        try:
            reader = PdfReader(str(input_pdf))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            random_uid = str(uuid.uuid4())
            metadata = reader.metadata
            new_meta = {k: v for k, v in metadata.items()} if metadata else {}
            new_meta['/Custom-UUID'] = random_uid
            new_meta['/Producer'] = f"JM-Bot-{random_uid[:8]}"
            writer.add_metadata(new_meta)
            writer.encrypt(password)
            out_path = output_dir / f"enc_{uuid.uuid4().hex[:8]}_{input_pdf.name}"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                writer.write(f)
            return out_path
        except Exception:
            logger.exception("PDF加密失败")
            return None
