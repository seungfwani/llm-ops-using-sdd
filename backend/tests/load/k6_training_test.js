import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const trainingLatency = new Trend('training_latency');

export const options = {
  stages: [
    { duration: '1m', target: 5 },    // Ramp up to 5 users
    { duration: '3m', target: 20 },   // Stay at 20 users
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '3m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'], // 95% of requests should be below 5s (training jobs take longer)
    http_req_failed: ['rate<0.05'],     // Error rate should be less than 5%
    errors: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/llm-ops/v1';
const USER_ID = __ENV.USER_ID || 'test-user';
const USER_ROLES = __ENV.USER_ROLES || 'admin,researcher';

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-User-Id': USER_ID,
    'X-User-Roles': USER_ROLES,
  };

  // Test training jobs list
  const listRes = http.get(`${BASE_URL}/training/jobs`, { headers });
  const listSuccess = check(listRes, {
    'list jobs status is 200': (r) => r.status === 200,
    'list jobs has envelope': (r) => {
      const body = JSON.parse(r.body);
      return body.status && body.message !== undefined && body.data !== undefined;
    },
  });
  errorRate.add(!listSuccess);
  trainingLatency.add(listRes.timings.duration);

  sleep(2);

  // Test training job submission (if we have model and dataset IDs)
  if (__ENV.MODEL_ID && __ENV.DATASET_ID) {
    const submitPayload = JSON.stringify({
      modelId: __ENV.MODEL_ID,
      datasetId: __ENV.DATASET_ID,
      jobType: 'finetune',
      resourceProfile: {
        gpuCount: 1,
        gpuType: 'nvidia-tesla-v100',
        maxDuration: 60,
      },
      hyperparameters: {
        learning_rate: 0.0001,
        batch_size: 32,
      },
    });
    const submitRes = http.post(`${BASE_URL}/training/jobs`, submitPayload, { headers });
    const submitSuccess = check(submitRes, {
      'submit job status is 200': (r) => r.status === 200,
      'submit job has envelope': (r) => {
        const body = JSON.parse(r.body);
        return body.status && body.message !== undefined;
      },
    });
    errorRate.add(!submitSuccess);
    trainingLatency.add(submitRes.timings.duration);
  }

  sleep(3);
}

export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data, null, 2),
    'training_load_test_summary.json': JSON.stringify(data, null, 2),
  };
}

