# infra/helm 배포 가이드

## 개요
- 차트 위치: `infra/helm/llm-ops-platform`.
- 포함 대상: KServe(선택), NVIDIA Device Plugin(선택, time-slicing 기본 설정), PostgreSQL, Redis, MinIO, MinIO 버킷 생성 Job(포스트 훅).
- 목적: 앱 워크로드가 아니라 **플랫폼 인프라 의존성**을 한 번에 세팅하는 용도.
- KServe용 self-signed webhook 인증서 패치와 기본 배포 모드(Standard) 설정이 post-install/upgrade 훅으로 실행됨.

## 사전 요구사항
- Helm 3.12+, kubectl, 클러스터 관리자 권한(ClusterRole/ClusterRoleBinding, namespace 생성, webhook/CRD 접근 필요).
- 대상 네임스페이스에 대한 쓰기 권한.
- 기본값은 NodePort(5432, 30001 / 9000, 30002 / 9001, 30003)를 사용하므로 방화벽/보안그룹 확인.

## 값 구조 빠르게 보기

```1:45:infra/helm/llm-ops-platform/values.yaml
kserve:
  enabled: true
  namespaceOverride: ""
  version: v0.16.0
  setDefaultDeploymentMode: true
  selfSignedCert:
    enabled: true
    serviceName: kserve-webhook-server-service
    secretName: kserve-webhook-server-cert
    image: bitnami/kubectl:1.29
gpuPlugin:
  enabled: true
nvidia-device-plugin:
  namespaceOverride: kube-system
  args:
    - --fail-on-init-error=false
    - --config-file=/config/config.yaml
  config:
    map:
      name: nvidia-device-plugin-config
      data:
        config.yaml: |
          version: v1
          sharing:
            timeSlicing:
              resources:
                - name: nvidia.com/gpu
                  replicas: 10
```

```32:106:infra/helm/llm-ops-platform/values.yaml
dependencies:
  postgresql:
    enabled: true
    storage: 5Gi
    image: postgres:16-alpine
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 250m
        memory: 256Mi
    service:
      type: NodePort
      port: 5432
      nodePort: 30001
    secret:
      user: llmops
      password: password
      db: llmops
  redis:
    enabled: true
    image: redis:7-alpine
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 200m
        memory: 256Mi
    service:
      type: ClusterIP
      port: 6379
  minio:
    enabled: true
    storage: 50Gi
    image: minio/minio:latest
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
      limits:
        cpu: 250m
        memory: 512Mi
    service:
      type: NodePort
      ports:
        api: 9000
        console: 9001
      nodePorts:
        api: 30002
        console: 30003
    secret:
      accessKey: llmops
      secretKey: llmops-secret
objectStore:
  bucket: models
  endpoint: http://minio:9000
  createBucket: true
  jobImage: quay.io/minio/mc:latest
minioBucketJob:
  enabled: true
```

## 빠른 시작 (개발/테스트)
1) 의존성 내려받기
```bash
cd infra/helm/llm-ops-platform
helm dependency update
```
2) 필요한 경우 값을 덮어쓸 `values-dev.yaml` 작성(예: CPU-only, 기본 NodePort 유지)
```yaml
# values-dev.yaml
kserve:
  enabled: false        # KServe 미사용 시 false
gpuPlugin:
  enabled: false        # GPU 없을 때 비활성화
dependencies:
  postgresql:
    service:
      type: NodePort
      nodePort: 30001
  minio:
    service:
      type: NodePort
      nodePorts:
        api: 30002
        console: 30003
objectStore:
  endpoint: http://minio:9000
  bucket: models
```
3) 설치
```bash
helm upgrade --install llm-ops-dev ./llm-ops-platform \
  -n llm-ops-dev --create-namespace \
  -f values-dev.yaml
```
4) 확인
```bash
kubectl get pods -n llm-ops-dev
helm status llm-ops-dev -n llm-ops-dev
```

## 프로덕션 예시 오버라이드
- 서비스 타입을 ClusterIP로 두고 Ingress/Service LB는 별도 구성 권장.
- KServe를 별도 네임스페이스(`kserve`)에 설치하려면 `kserve.namespaceOverride: kserve`.
- GPU time-slicing 조정: `nvidia-device-plugin.config.map.data.config.yaml` 내부 `replicas` 변경.

```yaml
# values-prod.yaml
kserve:
  enabled: true
  namespaceOverride: kserve
gpuPlugin:
  enabled: true
nvidia-device-plugin:
  namespaceOverride: kube-system
  config:
    map:
      data:
        config.yaml: |
          version: v1
          sharing:
            timeSlicing:
              resources:
                - name: nvidia.com/gpu
                  replicas: 4
dependencies:
  postgresql:
    service:
      type: ClusterIP
  redis:
    service:
      type: ClusterIP
  minio:
    service:
      type: ClusterIP
objectStore:
  endpoint: http://minio:9000
  bucket: models
```
설치:
```bash
cd infra/helm/llm-ops-platform
helm dependency update
helm upgrade --install llm-ops-prod ./llm-ops-platform \
  -n llm-ops-prod --create-namespace \
  -f values-prod.yaml
```

## 운영/트러블슈팅 메모
- KServe 훅(Job)과 ClusterRole/Binding을 생성하므로 설치 시 cluster-admin 권한이 필요하다.
- MinIO 버킷 생성 Job은 post-install/upgrade 훅으로 실행되며, 버킷이 이미 있으면 무시한다.
- NodePort 포트가 이미 사용 중이면 `dependencies.*.service.nodePort` 값을 조정한다.
- 기존 MinIO/DB를 재사용하려면 `dependencies.{minio,postgresql}.enabled=false`로 끄고 외부 엔드포인트를 애플리케이션 레이어에서 설정한다.
- 삭제 시: `helm uninstall <release> -n <namespace>` 후 PVC/Secrets를 수동 정리해야 할 수 있다.

## 자주 나는 에러와 해결
- KServe 차트 404: `Chart.yaml`의 kserve repository를 `oci://ghcr.io/kserve/charts`로 바꾸고 `helm pull oci://ghcr.io/kserve/charts/kserve --version 0.16.0 -d charts`, 이후 `helm dependency update`.
- nvidia-device-plugin validation 오류(`A default config must be provided...`): values에 기본 키를 지정한다.
  ```yaml
  nvidia-device-plugin:
    namespaceOverride: kube-system
    config:
      default: config.yaml          # 기본 config 이름
      map:
        name: nvidia-device-plugin-config
        data:
          config.yaml: |
            version: v1
            sharing:
              timeSlicing:
                resources:
                  - name: nvidia.com/gpu
                    replicas: 10
  ```
- nvidia-device-plugin mps template 오류(`wrong type for value; expected string; got map`): MPS 데몬 비활성화.
  ```yaml
  nvidia-device-plugin:
    mps:
      enabled: false
      controlDaemon:
        enabled: false
  ```
- KServe CRD 미설치 문제: 메인 차트에서 서브차트 CRD가 자동 설치되지 않는다. 배포 전에 CRD를 사전 설치한다.
  ```bash
  cd infra/scripts
  ./install-kserve-crds.sh
  # 필요 시 버전 지정: KSERVE_VERSION=0.16.0 ./install-kserve-crds.sh
  ```

