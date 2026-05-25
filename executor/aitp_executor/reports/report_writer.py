from html import escape
from typing import Any

from executor.aitp_executor.reports.artifact_writer import ArtifactWriter


class ReportWriter:
    def __init__(self, artifact_writer: ArtifactWriter) -> None:
        self.artifact_writer = artifact_writer

    def write(self, summary: dict[str, Any], steps: list[dict[str, Any]]) -> str:
        rows = "\n".join(_step_row(step) for step in steps)
        html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(summary.get("runCode", "Test Run"))}</title>
    <style>
      body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; color: #202733; background: #f3f6f9; }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
      header, section {{ background: #fff; border: 1px solid #dce4ee; border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
      h1, h2 {{ margin: 0 0 8px; letter-spacing: 0; }}
      .meta {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }}
      .meta div {{ background: #f7fafc; border: 1px solid #e3eaf2; border-radius: 6px; padding: 12px; }}
      .meta span {{ display: block; color: #637083; font-size: 13px; }}
      .meta strong {{ display: block; margin-top: 4px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border-bottom: 1px solid #e3eaf2; padding: 10px; text-align: left; vertical-align: top; }}
      th {{ color: #536174; background: #f7fafc; }}
      .status-passed {{ color: #17643a; font-weight: 700; }}
      .status-failed {{ color: #b42318; font-weight: 700; }}
      a {{ color: #146c75; }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <h1>测试执行报告</h1>
        <p>{escape(summary.get("caseName", ""))}</p>
        <div class="meta">
          <div><span>Run Code</span><strong>{escape(summary.get("runCode", ""))}</strong></div>
          <div><span>Status</span><strong>{escape(summary.get("status", ""))}</strong></div>
          <div><span>Total Steps</span><strong>{summary.get("totalSteps", 0)}</strong></div>
          <div><span>Duration</span><strong>{summary.get("durationMs", 0)} ms</strong></div>
        </div>
      </header>
      <section>
        <h2>步骤结果</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Action</th>
              <th>Target</th>
              <th>Status</th>
              <th>Evidence</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </section>
    </main>
  </body>
</html>
"""
        return self.artifact_writer.write_text("report.html", html)


def _step_row(step: dict[str, Any]) -> str:
    status = escape(str(step.get("status", "")))
    css = "status-passed" if status == "passed" else "status-failed"
    screenshot = step.get("screenshot_path")
    screenshot_link = f'<a href="/files/{escape(screenshot)}">screenshot</a>' if screenshot else ""
    return f"""<tr>
  <td>{step.get("step_number", "")}</td>
  <td>{escape(str(step.get("action", "")))}</td>
  <td>{escape(str(step.get("target", "")))}</td>
  <td class="{css}">{status}</td>
  <td>{screenshot_link}</td>
  <td>{escape(str(step.get("error_summary") or ""))}</td>
</tr>"""
