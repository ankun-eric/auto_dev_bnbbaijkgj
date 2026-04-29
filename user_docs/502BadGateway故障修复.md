# bini-health 系统 502 Bad Gateway 故障修复手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 管理后台登录入口（经 Nginx 代理，端口 80） |
| H5 客户端 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 用户端首页入口（经 Nginx 代理，端口 80） |

---

## 功能简介

本次修复了 bini-health 健康管理系统的 **502 Bad Gateway** 故障。该故障导致管理后台和 H5 客户端同时无法访问，表现为用户打开页面时直接返回 502 错误。

### 故障原因

经排查，502 故障的根因为：

1. **部署脚本被意外修改**：`deploy_remote.py` 在上一次会话中被替换为不完整的版本，缺少代码上传、完整的容器重建和 gateway 网络连接等关键步骤
2. **容器网络隔离**：新重建的 backend 和 admin-web 容器未正确连接到 gateway 所在的 Docker 网络，导致 Nginx 网关无法将请求转发到后端服务

### 修复措施

1. 恢复 `deploy_remote.py` 为正确的完整部署脚本版本
2. 恢复被删除的 `deploy_ssh.py`
3. 确认所有容器（backend、admin-web、h5-web、db）正常运行
4. 确认 gateway 与所有项目容器在同一 Docker 网络中
5. 全量链接可达性验证通过（20 个端点全部正常）

---

## 使用说明

### 管理后台登录

1. 在浏览器中打开管理后台地址：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/)
2. 在登录页面输入管理员手机号和密码
3. 点击「登录」按钮进入管理后台

### H5 客户端访问

1. 在浏览器（推荐手机浏览器）中打开 H5 地址：[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/)
2. 页面正常加载后即可使用各项健康管理功能

---

## 注意事项

1. 如果再次出现 502 错误，请优先检查 Docker 容器状态（`docker compose ps`）和容器日志（`docker compose logs --tail=50 backend`）
2. 部署新版本时请使用原始的 `deploy_remote.py` 脚本，该脚本包含完整的代码上传、容器构建和 gateway 网络连接流程
3. 部署完成后务必验证所有端点的可达性，确保 gateway 正确路由请求到各个容器
4. 切勿手动修改 `deploy_remote.py` 中的部署流程，避免遗漏关键步骤导致 502

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 管理后台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/) | 管理后台登录入口（经 Nginx 代理，端口 80） |
| H5 客户端 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 用户端首页入口（经 Nginx 代理，端口 80） |
