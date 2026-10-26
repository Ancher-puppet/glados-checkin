# glados-checkin

通过 GitHub Actions 自动签到，默认每天北京时间 09:07 运行，也可手动触发。

## 更新 Cookie 和 User-Agent

出现 `GLaDOS code: -2` /「没有权限」时，通常是 Cookie 已失效或复制不完整。HTTP 200 只代表 HTTP 请求成功，不代表签到成功。

1. 在浏览器中退出并重新登录 [GLaDOS](https://glados.cloud)，确认能正常访问账户页面。
2. 打开开发者工具（F12 或右键「检查」）→ **Network / 网络**，刷新页面，选择一个发往 `glados.cloud`、携带登录 Cookie 的接口请求（通常在 **Fetch/XHR** 中）。
3. 在 **Headers / 标头 → Request Headers / 请求标头** 中复制以下两个值，必须来自**同一个浏览器、同一次登录会话**：

   | Secret 名称 | 应填写的值 |
   | --- | --- |
   | `GLADOS_COOKIE` | `Cookie` 请求头的完整值，单行 `名称=值; 名称=值` 格式，不含 `Cookie:` 前缀。 |
   | `GLADOS_USER_AGENT` | `User-Agent` 请求头的完整值，不含 `User-Agent:` 前缀。 |

   优先复制请求头中的原始 Cookie 字符串，不要只复制 Cookie 表格中的某一项。若只有表格，可将该请求的全部 Cookie 按 `名称=值; 名称=值` 拼成一行；例如 `gld:sess=示例值; gld:sess.sig=示例值; koa:sess=示例值; koa:sess.sig=示例值`（仅为格式示例，实际以当前请求为准）。「没有响应 Cookie」不影响操作，这里需要的是**请求 Cookie**。

4. 打开仓库 [Actions Secrets 设置](https://github.com/Ancher-puppet/glados-checkin/settings/secrets/actions)：**Settings → Secrets and variables → Actions → Secrets → Repository secrets**。
5. 点击 `GLADOS_COOKIE` 右侧的铅笔，粘贴新值并点击 **Update secret**；同样更新 `GLADOS_USER_AGENT`。若尚未创建，点击 **New repository secret**，使用上述准确名称。
6. 前往 **Actions → GLaDOS Daily Check-in → Run workflow**，选择默认分支并启动一次新运行，查看签到结果。

若仍提示「没有权限」，检查 Cookie 是否完整、是否来自刚登录的账户；若提示 `device-mismatch`，重新从同一浏览器获取并同时更新这两项。网页本身也无法正常操作时，先解决账户或网站端问题。

## 为什么看不到已保存的值？

这两项存放在 **Secrets**，不是 **Variables**。GitHub 不提供已保存 Secret 原值的查看或取回功能，即使是仓库所有者也只能更新、删除；编辑框为空并不代表没有保存，API / CLI 也不能读回原值。Actions 日志通常会将匹配的 Secret 遮盖为 `***`。

**Variables** 用于非敏感配置，可查看明文。Cookie 是登录凭据，应保留在 Secrets 中；当前工作流也通过 `secrets.GLADOS_COOKIE` 和 `secrets.GLADOS_USER_AGENT` 读取这两项，直接改存 Variables 不会生效。需要自行留存时，请使用密码管理器；不要把 Cookie 写进 README、提交到仓库或打印到日志。
