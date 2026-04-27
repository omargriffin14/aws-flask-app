# AWS Two-Tier Flask Web Application

A production-grade two-tier web application deployed on AWS, featuring a containerized Flask backend, managed MySQL database, automated CI/CD pipeline, CDN-served static assets, and full observability. Built as a cloud engineering portfolio project demonstrating real-world AWS architecture patterns.

**Live URL:** `http://flask-alb-1442848183.us-east-1.elb.amazonaws.com`

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [AWS Services Used](#aws-services-used)
- [Project Structure](#project-structure)
- [Infrastructure Setup](#infrastructure-setup)
- [Application Setup](#application-setup)
- [CI/CD Pipeline](#cicd-pipeline)
- [Security](#security)
- [Observability](#observability)
- [Lessons Learned](#lessons-learned)

---

## Overview

This project is a task manager web application where users can add and view tasks. The primary purpose is to demonstrate a complete AWS cloud deployment including networking, compute, database, security, content delivery, automation, and monitoring — all following AWS best practices.

The application is accessible via an Application Load Balancer, runs in a Docker container on EC2, connects to a managed RDS MySQL instance in a private subnet, and deploys automatically on every push to the main branch via GitHub Actions.

---

## Architecture

```
Internet
    │
    ▼
Application Load Balancer (flask-alb)
    │  Port 80 → Port 5000
    ▼
EC2 t3.micro - Amazon Linux 2023 (Public Subnet 10.0.1.0/24)
    │  Docker container running Flask + Gunicorn
    │
    ├──→ AWS Secrets Manager (DB credentials)
    ├──→ Amazon ECR (container image)
    │
    ▼
RDS MySQL db.t3.micro (Private Subnet 10.0.2.0/24)
    Port 3306 — no internet access

Static assets (CSS) served via:
CloudFront → S3 (flask-static-assets-4003)

CI/CD:
GitHub → GitHub Actions → SSH → EC2 → Docker rebuild
```

**Key design decisions:**
- EC2 lives in a public subnet — reachable by the ALB
- RDS lives in a private subnet — reachable only from EC2, never from the internet
- Security groups are chained: ALB SG → EC2 SG → RDS SG
- No credentials are stored in code, environment variables, or CI/CD config

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask, SQLAlchemy, Gunicorn |
| Database | MySQL 8.0 |
| Containerization | Docker |
| Infrastructure | AWS (VPC, EC2, RDS, ALB, S3, CloudFront, Secrets Manager, CloudWatch) |
| CI/CD | GitHub Actions |
| IaC | AWS CLI (infrastructure provisioned manually and via CLI) |

---

## AWS Services Used

| Service | Purpose |
|---|---|
| VPC | Isolated network with public and private subnets |
| EC2 (t3.micro) | Hosts the Docker container running the Flask app |
| RDS MySQL (db.t3.micro) | Managed relational database in a private subnet |
| Application Load Balancer | Distributes internet traffic to EC2 on port 5000 |
| S3 | Stores static assets (CSS) |
| CloudFront | CDN — serves static assets from edge locations globally |
| Secrets Manager | Stores RDS credentials securely — fetched at runtime by the app |
| IAM | EC2 instance role with least-privilege permissions |
| CloudWatch | Monitors EC2 CPU and RDS connections, triggers alarms |
| SNS | Sends email alerts when CloudWatch alarms fire |
| Internet Gateway | Enables public subnet to communicate with the internet |
| Security Groups | Firewall rules chained across ALB, EC2, and RDS |
| Elastic IP | Static public IP for EC2 — survives instance stop/start |

---

## Project Structure

```
aws-flask-app/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions CI/CD pipeline
└── App/
    ├── Dockerfile              # Container definition
    ├── app.py                  # Flask application
    ├── requirements.txt        # Python dependencies
    └── templates/
        └── index.html          # Frontend template
```

---

## Infrastructure Setup

### Prerequisites
- AWS account with CLI configured
- EC2 key pair created and downloaded
- GitHub repository

### Networking

**VPC**
- CIDR: `10.0.0.0/16`
- 1 public subnet: `10.0.1.0/24` (us-east-1a)
- 1 private subnet: `10.0.2.0/24` (us-east-1a)
- 1 additional private subnet: `10.0.3.0/24` (us-east-1b) — required by RDS
- 1 additional public subnet: `10.0.4.0/24` (us-east-1b) — required by ALB
- Internet Gateway attached to VPC
- Public route table: `0.0.0.0/0 → IGW`
- Private route table: local only

**Security Groups**

| Group | Inbound Rules |
|---|---|
| flask-alb-sg | HTTP 80 from 0.0.0.0/0, HTTPS 443 from 0.0.0.0/0 |
| flask-ec2-sg | TCP 5000 from flask-alb-sg, SSH 22 from 0.0.0.0/0 |
| flask-rds-sg | MySQL 3306 from flask-ec2-sg |

### RDS MySQL

- Engine: MySQL 8.0
- Instance class: db.t3.micro (free tier)
- Storage: 20GB gp2
- Single-AZ deployment
- Subnet group spanning both private subnets
- Public access: disabled
- Initial database: `flaskdb`

### EC2

- AMI: Amazon Linux 2023
- Instance type: t3.micro (free tier)
- Subnet: flask-public-subnet
- Auto-assign public IP: enabled
- Elastic IP attached for stable addressing
- IAM role: `flask-ec2-role` with `AmazonEC2ContainerRegistryReadOnly`, `AmazonS3FullAccess`, `SecretsManagerReadWrite`
- Docker installed on launch

### Application Load Balancer

- Scheme: internet-facing
- Subnets: both public subnets across two AZs
- Security group: flask-alb-sg
- Listener: HTTP port 80 → forward to flask-tg
- Target group: flask-tg (HTTP, port 5000, health check on /)

### S3 and CloudFront

- S3 bucket: `flask-static-assets-4003`
- CSS file: `flask-app.css` stored at bucket root
- CloudFront distribution pointing to S3 origin
- CSS served via CloudFront domain in `index.html`

### Secrets Manager

```bash
aws secretsmanager create-secret \
  --name flask/db-credentials \
  --secret-string '{"DB_USER":"admin","DB_PASSWORD":"...","DB_HOST":"...","DB_NAME":"flaskdb"}'
```

---

## Application Setup

### Dependencies

```
flask
flask-sqlalchemy
pymysql
cryptography
gunicorn
boto3
```

### Environment

The app fetches all database credentials from AWS Secrets Manager at startup using `boto3`. No credentials are stored in environment variables, config files, or the codebase.

```python
def get_secret():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='flask/db-credentials')
    return json.loads(response['SecretString'])
```

### Running locally

```bash
# Set environment variables for local development
export DB_USER=admin
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
export DB_NAME=flaskdb

docker build -t flask-app .
docker run -d \
  --name flask-container \
  -p 5000:5000 \
  -e DB_USER=$DB_USER \
  -e DB_PASSWORD=$DB_PASSWORD \
  -e DB_HOST=$DB_HOST \
  -e DB_NAME=$DB_NAME \
  flask-app
```

### Building and running on EC2

```bash
cd /home/ec2-user/aws-flask-app/App
docker build -t flask-app .
docker run -d --name flask-container -p 5000:5000 flask-app
```

Credentials are fetched automatically from Secrets Manager via the EC2 IAM role — no flags needed.

---

## CI/CD Pipeline

GitHub Actions automates every deployment. On every push to `main`:

1. GitHub spins up an Ubuntu runner
2. Checks out the repository
3. SSHs into EC2 using stored secrets
4. Pulls the latest code from GitHub
5. Stops and removes the existing container
6. Rebuilds the Docker image
7. Starts a new container

```yaml
name: Deploy to EC2

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ec2-user/aws-flask-app/App
            git pull origin main
            docker stop flask-container || true
            docker rm flask-container || true
            docker build -t flask-app .
            docker run -d --name flask-container -p 5000:5000 flask-app
```

**GitHub Secrets required:**

| Secret | Description |
|---|---|
| EC2_HOST | Elastic IP of the EC2 instance |
| EC2_USER | `ec2-user` |
| EC2_SSH_KEY | Contents of the EC2 key pair .pem file |

---

## Security

**Network isolation**
- RDS has no public access and sits in a private subnet with no route to the internet
- EC2 only accepts port 5000 traffic from the ALB security group — not from the public internet directly
- Security groups are chained so each layer only trusts the layer above it

**Credential management**
- Database credentials stored in AWS Secrets Manager
- EC2 accesses Secrets Manager via IAM role — no access keys or hardcoded credentials anywhere
- No sensitive values in GitHub repository, workflow files, or Docker images

**Access control**
- EC2 IAM role follows least privilege — only the permissions the app actually needs
- SSH access uses key-based authentication — no password authentication

---

## Observability

**CloudWatch Alarms**

| Alarm | Metric | Threshold | Action |
|---|---|---|---|
| flask-ec2-high-cpu | EC2 CPUUtilization | > 80% for 10 min | SNS email alert |
| flask-rds-high-connections | RDS DatabaseConnections | > 50 for 10 min | SNS email alert |

**CloudWatch Dashboard**

`flask-app-dashboard` displays:
- EC2 CPU utilization over time
- RDS database connections over time
- Alarm status panel for both alarms

**SNS**

Alerts sent via `flask-alerts` SNS topic to a subscribed email address.

---

## Lessons Learned

- Docker build cache can serve stale files — always use `--no-cache` after file changes and verify with `docker run --rm image cat /app/file.py` before running
- CloudShell has its own outbound IP that differs from your local machine's IP — always run `curl ifconfig.me` in CloudShell when configuring security group SSH rules
- EC2 Instance Connect uses a fixed AWS IP range (`18.206.107.24/29` in us-east-1) — a more reliable alternative to tracking CloudShell IPs
- Python is strict about indentation — mixing tabs and spaces causes `IndentationError` that can be invisible in some editors. Use `cat -A` to reveal hidden characters
- ALB target groups must use HTTP protocol to match an HTTP listener — TCP target groups are incompatible with ALB listeners
- RDS requires a subnet group spanning at least two AZs even for single-AZ deployments
- GitHub Actions runs on GitHub's infrastructure, not on EC2 — the workflow file is instructions for GitHub, not for the server
