#!/usr/bin/env bash
# Cloud-environment setup for the Boardgames repo (video/manual toolchain).
# Run from the directory that holds the repository checkout.
# ffmpeg, pandoc, numpy, Pillow and Chromium/Playwright are preinstalled in the image.
set -e
if [ -d Boardgames ]; then
  pip install --quiet kokoro-onnx==0.6.1 soundfile
  V=Boardgames/tools/voices
  U=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
  mkdir -p "$V"
  for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
    [ -f "$V/$f" ] || curl -fsSL -o "$V/$f" "$U/$f"
  done
fi
