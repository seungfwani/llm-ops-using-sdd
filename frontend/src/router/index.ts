import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/getting-started',
    },
    {
      path: '/getting-started',
      component: () => import('@/pages/GettingStarted.vue'),
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
      path: '/catalog/models/import',
      component: () => import('@/pages/catalog/ModelImport.vue'),
    },
    {
      path: '/catalog/models/:id',
      component: () => import('@/pages/catalog/ModelDetail.vue'),
    },
    {
      path: '/catalog/datasets',
      component: () => import('@/pages/catalog/DatasetList.vue'),
    },
    {
      path: '/catalog/datasets/new',
      component: () => import('@/pages/catalog/DatasetCreate.vue'),
    },
    {
      path: '/catalog/datasets/:id',
      component: () => import('@/pages/catalog/DatasetDetail.vue'),
    },
    {
      path: '/catalog/datasets/:id/versions/compare',
      component: () => import('@/pages/catalog/DatasetVersionCompare.vue'),
    },
    {
      path: '/training/jobs',
      component: () => import('@/pages/training/JobList.vue'),
    },
    {
      path: '/training/jobs/submit',
      component: () => import('@/pages/training/JobSubmit.vue'),
    },
    {
      path: '/training/jobs/:id',
      component: () => import('@/pages/training/JobDetail.vue'),
    },
    {
      path: '/experiments/:id',
      component: () => import('@/pages/training/ExperimentDetail.vue'),
    },
    {
      path: '/experiments/search',
      component: () => import('@/components/ExperimentSearch.vue'),
    },
    {
      path: '/experiments/compare',
      component: () => import('@/pages/training/ExperimentCompare.vue'),
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
      path: '/prompts',
      name: 'PromptList',
      component: () => import('@/pages/prompts/PromptList.vue'),
    },
    {
      path: '/prompts/create',
      name: 'PromptCreate',
      component: () => import('@/pages/prompts/PromptCreate.vue'),
    },
    {
      path: '/prompts/:id',
      name: 'PromptDetail',
      component: () => import('@/pages/prompts/PromptDetail.vue'),
      props: true,
    },
    {
      path: '/prompts/experiments',
      component: () => import('@/pages/prompts/ExperimentCreate.vue'),
    },
    {
      path: '/workflows/pipelines',
      component: () => import('@/pages/workflows/PipelineList.vue'),
    },
    {
      path: '/workflows/pipelines/create',
      component: () => import('@/pages/workflows/PipelineCreate.vue'),
    },
    {
      path: '/workflows/pipelines/:id',
      component: () => import('@/pages/workflows/PipelineDetail.vue'),
    },
    {
      path: '/admin/integrations',
      component: () => import('@/pages/admin/IntegrationSettings.vue'),
    },
  ],
});

export default router;

