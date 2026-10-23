FROM python:3.13-slim
WORKDIR /app
# VOICE=1 also installs faster-whisper (adds ~300 MB to the image).
ARG VOICE=0
COPY requirements.txt requirements-voice.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$VOICE" = "1" ]; then pip install --no-cache-dir -r requirements-voice.txt; fi
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
