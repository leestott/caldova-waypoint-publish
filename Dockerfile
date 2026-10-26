FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY waypoint waypoint
COPY data data
USER 1000:1000
EXPOSE 8000
CMD ["python", "-m", "waypoint.server"]
