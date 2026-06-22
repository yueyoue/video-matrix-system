# 视频矩阵运营系统 - 桌面客户端

## 环境要求

- Python 3.11+
- PyQt6
- requests

## 安装依赖

```bash
cd client
pip install -r requirements.txt
```

## 启动方式

```bash
python main.py
```

## 项目结构

```
client/
├── main.py                 # 入口文件
├── requirements.txt        # Python依赖
├── app/
│   ├── __init__.py
│   ├── api.py             # API封装
│   ├── auth.py            # 登录认证
│   ├── views/
│   │   ├── login.py       # 登录页
│   │   ├── main_window.py # 主窗口
│   │   ├── dashboard.py   # 数据总览
│   │   ├── analysis.py    # 数据分析
│   │   ├── account.py     # 账号管理
│   │   ├── video.py       # 视频处理
│   │   ├── publish.py     # 发布调度
│   │   ├── config.py      # 接口配置
│   │   └── log_view.py    # 日志中心
│   ├── widgets/
│   │   ├── sidebar.py     # 侧边栏
│   │   ├── stat_card.py   # 统计卡片
│   │   └── toast.py       # 提示组件
│   └── styles/
│       └── theme.py       # 样式定义
```

## API 后端

默认后端地址：`http://localhost:3000/api`

请确保后端服务已启动后再运行客户端。
