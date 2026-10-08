FROM python:3.12-slim
WORKDIR /service
COPY requirements.txt ./
# CPU wheel first: the default PyPI torch pulls several GB of CUDA libraries a
# deployment without a GPU never uses. requirements.txt still pins the range.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY app.py provision_models.py ./
EXPOSE 8090
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
