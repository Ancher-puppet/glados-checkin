# GLaDOS 每日自动签到

由 GitHub Actions 在云端运行，个人 Mac 无需开机。使用系统 Chrome 打开官方签到页，由原页面完成 challenge、proof 和 Cloudflare Turnstile；出现标准验证勾选框时，通过键盘操作后等待网站生成真实验证令牌。

**2026-11-15 已用本仓库账号完成云端严格测试：验证令牌存在、状态 `ok`，网站返回今日已签到，设备不匹配问题已解决。** 当天此前已手动签到，因此本次没有新增积分，次日首次自动到账仍待定时运行验收。不能把重复签到当作新奖励。

## 运行时间

- 北京时间每天 **09:07** 首次运行。
- **15:17、21:27** 自动补漏；先核对当天签到流水，已签到就直接退出，不重复提交。
- 每月 1 日执行一次保活提交，减少公开仓库因长期没有活动而被停用定时任务的问题。

GitHub 的调度可能延迟。任务须在默认分支 `main` 上启用；无需个人电脑在线。

## 凭据

保留两项 Repository Secrets：`GLADOS_COOKIE` 和 `GLADOS_USER_AGENT`。已通过一次邮箱验证码登录建立了与云端 Chrome 相匹配的会话，并安全更新这两项。邮箱密码和验证码没有保存到仓库。

网站会检查登录设备。把 Safari 的 Cookie 搬到 Chrome，即使 Cloudflare 验证已通过，也可能被拒绝为 `device-mismatch`；只更改浏览器标识又可能使验证失败。登录过期或设备被拒绝时，需要重新建立匹配云端浏览器的登录态。不要把 Cookie 改存到公开 Variables、提交文件或日志。

## 结果判断

- 先查询 `/api/user/points`，只认可北京时间当天、业务为签到的流水。
- 签到前等待官网验证完成；失败时不提交空令牌请求。
- 新签到须由接口确认成功，并再次核对当天流水。
- `repeated=true` 或经流水确认的旧版 `code=1` 单独报告为已签到，不算新增奖励。
- `code=5` / `reason=turnstile`、登录失效、设备不匹配均明确失败；HTTP 200 本身不算成功。
- 日志只记录业务结果和验证令牌是否存在，不输出 Cookie、nonce、proof 或验证令牌原值。临时浏览器目录在结束后删除。
- 只签到，不兑换积分、不购买套餐、不参与抽奖。

手动运行 **Actions → GLaDOS Daily Check-in → Run workflow**。默认使用原生 Chrome。勾选 `verify_browser` 可在今日已经签到时继续验收完整验证流程；这是诊断选项，日常无需勾选。`native_safari` 和关闭 `native_chrome` 的路径保留作对照排查，之前均未通过云端验证，不作为每日默认方案。

## 实测记录

| 环境 | 验证 | 网站响应 |
| --- | --- | --- |
| Linux WebKit | 无令牌、超时 | 重复签到，不能证明验证成功 |
| GitHub macOS Safari | 无令牌、超时 | 重复签到，不能证明验证成功 |
| 原生 Chrome + Safari 旧登录态 | 有效令牌、`ok` | `device-mismatch` |
| 原生 Chrome + Safari 浏览器标识 | 未完成验证 | 没有提交签到 |
| 原生 Chrome + 新建匹配会话 | **有效令牌、`ok`** | **已签到；严格测试通过** |

本仓库严格通过记录：[43682878484](https://github.com/Ancher-puppet/glados-checkin/actions/runs/43682878484)。此前失败记录保留在 Actions 中，未将它们宣称为修复成功。

此次方案参考了 [MZRidaz/GLaDOS-Auto-Checkin PR #24](https://github.com/MZRidaz/GLaDOS-Auto-Checkin/pull/24) 的原生浏览器与标准验证框交互思路，并核对了作者 [GitHub 云端首次签到记录](https://github.com/Ingress007/GLaDOS-Auto-Checkin/actions/runs/43613098333)。后者属于其他账号的证据，不能替代本账号次日首次到账验收。

12 项离线测试通过，覆盖日期边界、重复签到、拒绝响应、凭据格式、脱敏和验证框选择范围。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

网站日后修改验证规则、会话过期或 GitHub 服务异常仍可能导致失败；以实际业务结果和当天流水为准。Cloudflare 的验证令牌只有短期有效性，不能保存为长期 Cookie 替代品。
