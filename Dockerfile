FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY tests/ ./tests/
COPY --from=frontend /build/dist ./frontend/dist
ENV PYTHONUNBUFFERED=1 FRONTEND_DIR=/app/frontend/dist LEAVE_DIR=/imports/eCount DATA_DIR=/data TZ=Asia/Seoul
EXPOSE 8787
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8787"]
