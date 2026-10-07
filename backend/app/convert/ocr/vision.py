"""macOS Vision OCR adapter (optional, primary engine on macOS).

Uses `pyobjc-framework-Vision` when installed. Nothing here is imported at
application start-up, so a missing pyobjc is harmless — detection simply
reports the engine as unavailable and the caller falls back to Tesseract.

Vision returns a real per-observation confidence (`VNRecognizedTextObservation`
top candidate), which we pass through unchanged.
"""

from __future__ import annotations

from app.convert.ocr.base import OcrLine, OcrUnavailable

NAME = "vision"


def available() -> bool:
    try:
        import Quartz  # noqa: F401
        import Vision  # noqa: F401
    except Exception:
        return False
    return True


def recognize(png: bytes, *, lang: str = "en") -> list[OcrLine]:
    try:
        import Quartz
        import Vision
        from Foundation import NSData
    except Exception as exc:                                # pragma: no cover
        raise OcrUnavailable(f"pyobjc Vision framework is not installed: {exc}") from exc

    source = Quartz.CGImageSourceCreateWithData(
        NSData.dataWithBytes_length_(png, len(png)), None
    )
    if source is None:
        raise OcrUnavailable("could not decode the page image for Vision")
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if image is None:
        raise OcrUnavailable("could not decode the page image for Vision")
    width = float(Quartz.CGImageGetWidth(image))
    height = float(Quartz.CGImageGetHeight(image))

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(1)                          # accurate
    request.setUsesLanguageCorrection_(True)
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise OcrUnavailable(f"Vision OCR failed: {error}")

    lines: list[OcrLine] = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        candidate = candidates[0]
        text = str(candidate.string())
        if not text.strip():
            continue
        bbox = observation.boundingBox()
        x = bbox.origin.x
        y = bbox.origin.y
        w = bbox.size.width
        h = bbox.size.height
        # Vision's normalized coordinates use a bottom-left origin.
        lines.append(OcrLine(
            text,
            x * width,
            (1.0 - (y + h)) * height,
            (x + w) * width,
            (1.0 - y) * height,
            float(candidate.confidence()),
        ))
    lines.sort(key=lambda line: (round(line.y0, 1), line.x0))
    return lines