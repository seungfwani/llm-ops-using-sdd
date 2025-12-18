## 0. 문서 목적

이 문서는 모비젠 LLM-Ops 플랫폼에서  
- **모델 트레이닝 방식(Pre-training / Fine-tuning / RAG / RLHF 등)**에 따라  
- **어떤 컨테이너 이미지로 학습하고**,  
- **어떤 구조의 모델만 허용하며**,  
- **어떤 형식의 아규먼트/데이터/배포 스펙을 사용해야 하는지**  

를 규격화하기 위한 **운영 스펙(Standard Spec)**이다.

---

## 1. 공통 개념 정의

### 1.1 Job 타입

```text
- PRETRAIN      : 처음부터 LLM을 학습
- SFT           : Instruction/대화/도메인 Task용 Supervised Fine-tuning
- RAG_TUNING    : RAG용 retriever/reader 튜닝
- RLHF          : Reward Modeling + PPO 등 강화학습
- EMBEDDING     : 임베딩 모델 학습
```

### 1.2 공통 엔티티

- **ModelFamily**: 플랫폼이 지원하는 모델 계열 (예: llama, mistral, gemma …)
- **TrainImage**: 트레이닝용 Docker 이미지
- **ServeImage**: 서빙용 Docker 이미지
- **DatasetRef**: 데이터셋 식별자(버전 포함)
- **ModelArtifact**: 학습 결과 산출물(모델 파일 + 메타데이터)

---

## 2. 글로벌 규칙 (필수)

### 2.1 모델 구조(ModelFamily) 화이트리스트

```yaml
model_families:
  - id: llama
    hf_arch: LlamaForCausalLM
    min_version: "3.0"
  - id: mistral
    hf_arch: MistralForCausalLM
  - id: gemma
    hf_arch: GemmaForCausalLM
  - id: bert
    hf_arch: BertModel
    usage: ["EMBEDDING", "ENCODER_ONLY"]
```

> ✅ 위에 정의된 **model_families에 포함되지 않는 구조는 플랫폼에서 학습/배포 불가**

---

### 2.2 컨테이너 이미지 버전 관리

```yaml
images:
  train:
    PRETRAIN: "registry/llm-train-pretrain:pytorch2.1-cuda12.1-v1"
    SFT: "registry/llm-train-sft:pytorch2.1-cuda12.1-v1"
    RAG_TUNING: "registry/llm-train-rag:pytorch2.1-cuda12.1-v1"
    RLHF: "registry/llm-train-rlhf:pytorch2.1-cuda12.1-v1"
    EMBEDDING: "registry/llm-train-embedding:pytorch2.1-cuda12.1-v1"
  serve:
    GENERATION: "registry/llm-serve:vllm-0.5.0-cuda12.1"
    RAG: "registry/llm-serve-rag:vllm-0.5.0-cuda12.1"
```

> ✅ 각 Job 타입은 **정해진 TrainImage만 사용 가능**  
> ✅ Serving도 GENERATION / RAG 등 용도별로 ServeImage를 고정

---

### 2.3 Dataset 규격 & 버전

```yaml
dataset:
  registry: "s3://llm-datasets"  # or DVC remote
  required_fields:
    - name          # ex) instructions-korean-v1
    - version       # ex) v1, v2
    - type          # ex) pretrain_corpus, sft_pair, rag_qa, rlhf_pair
    - storage_uri   # 실제 위치
    - schema_ref    # 데이터 포맷 스키마
```

예시:

```yaml
datasets:
  - name: "korean-web-corpus"
    version: "v3"
    type: "pretrain_corpus"
    storage_uri: "s3://llm-datasets/korean-web-corpus/v3"
  - name: "enterprise-instruction"
    version: "v1"
    type: "sft_pair"
    storage_uri: "s3://llm-datasets/enterprise-instruction/v1"
```

---

## 3. Training Job 스펙 (공통 스키마)

### 3.1 공통 필드 스키마

```yaml
TrainJobSpec:
  job_type:        # PRETRAIN | SFT | RAG_TUNING | RLHF | EMBEDDING
  model_family:    # llama | mistral | gemma | bert ...
  base_model_ref:  # PRETRAIN일 경우 null 가능
  train_image:     # 자동 결정 (job_type 기반), 오버라이드 금지 or 제한
  dataset_ref:     # datasets 중 하나 (name+version 조합)
  hyperparams:
    lr: float
    batch_size: int
    num_epochs: int
    max_seq_len: int
    precision: "fp16" | "bf16"
  method:          # "full" | "lora" | "qlora"
  resources:
    gpus: int
    gpu_type: string
    nodes: int
  output:
    artifact_name: string
    save_format: "hf" | "safetensors"
```

> ✅ LLM-Ops 플랫폼은 **이 스키마를 벗어나는 Job은 실행 거부** (Validation 단계)

---

## 4. 케이스별 스펙 구조

이제 질문하신 것처럼 **방식별로 구조**를 나눠봅니다.

---

### 4.1 케이스 1: 처음 모델 트레이닝 (PRETRAIN)

#### 4.1.1 Training 스펙

```yaml
PretrainJobSpec extends TrainJobSpec:
  job_type: PRETRAIN
  model_family: llama | mistral | gemma ...
  base_model_ref: null           # 처음 학습이므로 없음
  train_image: images.train.PRETRAIN (고정)
  dataset_ref.type: pretrain_corpus
  hyperparams:
    lr: required
    batch_size: required
    num_epochs: required
    max_seq_len: required
    precision: bf16 | fp16
  method: "full"                  # Pretrain은 풀파라미터가 기본
```

#### 4.1.2 Output & 배포 스펙

