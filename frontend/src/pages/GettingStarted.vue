<template>
  <section class="getting-started">
    <header>
      <h1>Getting Started: LLM Ops 플랫폼 빠른 시작</h1>
      <p class="subtitle">
        이 페이지는 &ldquo;처음 들어와서 무엇을 눌러야 하는지&rdquo;를 단계별로 안내합니다.
        아래 순서대로 따라 하면, 예제 데이터셋과 모델로 학습을 돌리고 서빙까지 테스트할 수 있습니다.
      </p>
    </header>

    <div class="steps">
      <article class="step-card">
        <h2>1. 데이터셋 준비 및 업로드</h2>
        <p class="step-intro">
          먼저 학습에 사용할 데이터셋을 등록합니다. CSV / JSONL 형식의 파일을 사용할 수 있고,
          리포지토리에서는 <code>examples/datasets</code> 에 샘플이 포함되어 있습니다.
        </p>
        <ol>
          <li>
            상단 메뉴에서 <strong>Datasets</strong> 를 클릭해 <strong>Dataset Catalog</strong> 페이지로 이동합니다.
          </li>
          <li>
            우측 상단에서 <strong>New Dataset</strong> 버튼을 클릭합니다.
          </li>
          <li>
            폼을 다음 기준으로 채웁니다:
            <ul>
              <li><strong>Name</strong>: 데이터셋 이름 (예: <code>customer-support-sample</code>)</li>
              <li><strong>Version</strong>: 버전 태그 (예: <code>v1</code>, <code>2025-01-01</code>)</li>
              <li><strong>Owner Team</strong>: 책임 팀명 (예: <code>ml-platform</code>)</li>
            </ul>
          </li>
          <li>
            파일 업로드 섹션에서:
            <ul>
              <li>
                지원 형식: <strong>CSV</strong> (<code>.csv</code>), <strong>JSON Lines</strong> (<code>.jsonl</code>),
                필요 시 Parquet(<code>.parquet</code>)
              </li>
              <li>
                예제 파일:
                <code>examples/datasets/customer-support-sample.csv</code>,
                <code>examples/datasets/code-generation-sample.jsonl</code>
              </li>
              <li>
                한 번에 여러 파일을 올릴 수 있지만, 처음에는 단일 파일로 동작을 확인하는 것을 권장합니다.
              </li>
            </ul>
          </li>
          <li>
            저장 후, 상세 페이지에서:
            <ul>
              <li><strong>Dataset Preview</strong> 영역에서 스키마/샘플 행이 보이면 성공</li>
              <li><strong>Validation Results</strong> 에서 PII/Quality 정보가 채워지는지 확인</li>
            </ul>
          </li>
        </ol>
      </article>

      <article class="step-card">
        <h2>2. 모델 등록 또는 Hugging Face에서 임포트</h2>
        <p class="step-intro">
          학습에 사용할 베이스 모델을 카탈로그에 등록합니다. 이미 Hugging Face 모델을 사용한다면
          &ldquo;Import from Registry&rdquo; 기능을 쓰면 편합니다.
        </p>
        <h3>2-1. Hugging Face 모델 임포트 (권장)</h3>
        <ol>
          <li>상단 메뉴에서 <strong>Models</strong> 를 클릭해 <strong>Model Catalog</strong> 로 이동합니다.</li>
          <li>우측 상단에서 <strong>Import from Registry</strong> 를 클릭합니다.</li>
          <li>
            폼을 다음 기준으로 채웁니다:
            <ul>
              <li><strong>Registry</strong>: 기본값 <code>huggingface</code> 그대로 사용</li>
              <li>
                <strong>Registry Model ID</strong>:
                예: <code>microsoft/DialoGPT-medium</code>, <code>meta-llama/Llama-3.1-8B</code> 등
              </li>
              <li><strong>Registry Version</strong>: 태그/브랜치가 필요할 때만(예: <code>main</code>)</li>
              <li><strong>Catalog Name</strong>: 비워두면 ID의 마지막 세그먼트를 자동 사용</li>
              <li><strong>Catalog Version</strong>: 예: <code>1.0.0</code></li>
              <li><strong>Model Type</strong>: 외부 Hub에서 가져온 모델은 보통 <code>external</code> 또는 <code>base</code></li>
              <li><strong>Owner Team</strong>: 예: <code>ml-platform</code></li>
            </ul>
          </li>
          <li>제출 후 성공 메시지가 나오면, 모델 상세 페이지로 이동해 Storage URI / Registry Links 를 확인합니다.</li>
        </ol>

        <h3>2-2. 내부 모델 수동 등록 (선택)</h3>
        <p>
          사내에서 이미 학습한 모델이 있고, 스토리지 경로만 알고 있다면
          <strong>New Model</strong> 버튼을 사용해 수동으로 등록할 수 있습니다.
          이 경우 <strong>Storage URI</strong> 에 <code>s3://...</code> 또는 <code>gs://...</code> 같은 실제 경로를 넣어야 합니다.
        </p>
      </article>

      <article class="step-card">
        <h2>3. 트레이닝 잡 생성 (Training Jobs)</h2>
        <p class="step-intro">
          준비된 데이터셋과 모델을 사용해 학습 잡을 생성합니다. 이때 MLflow를 통한 실험 추적도 자동으로 연동됩니다.
        </p>
        <ol>
          <li>상단 메뉴에서 <strong>Training</strong> 을 클릭합니다.</li>
          <li>우측 상단에서 <strong>New Job</strong> 버튼을 클릭해 <strong>Submit Training Job</strong> 화면으로 이동합니다.</li>
          <li>
            <strong>Job Configuration</strong> 섹션:
            <ul>
              <li><strong>Job Type</strong>: 처음에는 <code>finetune</code> 선택을 권장</li>
              <li><strong>Base Model</strong>: 2단계에서 등록한 모델 선택</li>
              <li><strong>Dataset</strong>: 1단계에서 업로드한 데이터셋 선택</li>
              <li>
                <strong>Architecture Configuration (JSON)</strong>:
                - <code>from_scratch</code>, <code>pretrain</code> 타입에서만 필수.
                처음에는 비워두고 <code>finetune</code> 플로우만 사용하는 것을 추천합니다.
              </li>
            </ul>
          </li>
          <li>
            <strong>Resource Configuration</strong> 섹션:
            <ul>
              <li>
                <strong>Use GPU Resources</strong>:
                - GPU 클러스터가 있다면 체크 유지<br>
                - 로컬/테스트 환경에서 GPU가 없으면 체크 해제 후 CPU 전용 설정 사용
              </li>
              <li>
                GPU 사용 시:
                <ul>
                  <li><strong>GPU Count</strong>: 노드당 GPU 개수 (예: 1)</li>
                  <li><strong>GPU Type</strong>: 클러스터에서 제공하는 타입 선택 (예: <code>nvidia-tesla-v100</code>)</li>
                  <li><strong>Number of Nodes</strong>:
                    <code>distributed</code> 잡일 때만 필수, 아닐 때는 비워둡니다.
                  </li>
                </ul>
              </li>
              <li>
                CPU 전용 시:
                <ul>
                  <li><strong>CPU Cores</strong>: 예: <code>4</code></li>
                  <li><strong>Memory</strong>: 예: <code>8Gi</code></li>
                </ul>
              </li>
              <li><strong>Max Duration (minutes)</strong>: 잡 타임아웃 (예: <code>60</code>)</li>
            </ul>
          </li>
          <li>
            <strong>Additional Hyperparameters (JSON)</strong> 에는
            <code>{"learning_rate": 5e-5, "batch_size": 8}</code> 와 같이
            학습에 필요한 값들을 JSON 형식으로 넣을 수 있습니다. 비워두면 기본값을 사용합니다.
          </li>
          <li>제출 후, <strong>Training Jobs</strong> 리스트에서 상태가 <code>queued → running → succeeded</code> 로 변하는지 확인합니다.</li>
        </ol>
      </article>

      <article class="step-card">
        <h2>4. 서빙 엔드포인트 배포 (Serving Endpoint)</h2>
        <p class="step-intro">
          학습이 끝난 모델을 서빙 엔드포인트로 배포합니다. 이때 KServe / Ray Serve 같은 프레임워크가 내부에서 사용됩니다.
        </p>
        <ol>
          <li>상단 메뉴에서 <strong>Serving</strong> 을 클릭해 <strong>Serving Endpoints</strong> 페이지로 이동합니다.</li>
          <li>우측 상단에서 <strong>New Endpoint</strong> 버튼을 클릭해 <strong>Deploy Serving Endpoint</strong> 페이지로 이동합니다.</li>
          <li>
            기본 필드:
            <ul>
              <li><strong>Model</strong>: 배포할 모델 선택 (직접 등록/임포트한 모델)</li>
              <li><strong>Environment</strong>: <code>dev</code> / <code>stg</code> / <code>prod</code> 중 하나</li>
              <li><strong>Route</strong>: 엔드포인트 경로 (예: <code>/llm-ops/v1/serve/chat-model</code>)</li>
              <li><strong>Min Replicas</strong> / <strong>Max Replicas</strong>: 예: <code>1</code> / <code>3</code></li>
            </ul>
          </li>
          <li>
            <strong>Serving Framework</strong>:
            <ul>
              <li>비워두면 서버 설정의 기본 프레임워크(KServe 등)를 사용합니다.</li>
              <li>특정 프레임워크를 테스트하려면 목록에서 선택합니다.</li>
            </ul>
          </li>
          <li>
            <strong>Autoscaling Configuration</strong>:
            <ul>
              <li><strong>Target Latency (ms)</strong>: 응답 지연 기준 (예: <code>1000</code>)</li>
              <li><strong>GPU/CPU Utilization (%)</strong>: 자원 사용률 기준. 처음에는 비워두고 기본값 사용 가능</li>
            </ul>
          </li>
          <li>
            <strong>Use GPU Resources</strong>:
            <ul>
              <li>GPU 클러스터가 있다면 체크 상태 유지</li>
              <li>GPU가 없는 PoC 환경이라면 체크 해제 후 CPU Request/Limit만 설정</li>
            </ul>
          </li>
          <li>
            <strong>CPU / Memory Request/Limit</strong>:
            <ul>
              <li>형식 예: <code>cpuRequest=2</code>, <code>cpuLimit=4</code>, <code>memoryRequest=4Gi</code>, <code>memoryLimit=8Gi</code></li>
              <li>비워두면 서버 기본값을 사용합니다.</li>
            </ul>
          </li>
          <li>
            <strong>Serving Runtime Image</strong>:
            <ul>
              <li>비워두면 서버 기본 이미지 사용</li>
              <li>vLLM/TGI 등을 테스트하려면 준비된 옵션 중 하나를 선택</li>
              <li><strong>Custom image...</strong> 선택 시, <code>my-registry.io/my-image:tag</code> 형식으로 직접 입력</li>
            </ul>
          </li>
          <li>배포 후 <strong>Serving Endpoints</strong> 리스트에서 상태가 <code>deploying → healthy</code> 가 되는지 확인합니다.</li>
        </ol>
      </article>

      <article class="step-card">
        <h2>5. Chat으로 엔드포인트 테스트</h2>
        <p class="step-intro">
          배포된 엔드포인트가 실제로 응답하는지, Chat UI를 통해 간단히 확인할 수 있습니다.
        </p>
        <ol>
          <li>상단 메뉴에서 <strong>Serving</strong> → <strong>Chat</strong> 링크를 클릭하거나, URL <code>/serving/chat</code> 으로 이동합니다.</li>
          <li>
            <strong>Select Endpoint</strong> 드롭다운에서 상태가 <code>healthy</code> 인 엔드포인트를 선택합니다.
          </li>
          <li>
            우측 하단 입력창에 질문을 입력하고 <strong>Enter</strong> 또는 <strong>Send</strong> 버튼을 누릅니다.
          </li>
          <li>
            상단의 <strong>Temperature</strong>, <strong>Max Tokens</strong> 옵션으로 생성 다양성과 응답 길이를 조절할 수 있습니다.
          </li>
        </ol>
      </article>
    </div>

    <footer class="footnote">
      <p>
        보다 상세한 설치/운영 안내는 리포지토리의 <code>docs/</code> 및
        <code>specs/001-open-source-integration/quickstart.md</code> 를 참고하세요.
        이 페이지는 &ldquo;최소한 여기까지만 따라 하면 데모가 돈다&rdquo;는 관점으로 구성되어 있습니다.
      </p>
    </footer>
  </section>
