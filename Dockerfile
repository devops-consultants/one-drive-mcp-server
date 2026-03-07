FROM python:3.12-slim

WORKDIR /app

# Copy project metadata and install dependencies
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Set Python path
ENV PYTHONPATH=/app/src
ENV PORT=8080

EXPOSE 8080

CMD ["python", "-m", "onedrive_mcp.server"]
