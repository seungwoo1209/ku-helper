# Infra Roadmap

ku-helper AWS 인프라(Terraform + Packer + GitHub Actions)의 잔여 작업·정책 미결 사항·잠재 부채를 추적하는 문서. 다음 세션이 인프라에 다시 들어올 때 **여기서부터 읽어서 컨텍스트를 복구**할 것.

마지막 갱신: 2026-05-25 — 인프라 재구성 PR 진행 중(issue #34, 브랜치 `infra/aws-rebuild`). 기존 infra/*.tf + `.github/workflows/deploy-api-server.yml` 폐기. 새 구조 `infra/{bootstrap,persistent,ephemeral,packer}/` 작성 중.

## 0. 설계 원칙

- **재현성**: 모든 AWS 리소스는 Terraform/Packer 로 코드화. 콘솔 수동 변경 금지.
- **비용 캡**: 학생 프로젝트 — t3.micro·t4g.micro·serverless 최소. NAT GW, Multi-AZ RDS, 정기 EC2 24/7 미사용 시 teardown 권장.
- **자격증명 0 정적**: 모든 외부 자격은 OIDC + IAM Role assume. GitHub Actions 의 정적 AWS Access Key 사용 금지.
- **데이터 보존**: RDS 는 `skip_final_snapshot=false` + manual snapshot 이중. teardown 으로 데이터 손실 없게.
- **사전 발급 vs 사이클**: ACM·EC2 IAM Role·AMI 는 persistent 모듈. VPC·EC2·RDS·Valkey 는 ephemeral 모듈 (한 번에 올리고 한 번에 내릴 수 있어야 함).
- **태그 강제**: 모든 AWS 리소스에 `project = "ku-helper"` (cost allocation 추적용).

## 1. 진행 상황 스냅샷

진행 중(이번 PR 범위):
1. `infra/bootstrap/` — S3 tfstate + DynamoDB lock
2. `infra/persistent/` — ACM(api.ku-helper.seungwoo1209.site) + EC2 IAM Role + AMI data
3. `infra/ephemeral/` — VPC(2AZ) + ALB + EC2 × 2 + RDS PG + Valkey serverless
4. `infra/packer/` — app AMI (docker, compose, awscli, cloudwatch agent, ssm-agent)
5. `backend/Dockerfile` + `infra/packer/files/docker-compose.yml`
6. backend/bot IAM DB 인증 코드 (`app/core/aws_auth.py`)
7. `.github/workflows/{deploy-backend-bot-startup,deploy-backend,deploy-bot,spin-up,teardown}.yml`

사전 등록 완료 (이번 IaC 가 생성하지 않음 — 변수/data 참조만):
- GitHub Actions Secret `DEPLOYMENT_AWS_ACCOUNT_ID`, `ROUTE53_PROVIDER_AWS_ID`
- IAM Role `ku-helper-github-oidc-role` (배포 계정)
- IAM Role `Route53-kuhelper-CrossAccount-Role` (Route53 계정)

## 2. 운영 명령 (PR 머지 후 갱신)

```bash
# state backend 1회 부트스트랩
cd infra/bootstrap && terraform init && terraform apply

# AMI 빌드 (코드 변경 없으면 재빌드 불필요)
cd infra/packer && packer build app.pkr.hcl

# 영속 리소스 (ACM, IAM Role)
cd infra/persistent && terraform init && terraform apply

# spin-up / teardown (수동 검증) — 평소엔 GitHub Actions 워크플로 사용
cd infra/ephemeral && terraform apply
cd infra/ephemeral && terraform destroy   # RDS final snapshot 자동 생성
```

GitHub Actions:
- `spin-up.yml` (workflow_dispatch) — 인프라 전체 + 앱 배포 + smoke test
- `teardown.yml` (workflow_dispatch, confirm 입력 필요) — 인프라 전체 삭제 (RDS snapshot 보존)
- `deploy-backend.yml` / `deploy-bot.yml` — `push main` 시 paths-filter 로 자동 분기

## 3. 다음 작업 (이번 PR 범위 밖)

### N-1. Bastion → SSM Managed Instance 전환  (우선순위: 보통)
- **현재**: bastion EC2 가 SSH 22 포트 + 사용자 IP CIDR 제한으로 운영. SSH 키 회전·관리 부담.
- **목표**: SSM Agent 만 켜진 EC2 + `aws ssm start-session --document-name AWS-StartPortForwardingSessionToRemoteHost` 로 로컬↔RDS/Valkey 터널. SSH 포트 0개.
- **선결**: EC2 IAM Role 에 `AmazonSSMManagedInstanceCore` 첨부, bastion SG ingress 22 제거.

### N-2. CloudWatch alarm + Discord webhook  (우선순위: 보통)
- 크롤러 연속 실패, RDS CPU > 80%, ALB 5xx > 임계, Valkey DataStored > 80% 등 → SNS → Lambda → Discord webhook (관리자 DM 채널).
- 봇 측 `ADMIN_DISCORD_IDS` 와 별개 채널.

### N-3. RDS final snapshot 자동 복원  (우선순위: 낮음)
- **현재**: teardown 시 final snapshot 생성됨. 다음 spin-up 은 비어있는 신규 인스턴스.
- **목표**: `spin-up.yml` 입력 `restore_from_latest_snapshot=true` 시 `aws_db_instance.snapshot_identifier` 로 최신 final snapshot 자동 복원.

### N-4. S3 + CloudFront frontend 배포  (ADR-A3, 범위 분리)
- 별 PR. 현재 `deploy-frontend.yml` 가 어떻게 동작하는지 먼저 점검 필요.

### N-5. 멀티 환경 (staging)  (우선순위: 낮음)
- 현재 prod 단일. Terraform workspace 또는 `infra/envs/{prod,staging}/*.tfvars` 분리.

## 4. 잠재 부채 / 한계

### D-1. NAT gateway 없음 — 모든 EC2 가 public subnet 배치
- **트레이드오프**: NAT GW 월 ~$35 절감 vs private subnet EC2 사용 불가.
- **현재 안전장치**: EC2 SG ingress 는 8000(ALB SG)/22(Bastion SG)만 허용. 인터넷에서 직접 SSH/HTTP 불가능.
- **위험**: EC2 가 public IP 노출되어 있어 정찰 트래픽은 받음. SG 가 1차 방어.

### D-2. GitHub runner 가 private subnet 직통 접근 불가
- **현재**: `alembic upgrade head` 를 bastion 경유 SSH 터널로 실행. 워크플로 한 step 증가.
- **대안**: self-hosted runner (EC2 안) — 운영 부담 증가로 미채택.

### D-3. Valkey serverless 비용 변동
- ECPU + storage 가산 과금. 트래픽 폭증 시 예상 외 비용. **CloudWatch alarm 등록(N-2) 까지 수동 모니터링**.

### D-4. RDS db.t4g.micro — burst credit 의존
- 평시 트래픽이 baseline 넘으면 credit 소진 → throttle. 알림 폭증 시각대(매시 정각 등)에 모니터링 필요.

### D-5. ACM cross-account DNS 자동화는 1회성에 가까움
- Route53 호스팅 존이 별도 계정이라 `assume_role` 로 검증 레코드 생성. 호스팅 존 이전 시 `Route53-kuhelper-CrossAccount-Role` trust 갱신 필요.

## 5. 변경 이력

- 2026-05-25 — 문서 신설. infra 재구성 PR(issue #34) 시작.
