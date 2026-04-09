import wave
import threading
import numpy as np
import sounddevice as sd


class WavPlayer:
    def __init__(self, path: str):
        with wave.open(path, "rb") as f:
            self._params = f.getparams()
            raw = f.readframes(f.getnframes())

        sampwidth = self._params.sampwidth
        dtype = {1: np.int8, 2: np.int16, 4: np.int32}[sampwidth]
        samples = np.frombuffer(raw, dtype=dtype)

        # Reshape to (nframes, nchannels) and normalize to float32 in [-1.0, 1.0]
        self._audio = samples.reshape(-1, self._params.nchannels).astype(np.float32)
        self._audio /= float(np.iinfo(dtype).max)

        self._path = path
        self._cursor = 0
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None
        self._playing = False
        self._fx_volume = 0.0
        self._fx_lowpass = 0.0
        self._fx_highpass = 0.0

    def _callback(self, outdata: np.ndarray, frames: int, time, status):
        with self._lock:
            remaining = len(self._audio) - self._cursor
            if remaining <= 0:
                outdata[:] = 0
                self._playing = False
                raise sd.CallbackStop

            chunk_idx = min(frames, remaining)
            chunk = self._audio[self._cursor : self._cursor + chunk_idx]
            outdata[:chunk_idx] = self._apply_filters(chunk)

            if chunk_idx < frames:
                outdata[chunk_idx:] = 0

            self._cursor += chunk_idx

    def _apply_filters(self, chunk: np.ndarray) -> np.ndarray:
        if self._fx_volume != 0.0:
            # dB to linear scale; /20 for amplitude, /10 for power
            chunk *= 10 ** (self._fx_volume / 20)

        if self._fx_lowpass != 0.0 or self._fx_highpass != 0.0:
            # second half of FFT contains mirrored negative frequency terms
            sig = np.fft.fft(chunk, axis=0)
            n = len(sig)

            if self._fx_highpass != 0.0:
                cutoff_idx_high = int(abs(self._fx_highpass) * n / self.framerate)
                sig[:cutoff_idx_high] = 0
                sig[n // 2 : n // 2 + cutoff_idx_high] = 0

            if self._fx_lowpass != 0.0:
                cutoff_idx_low = int(self._fx_lowpass * n / self.framerate)
                # zero positive AND mirrored negative band above cutoff
                sig[cutoff_idx_low : n - cutoff_idx_low] = 0

            chunk = np.fft.ifft(sig, axis=0).real.astype(np.float32)

        return chunk

    def play(self):
        if self._playing:
            return

        self._playing = True
        if not self._stream:
            self._cursor = 0
            self._stream = sd.OutputStream(
                samplerate=self._params.framerate,
                channels=self._params.nchannels,
                dtype="float32",
                callback=self._callback,
                finished_callback=self._on_finished,
            )

        self._stream.start()

    def pause(self):
        if self._stream and self._playing:
            self._stream.stop()
            self._playing = False

    def resume(self):
        if self._stream and not self._playing:
            self._playing = True
            self._stream.start()

    def seek(self, seconds: float):
        frame = int(seconds * self._params.framerate)
        with self._lock:
            self._cursor = max(0, min(frame, len(self._audio)))

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self._playing = False
        self._cursor = 0

    def _on_finished(self):
        self._playing = False

    def fx_set_volume(self, adjust_db: float) -> None:
        """Live adjust playback gain. Negative values *increase* volume, positive values decrease it.

        Parameters
        ----------
        adjust_db : float
            How much to adjust the volume in DB.
        """
        self._fx_volume = adjust_db

    def fx_set_lowpass(self, threshold_hz: float) -> None:
        """Apply a lowpass filter on the signal during playback.

        Parameters
        ----------
        threshold_hz : float
            Lowpass threshold in Hz.
        """
        self._fx_lowpass = threshold_hz

    def fx_set_highpass(self, threshold_hz: float) -> None:
        """Apply a highpass filter on the signal during playback.

        Parameters
        ----------
        threshold_hz : float
            Highpass threshold in Hz.
        """
        self._fx_highpass = threshold_hz

    @property
    def position(self) -> float:
        return self._cursor / self._params.framerate

    @property
    def duration(self) -> float:
        return len(self._audio) / self._params.framerate

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def num_channels(self) -> int:
        return self._params.nchannels

    @property
    def frames(self) -> np.ndarray:
        return self._audio

    @property
    def num_frames(self) -> int:
        return self._params.nframes

    @property
    def framerate(self) -> int:
        return self._params.framerate
