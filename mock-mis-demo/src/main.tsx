import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type TodoItem = {
  id: string;
  applicant: string;
  type: string;
  status: string;
  amount: string;
  department: string;
};

type UserItem = {
  id: number;
  username: string;
  displayName: string;
  role: string;
  status: string;
};

type ApprovalMode = "A" | "B" | "C";

const todoItems: TodoItem[] = [
  {
    id: "REQ-2026-0017",
    applicant: "王敏",
    type: "采购申请",
    status: "待审批",
    amount: "18,600.00",
    department: "行政部"
  },
  {
    id: "REQ-2026-0021",
    applicant: "李强",
    type: "合同付款",
    status: "待审批",
    amount: "42,300.00",
    department: "财务部"
  },
  {
    id: "REQ-2026-0028",
    applicant: "赵倩",
    type: "权限开通",
    status: "待处理",
    amount: "-",
    department: "信息部"
  }
];

const initialUsers: UserItem[] = [
  { id: 1, username: "admin", displayName: "系统管理员", role: "管理员", status: "启用" },
  { id: 2, username: "auditor", displayName: "审批专员", role: "审批员", status: "启用" },
  { id: 3, username: "viewer", displayName: "只读用户", role: "查看员", status: "停用" }
];

function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [isAuthed, setIsAuthed] = useState(localStorage.getItem("mock-mis-auth") === "true");

  const navigate = (nextPath: string) => {
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
  };

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (path === "/" || path === "") {
      navigate(isAuthed ? "/dashboard" : "/login");
      return;
    }
    if (!isAuthed && !path.startsWith("/login")) {
      navigate("/login");
    }
  }, [isAuthed, path]);

  if (path === "/" || path === "") {
    return null;
  }

  if (path.startsWith("/login")) {
    return (
      <LoginPage
        onSuccess={() => {
          localStorage.setItem("mock-mis-auth", "true");
          setIsAuthed(true);
          navigate("/dashboard");
        }}
      />
    );
  }

  if (!isAuthed) {
    return null;
  }

  return (
    <Shell
      activePath={path}
      onNavigate={navigate}
      onLogout={() => {
        localStorage.removeItem("mock-mis-auth");
        setIsAuthed(false);
        navigate("/login");
      }}
    >
      {path.startsWith("/dashboard") && <DashboardPage onNavigate={navigate} />}
      {path.startsWith("/todo/") && <TodoDetailPage id={decodeURIComponent(path.replace("/todo/", ""))} />}
      {path === "/todo" && <TodoPage onNavigate={navigate} />}
      {path.startsWith("/users") && <UsersPage />}
      {path.startsWith("/approval") && <ApprovalManagementPage />}
    </Shell>
  );
}

function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const params = new URLSearchParams(window.location.search);
  const notice = params.get("notice");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const notices: Record<string, { title: string; content: string; tone: string }> = {
    "account-expiry": {
      title: "账号有效期提醒",
      content: "测试账号将在 7 天后到期，请在测试计划中预留账号更新窗口。",
      tone: "warning"
    },
    "system-announcement": {
      title: "系统公告",
      content: "本地 MIS 演示系统今日开放审批、待办和用户管理验证场景。",
      tone: "info"
    },
    "force-change-password": {
      title: "强制改密提示",
      content: "检测到账户策略变化，生产测试中应转入人工介入流程。",
      tone: "danger"
    }
  };
  const activeNotice = notice ? notices[notice] : undefined;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (username === "admin" && password === "123456") {
      setError("");
      onSuccess();
      return;
    }
    setError("用户名或密码错误");
  };

  return (
    <main className="login-layout">
      <section className="login-visual" aria-label="MIS login backdrop">
        <div className="product-mark">
          <span className="product-mark__symbol">MIS</span>
          <div>
            <strong>企业运营管理平台</strong>
            <span>审批、待办、用户权限与业务查询</span>
          </div>
        </div>
        <div className="login-visual__metrics">
          <div>
            <strong>28</strong>
            <span>待办事项</span>
          </div>
          <div>
            <strong>6</strong>
            <span>审批流程</span>
          </div>
          <div>
            <strong>94%</strong>
            <span>今日处理率</span>
          </div>
        </div>
      </section>

      <section className="login-panel" aria-label="登录面板">
        <div className="login-card">
          <div className="login-card__header">
            <p>Production Validation Site</p>
            <h1>企业 MIS 登录</h1>
          </div>

          {activeNotice && (
            <div className={`notice notice--${activeNotice.tone}`} role="alert">
              <strong>{activeNotice.title}</strong>
              <span>{activeNotice.content}</span>
            </div>
          )}

          <form className="form-stack" onSubmit={submit}>
            <label htmlFor="username">用户名</label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="admin"
            />

            <label htmlFor="password">密码</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="123456"
            />

            {error && <div className="form-error">{error}</div>}

            <button className="primary-button" type="submit">
              登录
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}

