import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path
from urllib.parse import urljoin
import subprocess
import tempfile
import requests
from app.models.responses import Segment
from app.config import CACHE_DIR
import time
from app.core.logger import Logger

logger = Logger("subtitles")

class Subtitles:
    def __init__(self) -> None:
        self.cache_path = Path(CACHE_DIR) / "subtitles"

    def get_segments(self, m3u8_url: str) -> list[Segment]:
        r = requests.get(m3u8_url, timeout=20)
        r.raise_for_status()

        lines = r.text.splitlines()

        # Master playlist
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                return self.get_segments(urljoin(m3u8_url, lines[i + 1].strip()))

        segments: list[Segment] = []

        for i, line in enumerate(lines):
            if line.startswith("#EXTINF"):
                duration = float(line.split(":")[1].rstrip(","))
                seg_url = urljoin(m3u8_url, lines[i + 1].strip())
                segments.append(
                    Segment(
                        url=seg_url,
                        duration=duration
                    )
                )

        return segments

    def extract_audio(self, m3u8_url: str, wav_file: Path, duration_seconds: int = 600) -> None:
        segments = self.get_segments(m3u8_url)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            output_file = (wav_file).resolve()
            output_file.parent.mkdir(parents=True, exist_ok=True)

            concat = tmp / "concat.txt"

            elapsed = 0.0

            with open(concat, "w") as f:
                for idx, seg in enumerate(segments):
                    if elapsed >= duration_seconds: break

                    seg_file = tmp / f"{idx}.ts"

                    r = requests.get(seg.url, timeout=30)
                    r.raise_for_status()

                    seg_file.write_bytes(r.content)

                    f.write(f"file '{seg_file.name}'\n")

                    elapsed += seg.duration

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    # "-threads", "8",                  # Utilize multi-threading for faster decoding
                    # "-thread_queue_size", "1024",     # Increase packet queue buffer to prevent network stalls
                    # "-analyzeduration", "5000000",    # Helps FFmpeg read streams faster without waiting
                    "-probesize", "5000000",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(output_file),
                ],
                cwd=tmp,
                check=True,
            )


    def sync_hls_subtitle(self, m3u8_url: str, subtitle_url: str, output_srt: str="synced.srt"):
        # with tempfile.TemporaryDirectory() as tmp:
        start_time = time.time()

        wav_file = self.cache_path / "audio.wav"
        sub_file = self.cache_path / "input.srt"
        output_file = self.cache_path / output_srt

        self.extract_audio(m3u8_url, wav_file)

        r = requests.get(subtitle_url, timeout=30)
        r.raise_for_status()

        sub_file.write_text(
            r.text.replace("\r\n", "\n"),
            encoding="utf-8",
        )

        subprocess.run(
            [
                "ffsubsync",
                str(wav_file),
                # m3u8_url,
                "-i",
                str(sub_file),
                "-o",
                output_file,
            ],
            check=True,
        )
        logger.info(f"Response time: {time.time() - start_time}")
        return output_srt
    

if __name__ == "__main__":
    hsl_url = """http://localhost:8000/stream.m3u8?url=https%3A%2F%2Fjoe.goldweather.net%2F6TTEmttenJT-nx90N25XqQYxrcYfU5iBQVhOtACrBYdbwDL16XQVLHmoonbYFqiP_tBDJE32d1VWk7rHFjXZofmimYzvncLnitLD7bGAcT_o3iMn1eV0XZYYVbpfSkcQsWnTD0jZ9TOwvDkvsnlIqPie4IY9RmMwZUyH8rzO_ee2ROaAOwiQjkGmhh2qZ6lpW7w_nJw2UWz5Y1a2nO0bx1PoV_HMBHok8I0dV__rrtw5COqOx401dKqJp9fXqTgFxpF68cAEO7eGFqvC8FD4SKSI2eYExzqGzV1Q150QbGCceprnz4kZ5ZnM6PR3_zP-4y9zvzXfwGAAF-ev3imPS5-vy1ya_Xgu4E9YQ7c9PyPDFCFudX4oF2UYzyvWcOSae5bPnAmvg4u2EmqrkSbv6RNcD4-PQPgIDXOsDpMxhdT9zeid1slkaUUOdQRTehT9o1_Bkt_trINy72yJoEvhIoYJVDQ6pL1OQjgt3W2Ubbg0EHkRmis7meSepFkjGhyNzW8RbEAr29pN3FMJBTpBsriB7o3pscZ1Wi6B9ivYwbPXI2zGgBXiyX0rO5k5ZiaVhdw3EF7XDTcppe93GJnOXnx-LmAKAmzobX492zfdKCx7Ucc2RENOsUJMaWagag8jg4B8EI0pHb8jlT47zHTmUnnm2AuzN_72UgrX-k056nuNnSEoU1XC4rmcplqnnU5Kmok_db1V1JvCFSXI9Y_G1r%2Findex.m3u8&headers=%7B%22origin%22%3A%20%22https%3A%2F%2Fvidking.net%22%2C%20%22referer%22%3A%20%22https%3A%2F%2Fvidking.net%2F%22%7D"""
    sub_url = "https://subs5.strem.io/en/download/subencoding-stremio-utf8/src-api/file/1954741640"

    Subtitles().sync_hls_subtitle(hsl_url, sub_url)