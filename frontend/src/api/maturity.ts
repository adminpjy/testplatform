import { deleteJson, getJson, postJson, putJson } from "./client";
import type {
  AssetItem,
  DefectItem,
  FailureWorkbenchItem,
  GenerateCasesResponse,
  LearningItem,
  PageResponse,
  PlatformUserItem,
  PluginItem,
  QualityOverview
} from "../types/maturity";

export function getAssets(page = 1): Promise<PageResponse<AssetItem>> {
  return getJson<PageResponse<AssetItem>>(`/api/maturity/assets?page=${page}&page_size=10`);
}

export function createAsset(payload: {
  assetName: string;
  assetType: string;
  projectId?: number | null;
  module?: string | null;
  riskLevel?: string;
  description?: string | null;
  content?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  return postJson("/api/maturity/assets", payload);
}

export function publishAsset(assetId: number): Promise<Record<string, unknown>> {
  return postJson(`/api/maturity/assets/${assetId}/publish`, {});
}

export function deleteAsset(assetId: number): Promise<void> {
  return deleteJson<void>(`/api/maturity/assets/${assetId}`);
}

export function generateCases(sourceText: string): Promise<GenerateCasesResponse> {
  return postJson<GenerateCasesResponse>("/api/maturity/generation/cases", {
    sourceText,
    includeNegative: true,
    includeBoundary: true,
    includePermission: true
  });
}

export function getDefects(page = 1): Promise<PageResponse<DefectItem>> {
  return getJson<PageResponse<DefectItem>>(`/api/maturity/defects?page=${page}&page_size=10`);
}

export function createDefectFromFailure(failureSampleId: number): Promise<Record<string, unknown>> {
  return postJson(`/api/maturity/defects/from-failure/${failureSampleId}`, {});
}

export function updateDefect(defectId: number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return putJson(`/api/maturity/defects/${defectId}`, payload);
}

export function deleteDefect(defectId: number): Promise<void> {
  return deleteJson<void>(`/api/maturity/defects/${defectId}`);
}

export function getQualityOverview(projectId?: number | null): Promise<QualityOverview> {
  const suffix = projectId ? `?project_id=${projectId}` : "";
  return getJson<QualityOverview>(`/api/maturity/quality/overview${suffix}`);
}

export function getLearningItems(page = 1): Promise<PageResponse<LearningItem>> {
  return getJson<PageResponse<LearningItem>>(`/api/maturity/learning/items?page=${page}&page_size=10`);
}

export function createLearningItem(payload: {
  itemType: string;
  title: string;
  riskLevel?: string;
  proposal?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  return postJson("/api/maturity/learning/items", payload);
}

export function transitionLearningItem(itemId: number, status: string): Promise<Record<string, unknown>> {
  return postJson(`/api/maturity/learning/items/${itemId}/transition/${status}`, {});
}

export function updateLearningItem(itemId: number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return putJson(`/api/maturity/learning/items/${itemId}`, payload);
}

export function deleteLearningItem(itemId: number): Promise<void> {
  return deleteJson<void>(`/api/maturity/learning/items/${itemId}`);
}

export function getPlugins(page = 1): Promise<PageResponse<PluginItem>> {
  return getJson<PageResponse<PluginItem>>(`/api/maturity/plugins?page=${page}&page_size=10`);
}

export function registerPlugin(payload: {
  pluginName: string;
  pluginType: string;
  version?: string;
  configSchema?: Record<string, unknown>;
  config?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  return postJson("/api/maturity/plugins", payload);
}

export function checkPlugin(pluginId: number): Promise<Record<string, unknown>> {
  return postJson(`/api/maturity/plugins/${pluginId}/health-check`, {});
}

export function updatePlugin(pluginId: number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return putJson(`/api/maturity/plugins/${pluginId}`, payload);
}

export function deletePlugin(pluginId: number): Promise<void> {
  return deleteJson<void>(`/api/maturity/plugins/${pluginId}`);
}

export function getFailureWorkbench(page = 1): Promise<PageResponse<FailureWorkbenchItem>> {
  return getJson<PageResponse<FailureWorkbenchItem>>(`/api/maturity/failure-workbench/items?page=${page}&page_size=10`);
}

export function generateFailureSolution(failureSampleId: number): Promise<Record<string, unknown>> {
  return postJson(`/api/maturity/failure-workbench/${failureSampleId}/solution`, {});
}

export function updateFailureWorkbenchItem(failureSampleId: number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return putJson(`/api/maturity/failure-workbench/${failureSampleId}`, payload);
}

export function deleteFailureWorkbenchItem(failureSampleId: number): Promise<void> {
  return deleteJson<void>(`/api/maturity/failure-workbench/${failureSampleId}`);
}

export function createPlatformUser(payload: { username: string; displayName?: string | null; role: string }): Promise<Record<string, unknown>> {
  return postJson("/api/maturity/security/users", payload);
}

export function getPlatformUsers(page = 1): Promise<PageResponse<PlatformUserItem>> {
  return getJson<PageResponse<PlatformUserItem>>(`/api/maturity/security/users?page=${page}&page_size=10`);
}

export function updatePlatformUser(userId: number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return putJson(`/api/maturity/security/users/${userId}`, payload);
}

export function deletePlatformUser(userId: number): Promise<void> {
  return deleteJson<void>(`/api/maturity/security/users/${userId}`);
}

export function updateAsset(assetId: number, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return putJson(`/api/maturity/assets/${assetId}`, payload);
}
