import math
import struct
import wave
import subprocess
from pathlib import Path

def synthesize_wav(output_wav: Path, duration_sec: float, base_freq: float, pulse_rate: float, sample_rate: int = 44100):
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    
    with wave.open(str(output_wav), "w") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # Engine rumble simulation: fundamental + harmonics + pulse amplitude modulation
            pulse = 0.7 + 0.3 * math.sin(2 * math.pi * pulse_rate * t)
            f1 = math.sin(2 * math.pi * base_freq * t)
            f2 = 0.5 * math.sin(2 * math.pi * (base_freq * 2.0) * t)
            f3 = 0.25 * math.sin(2 * math.pi * (base_freq * 3.5) * t)
            
            sample_val = (f1 + f2 + f3) * pulse * 0.4
            int_val = int(max(-1.0, min(1.0, sample_val)) * 32767)
            frames.extend(struct.pack("<h", int_val))
            
        wav.writeframes(frames)

def wav_to_ogg(input_wav: Path, output_ogg: Path):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(input_wav),
        "-c:a", "libvorbis",
        "-qscale:a", "4",
        str(output_ogg)
    ]
    subprocess.run(cmd, check=True)
    input_wav.unlink(missing_ok=True)

def generate_all_sounds(repo_root=None):
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    sounds_dir = root / "resource_packs" / "MonsterTruck_RP" / "sounds" / "monster_truck"
    sounds_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Engine Idle: 1.0 second loop, low 45 Hz rumble, 12 Hz cylinder pulsing
    idle_wav = sounds_dir / "temp_idle.wav"
    idle_ogg = sounds_dir / "engine_idle.ogg"
    synthesize_wav(idle_wav, duration_sec=1.0, base_freq=45.0, pulse_rate=12.0)
    wav_to_ogg(idle_wav, idle_ogg)
    print(f"Generated {idle_ogg}")
    
    # 2. Engine Drive: 1.0 second loop, higher 110 Hz rev roar, 24 Hz pulsing
    drive_wav = sounds_dir / "temp_drive.wav"
    drive_ogg = sounds_dir / "engine_drive.ogg"
    synthesize_wav(drive_wav, duration_sec=1.0, base_freq=110.0, pulse_rate=24.0)
    wav_to_ogg(drive_wav, drive_ogg)
    print(f"Generated {drive_ogg}")

if __name__ == "__main__":
    generate_all_sounds()
