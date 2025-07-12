"""
Main orchestrator for Greenwich Travel Report generation.
"""

import logging
import argparse
from config import BOUNDARY_POLYGON
from data_ingestion import ingest_all
from traffic_analysis import TrafficFusion, Analyzer
from report_generator import ReportGenerator
from tts_client import TTSClient  # <- updated import


def run_report(dry_run: bool = False) -> None:
    """
    Fetch, process, generate script and audio.
    """
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting travel report generation")

    raw_incidents = ingest_all(BOUNDARY_POLYGON)
    logging.info("Ingested %d raw incidents", len(raw_incidents))

    fused = TrafficFusion.merge(raw_incidents)
    incidents = Analyzer.prioritize(
        fused,
        ReportGenerator().max_incidents
    )
    logging.info("Selected %d incidents for report", len(incidents))

    generator = ReportGenerator()
    script = generator.generate_script(incidents)
    logging.info("Generated script: %s", script)

    if dry_run:
        print("=== SCRIPT ===")
        print(script)
        return

    # Use Google Cloud TTS
    tts = TTSClient(
        language_code="en-GB",
        voice_name="en-GB-Wavenet-D",
        speaking_rate=1.0,
        pitch=0.0
    )
    audio_path = tts.synthesize(script)
    logging.info("Report audio saved at %s", audio_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Greenwich travel report"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only print script, no audio synthesis"
    )
    args = parser.parse_args()
    run_report(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
