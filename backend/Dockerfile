FROM python:3.10-slim

WORKDIR /app

# 安装依赖（faiss-cpu/numpy 较大，构建时间稍长属正常）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT:-8000}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
