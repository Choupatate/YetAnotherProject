FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin storybook \
    && mkdir -p /data/stories \
    && chown -R storybook:storybook /app /data/stories

ENV STORYBOOK_STORIES_DIR=/data/stories
VOLUME ["/data/stories"]
EXPOSE 8000

USER storybook

CMD ["python", "serve.py"]
