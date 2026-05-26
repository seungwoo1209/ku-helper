# infra/packer

ku-helper app/bastion EC2 가 사용할 AMI 를 빌드한다. persistent 모듈의 `data "aws_ami"` 가 가장 최근 `ku-helper-app-*` 을 자동 lookup 한다.

## 산출물

- AMI 이름: `ku-helper-app-{{timestamp}}` (예: `ku-helper-app-1737099900`)
- 베이스: AL2023 x86_64
- 사전 설치: docker, docker compose v2 plugin, amazon-cloudwatch-agent, jq, awscli v2(기본), ssm-agent(기본)
- 사전 배치:
  - `/opt/ku-helper/docker-compose.yml` — backend + bot 2 서비스
  - `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json` — 시스템 로그·메트릭 수집
  - `/etc/systemd/system/ku-helper-app.service` — enable 만, ephemeral EC2 user-data 가 .env 작성·ghcr 로그인 후 start

## 사용

```bash
cd infra/packer

# AWS 자격증명은 OIDC 또는 로컬 ~/.aws/credentials 사용
packer init app.pkr.hcl
packer fmt -recursive .
packer validate app.pkr.hcl
packer build app.pkr.hcl
```

자주 재빌드하지 않는다(compose 파일이 바뀌어도 ephemeral EC2 user-data 단계에서 갱신 가능). docker/cwagent 메이저 업데이트 또는 base OS 패치가 필요할 때만 다시 빌드.

## 변수

| 변수 | 기본값 | 비고 |
| --- | --- | --- |
| `aws_region` | `ap-northeast-2` | ku-helper 리전과 동일해야 함 |
| `ami_name_prefix` | `ku-helper-app` | persistent 모듈 lookup 패턴 변경 시 함께 |
| `instance_type` | `t3.micro` | 빌드용 임시 인스턴스 — 비용 최소 |

## 정리

오래된 AMI 와 그 스냅샷은 별도로 정리하지 않는다(persistent 모듈은 항상 `most_recent`). 비용이 신경 쓰이면 콘솔이나 별도 lambda 로 N+1 세대 deregister.
