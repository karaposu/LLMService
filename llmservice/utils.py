

# python utils.py

from datetime import datetime, timezone


def _now_dt() -> datetime:
    """Current UTC time with microsecond precision."""
    return datetime.now(timezone.utc)



from pathlib import Path
import io

from datetime import datetime

def record_audio_to_file(
    duration: int = 3,
    fs: int = 16_000,
    channels: int = 1,
    filepath: str | Path | None = None,
    *,
    also_return_bytes: bool = False,
    playback: bool = True,
) -> bytes | None:
    

    import sounddevice as sd
    import soundfile as sf
    """
    Record audio from the default input device and save it as a WAV file.

    Parameters
    ----------
    duration : int
        Length of the recording in seconds.
    fs : int
        Sampling rate in Hertz.
    channels : int
        Number of input channels.
    filepath : str | Path | None
        Destination path for the WAV file.  If None, a timestamped
        filename like 'recording_20250705_141523.wav' is used in the
        current working directory.
    also_return_bytes : bool
        If True, return the WAV as raw bytes in addition to saving.
    playback : bool
        If True, play the recording through the default output.

    Returns
    -------
    bytes | None
        Raw WAV bytes if `also_return_bytes` is True, else None.
    """
    # Determine output path
    if filepath is None:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = Path.cwd() / f"recording_{stamp}.wav"
    else:
        filepath = Path(filepath).expanduser().resolve()
        filepath.parent.mkdir(parents=True, exist_ok=True)

    # Record
    print(f"recording started...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=channels)
    sd.wait()  # blocks until recording is finished
    print(f"recording finished...")

    # Optional playback
    if playback:
        sd.play(recording, fs)
        sd.wait()

    # Write to disk
    sf.write(filepath, recording, fs, format="WAV")
    print(f"Saved recording to: {filepath}")

    # Optionally return bytes
    if also_return_bytes:
        buf = io.BytesIO()
        sf.write(buf, recording, fs, format="WAV")
        return buf.getvalue()

# Usage example
if __name__ == "__main__":
    record_audio_to_file(duration=3, filepath="my_voice.wav")
