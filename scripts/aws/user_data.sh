#!/usr/bin/env bash
# user_data.sh — Bootstrap de AWS_EXECUTION_HOST (Ubuntu 24.04 ARM64 / Graviton2).
# Se ejecuta como cloud-init al lanzar la EC2. NO crea recursos AWS por si solo;
# solo prepara el entorno para que Hermes corra auditorias/experimentos.
#
# Free-tier: usar AMI Ubuntu 24.04 ARM64 (Graviton). t4g.small es free-tier
# eligible SOLO en cuentas creadas el/despues de 2025-07-15 (6 meses, capado).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git curl unzip htop ca-certificates \
  python3.11 python3.11-venv python3-pip

# Repo (publico; clone sin token)
cd /home/ubuntu
if [ ! -d ict2.0 ]; then
  git clone --depth 1 https://github.com/vjack666/ict2.0.git
fi
cd ict2.0
git pull --ff-only || true

# Entorno Python
python3.11 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# Dataset 20Y: esta gitignored en el repo. El usuario debe colocarlo en
# data/raw/EURUSD/ (via scp desde su PC, o `aws s3 sync` desde un bucket propio).
# NO se descarga de ningun sitio publico aqui para no depender de URLs externas.
mkdir -p data/raw/EURUSD
echo "AWS_EXECUTION_HOST: entorno listo."
echo "Pendiente: colocar EURUSD_*.parquet en data/raw/EURUSD/ y correr scripts/aws/benchmark.py"