```yaml
PretrainOutputSpec:
  artifact_format: "hf"
  artifact_uri: "s3://llm-models/pretrain/{model_family}/{version}"
  serve_target:
    - type: "GENERATION"
      serve_image: images.serve.GENERATION
      constraints:
        max_model_size_gb: 40
        max_seq_len: 4096
```

> 보통 Pretrained 모델은 **곧바로 서비스 배포용이 아니라**,  
> 이후 **SFT, RLHF 등의 베이스 모델**로 사용.

---

## 5. 운영 동작 업데이트 (개발 적용 사항)

- **Serving 삭제 안전장치**
  - K8s 리소스(Deployment/KServe 등) 삭제가 실패하면 DB 엔드포인트 레코드는 삭제하지 않는다.
  - 성공적으로 K8s 리소스가 제거된 경우에만 DB에서 엔드포인트를 제거한다.
  - 실패 시 호출자에게 실패 결과를 반환하여 재시도/수동 정리를 유도한다.

- **Training 모델 목록 정렬**
  - 모델 카탈로그 조회 시 `created_at` 기준 최신 항목이 먼저 노출되도록 정렬한다(내림차순).
  - 추가 정렬 기준이 필요한 경우(예: `updated_at`)는 API/서비스 계층에서 확장할 수 있다.


### 4.2 케이스 2: 베이스 모델 파인튜닝 (SFT)

#### 4.2.1 Training 스펙

```yaml
SftJobSpec extends TrainJobSpec:
  job_type: SFT
  model_family: llama | mistral | gemma
  base_model_ref: "llama-3-8b-pretrain-v1"  # PretrainOutputSpec 중 하나
  train_image: images.train.SFT
  dataset_ref.type: sft_pair
  method: "lora" | "qlora" | "full"
  hyperparams:
    lr: required
    batch_size: required
    num_epochs: required
    max_seq_len: <= base_model.max_position_embeddings
    precision: bf16 | fp16
```

#### 4.2.2 Output & 배포 스펙

```yaml
SftOutputSpec:
  artifact_format: "hf"           # merged 기준
  artifact_uri: "s3://llm-models/sft/{model_name}/{version}"
  lora_artifact_uri: optional     # lora-only artifact 위치
  serve_target:
    - type: "GENERATION"
      serve_image: images.serve.GENERATION
      load_mode: "merged" | "base+adapter"
```

> 규칙 예시  
> - 내부 서비스는 기본: **merged 모델만 배포 허용**  
> - 연구용/실험용: base + LoRA adapter 방식 허용

---

### 4.3 케이스 3: RAG 특화 튜닝 (RAG_TUNING)

#### 4.3.1 Training 스펙

```yaml
RagTuningJobSpec extends TrainJobSpec:
  job_type: RAG_TUNING
  model_family: llama | mistral
  base_model_ref: "llama-3-8b-sft-v1"
  train_image: images.train.RAG_TUNING
  dataset_ref.type: "rag_qa"
  hyperparams:
    lr: required
    batch_size: required
    num_epochs: required
    max_seq_len: <= 4096
  rag:
    retriever_type: "dense" | "sparse"
    retriever_model_ref: "bge-large-v1" # optional
```

#### 4.3.2 Output & 배포 스펙

```yaml
RagOutputSpec:
  artifact_uri: "s3://llm-models/rag/{model_name}/{version}"
  retriever_artifact_uri: "s3://llm-models/retriever/{name}/{version}"
  serve_target:
    - type: "RAG"
      serve_image: images.serve.RAG
      components:
        - "generator"
        - "retriever"
        - "index_client"
```

---

### 4.4 케이스 4: RLHF (RLHF)

#### 4.4.1 Training 스펙

```yaml
RlhfJobSpec extends TrainJobSpec:
  job_type: RLHF
  model_family: llama | mistral
  base_model_ref: "llama-3-8b-sft-v1"
  train_image: images.train.RLHF
  dataset_ref.type: "rlhf_pair"
  hyperparams:
    lr: required
    batch_size: required
    num_epochs: required
    max_seq_len: <= 4096
  rlhf:
    reward_model_ref: "rm-llama-3-8b-v1"
    kl_coeff: float
    ppo_steps: int
```

#### 4.4.2 Output & 배포 스펙

```yaml
RlhfOutputSpec:
  artifact_uri: "s3://llm-models/rlhf/{model_name}/{version}"
  serve_target:
    - type: "GENERATION"
      serve_image: images.serve.GENERATION
```

---

## 5. Deployment Spec (공통)

모든 Training Job은 완료 후 **DeploymentSpec**을 생성할 수 있어야 함.

```yaml
DeploymentSpec:
  model_ref: "llama-3-8b-sft-rag-v2"
  model_family: llama
  job_type: SFT | RAG_TUNING | RLHF | ...
  serve_image: images.serve.GENERATION | images.serve.RAG
  resources:
    gpus: 2
    gpu_memory_gb: 80
  runtime:
    max_concurrent_requests: 256
    max_input_tokens: 4096
    max_output_tokens: 1024
  rollout:
    strategy: "blue-green" | "canary"
    traffic_split:
      old: 90
      new: 10
```

---

## 6. 이 스펙으로 얻는 효과 정리

- **이미지 고정**: job_type별 train/serve 이미지가 명시되어 혼선 없음  
- **모델 구조 규격화**: model_family whitelist로 이상한 구조 차단  
- **아규먼트 스키마화**: YAML/JSON Schema로 검증 가능  
- **케이스별(Pretrain/SFT/RAG/RLHF) 스펙 분리**: 각 방식별 요구조건이 명확  
