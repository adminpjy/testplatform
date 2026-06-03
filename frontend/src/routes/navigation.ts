import {
  Activity,
  AlertTriangle,
  Building2,
  Database,
  FileText,
  FolderKanban,
  ListChecks,
  Settings
} from "lucide-react";
import type { ComponentType } from "react";
import type { CurrentUser } from "../types/platform";

export type AppRoute =
  | "projects"
  | "project-wizard"
  | "project-detail"
  | "case-detail"
  | "test-run"
  | "ability-center"
  | "enterprise-center"
  | "failure-samples"
  | "reports"
  | "settings";

export interface AppNavItem {
  id: AppRoute;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

export const navigationItems: AppNavItem[] = [
  {
    id: "projects",
    label: "项目管理",
    description: "项目、账号和功能测试用例",
    icon: FolderKanban
  },
  {
    id: "project-wizard",
    label: "项目向导",
    description: "初始化项目、导入用例并发起预扫",
    icon: ListChecks
  },
  {
    id: "test-run",
    label: "测试运行",
    description: "分析目标并执行功能测试",
    icon: Activity
  },
  {
    id: "ability-center",
    label: "能力中心",
    description: "规则、知识与草案沉淀",
    icon: Database
  },
  {
    id: "enterprise-center",
    label: "企业中心",
    description: "资产、缺陷、学习治理和插件",
    icon: Building2
  },
  {
    id: "failure-samples",
    label: "失败样本",
    description: "查看失败证据与复盘入口",
    icon: AlertTriangle
  },
  {
    id: "reports",
    label: "测试报告",
    description: "查看执行报告和产物",
    icon: FileText
  },
  {
    id: "settings",
    label: "系统设置",
    description: "服务状态和运行配置",
    icon: Settings
  }
];

export function routeFromHash(hash: string): AppRoute {
  const clean = hash.replace(/^#\/?/, "");
  if (/^projects\/\d+/.test(clean)) {
    return "project-detail";
  }
  if (/^cases\/\d+/.test(clean)) {
    return "case-detail";
  }
  const value = clean as AppRoute;
  return navigationItems.some((item) => item.id === value) ? value : "test-run";
}

export function idFromHash(hash: string, prefix: "projects" | "cases"): number | null {
  const match = hash.replace(/^#\/?/, "").match(new RegExp(`^${prefix}/(\\d+)`));
  return match ? Number(match[1]) : null;
}

export function navRouteFor(route: AppRoute): AppRoute {
  if (route === "project-detail" || route === "case-detail") {
    return "projects";
  }
  return route;
}

export function navigationForUser(user: CurrentUser | null): AppNavItem[] {
  if (!user) {
    return [];
  }
  if (user.role === "admin") {
    return navigationItems;
  }
  const allowed = new Set(user.navigation?.length ? user.navigation : ["projects", "project-wizard", "test-run"]);
  return navigationItems.filter((item) => allowed.has(item.id));
}

export function canAccessRoute(route: AppRoute, user: CurrentUser | null): boolean {
  if (!user) {
    return false;
  }
  const routeKey = navRouteFor(route);
  return navigationForUser(user).some((item) => item.id === routeKey);
}
