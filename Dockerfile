# Usa uma imagem oficial e leve do Python como base
FROM python:3.9-slim

# Define o diretório de trabalho dentro do "pacote"
WORKDIR /app

# Copia o arquivo de dependências para dentro do pacote
COPY requirements.txt .

# Instala as dependências listadas no requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do seu dashboard para dentro do pacote
COPY Dashboard.py .

# Informa ao Docker que o aplicativo usa a porta 8501
EXPOSE 8501

# O comando que será executado para iniciar seu dashboard
# O endereço 0.0.0.0 é essencial para que o EasyPanel consiga se comunicar com o app
# O enableCORS=false ajuda a evitar problemas de comunicação com o navegador
CMD ["streamlit", "run", "Dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]
