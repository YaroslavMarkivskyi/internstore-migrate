FROM python:3.12-slim
WORKDIR /app

# ffmpeg is only needed at build time, to synthesize the fixed test clip —
# not installed in any runtime image layer we'd ship.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN ffmpeg -f lavfi -i testsrc=duration=3:size=320x240:rate=15 -pix_fmt yuv420p -y video.mp4

COPY server.py ./

EXPOSE 8001
CMD ["python", "server.py"]
