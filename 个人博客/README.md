# 个人笔记博客系统

这是一个基于Flask的个人笔记博客系统，专为记录和管理个人笔记设计。系统提供了丰富的笔记编辑、分类管理、标签、版本控制等功能，是您记录知识和思考的理想工具。

## 主要功能

### 笔记创建与编辑
- 快速创建笔记，支持快捷键（Ctrl+N）
- 完整的Markdown编辑器，支持各种格式化功能
- 实时预览编辑效果
- 图片上传与插入
- 自动保存功能，避免意外丢失

### 笔记分类管理
- 自定义分类，支持多层级分类结构
- 灵活的分类排序
- 多维度的组织方式

### 笔记搜索与筛选
- 全文搜索
- 按分类筛选
- 按标签筛选
- 按日期范围筛选

### 笔记展示与阅读
- 清晰的列表展示
- 优雅的阅读体验
- 自动生成目录导航

### 标签系统
- 为笔记添加多个标签
- 标签云可视化
- 按标签快速筛选内容

### 版本管理
- 自动记录笔记历史版本
- 查看历史版本内容
- 随时恢复到之前的版本

### 数据备份与恢复
- 一键备份所有笔记数据
- 从备份文件恢复数据

## 技术栈

- **后端**: Flask, SQLAlchemy, Flask-Login, Flask-Migrate
- **前端**: Bootstrap 5, JavaScript, jQuery, SimpleMDE, Marked.js
- **数据库**: SQLite (默认，可换成其他数据库)

## 安装与运行

### 前提条件

- Python 3.7 或更高版本
- pip (Python包管理器)

### 安装步骤

1. 克隆或下载本项目到本地

2. 进入项目目录
   ```
   cd 个人博客
   ```

3. 创建并激活虚拟环境（可选但推荐）
   ```
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

4. 安装依赖包
   ```
   pip install -r requirements.txt
   ```

5. 初始化数据库
   ```
   flask db init
   flask db migrate -m "初始化数据库"
   flask db upgrade
   ```

6. 运行应用
   ```
   flask run
   ```
   或
   ```
   python app.py
   ```

7. 访问应用
   打开浏览器，访问 `http://127.0.0.1:5000`

## 部署到Vercel

本项目可以部署到Vercel平台，按照以下步骤操作：

1. 确保项目已上传到GitHub

2. 在项目根目录中添加以下文件:
   - `vercel.json`: 配置部署设置
   - `wsgi.py`: WSGI入口点
   - 确保`requirements.txt`包含所有依赖

3. 在Vercel上导入项目:
   - 使用GitHub账号登录[Vercel](https://vercel.com/)
   - 点击"Add New Project"，从GitHub导入仓库
   - 配置项目设置（指定根目录等）
   - 点击"Deploy"开始部署

4. **注意事项**:
   - Vercel是无状态平台，不适合持久化存储
   - 对于生产环境，建议将TinyDB替换为MongoDB Atlas或其他云数据库
   - 用户上传的图片应存储在S3、Cloudinary等云存储服务

## 使用指南

1. 首次使用时，需要注册一个账号
2. 登录后，可以开始创建笔记
3. 使用左侧的分类栏和标签云来组织和筛选笔记
4. 可以在"分类管理"中创建和管理分类
5. 编辑笔记时可添加标签，标签之间用空格或逗号分隔
6. 查看笔记的历史版本，需进入笔记详情页，点击"历史版本"
7. 随时可以通过数据管理进行备份和恢复

## 自定义配置

可以在`app.py`文件中修改默认配置：

- `SECRET_KEY`: 应用密钥，请修改为随机字符串
- `SQLALCHEMY_DATABASE_URI`: 数据库连接URI
- `UPLOAD_FOLDER`: 上传文件存储路径
- `MAX_CONTENT_LENGTH`: 上传文件大小限制

## 联系方式

如有问题或建议，请提交Issue或Pull Request。

## 许可证

本项目采用MIT许可证。 