"""Loads the document pack named as Current in the Document Register."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from docx import Document as read_docx
from docx.table import Table
from openpyxl import load_workbook

REGISTER_SHEET = "Document Register"
# Slowest-changing documents first, so the stable part of the prefix comes first
CYCLE_ORDER = {"Annually": 0, "Quarterly": 1}


class PackError(Exception):
    """The register and the Data Sources folder don't agree."""


@dataclass(frozen=True)
class PackDocument:
    doc: int
    name: str
    file: str
    version: str
    revised: str
    blocks: tuple[str, ...]

    @property
    def title(self) -> str:
        return f"{self.name} v{self.version}"


@dataclass(frozen=True)
class Pack:
    documents: tuple[PackDocument, ...]
    warnings: tuple[str, ...]

    @property
    def pack_id(self) -> str:
        """Changes whenever any loaded text changes, so answers can name their release."""
        content = [[d.title, list(d.blocks)] for d in self.documents]
        return hashlib.sha256(json.dumps(content).encode()).hexdigest()[:12]


def read_register(register_path: Path) -> list[dict]:
    workbook = load_workbook(register_path, data_only=True, read_only=True)
    try:
        if REGISTER_SHEET not in workbook.sheetnames:
            raise PackError(f"{register_path.name} has no '{REGISTER_SHEET}' sheet")
        rows = workbook[REGISTER_SHEET].iter_rows(values_only=True)
        headers = [str(h).strip() if h else "" for h in next(rows)]
        records = [dict(zip(headers, row)) for row in rows]
    finally:
        workbook.close()
    return [r for r in records if r.get("File")]


def read_blocks(path: Path) -> list[str]:
    """One block per paragraph or table row, so a citation lands on that exact row."""
    blocks = []
    for item in read_docx(path).iter_inner_content():
        if isinstance(item, Table):
            header, *rows = [[c.text.strip() for c in row.cells] for row in item.rows]
            for row in rows:
                blocks.append(" | ".join(f"{h}: {v}" for h, v in zip(header, row) if v))
        elif item.text.strip():
            blocks.append(item.text.strip())
    return blocks


def load_pack(register_path: Path, data_dir: Path) -> Pack:
    register = read_register(register_path)
    documents = []
    for row in (r for r in register if r.get("Status") == "Current"):
        path = data_dir / str(row["File"])
        if not path.exists():
            raise PackError(f"The register lists {row['File']} as Current, but the file is missing")
        try:
            blocks = tuple(read_blocks(path))
        except PermissionError:
            raise PackError(f"Can't read {row['File']}. Close it in Word and start again.") from None
        documents.append(PackDocument(
            doc=int(row["Doc"]),
            name=str(row["Document"]),
            file=str(row["File"]),
            version=str(row["Version"]),
            revised=str(row["Revised"]),
            blocks=blocks,
        ))

    if not documents:
        raise PackError("The register has no Current documents")
    doc_numbers = [d.doc for d in documents]
    duplicates = sorted({n for n in doc_numbers if doc_numbers.count(n) > 1})
    if duplicates:
        raise PackError(f"More than one Current version of doc {duplicates}")

    documents.sort(key=lambda d: (CYCLE_ORDER.get(d.revised, len(CYCLE_ORDER)), d.doc))

    registered = {str(r["File"]) for r in register}
    unregistered = sorted(
        p.name for p in data_dir.glob("*.docx")
        if p.name not in registered and not p.name.startswith("~$")
    )
    warnings = tuple(f"{name} is not in the register, so it was not loaded" for name in unregistered)
    return Pack(documents=tuple(documents), warnings=warnings)
