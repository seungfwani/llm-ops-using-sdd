import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/catalog/models',
    },
    {
      path: '/catalog/models',
      component: () => import('@/pages/catalog/ModelList.vue'),
    },
    {
      path: '/catalog/models/new',
      component: () => import('@/pages/catalog/ModelCreate.vue'),
    },
    {
      path: '/catalog/models/:id',
      component: () => import('@/pages/catalog/ModelDetail.vue'),
    },
    {
      path: '/training/jobs',
      component: () => import('@/pages/training/JobSubmit.vue'),
    },
    {
      path: '/training/jobs/:id',
      component: () => import('@/pages/training/JobDetail.vue'),
    },
    {
      path: '/serving/endpoints',
      component: () => import('@/pages/serving/EndpointList.vue'),
    },
    {
      path: '/serving/endpoints/:id',
      component: () => import('@/pages/serving/EndpointDetail.vue'),
    },
    {
      path: '/serving/endpoints/deploy',
      component: () => import('@/pages/serving/EndpointDeploy.vue'),
    },
    {
      path: '/serving/chat',
      component: () => import('@/pages/serving/ChatTest.vue'),
    },
    {
      path: '/serving/chat/:endpointId',
      component: () => import('@/pages/serving/ChatTest.vue'),
    },
    {
      path: '/governance/policies',
      component: () => import('@/pages/governance/PolicyList.vue'),
    },
    {
      path: '/governance/audit',
      component: () => import('@/pages/governance/AuditLogs.vue'),
    },
    {
      path: '/governance/costs',
      component: () => import('@/pages/governance/CostDashboard.vue'),
    },
    {
      path: '/prompts/experiments',
      component: () => import('@/pages/prompts/ExperimentCreate.vue'),
    },
  ],
});

export default router;

