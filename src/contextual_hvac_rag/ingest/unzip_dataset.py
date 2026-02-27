"""Dataset unzip helpers."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def unzip_dataset_to_dir(*, zip_path: Path, output_dir: Path) -> None:
    """Extract a ZIP archive using Python first, then a system fallback."""

    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP archive not found: {zip_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(output_dir)
            LOGGER.info("Extracted ZIP archive with zipfile: %s", zip_path)
            return
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        LOGGER.warning("zipfile extraction failed for %s: %s", zip_path, exc)

    _fallback_extract(zip_path=zip_path, output_dir=output_dir)


def _fallback_extract(*, zip_path: Path, output_dir: Path) -> None:
    """Fallback to an OS-level extraction command."""

    if shutil.which("unzip"):
        command = ["unzip", "-o", str(zip_path), "-d", str(output_dir)]
    elif os.name == "nt":
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                f"Expand-Archive -Path '{zip_path}' "
                f"-DestinationPath '{output_dir}' -Force"
            ),
        ]
    else:
        raise RuntimeError(
            "Unable to extract archive: zipfile failed and no system unzip fallback is available."
        )

    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Fallback extraction failed with code "
            f"{result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
        )
    LOGGER.info("Extracted ZIP archive with fallback command: %s", zip_path)

