import { mount, flushPromises } from "@vue/test-utils";
import JobSubmit from "@/pages/training/JobSubmit.vue";
import { trainingClient } from "@/services/trainingClient";
import { catalogClient } from "@/services/catalogClient";

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/services/trainingClient", () => ({
  trainingClient: {
    listGpuTypes: vi.fn().mockResolvedValue({
      status: "success",
      message: "",
      data: {
        gpuTypes: [
          { id: "nvidia-rtx-4090", label: "NVIDIA RTX 4090", enabled: true },
          { id: "nvidia-rtx-a6000", label: "NVIDIA RTX A6000", enabled: true },
        ],
      },
    }),
    submitJob: vi.fn().mockResolvedValue({ status: "success", message: "", data: { id: "job-1" } }),
    listJobs: vi.fn(),
    getJob: vi.fn(),
    cancelJob: vi.fn(),
    resubmitJob: vi.fn(),
    getExperiment: vi.fn(),
    registerModel: vi.fn(),
  },
}));

vi.mock("@/services/catalogClient", () => ({
  catalogClient: {
    listModels: vi.fn().mockResolvedValue({ status: "success", data: [] }),
    listDatasets: vi.fn().mockResolvedValue({ status: "success", data: [] }),
  },
}));

describe("JobSubmit.vue", () => {
  it("loads GPU types from API and sets default selection", async () => {
    const wrapper = mount(JobSubmit);
    await flushPromises();

    const select = wrapper.find("select#gpuType");
    expect(select.exists()).toBe(true);
    const options = select.findAll("option");
    expect(options.length).toBeGreaterThan(0);
    expect((select.element as HTMLSelectElement).value).toBe("nvidia-rtx-4090");
  });
});

