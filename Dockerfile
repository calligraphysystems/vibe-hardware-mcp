FROM python:3.12-slim
WORKDIR /app
COPY calligraphy_mcp_stdio.py calligraphy_vibe_cli.py mcp_config.json README.md LICENSE ./
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/app/calligraphy_mcp_stdio.py"]
