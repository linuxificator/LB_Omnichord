"""Small, dependency-free audio metrics used by offline balance audits.

The loudness value follows the K-weighting filters and channel summation from
ITU-R BS.1770.  The standards' programme gating is intentionally not applied:
these audits compare short, equally bounded musical excerpts rather than
produce a broadcast programme loudness value.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def _biquad_coefficients(
    sample_rate: int,
    *,
    kind: str,
    frequency: float,
    q: float,
    gain_db: float = 0.0,
) -> tuple[float, float, float, float, float]:
    """Return normalized RBJ cookbook coefficients b0,b1,b2,a1,a2."""

    omega = 2.0 * math.pi * frequency / sample_rate
    cosine = math.cos(omega)
    sine = math.sin(omega)
    alpha = sine / (2.0 * q)
    if kind == "high_pass":
        b0 = (1.0 + cosine) / 2.0
        b1 = -(1.0 + cosine)
        b2 = b0
        a0 = 1.0 + alpha
        a1 = -2.0 * cosine
        a2 = 1.0 - alpha
    elif kind == "high_shelf":
        amplitude = 10.0 ** (gain_db / 40.0)
        root = 2.0 * math.sqrt(amplitude) * alpha
        b0 = amplitude * (
            (amplitude + 1.0)
            + (amplitude - 1.0) * cosine
            + root
        )
        b1 = -2.0 * amplitude * (
            (amplitude - 1.0) + (amplitude + 1.0) * cosine
        )
        b2 = amplitude * (
            (amplitude + 1.0)
            + (amplitude - 1.0) * cosine
            - root
        )
        a0 = (
            (amplitude + 1.0)
            - (amplitude - 1.0) * cosine
            + root
        )
        a1 = 2.0 * (
            (amplitude - 1.0) - (amplitude + 1.0) * cosine
        )
        a2 = (
            (amplitude + 1.0)
            - (amplitude - 1.0) * cosine
            - root
        )
    else:
        raise ValueError(f"unsupported biquad kind {kind!r}")
    return tuple(value / a0 for value in (b0, b1, b2, a1, a2))


def _filter_biquad(
    samples: np.ndarray,
    coefficients: Sequence[float],
) -> np.ndarray:
    """Apply one biquad with zero initial state using an FFT convolution."""

    source = np.asarray(samples, dtype=np.float64)
    if source.ndim == 1:
        source = source[:, np.newaxis]
    if not source.size:
        return source.copy()
    b0, b1, b2, a1, a2 = (float(value) for value in coefficients)
    fft_size = 1 << max(1, (2 * len(source) - 1).bit_length())
    bins = np.arange(fft_size // 2 + 1, dtype=np.float64)
    z1 = np.exp(-2j * math.pi * bins / fft_size)
    response = (b0 + b1 * z1 + b2 * z1 * z1) / (
        1.0 + a1 * z1 + a2 * z1 * z1
    )
    spectrum = np.fft.rfft(source, n=fft_size, axis=0)
    filtered = np.fft.irfft(spectrum * response[:, np.newaxis], n=fft_size, axis=0)
    return filtered[: len(source)]


def k_weight(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Apply the two filters specified by ITU-R BS.1770 K-weighting."""

    shelf = _biquad_coefficients(
        sample_rate,
        kind="high_shelf",
        frequency=1681.974450955533,
        gain_db=3.99984385397,
        q=0.7071752369554196,
    )
    high_pass = _biquad_coefficients(
        sample_rate,
        kind="high_pass",
        frequency=38.13547087602444,
        q=0.5003270373238773,
    )
    return _filter_biquad(_filter_biquad(samples, shelf), high_pass)


def audio_metrics(samples: np.ndarray, sample_rate: int) -> dict[str, float | int]:
    source = np.asarray(samples, dtype=np.float64)
    if source.ndim == 1:
        source = source[:, np.newaxis]
    peak = float(np.max(np.abs(source), initial=0.0))
    rms = float(np.sqrt(np.mean(source * source))) if source.size else 0.0
    weighted = k_weight(source, sample_rate)
    channel_energy = np.mean(weighted * weighted, axis=0) if weighted.size else [0.0]
    # Stereo and mono channels use unit weights in BS.1770.
    loudness = -0.691 + 10.0 * math.log10(max(float(np.sum(channel_energy)), 1e-24))
    return {
        "loudness_lkfs": round(loudness, 3),
        "rms_dbfs": round(20.0 * math.log10(max(rms, 1e-12)), 3),
        "peak_dbfs": round(20.0 * math.log10(max(peak, 1e-12)), 3),
        "crest_db": round(
            20.0 * math.log10(max(peak / max(rms, 1e-12), 1e-12)),
            3,
        ),
        "clipped_samples": int(np.count_nonzero(np.abs(source) >= 0.999969)),
    }
