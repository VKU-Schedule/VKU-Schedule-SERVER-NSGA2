FROM python:3.12.10-slim

# Tăng tốc độ và giảm size khi cài gói hệ thống
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /code

# Copy requirements riêng để tối ưu cache layer
COPY app/requirements.txt ./app/requirements.txt

# Cài đặt dependencies và cleanup
# Sử dụng torch CPU-only để giảm dung lượng (~500MB thay vì ~2GB+ với CUDA)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.1.0+cpu torchvision==0.16.0+cpu && \
    pip install --no-cache-dir -r ./app/requirements.txt && \
    pip uninstall -y torch torchvision || true && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.1.0+cpu torchvision==0.16.0+cpu && \
    rm -rf /root/.cache/pip /tmp/pip-*

# Copy app code
COPY app/ ./app/

ENV PYTHONPATH=/code

EXPOSE 8001

CMD ["python", "-m", "app.main"]
