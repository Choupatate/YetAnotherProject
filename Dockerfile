FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STORYBOOK_STORIES_DIR=/data/stories
VOLUME ["/data/stories"]
EXPOSE 8000

CMD ["python", "serve.py"]
