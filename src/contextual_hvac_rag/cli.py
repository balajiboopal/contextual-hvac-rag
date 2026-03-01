"""Typer command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from contextual_hvac_rag.config import get_settings
from contextual_hvac_rag.logging_config import configure_logging

app = typer.Typer(add_completion=False, help="Contextual HVAC RAG utilities.")


@app.callback()
def main() -> None:
    """Configure logging before handling commands."""

    configure_logging(get_settings().app_log_level)


@app.command("validate-env")
def validate_env() -> None:
    """Print whether required environment variables are configured."""

    settings = get_settings()
    for key, is_set in settings.env_presence().items():
        state = "set" if is_set else "missing"
        typer.echo(f"{key}: {state}")


@app.command("unzip-dataset")
def unzip_dataset(
    zip_path: Path = typer.Option(..., "--zip-path", exists=True, dir_okay=False),
    extract_dir: Path = typer.Option(..., "--extract-dir", file_okay=False, dir_okay=True),
) -> None:
    """Extract a ZIP archive to a local directory."""

    from contextual_hvac_rag.ingest.unzip_dataset import unzip_dataset_to_dir

    unzip_dataset_to_dir(zip_path=zip_path, output_dir=extract_dir)
    typer.echo(f"Extracted {zip_path} -> {extract_dir}")


@app.command("ingest-pdfs")
def ingest_pdfs(
    pdf_dir: Path = typer.Option(..., "--pdf-dir", exists=True, file_okay=False),
    source_label: str = typer.Option("upload", "--source-label"),
) -> None:
    """Ingest all PDFs in a directory into the configured Contextual datastore."""

    from contextual_hvac_rag.ingest.ingest_pdfs import ingest_directory

    summary = ingest_directory(pdf_dir=pdf_dir, source_label=source_label)
    typer.echo(
        "Processed={processed} success={success} failed={failed} log={log_path}".format(
            processed=summary.processed,
            success=summary.succeeded,
            failed=summary.failed,
            log_path=summary.log_path,
        )
    )


@app.command("eval")
def run_eval(
    input_csv: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    out_dir: Path = typer.Option(..., "--out", file_okay=False),
    top_k: int = typer.Option(10, "--top-k", min=10),
    anchor_threshold: int = typer.Option(80, "--anchor-threshold", min=0, max=100),
    limit: int | None = typer.Option(None, "--limit", min=1),
) -> None:
    """Run the offline golden-dataset evaluation pipeline."""

    from contextual_hvac_rag.eval.run import run_evaluation

    run_evaluation(
        input_csv=input_csv,
        out_dir=out_dir,
        top_k=top_k,
        anchor_threshold=anchor_threshold,
        limit=limit,
    )


if __name__ == "__main__":
    app()
