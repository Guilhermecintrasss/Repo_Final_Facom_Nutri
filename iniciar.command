#!/bin/bash

cd "$(dirname "$0")"

echo "--- [SISTEMA] Iniciando Ambiente IoT ---"

echo "--- [DOCKER] Subindo containers..."
docker compose up -d --build

conda init
sleep 5
conda activate medicao
python app.py

read -p "Pressione Enter para fechar..."