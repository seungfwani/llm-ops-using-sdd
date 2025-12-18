# 📚 Documentation Index

## 구조
- [api/](api/) : API 명세 및 연동 관련 문서
- [architecture/](architecture/) : 시스템 다이어그램/흐름 등
- [database/](database/) : DB 설계 및 저장 규칙
- [integrations/](integrations/) : 외부/레거시 시스템 연동
- [operations/](operations/) : 배포, 운영, 장애 대응, 서빙 롤백 등
- [requirements/](requirements/) : 필수/최소 요구 사항, 요구 분석
- [security/](security/) : 보안/비밀관리 규정
- [serving/](serving/) : 서빙 서비스 예시와 트레이닝 명세
- 기타 정책/헌장: Constitution.txt

## 목차

### api/
- [integrations.md](api/integrations.md)

### architecture/
- [component-diagram.md](architecture/component-diagram.md)
- [dataflow-diagram.md](architecture/dataflow-diagram.md)
- [topology-diagram.md](architecture/topology-diagram.md)

### database/
- [DB_STORED_FIELDS.md](database/DB_STORED_FIELDS.md)

### integrations/
- [EXTERNAL_K8S_INTEGRATION.md](integrations/EXTERNAL_K8S_INTEGRATION.md)
- [legacy-cleanup.md](integrations/legacy-cleanup.md)
- [troubleshooting.md](integrations/troubleshooting.md)
- [upgrade-procedures.md](integrations/upgrade-procedures.md)

### operations/
- [HELM_DEPLOYMENT.md](operations/HELM_DEPLOYMENT.md)
- [KSERVE-CERT-FIX.md](operations/KSERVE-CERT-FIX.md)
- [SERVING_DELETION_LOGIC.md](operations/SERVING_DELETION_LOGIC.md)
- [SERVING_REDEPLOY_FIX_PLAN.md](operations/SERVING_REDEPLOY_FIX_PLAN.md)
- [SERVING_REDEPLOY_FLOW.md](operations/SERVING_REDEPLOY_FLOW.md)
- [SERVING_REDEPLOY_LOGIC.md](operations/SERVING_REDEPLOY_LOGIC.md)

### requirements/
- [MINIMUM_REQUIREMENTS.md](requirements/MINIMUM_REQUIREMENTS.md)
- [PRD.md](requirements/PRD.md)
- [필수_기능_목록.md](requirements/필수_기능_목록.md)

### security/
- [SECRET_MANAGEMENT.md](security/SECRET_MANAGEMENT.md)

### serving/
- [serving-examples.md](serving/serving-examples.md)
- [training-serving-spec.md](serving/training-serving-spec.md)

### 루트 주요 문서
- [Constitution.txt](Constitution.txt)

