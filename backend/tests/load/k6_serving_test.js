import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const servingLatency = new Trend('serving_latency');

export const options = {
  stages: [
    { duration: '1m', target: 10 },   // Ramp up to 10 users
    { duration: '3m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '3m', target: 100 }, // Stay at 100 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests should be below 2s
    http_req_failed: ['rate<0.05'],    // Error rate should be less than 5%
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

  // Test serving endpoints list
  const listRes = http.get(`${BASE_URL}/serving/endpoints`, { headers });
  const listSuccess = check(listRes, {
    'list endpoints status is 200': (r) => r.status === 200,
    'list endpoints has envelope': (r) => {
      const body = JSON.parse(r.body);
      return body.status && body.message !== undefined && body.data !== undefined;
    },
  });
  errorRate.add(!listSuccess);
  servingLatency.add(listRes.timings.duration);

  sleep(1);

  // Test serving endpoint creation (if we have a model ID)
  if (__ENV.MODEL_ID) {
    const deployPayload = JSON.stringify({
      modelId: __ENV.MODEL_ID,
      environment: 'dev',
      route: `/llm-ops/v1/serve/test-${__VU}-${__ITER}`,
      minReplicas: 1,
      maxReplicas: 3,
    });
    const deployRes = http.post(`${BASE_URL}/serving/endpoints`, deployPayload, { headers });
    const deploySuccess = check(deployRes, {
      'deploy endpoint status is 200': (r) => r.status === 200,
      'deploy endpoint has envelope': (r) => {
        const body = JSON.parse(r.body);
        return body.status && body.message !== undefined;
      },
    });
    errorRate.add(!deploySuccess);
    servingLatency.add(deployRes.timings.duration);
  }

  sleep(1);
}

export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data, null, 2),
    'serving_load_test_summary.json': JSON.stringify(data, null, 2),
  };
}

