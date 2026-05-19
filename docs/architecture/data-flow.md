# 데이터 흐름 (Data Flow)

## 1. 내부 데이터 흐름

본 다이어그램은 EC2 내부에서 API Server와 Bot 컨테이너가 Redis 및 PostgreSQL과 어떻게 연결되는지를 나타낸다.

API Server(FastAPI)는 두 데이터 저장소와 각각 다른 목적으로 통신한다. Redis에는 Discord OAuth2 인증 흐름에서 CSRF 공격을 방지하기 위한 state 토큰을 TTL 기반으로 임시 저장하고, PostgreSQL에는 사용자가 웹 대시보드에서 설정한 알림 조건을 JSONB 형태로 저장한다.

Bot 컨테이너(APScheduler + asyncio.Queue + discord.py)도 두 저장소와 각각 다른 목적으로 통신한다. PostgreSQL을 주기적으로 폴링(polling)하여 활성화된 알림 설정을 감지하고, 데이터 수집 시 공공 API 응답 및 크롤링 결과를 Redis에 캐싱(API response caching)하여 외부 서버에 대한 중복 요청을 방지한다. 이 외에도 Redis는 중복 알림 방지를 위한 쿨다운 키 저장과 크롤러 연속 실패 횟수 카운팅에 활용된다.

두 컨테이너는 서로 직접 통신하지 않으며, PostgreSQL을 매개로 간접적으로 연결된다. API Server가 PostgreSQL에 알림 설정을 저장하면, Bot 컨테이너의 APScheduler가 이를 폴링으로 감지하여 스케줄에 반영하는 구조이다.

## 2. 데이터 흐름 개요

### 흐름 1 : 지하철 알림 조건 설정 → 조건 충족 → 디스코드 DM 발송

* 사용자 로그인 → 알림 조건 설정 → PostgreSQL 저장 + 스케줄 등록 → 공공 API 조회 (Redis 캐시) → 조건 판단 → Discord DM 발송 → 발송 이력 저장
* 사용자가 웹 대시보드에 접속하여 Discord OAuth2로 로그인하면, 서버는 해당 사용자의 Discord ID와 함께 JWT 토큰을 발급한다. 사용자는 대시보드에서 원하는 알림 조건을 설정하고 저장 요청을 전송한다. FastAPI 서버는 이를 수신하여 PostgreSQL에 해당 알림 설정을 JSONB 형태로 저장하고, bot 컨테이너의 APScheduler가 PostgreSQL을 **폴링**하여 새로운/변경된 설정을 감지한다. 이후 스케줄러가 설정된 시간대에 작업을 실행하면, 서울 공공 API로부터 지하철 실시간 도착 정보를 조회하고(Redis 캐시 우선 확인), 조건 충족 여부를 판단한다. 조건이 충족되면 AsyncIO Queue에 발송 작업을 등록하고, 큐가 discord.py를 통해 해당 사용자의 Discord DM으로 임베드 메시지를 전송한다. 발송 완료 후 이력은 PostgreSQL에 기록되어 이후 동일 조건에 대한 중복 발송을 방지하는 데 활용된다.

### 흐름 2 : 시스템 장애 감지 → 관리자 디스코드 DM 발송

* 크롤러/API 실행 → 실패 감지 → 연속 실패 판단 → 관리자 Discord DM 발송 → 장애 이력 저장
* bot 컨테이너의 APScheduler가 주기적으로 데이터 수집 작업(크롤링 또는 공공 API 호출)을 실행하는 과정에서 실패가 발생하면, 해당 실패 횟수를 Redis에 기록한다. 동일 수집 대상에 대해 연속 3회 이상 실패가 감지되면, 시스템은 이를 장애 상황으로 판단하고 asyncio.Queue에 관리자 알림 작업을 등록한다. 큐의 발송 워커가 discord.py를 통해 관리자의 Discord DM으로 에러 로그(실패 대상, 실패 시각, 에러 메시지)를 포함한 임베드 메시지를 전송한다. 발송 완료 후 장애 이력은 PostgreSQL에 기록되며, 동일 장애에 대한 중복 알림을 방지하기 위해 Redis에 쿨다운 키를 설정한다.
