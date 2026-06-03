export interface PageResponse<T = Record<string, unknown>> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface AssetItem {
  id: number;
  assetCode: string;
  assetName: string;
  assetType: string;
  projectId: number | null;
  module: string | null;
  tags: string[];
  status: string;
  owner: string | null;
  riskLevel: string;
  description: string | null;
  currentVersionId: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface DefectItem {
  id: number;
  defectCode: string;
  projectId: number | null;
  caseId: number | null;
  runId: number | null;
  failureSampleId: number | null;
  title: string;
  defectType: string;
  severity: string;
  priority: string;
  status: string;
  assignee: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface FailureWorkbenchItem {
  id: number;
  projectId: number | null;
  caseId: number | null;
  runId: number;
  stepId: number | null;
  failureType: string | null;
  failureSummary: string | null;
  status: string;
  riskLevel: string;
  analysisStatus: string;
  recommendedAction: string;
  screenshotPath: string | null;
  createdAt: string;
}

export interface LearningItem {
  id: number;
  learningCode: string;
  projectId: number | null;
  itemType: string;
  title: string;
  status: string;
  riskLevel: string;
  sourceType: string | null;
  sourceId: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface PluginItem {
  id: number;
  pluginCode: string;
  pluginName: string;
  pluginType: string;
  version: string;
  status: string;
  priority: number;
  health: Record<string, unknown>;
}

export interface PlatformUserItem {
  id: number;
  username: string;
  displayName: string | null;
  role: string;
  status: string;
}

export interface QualityOverview {
  projectId: number | null;
  totals: Record<string, number>;
  trends: Array<Record<string, unknown>>;
  modules: Array<Record<string, unknown>>;
  failures: Array<Record<string, unknown>>;
  recommendations: string[];
}

export interface GeneratedCase {
  caseName: string;
  module: string | null;
  feature: string | null;
  scenarioType: string;
  naturalLanguageGoal: string;
  testData: Record<string, unknown>;
  expectedResult: string;
  riskLevel: string;
  coverage: string[];
  automationScore: number;
}

export interface GenerateCasesResponse {
  items: GeneratedCase[];
  coverage: Record<string, unknown>;
  summary: Record<string, unknown>;
}
