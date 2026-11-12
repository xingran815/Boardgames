#!/usr/bin/env bash
# Cloud-environment setup for the Boardgames repo (video/manual toolchain).
# Run from the directory that holds the repository checkout.
# ffmpeg, pandoc, Pillow and Chromium/Playwright are preinstalled in the image.
set -e
if [ -d Boardgames ]; then
  pip install --quiet piper-tts==1.8.0
  mkdir -p Boardgames/tools/voices
  if [ ! -f Boardgames/tools/voices/en_US-lessac-medium.onnx ]; then
    (cd Boardgames/tools/voices && python3 -m piper.download_voices en_US-lessac-medium)
  fi
fi
