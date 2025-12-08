<template>
  <div class="integration-settings">
    <h1>Integration Settings</h1>
    <p class="description">
      오픈소스 통합(MLflow, KServe, Argo Workflows, Hugging Face Hub, DVC)의
      환경별 설정과 feature flag를 한 눈에 볼 수 있는 관리용 페이지입니다.
      실제 값 변경은 Kubernetes Secret / ConfigMap 또는 .env 수정이 필요합니다.
    </p>

    <section class="cards">
      <article class="card">
        <h2>Experiment Tracking (MLflow)</h2>
        <ul>
          <li><code>EXPERIMENT_TRACKING_ENABLED</code></li>
          <li><code>EXPERIMENT_TRACKING_SYSTEM=mlflow</code></li>
          <li><code>MLFLOW_TRACKING_URI</code></li>
          <li><code>MLFLOW_BACKEND_STORE_URI</code></li>
          <li><code>MLFLOW_DEFAULT_ARTIFACT_ROOT</code></li>
        </ul>
      </article>

      <article class="card">
        <h2>Serving Framework (KServe)</h2>
        <ul>
          <li><code>SERVING_FRAMEWORK_ENABLED</code></li>
          <li><code>SERVING_FRAMEWORK_DEFAULT=kserve</code></li>
          <li><code>USE_KSERVE</code></li>
          <li><code>KSERVE_NAMESPACE</code></li>
        </ul>
      </article>

      <article class="card">
        <h2>Workflow Orchestration (Argo)</h2>
        <ul>
          <li><code>WORKFLOW_ORCHESTRATION_ENABLED</code></li>
          <li><code>WORKFLOW_ORCHESTRATION_SYSTEM=argo_workflows</code></li>
          <li><code>ARGO_WORKFLOWS_ENABLED</code></li>
          <li><code>ARGO_WORKFLOWS_NAMESPACE</code></li>
          <li><code>ARGO_WORKFLOWS_CONTROLLER_SERVICE</code></li>
        </ul>
      </article>

      <article class="card">
        <h2>Model Registry (Hugging Face Hub)</h2>
        <ul>
          <li><code>MODEL_REGISTRY_ENABLED</code></li>
          <li><code>MODEL_REGISTRY_DEFAULT=huggingface</code></li>
          <li><code>HUGGINGFACE_HUB_ENABLED</code></li>
          <li><code>HUGGINGFACE_HUB_TOKEN</code></li>
          <li><code>HUGGINGFACE_HUB_CACHE_DIR</code></li>
        </ul>
      </article>

      <article class="card">
        <h2>Data Versioning (DVC)</h2>
        <ul>
          <li><code>DATA_VERSIONING_ENABLED</code></li>
          <li><code>DATA_VERSIONING_SYSTEM=dvc</code></li>
          <li><code>DVC_ENABLED</code></li>
          <li><code>DVC_REMOTE_NAME</code></li>
          <li><code>DVC_REMOTE_URL</code></li>
          <li><code>DVC_CACHE_DIR</code></li>
        </ul>
      </article>
    </section>

    <section class="hint">
      <h2>운영 가이드</h2>
      <p>
        통합 상태는 <code>/llm-ops/v1/health/integrations</code> 엔드포인트와
        Grafana 대시보드(Integration Status 패널)에서 모니터링할 수 있습니다.
      </p>
      <p>
        롤백이 필요한 경우 <code>docs/integrations/upgrade-procedures.md</code> 와
        <code>backend/scripts/rollback_integrations.py</code> 를 참고하세요.
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.integration-settings {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.description {
  margin-bottom: 16px;
  color: #555;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 16px;
  background-color: #fafafa;
}

.card h2 {
  margin-top: 0;
  margin-bottom: 8px;
  font-size: 1.1rem;
}

.card ul {
  padding-left: 18px;
  margin: 0;
}

.hint {
  margin-top: 24px;
  padding: 16px;
  border-radius: 8px;
  background-color: #f0f7ff;
  border: 1px solid #d0e3ff;
}
</style>


