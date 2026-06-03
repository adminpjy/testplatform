import { FormEvent, useState } from "react";
import { LogIn } from "lucide-react";

import { login } from "../api/platform";
import type { CurrentUser } from "../types/platform";

export function LoginPage({ onLogin }: { onLogin: (user: CurrentUser) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await login(username, password);
      onLogin(response.user);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : String(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-panel" onSubmit={handleSubmit}>
        <div className="login-panel__heading">
          <h1>石化智云智能功能测试平台</h1>
          <p>登录后按项目权限查看和执行功能测试。</p>
        </div>
        <label>
          <span>用户名</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          <span>密码</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
        </label>
        {error ? <pre className="error-detail error-detail--collapsed">{error}</pre> : null}
        <button className="primary-button login-button" type="submit" disabled={!username || loading}>
          <LogIn size={16} />
          {loading ? "登录中" : "登录"}
        </button>
        <p className="login-help">管理员默认账号：admin/admin。新增成员首次登录时，初始密码默认为用户名。</p>
      </form>
    </div>
  );
}
