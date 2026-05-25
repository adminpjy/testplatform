import {
  Activity,
  AlertTriangle,
  Database,
  FileText,
  Monitor,
  Settings
} from "lucide-react";
import type { ComponentType } from "react";

export type AppRoute =
  | "test-run"
  | "ability-center"
  | "failure-samples"
  | "reports"
  | "mock-mis-demo"
  | "settings";

export interface AppNavItem {
  id: AppRoute;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

export const navigationItems: AppNavItem[] = [
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
    id: "mock-mis-demo",
    label: "Mock MIS Demo",
    description: "本地被测系统入口",
    icon: Monitor
  },
  {
    id: "settings",
    label: "系统设置",
    description: "服务状态和运行配置",
    icon: Settings
  }
];

export function routeFromHash(hash: string): AppRoute {
  const value = hash.replace(/^#\/?/, "") as AppRoute;
  return navigationItems.some((item) => item.id === value) ? value : "test-run";
}