function Shell({
  activePath,
  onNavigate,
  onLogout,
  children
}: {
  activePath: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const menu = [
    { path: "/dashboard", label: "工作台", icon: "◇" },
    { path: "/todo", label: "我的待办", icon: "✓" },
    { path: "/users", label: "用户管理", icon: "□" },
    { path: "/approval", label: "审批管理", icon: "◎" }
  ];

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="左侧菜单">
        <div className="sidebar__brand">
          <span>MIS</span>
          <strong>管理控制台</strong>
        </div>
        <nav className="sidebar__nav">
          {menu.map((item) => (
            <button
              key={item.path}
              className={activePath.startsWith(item.path) ? "nav-item nav-item--active" : "nav-item"}
              onClick={() => onNavigate(item.path)}
              type="button"
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p>Mock MIS Demo</p>
            <h1>{pageTitle(activePath)}</h1>
          </div>
          <div className="topbar__actions">
            <span className="tenant-badge">华东生产验证环境</span>
            <button className="ghost-button" type="button" onClick={onLogout}>
              退出
            </button>
          </div>
        </header>
        <div className="page-body">{children}</div>
      </section>
    </main>
  );
}

function DashboardPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  return (
    <div className="dashboard-grid">
      <section className="summary-strip">
        <Metric title="我的待办" value="28" note="含 3 条高优先级" />
        <Metric title="用户管理" value="156" note="12 个停用账号" />
        <Metric title="审批管理" value="6" note="流程配置可用" />
      </section>
      <section className="workbench">
        <div className="section-heading">
          <h2>工作台</h2>
          <span>常用入口</span>
        </div>
        <div className="quick-actions">
          <button type="button" onClick={() => onNavigate("/todo")}>
            <strong>我的待办</strong>
            <span>处理采购、付款、权限申请</span>
          </button>
          <button type="button" onClick={() => onNavigate("/users")}>
            <strong>用户管理</strong>
            <span>查询、新增、修改、删除用户</span>
          </button>
          <button type="button" onClick={() => onNavigate("/approval")}>
            <strong>审批管理</strong>
            <span>查看审批配置和流转状态</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function Metric({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <div className="metric">
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

function TodoPage({ onNavigate }: { onNavigate: (path: string) => void }) {
  const [mode, setMode] = useState<ApprovalMode>("A");
  const [activeApproval, setActiveApproval] = useState<TodoItem | null>(null);
  const [toast, setToast] = useState("");

  const approve = (message: string) => {
    setActiveApproval(null);
    setToast(message);
  };

  return (
    <section className="content-section">
      <div className="section-heading section-heading--row">
        <div>
          <h2>我的待办</h2>
          <span>表格同时提供“审批”和“查看审批流程”，用于验证业务目标候选冲突。</span>
        </div>
        <div className="segmented-control" aria-label="审批模式">
          {(["A", "B", "C"] as ApprovalMode[]).map((item) => (
            <button
              key={item}
              className={mode === item ? "segmented-control__item segmented-control__item--active" : "segmented-control__item"}
              type="button"
              onClick={() => setMode(item)}
            >
              模式 {item}
            </button>
          ))}
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}

      <div className="data-panel">
        <table>
          <thead>
            <tr>
              <th>申请编号</th>
              <th>申请人</th>
              <th>类型</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {todoItems.map((item) => (
              <tr key={item.id}>
                <td>
                  <button className="link-button" type="button" onClick={() => onNavigate(`/todo/${item.id}`)}>
                    {item.id}
                  </button>
                </td>
                <td>{item.applicant}</td>
                <td>{item.type}</td>
                <td>
                  <span className="status-pill status-pill--pending">{item.status}</span>
                </td>
                <td>
                  <div className="table-actions">
                    <button type="button" onClick={() => setActiveApproval(item)}>
                      审批
                    </button>
                    <button type="button" onClick={() => onNavigate(`/todo/${item.id}?flow=true`)}>
                      查看审批流程
                    </button>
                    <button type="button" onClick={() => onNavigate(`/todo/${item.id}`)}>
                      详情
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {activeApproval && (
        <ApprovalDialog
          item={activeApproval}
          mode={mode}
          onClose={() => setActiveApproval(null)}
          onApprove={approve}
        />
      )}
    </section>
  );
}

function ApprovalDialog({
  item,
  mode,
  onClose,
  onApprove
}: {
  item: TodoItem;
  mode: ApprovalMode;
  onClose: () => void;
  onApprove: (message: string) => void;
}) {
  const [decision, setDecision] = useState("通过");
  const [comment, setComment] = useState("");

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="approval-title">
        <header className="modal__header">
          <div>
            <p>申请编号 {item.id}</p>
            <h2 id="approval-title">审批</h2>
          </div>
          <button className="icon-button" type="button" aria-label="关闭审批弹窗" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="modal__content">
          <dl className="detail-list">
            <div>
              <dt>申请人</dt>
              <dd>{item.applicant}</dd>
            </div>
            <div>
              <dt>类型</dt>
              <dd>{item.type}</dd>
            </div>
            <div>
              <dt>金额</dt>
              <dd>{item.amount}</dd>
            </div>
          </dl>

          {mode === "A" && (
            <div className="approval-mode">
              <p>模式 A：直接点击“通过”并确认。</p>
              <button className="primary-button" type="button" onClick={() => onApprove("审批成功")}>
                通过
              </button>
              <button className="secondary-button" type="button" onClick={() => onApprove("审批成功")}>
                确定
              </button>
            </div>
          )}

          {mode === "B" && (
            <form className="approval-mode" onSubmit={(event) => {
              event.preventDefault();
              onApprove(decision === "通过" ? "审批成功" : "已驳回");
            }}>
              <fieldset className="radio-group">
                <legend>审批结论</legend>
                <label>
                  <input
                    type="radio"
                    name="approvalDecision"
                    value="通过"
                    checked={decision === "通过"}
                    onChange={(event) => setDecision(event.target.value)}
                  />
                  通过
                </label>
                <label>
                  <input
                    type="radio"
                    name="approvalDecision"
                    value="驳回"
                    checked={decision === "驳回"}
                    onChange={(event) => setDecision(event.target.value)}
                  />
                  驳回
                </label>
              </fieldset>
              <button className="primary-button" type="submit">
                确定
              </button>
            </form>
          )}

          {mode === "C" && (
            <form className="approval-mode" onSubmit={(event) => {
              event.preventDefault();
              onApprove("审批成功，意见已提交");
            }}>
              <label htmlFor="approval-comment">审批意见</label>
              <textarea
                id="approval-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="同意，按流程继续办理。"
              />
              <button className="primary-button" type="submit">
                提交
              </button>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}

function TodoDetailPage({ id }: { id: string }) {
  const item = todoItems.find((entry) => entry.id === id) || todoItems[0];
  const showFlow = new URLSearchParams(window.location.search).get("flow") === "true";

  return (
    <section className="content-section">
      <div className="section-heading">
        <h2>{showFlow ? "审批流程" : "申请详情"}</h2>
        <span>{item.id}</span>
      </div>
      <div className="detail-grid">
        <div className="detail-panel">
          <dl className="detail-list detail-list--wide">
            <div>
              <dt>申请编号</dt>
              <dd>{item.id}</dd>
            </div>
            <div>
              <dt>申请人</dt>
              <dd>{item.applicant}</dd>
            </div>
            <div>
              <dt>申请类型</dt>
              <dd>{item.type}</dd>
            </div>
            <div>
              <dt>所属部门</dt>
              <dd>{item.department}</dd>
            </div>
            <div>
              <dt>当前状态</dt>
              <dd>{item.status}</dd>
            </div>
          </dl>
        </div>
        <div className="flow-panel">
          <h3>审批流程</h3>
          <ol className="timeline">
            <li>发起申请</li>
            <li>部门负责人审核</li>
            <li>财务复核</li>
            <li>审批完成</li>
          </ol>
        </div>
      </div>
    </section>
  );
}

function UsersPage() {
  const [users, setUsers] = useState<UserItem[]>(initialUsers);
  const [keyword, setKeyword] = useState("");
  const [editing, setEditing] = useState<UserItem | null>(null);
  const [form, setForm] = useState({ username: "", displayName: "", role: "查看员" });

  const filteredUsers = useMemo(() => {
    if (!keyword.trim()) {
      return users;
    }
    return users.filter((user) =>
      `${user.username} ${user.displayName} ${user.role}`.toLowerCase().includes(keyword.toLowerCase())
    );
  }, [keyword, users]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.username.trim()) {
      return;
    }
    if (editing) {
      setUsers((current) =>
        current.map((user) =>
          user.id === editing.id ? { ...user, ...form, status: user.status } : user
        )
      );
    } else {
      setUsers((current) => [
        ...current,
        {
          id: Math.max(...current.map((user) => user.id)) + 1,
          username: form.username,
          displayName: form.displayName || form.username,
          role: form.role,
          status: "启用"
        }
      ]);
    }
    setEditing(null);
    setForm({ username: "", displayName: "", role: "查看员" });
  };

  const startEdit = (user: UserItem) => {
    setEditing(user);
    setForm({ username: user.username, displayName: user.displayName, role: user.role });
  };

  return (
    <section className="content-section">
      <div className="section-heading">
        <h2>用户管理</h2>
        <span>支持查询、新增、修改和删除。</span>
      </div>

      <div className="split-layout">
        <div className="data-panel">
          <div className="query-bar">
            <label htmlFor="user-query">查询</label>
            <input
              id="user-query"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="用户名、姓名或角色"
            />
            <button type="button">查询</button>
          </div>

          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>姓名</th>
                <th>角色</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>{user.displayName}</td>
                  <td>{user.role}</td>
                  <td>{user.status}</td>
                  <td>
                    <div className="table-actions">
                      <button type="button" onClick={() => startEdit(user)}>
                        修改
                      </button>
                      <button type="button" onClick={() => setUsers((current) => current.filter((item) => item.id !== user.id))}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <form className="side-form" onSubmit={submit}>
          <h3>{editing ? "修改用户" : "新增用户"}</h3>
          <label htmlFor="j_name">用户名</label>
          <div className="legacy-field" data-control="legacy-user-name">
            <span className="legacy-field__prefix">@</span>
            <input
              id="j_name"
              value={form.username}
              onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
              placeholder="例如 ops_user"
            />
          </div>

          <label htmlFor="display-name">姓名</label>
          <input
            id="display-name"
            value={form.displayName}
            onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
          />

          <label htmlFor="role-name">角色</label>
          <select
            id="role-name"
            value={form.role}
            onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))}
          >
            <option>管理员</option>
            <option>审批员</option>
            <option>查看员</option>
          </select>

          <button className="primary-button" type="submit">
            {editing ? "保存修改" : "新增"}
          </button>
        </form>
      </div>
    </section>
  );
}

function ApprovalManagementPage() {
  return (
    <section className="content-section">
      <div className="section-heading">
        <h2>审批管理</h2>
        <span>流程配置、节点负责人和审批记录。</span>
      </div>
      <div className="data-panel">
        <table>
          <thead>
            <tr>
              <th>流程名称</th>
              <th>适用类型</th>
              <th>当前版本</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>采购申请审批</td>
              <td>采购申请</td>
              <td>v3</td>
              <td>启用</td>
            </tr>
            <tr>
              <td>合同付款审批</td>
              <td>付款申请</td>
              <td>v5</td>
              <td>启用</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function pageTitle(path: string) {
  if (path.startsWith("/todo/")) return "申请详情";
  if (path.startsWith("/todo")) return "我的待办";
  if (path.startsWith("/users")) return "用户管理";
  if (path.startsWith("/approval")) return "审批管理";
  return "工作台";
}

createRoot(document.getElementById("root") as HTMLElement).render(<App />);