</template>

<script setup lang="ts">
// 정적 온보딩 페이지 - 별도의 로직 없음
</script>

<style scoped>
.getting-started {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem;
}

header {
  margin-bottom: 2rem;
}

header h1 {
  margin: 0 0 0.75rem 0;
  font-size: 1.8rem;
}

.subtitle {
  margin: 0;
  color: #555;
  line-height: 1.6;
  font-size: 0.95rem;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.step-card {
  background: #ffffff;
  border-radius: 8px;
  padding: 1.5rem 1.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  border: 1px solid #e5e5e5;
}

.step-card h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.3rem;
}

.step-card h3 {
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  font-size: 1.05rem;
}

.step-intro {
  margin: 0 0 0.75rem 0;
  color: #555;
  font-size: 0.95rem;
}

ol {
  padding-left: 1.25rem;
  margin: 0.25rem 0 0 0;
}

ol > li {
  margin-bottom: 0.5rem;
  line-height: 1.6;
}

ul {
  padding-left: 1.1rem;
  margin: 0.25rem 0 0.25rem 0;
}

ul li {
  margin-bottom: 0.25rem;
}

code {
  font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
  font-size: 0.9em;
  background: #f5f5f5;
  padding: 0.1rem 0.25rem;
  border-radius: 3px;
}

.footnote {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #eee;
  font-size: 0.9rem;
  color: #666;
}
</style>


