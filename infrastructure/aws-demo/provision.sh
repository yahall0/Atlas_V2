#!/usr/bin/env bash
# Atlas_V2 — one-shot AWS provisioning for the demo EC2 box.
# Prereqs:  aws CLI configured (aws sts get-caller-identity works), jq installed.
#
# What this does (idempotent-ish, safe to re-run once STACK_TAG is set):
#   1. Creates a key pair (saves private key to ./.secrets/atlas-demo.pem)
#   2. Creates a security group with demo-appropriate rules
#   3. Launches a t3.xlarge Ubuntu 22.04 EC2 with 60 GB gp3 + user-data bootstrap
#   4. Allocates an Elastic IP and associates it with the instance
#   5. Prints SSH command + public DNS for the deploy step
#
# Re-runs: delete the resources first (aws ec2 terminate-instances ... etc) or
# change STACK_TAG to provision a fresh stack.

set -euo pipefail

# ───────────────────────────── Config ─────────────────────────────
REGION="${REGION:-ap-south-1}"
STACK_TAG="${STACK_TAG:-atlas-demo}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.xlarge}"
VOLUME_GB="${VOLUME_GB:-60}"
MY_IP_CIDR="${MY_IP_CIDR:-}"   # e.g. 203.0.113.4/32 — auto-detected if empty

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="${SCRIPT_DIR}/.secrets"
KEY_NAME="${STACK_TAG}-key"
KEY_PATH="${SECRETS_DIR}/${KEY_NAME}.pem"
SG_NAME="${STACK_TAG}-sg"
USER_DATA_FILE="${SCRIPT_DIR}/user-data.sh"
STATE_FILE="${SCRIPT_DIR}/.state.json"

# Windows git-bash: AWS CLI (Windows binary) needs native paths, not /c/... POSIX paths.
if command -v cygpath >/dev/null 2>&1; then
  USER_DATA_FILE_URI="file://$(cygpath -w "${USER_DATA_FILE}")"
else
  USER_DATA_FILE_URI="file://${USER_DATA_FILE}"
fi

mkdir -p "${SECRETS_DIR}"
chmod 700 "${SECRETS_DIR}"

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

# ───────────── Sanity ─────────────
aws sts get-caller-identity --region "${REGION}" >/dev/null || {
  echo "aws CLI not configured. Run: aws configure" >&2; exit 1;
}
command -v python >/dev/null || command -v python3 >/dev/null || { echo "python is required" >&2; exit 1; }

if [[ -z "${MY_IP_CIDR}" ]]; then
  MY_IP="$(curl -s https://checkip.amazonaws.com | tr -d '\n')"
  MY_IP_CIDR="${MY_IP}/32"
  log "Detected public IP: ${MY_IP_CIDR} (SSH will be restricted to this)"
fi

# ───────────── 1. Key pair ─────────────
log "Ensuring key pair '${KEY_NAME}'"
if aws ec2 describe-key-pairs --region "${REGION}" --key-names "${KEY_NAME}" >/dev/null 2>&1; then
  echo "Key pair already exists in AWS. Using existing ${KEY_PATH} (must exist locally)."
  [[ -f "${KEY_PATH}" ]] || { echo "Local key file missing at ${KEY_PATH} — delete the AWS key pair or restore the file." >&2; exit 1; }
else
  aws ec2 create-key-pair \
    --region "${REGION}" \
    --key-name "${KEY_NAME}" \
    --key-type ed25519 \
    --key-format pem \
    --query 'KeyMaterial' \
    --output text > "${KEY_PATH}.raw"
  # Windows AWS CLI emits CRLF; ssh libcrypto requires LF-only PEM.
  python -c "import sys; p=sys.argv[1]; d=open(p,'rb').read().replace(b'\r\n',b'\n').replace(b'\r',b'\n'); open(sys.argv[2],'wb').write(d)" "${KEY_PATH}.raw" "${KEY_PATH}"
  rm -f "${KEY_PATH}.raw"
  chmod 400 "${KEY_PATH}"
  echo "Saved private key → ${KEY_PATH}"
fi

