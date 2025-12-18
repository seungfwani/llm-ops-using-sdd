# KServe 인증서 오류 해결 가이드

## 에러 상황

배포 중 다음 에러가 발생한 경우:

```
failed calling webhook "inferenceservice.kserve-webhook-server.defaulter": 
could not get REST client: unable to load root certificates: 
unable to parse bytes as PEM block
```

이는 KServe webhook의 인증서가 손상되었거나 잘못 설정된 경우입니다.

## 해결 방법

### 옵션 1: KServe 인증서 수정 (KServe 계속 사용)

인증서를 재생성하여 문제를 해결합니다:

```bash
# KServe 인증서 수정
cd infra/scripts
chmod +x setup-kserve.sh
./setup-kserve.sh kserve fix-cert
```

이 명령어는:
1. 기존 인증서 secret 삭제
2. 새로운 self-signed 인증서 생성
3. KServe controller pod 재시작

**상태 확인:**
```bash
# KServe 상태 확인
./setup-kserve.sh kserve check

# 또는 수동 확인
kubectl get pods -n kserve
kubectl get secret kserve-webhook-server-cert -n kserve
```

### 옵션 2: KServe 비활성화 (빠른 해결)

KServe 없이 Raw Kubernetes Deployment를 사용합니다.

**1. 환경 변수 설정:**

`backend/.env` 파일에 추가:
```bash
USE_KSERVE=false
```

**2. 백엔드 재시작:**

설정 변경 후 백엔드를 재시작해야 합니다.

**장점:**
- KServe 설치 문제와 무관하게 바로 사용 가능
- 더 간단한 구성
- 기본적인 서빙 기능은 모두 지원

**단점:**
- KServe의 고급 기능(canary 배포, 트래픽 분할 등) 사용 불가

### 옵션 3: KServe 재설치

인증서 문제가 지속되는 경우 KServe를 완전히 재설치:

```bash
cd infra/scripts
./setup-kserve.sh kserve reinstall
```

재설치 후:
1. 인증서가 자동으로 생성됩니다
2. KServe controller가 정상적으로 시작됩니다

## 현재 상태 확인

```bash
# KServe 상태 확인
cd infra/scripts
./setup-kserve.sh kserve check

# 수동 확인
kubectl get pods -n kserve
kubectl logs -n kserve -l control-plane=kserve-controller-manager --tail=50
kubectl get validatingwebhookconfiguration | grep kserve
kubectl get mutatingwebhookconfiguration | grep kserve
```

## 권장 사항

**개발/테스트 환경:**
- 옵션 2 (KServe 비활성화) 권장
- 더 간단하고 빠름
- KServe의 고급 기능이 필요하지 않은 경우

**프로덕션 환경:**
- 옵션 1 (인증서 수정) 또는 옵션 3 (재설치) 시도
- KServe의 canary 배포, 트래픽 분할 등 고급 기능이 필요한 경우

## 추가 문제 해결

여전히 문제가 발생하는 경우:

1. **KServe namespace 확인:**
   ```bash
   kubectl get namespace kserve
   ```

2. **Webhook 서비스 확인:**
   ```bash
   kubectl get svc -n kserve kserve-webhook-server-service
   kubectl get endpoints -n kserve kserve-webhook-server-service
   ```

3. **Webhook 설정 확인:**
   ```bash
   kubectl get validatingwebhookconfiguration inferenceservice.kserve-webhook-server.defaulter -o yaml
   ```

4. **Controller 로그 확인:**
   ```bash
   kubectl logs -n kserve -l control-plane=kserve-controller-manager --tail=100
   ```

## 참고 자료

- [KServe 설치 문제 해결 가이드](../infra/scripts/README-KSERVE-ISSUES.md)
- [KServe 공식 문서](https://kserve.github.io/website/)

