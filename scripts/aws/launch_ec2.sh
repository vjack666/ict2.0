#!/usr/bin/env bash
# launch_ec2.sh — RECETA documentada para crear AWS_EXECUTION_HOST.
#
# ⚠️ REQUIERE AUTORIZACION EXPLICITA DE RUBEN (crea recursos con posible cargo).
# ⚠️ NO EJECUTAR SIN ESE OK. Hermes lo deja listo para revision.
# Requisitos: AWS CLI instalado + credenciales configuradas (`aws sts get-caller-identity`).
#
# Antes de lanzar: configurar AWS Budgets/alerta de costo en la consola.
set -euo pipefail

REGION="${REGION:-us-east-1}"          # region free-tier friendly
TYPE="${TYPE:-t4g.small}"               # Graviton ARM64; free-tier solo cuentas post-2025-07-15
KEY_NAME="${KEY_NAME:-hermes-ict2-0}"  # se crea si no existe
SG_NAME="${SG_NAME:-hermes-ict2-0-sg}"
AMI="${AMI:-}"                          # resolver abajo (Ubuntu 24.04 ARM64)

# 0) Aviso de elegibilidad free-tier (no bloquea, solo alerta)
echo ">> Chequeando free-tier eligibility para $TYPE ..."
if aws ec2 describe-instance-types \
     --filters Name=free-tier-eligible,Values=true \
     --query "InstanceTypes[*].InstanceType" --output text 2>/dev/null | grep -qw "$TYPE"; then
  echo "   OK: $TYPE es free-tier eligible en esta cuenta."
else
  echo "   AVISO: $TYPE NO es free-tier eligible -> SE FACTURARA. Cancela si no es intencional."
fi

# 1) AMI Ubuntu 24.04 ARM64 (Graviton) via SSM public parameter
if [ -z "$AMI" ]; then
  AMI=$(aws ssm get-parameter \
    --name /aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id \
    --query 'Parameter.Value' --output text)
  echo "   AMI resuelta: $AMI"
fi

# 2) Key pair (escribe .pem localmente)
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  aws ec2 create-key-pair --key-name "$KEY_NAME" \
    --query 'KeyMaterial' --output text > "$HOME/$KEY_NAME.pem"
  chmod 600 "$HOME/$KEY_NAME.pem"
  echo "   Key pair creado: $HOME/$KEY_NAME.pem"
fi

# 3) Security group (SSH solo desde tu IP publica)
MY_IP=$(curl -s https://checkip.amazonaws.com)/32
if ! SG_ID=$(aws ec2 describe-security-groups --group-names "$SG_NAME" \
       --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null); then
  SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" \
    --description "SSH Hermes ict2.0" --query 'GroupId' --output text)
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --protocol tcp --port 22 --cidr "$MY_IP" || true
  echo "   SG creado: $SG_ID (SSH desde $MY_IP)"
fi

# 4) Lanzar instancia
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI" --instance-type "$TYPE" --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --user-data file://"$(dirname "$0")/user_data.sh" \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=hermes-ict2-0},{Key=Owner,Value=ruben}]' \
  --query 'Instances[0].InstanceId' --output text)
echo ">> Instancia lanzada: $INSTANCE_ID (region $REGION)"
echo ">> Recuerda: apagar (stop) y ELIMINAR el volume EBS al terminar para no facturar almacenamiento."