# ───────────── 2. Security group ─────────────
log "Ensuring security group '${SG_NAME}'"
VPC_ID="$(aws ec2 describe-vpcs --region "${REGION}" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
SG_ID="$(aws ec2 describe-security-groups --region "${REGION}" --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"

if [[ -z "${SG_ID}" || "${SG_ID}" == "None" ]]; then
  SG_ID="$(aws ec2 create-security-group \
    --region "${REGION}" \
    --group-name "${SG_NAME}" \
    --description "Atlas_V2 demo - HTTP/HTTPS public, SSH restricted" \
    --vpc-id "${VPC_ID}" \
    --query 'GroupId' --output text)"

  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=${MY_IP_CIDR},Description=admin-ssh}]" >/dev/null
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http}]" >/dev/null
  aws ec2 authorize-security-group-ingress --region "${REGION}" --group-id "${SG_ID}" \
    --ip-permissions "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description=https}]" >/dev/null
  echo "Created SG ${SG_ID}"
else
  echo "SG already exists: ${SG_ID}"
fi

# ───────────── 3. Launch instance ─────────────
log "Looking up latest Ubuntu 22.04 LTS AMI"
AMI_ID="$(aws ec2 describe-images --region "${REGION}" \
  --owners 099720109477 \
  --filters 'Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*' \
            'Name=state,Values=available' \
  --query 'sort_by(Images, &CreationDate) | [-1].ImageId' \
  --output text)"
echo "AMI: ${AMI_ID}"

log "Launching ${INSTANCE_TYPE} instance"
INSTANCE_ID="$(aws ec2 run-instances --region "${REGION}" \
  --image-id "${AMI_ID}" \
  --instance-type "${INSTANCE_TYPE}" \
  --key-name "${KEY_NAME}" \
  --security-group-ids "${SG_ID}" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${VOLUME_GB},\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
  --user-data "${USER_DATA_FILE_URI}" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${STACK_TAG}},{Key=Project,Value=Atlas_V2}]" \
                       "ResourceType=volume,Tags=[{Key=Name,Value=${STACK_TAG}-root},{Key=Project,Value=Atlas_V2}]" \
  --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
  --query 'Instances[0].InstanceId' --output text)"
echo "Instance: ${INSTANCE_ID}"

log "Waiting for instance to reach 'running'"
aws ec2 wait instance-running --region "${REGION}" --instance-ids "${INSTANCE_ID}"

# ───────────── 4. Elastic IP ─────────────
log "Allocating & associating Elastic IP"
ALLOC_ID="$(aws ec2 allocate-address --region "${REGION}" --domain vpc \
  --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=${STACK_TAG}-eip}]" \
  --query 'AllocationId' --output text)"
aws ec2 associate-address --region "${REGION}" --instance-id "${INSTANCE_ID}" --allocation-id "${ALLOC_ID}" >/dev/null

PUBLIC_IP="$(aws ec2 describe-addresses --region "${REGION}" --allocation-ids "${ALLOC_ID}" --query 'Addresses[0].PublicIp' --output text)"
PUBLIC_DNS="$(aws ec2 describe-instances --region "${REGION}" --instance-ids "${INSTANCE_ID}" --query 'Reservations[0].Instances[0].PublicDnsName' --output text)"

# ───────────── 5. Persist state ─────────────
cat > "${STATE_FILE}" <<EOF
{
  "region": "${REGION}",
  "stack_tag": "${STACK_TAG}",
  "key_name": "${KEY_NAME}",
  "key_path": "${KEY_PATH}",
  "security_group_id": "${SG_ID}",
  "instance_id": "${INSTANCE_ID}",
  "allocation_id": "${ALLOC_ID}",
  "public_ip": "${PUBLIC_IP}",
  "public_dns": "${PUBLIC_DNS}"
}
EOF

log "DONE"
cat <<EOF

Instance:  ${INSTANCE_ID}
Public IP: ${PUBLIC_IP}
DNS:       ${PUBLIC_DNS}

SSH:
  ssh -i ${KEY_PATH} ubuntu@${PUBLIC_IP}

Next step — wait ~2-3 min for user-data bootstrap to finish, then run:
  ./infrastructure/aws-demo/deploy.sh
EOF
