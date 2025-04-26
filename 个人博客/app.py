import os
import time
import uuid
import json
import markdown
import bleach
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from db_tinydb import (
    UserModel, CategoryModel, TagModel, NoteModel, 
    VersionModel, HistoryModel, backup_data, restore_data,
    create_default_categories
)
import tempfile
import secrets

# 配置应用
app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_should_be_changed_in_production')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 限制上传文件大小为10MB

# 确保上传目录存在
upload_folder = app.config['UPLOAD_FOLDER']
os.makedirs(upload_folder, exist_ok=True)

# Vercel环境中的临时目录处理
if os.environ.get('VERCEL_ENV') == 'production':
    app.config['TEMP_FOLDER'] = '/tmp'
else:
    app.config['TEMP_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
    os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

# 初始化Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # 未登录时重定向到登录页面

# 添加min函数到Jinja2模板环境
@app.context_processor
def utility_processor():
    return {'min': min}

# 生成CSRF令牌函数
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

# 添加CSRF令牌到所有模板
@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf_token}

# 验证CSRF令牌的函数
def validate_csrf_token(request_token):
    token = session.get('csrf_token')
    return token and request_token and token == request_token

# CSRF保护装饰器
def csrf_protect(view_function):
    def wrapped_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token')
            if not token or not validate_csrf_token(token):
                flash('CSRF验证失败，请重试')
                return redirect(url_for('index'))
        return view_function(*args, **kwargs)
    wrapped_function.__name__ = view_function.__name__
    return wrapped_function

@login_manager.user_loader
def load_user(user_id):
    return UserModel.get_by_id(user_id)

@app.route('/')
def index():
    # 获取分类参数
    category_id = request.args.get('category')
    tag_id = request.args.get('tag')
    search = request.args.get('search')
    date_range = request.args.get('date_range')  # 'week' 或 'month'
    
    # 获取用户分类
    categories = []
    if current_user.is_authenticated:
        categories = CategoryModel.get_all_by_user(current_user.id)
    
    # 获取所有标签
    tags = TagModel.get_all()
    tag_counts = TagModel.get_usage_counts()
    
    # 获取笔记列表
    notes = []
    if current_user.is_authenticated:
        notes = NoteModel.get_all_by_user(
            current_user.id, 
            category_id=category_id, 
            tag_id=tag_id, 
            search=search, 
            date_range=date_range
        )
    else:
        # 未登录用户只能看到公开笔记
        notes = NoteModel.get_public_notes(
            category_id=category_id,
            tag_id=tag_id,
            search=search
        )
    
    return render_template(
        'index.html', 
        notes=notes, 
        categories=categories, 
        tags=tags,
        tag_counts=tag_counts
    )

@app.route('/register', methods=['GET', 'POST'])
@csrf_protect
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # 简单验证
        if not username or not password:
            flash('用户名和密码不能为空')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('两次输入的密码不一致')
            return redirect(url_for('register'))
        
        # 检查用户名是否已存在
        existing_user = UserModel.get_by_username(username)
        if existing_user:
            flash('用户名已存在，请选择其他用户名')
            return redirect(url_for('register'))
        
        # 创建新用户
        user = UserModel.create(username, password)
        
        # 创建默认分类
        create_default_categories(user.id)
        
        # 自动登录
        login_user(user)
        
        flash('注册成功，已自动登录')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@csrf_protect
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        # 验证用户名和密码
        user = UserModel.get_by_username(username)
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash('登录成功')
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已成功退出登录')
    return redirect(url_for('index'))

@app.route('/note/edit/<string:note_id>', methods=['GET', 'POST'])
@app.route('/note/new', methods=['GET', 'POST'])
@login_required
@csrf_protect
def edit_note(note_id=None):
    # 获取分类
    categories = CategoryModel.get_all_by_user(current_user.id)
    
    # 获取所有标签
    all_tags = TagModel.get_all()
    
    # 如果是编辑现有笔记
    note = None
    if note_id:
        note = NoteModel.get_by_id(note_id)
        if not note or note.user_id != current_user.id:
            flash('笔记不存在或您无权编辑')
            return redirect(url_for('index'))
    
    # 处理表单提交
    if request.method == 'POST':
        print(f"接收到表单提交: {request.form}")
        title = request.form.get('title')
        content = request.form.get('content')
        category_id = request.form.get('category_id') or None  # 处理空字符串
        is_public = 'is_public' in request.form
        tags = request.form.getlist('tags')  # 获取所有选中的标签
        
        print(f"表单数据: 标题={title}, 分类={category_id}, 公开={is_public}, 标签={tags}")
        
        # 简单验证
        if not title or not content:
            flash('标题和内容不能为空')
            print("验证失败: 标题或内容为空")
            return render_template('edit_note.html', note=note, categories=categories, all_tags=all_tags)
        
        try:
            # 创建或更新笔记
            if note:
                # 更新现有笔记
                print(f"更新笔记: {note.id}")
                NoteModel.update(
                    note.id,
                    title=title,
                    content=content,
                    category_id=category_id,
                    is_public=is_public,
                    user_id=current_user.id
                )
                # 更新标签
                NoteModel.set_tags(note.id, tags)
                
                flash('笔记已更新')
                return redirect(url_for('view_note', note_id=note.id))
            else:
                # 创建新笔记
                print("创建新笔记")
                new_note = NoteModel.create(
                    title=title,
                    content=content,
                    user_id=current_user.id,
                    category_id=category_id,
                    is_public=is_public
                )
                print(f"新笔记创建成功: {new_note.id}")
                # 设置标签
                NoteModel.set_tags(new_note.id, tags)
                
                flash('笔记已创建')
                return redirect(url_for('view_note', note_id=new_note.id))
        except Exception as e:
            print(f"保存笔记时发生错误: {e}")
            flash(f'保存笔记时发生错误: {str(e)}')
            return render_template('edit_note.html', note=note, categories=categories, all_tags=all_tags)
    
    return render_template('edit_note.html', note=note, categories=categories, all_tags=all_tags)

@app.route('/note/<string:note_id>')
def view_note(note_id):
    note = NoteModel.get_by_id(note_id)
    
    if not note:
        flash('笔记不存在')
        return redirect(url_for('index'))
    
    # 检查访问权限：笔记必须是公开的或属于当前用户
    if not note.is_public and (not current_user.is_authenticated or note.user_id != current_user.id):
        flash('您无权查看该笔记')
        return redirect(url_for('index'))
    
    # 将Markdown转换为HTML，并进行安全过滤
    content_html = markdown.markdown(
        note.content,
        extensions=['extra', 'codehilite', 'nl2br', 'tables']
    )
    
    # 允许的标签和属性
    allowed_tags = [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a', 'abbr', 'acronym', 'b', 'blockquote',
        'code', 'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul', 'br', 'div', 'span', 'hr',
        'img', 'table', 'tr', 'th', 'td', 'thead', 'tbody', 'input', 'del', 'ins'
    ]
    allowed_attrs = {
        '*': ['class', 'id', 'style'],
        'a': ['href', 'rel', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'input': ['type', 'checked', 'disabled']
    }
    
    # 清洗HTML内容
    content_html = bleach.clean(
        content_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    
    # 获取笔记标签
    tags = note.tags
    
    return render_template('view_note.html', note=note, content_html=content_html, tags=tags)

@app.route('/note/delete/<string:note_id>', methods=['POST'])
@login_required
@csrf_protect
def delete_note(note_id):
    note = NoteModel.get_by_id(note_id)
    
    if not note:
        flash('笔记不存在')
        return redirect(url_for('index'))
    
    if note.user_id != current_user.id:
        flash('您无权删除该笔记')
        return redirect(url_for('index'))
    
    # 删除笔记
    NoteModel.delete(note_id, current_user.id)
    
    flash('笔记已删除')
    return redirect(url_for('index'))

@app.route('/categories', methods=['GET'])
@login_required
def manage_categories():
    categories = CategoryModel.get_all_by_user(current_user.id)
    return render_template('categories.html', categories=categories)

@app.route('/category/add', methods=['POST'])
@login_required
@csrf_protect
def add_category():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id') or None
    
    if not name:
        flash('分类名称不能为空')
        return redirect(url_for('manage_categories'))
    
    # 检查父分类是否存在且属于当前用户
    if parent_id:
        parent = CategoryModel.get_by_id(parent_id)
        if not parent or parent.user_id != current_user.id:
            flash('父分类不存在或不属于您')
            return redirect(url_for('manage_categories'))
    
    # 获取所有分类，用于确定新分类的顺序
    existing_categories = CategoryModel.get_all_by_user(current_user.id)
    if existing_categories:
        max_order = max(c.order for c in existing_categories)
        order = max_order + 1
    else:
        order = 0
    
    # 创建新分类
    CategoryModel.create(name, current_user.id, parent_id, order)
    
    flash('分类已创建')
    return redirect(url_for('manage_categories'))

@app.route('/category/edit/<string:category_id>', methods=['POST'])
@login_required
@csrf_protect
def edit_category(category_id):
    category = CategoryModel.get_by_id(category_id)
    
    if not category:
        flash('分类不存在')
        return redirect(url_for('manage_categories'))
    
    if category.user_id != current_user.id:
        flash('您无权编辑该分类')
        return redirect(url_for('manage_categories'))
    
    name = request.form.get('name')
    parent_id = request.form.get('parent_id') or None
    
    if not name:
        flash('分类名称不能为空')
        return redirect(url_for('manage_categories'))
    
    # 检查父分类是否存在且属于当前用户
    if parent_id:
        parent = CategoryModel.get_by_id(parent_id)
        if not parent or parent.user_id != current_user.id:
            flash('父分类不存在或不属于您')
            return redirect(url_for('manage_categories'))
        
        # 防止循环引用：一个分类不能成为其子孙分类的父分类
        if parent_id == category_id:
            flash('分类不能作为自己的父分类')
            return redirect(url_for('manage_categories'))
    
    # 更新分类
    CategoryModel.update(category_id, name=name, parent_id=parent_id)
    
    flash('分类已更新')
    return redirect(url_for('manage_categories'))

@app.route('/category/delete/<string:category_id>', methods=['POST'])
@login_required
@csrf_protect
def delete_category(category_id):
    category = CategoryModel.get_by_id(category_id)
    
    if not category:
        flash('分类不存在')
        return redirect(url_for('manage_categories'))
    
    if category.user_id != current_user.id:
        flash('您无权删除该分类')
        return redirect(url_for('manage_categories'))
    
    # 删除分类
    CategoryModel.delete(category_id)
    
    flash('分类已删除')
    return redirect(url_for('manage_categories'))

@app.route('/category/reorder', methods=['POST'])
@login_required
def reorder_categories():
    data = request.get_json()
    
    if not data or 'categories' not in data:
        return jsonify({'success': False, 'error': '数据格式错误'}), 400
    
    # CSRF验证
    token = data.get('csrf_token')
    if not token or not validate_csrf_token(token):
        return jsonify({'success': False, 'error': 'CSRF验证失败'}), 403
    
    # 更新分类顺序
    for idx, cat_id in enumerate(data['categories']):
        category = CategoryModel.get_by_id(cat_id)
        if category and category.user_id == current_user.id:
            CategoryModel.update(cat_id, order=idx)
    
    return jsonify({'success': True})

@app.route('/tags', methods=['GET'])
@login_required
def manage_tags():
    tags = TagModel.get_all()
    tag_counts = TagModel.get_usage_counts()
    
    return render_template('tags.html', tags=tags, tag_counts=tag_counts)

@app.route('/note/history/<string:note_id>')
@login_required
def note_history(note_id):
    note = NoteModel.get_by_id(note_id)
    
    if not note:
        flash('笔记不存在')
        return redirect(url_for('index'))
    
    if note.user_id != current_user.id:
        flash('您无权查看该笔记的历史记录')
        return redirect(url_for('index'))
    
    # 获取笔记版本
    versions = NoteModel.get_versions(note_id)
    
    # 获取笔记操作历史
    changes = NoteModel.get_history(note_id)
    
    return render_template('note_history.html', note=note, versions=versions, changes=changes)

@app.route('/note/version/<string:version_id>')
@login_required
def view_note_version(version_id):
    version = VersionModel.get_by_id(version_id)
    
    if not version:
        flash('版本不存在')
        return redirect(url_for('index'))
    
    note = version.note
    
    if not note:
        flash('笔记不存在')
        return redirect(url_for('index'))
    
    # 权限检查：必须是笔记所有者
    if note.user_id != current_user.id:
        flash('您无权查看该笔记版本')
        return redirect(url_for('index'))
    
    # 将Markdown转换为HTML
    content_html = markdown.markdown(
        version.content,
        extensions=['extra', 'codehilite', 'nl2br', 'tables']
    )
    
    # 允许的标签和属性
    allowed_tags = [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a', 'abbr', 'acronym', 'b', 'blockquote',
        'code', 'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul', 'br', 'div', 'span', 'hr',
        'img', 'table', 'tr', 'th', 'td', 'thead', 'tbody', 'input', 'del', 'ins'
    ]
    allowed_attrs = {
        '*': ['class', 'id', 'style'],
        'a': ['href', 'rel', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'input': ['type', 'checked', 'disabled']
    }
    
    # 清洗HTML内容
    content_html = bleach.clean(
        content_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    
    return render_template('view_version.html', note=note, version=version, content_html=content_html)

@app.route('/note/compare')
@login_required
def compare_versions():
    old_version_id = request.args.get('old')
    new_version_id = request.args.get('new')
    note_id = request.args.get('note_id')
    
    if not old_version_id:
        flash('请选择要比较的旧版本')
        return redirect(url_for('note_history', note_id=note_id))
    
    # 获取旧版本
    old_version = VersionModel.get_by_id(old_version_id)
    if not old_version:
        flash('选择的旧版本不存在')
        return redirect(url_for('note_history', note_id=note_id))
    
    note = old_version.note
    
    # 权限检查
    if not note or note.user_id != current_user.id:
        flash('您无权访问该笔记')
        return redirect(url_for('index'))
    
    # 获取新版本数据
    if new_version_id:
        new_version = VersionModel.get_by_id(new_version_id)
        if not new_version:
            flash('选择的新版本不存在')
            return redirect(url_for('note_history', note_id=note.id))
        new_content = new_version.content
    else:
        # 如果没有指定新版本，使用当前笔记内容
        new_version = None
        new_content = note.content
    
    # 传递内容到模板
    old_content = old_version.content
    
    return render_template('version_compare.html', 
                          note=note,
                          old_version=old_version,
                          new_version=new_version,
                          old_content=old_content,
                          new_content=new_content)

@app.route('/note/restore/<string:version_id>', methods=['POST'])
@login_required
@csrf_protect
def restore_note_version(version_id):
    version = VersionModel.get_by_id(version_id)
    
    if not version:
        flash('版本不存在')
        return redirect(url_for('index'))
    
    note = version.note
    
    if not note:
        flash('笔记不存在')
        return redirect(url_for('index'))
    
    if note.user_id != current_user.id:
        flash('您无权恢复该笔记的历史版本')
        return redirect(url_for('index'))
    
    # 保存当前版本为历史版本
    last_version = NoteModel.get_last_version_number(note.id)
    VersionModel.create(note.id, note.content, last_version + 1)
    
    # 更新笔记内容为历史版本的内容
    NoteModel.update(
        note.id,
        content=version.content,
        user_id=current_user.id
    )
    
    # 记录恢复操作
    HistoryModel.create(
        note.id,
        current_user.id,
        'restore',
        f"恢复到版本 {version.version_number} ({version.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
    )
    
    flash('笔记已恢复到历史版本')
    return redirect(url_for('view_note', note_id=note.id))

@app.route('/backup', methods=['GET', 'POST'])
@login_required
def backup_data_route():
    if request.method == 'POST':
        # 获取备份选项
        backup_scope = request.form.get('backup_scope', 'all')
        category_id = request.form.get('category_id') if backup_scope == 'category' else None
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        
        # 创建临时目录
        temp_dir = os.path.join(tempfile.gettempdir(), f'note_backup_{current_user.id}_{int(time.time())}')
        os.makedirs(temp_dir, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"note_backup_{timestamp}.json"
        backup_path = os.path.join(temp_dir, backup_filename)
        
        # 执行备份
        try:
            backup_data(current_user.id, backup_path, category_id=category_id, date_from=date_from, date_to=date_to)
            
            # 发送文件给用户下载
            return send_file(
                backup_path,
                as_attachment=True,
                download_name=backup_filename,
                mimetype='application/json'
            )
        except Exception as e:
            flash(f'备份失败: {str(e)}')
            return redirect(url_for('backup_data_route'))
    
    # GET请求 - 显示备份页面
    # 获取用户的所有笔记
    notes = NoteModel.get_all_by_user(current_user.id)
    
    # 获取分类
    categories = CategoryModel.get_all_by_user(current_user.id)
    
    # 获取自动备份信息
    auto_backups = []
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups', current_user.id)
    if os.path.exists(backup_dir):
        for filename in os.listdir(backup_dir):
            if filename.endswith('.json') and filename != 'backup_info.json':
                file_path = os.path.join(backup_dir, filename)
                file_size = os.path.getsize(file_path) / 1024  # KB
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # 读取备份内容以获取笔记数量
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        backup_content = json.load(f)
                        note_count = len(backup_content.get('notes', []))
                except:
                    note_count = 0
                
                auto_backups.append({
                    'filename': filename,
                    'date': file_time,
                    'size': f"{file_size:.2f} KB",
                    'note_count': note_count,
                    'is_auto': filename.startswith('auto_backup_')
                })
        
        # 按时间排序（最新的在前）
        auto_backups.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template(
        'backup.html', 
        notes=notes, 
        categories=categories, 
        auto_backups=auto_backups,
        note_count=len(notes)
    )

@app.route('/backup/download/<string:filename>')
@login_required
def download_auto_backup(filename):
    # 安全检查 - 防止目录遍历
    if '..' in filename or '/' in filename:
        flash('无效的文件名')
        return redirect(url_for('backup_data_route'))
    
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups', current_user.id)
    file_path = os.path.join(backup_dir, filename)
    
    # 检查文件是否存在且属于当前用户
    if not os.path.exists(file_path):
        flash('备份文件不存在')
        return redirect(url_for('backup_data_route'))
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/json'
    )

@app.route('/backup/delete/<string:filename>', methods=['POST'])
@login_required
@csrf_protect
def delete_auto_backup(filename):
    # 安全检查 - 防止目录遍历
    if '..' in filename or '/' in filename:
        flash('无效的文件名')
        return redirect(url_for('backup_data_route'))
    
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups', current_user.id)
    file_path = os.path.join(backup_dir, filename)
    
    # 检查文件是否存在且属于当前用户
    if not os.path.exists(file_path):
        flash('备份文件不存在')
        return redirect(url_for('backup_data_route'))
    
    # 删除文件
    try:
        os.remove(file_path)
        flash(f'已删除备份: {filename}')
    except Exception as e:
        flash(f'删除备份失败: {str(e)}')
    
    return redirect(url_for('backup_data_route'))

@app.route('/restore', methods=['GET', 'POST'])
@login_required
def restore_data_route():
    if request.method == 'POST':
        # 检查CSRF令牌
        token = request.form.get('csrf_token')
        if not token or not validate_csrf_token(token):
            flash('表单已过期，请重新提交', 'danger')
            return redirect(url_for('restore_data_route'))
        
        # 获取上传的文件
        if 'backup_file' not in request.files:
            flash('未找到备份文件', 'danger')
            return redirect(request.url)
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('未选择备份文件', 'danger')
            return redirect(request.url)
        
        # 检验文件类型
        if not file.filename.endswith('.json'):
            flash('仅支持 .json 格式的备份文件', 'danger')
            return redirect(request.url)
        
        # 检查文件大小
        if file.content_length and file.content_length > 50 * 1024 * 1024:  # 50MB限制
            flash('备份文件太大，超过50MB限制', 'danger')
            return redirect(request.url)
            
        # 获取恢复模式
        restore_mode = request.form.get('restore_mode', 'add')
        if restore_mode not in ['add', 'overwrite']:
            restore_mode = 'add'
        
        try:
            # 创建临时文件来保存上传的备份
            import tempfile
            import os
            import time
            
            # 创建临时文件
            temp_dir = tempfile.gettempdir()
            temp_file_name = f"backup_{current_user.id}_{int(time.time())}.json"
            temp_file_path = os.path.join(temp_dir, temp_file_name)
            
            app.logger.info(f"保存备份文件到临时位置: {temp_file_path}")
            
            try:
                # 保存上传文件
                file.save(temp_file_path)
                
                # 验证文件是否成功保存
                if not os.path.exists(temp_file_path):
                    raise Exception("临时文件保存失败")
                
                # 验证文件大小
                file_size = os.path.getsize(temp_file_path)
                if file_size == 0:
                    raise Exception("备份文件为空")
                
                app.logger.info(f"文件已保存，大小: {file_size} 字节")
                
                # 调用恢复函数，传入文件路径
                success, message = restore_data(current_user.id, temp_file_path, restore_mode=restore_mode)
                
                # 恢复完成后删除临时文件
                try:
                    os.remove(temp_file_path)
                    app.logger.info(f"临时文件已删除: {temp_file_path}")
                except Exception as e:
                    app.logger.warning(f"无法删除临时文件: {temp_file_path}, 错误: {str(e)}")
                
                if success:
                    flash(message, 'success')
                    return redirect(url_for('index'))
                else:
                    app.logger.error(f"恢复失败: {message}")
                    flash(message, 'danger')
                    return redirect(request.url)
            except json.JSONDecodeError:
                flash('备份文件不是有效的JSON格式', 'danger')
                return redirect(request.url)
            except Exception as e:
                if os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                raise e
                
        except Exception as e:
            app.logger.error(f"恢复数据失败: {str(e)}", exc_info=True)
            flash(f'恢复数据失败: {str(e)}', 'danger')
            return redirect(request.url)
    
    return render_template('restore.html', csrf_token=generate_csrf_token())

@app.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    try:
        # CSRF验证
        token = request.form.get('csrf_token')
        if not token or not validate_csrf_token(token):
            print(f"CSRF验证失败: {token}")
            return jsonify({'error': 'CSRF验证失败'}), 403
        
        if 'image' not in request.files:
            print("请求中没有图片文件")
            return jsonify({'error': '未选择图片文件'}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            print("文件名为空")
            return jsonify({'error': '未选择图片文件'}), 400
        
        print(f"尝试上传文件: {file.filename}")
        
        if file and allowed_file(file.filename):
            # 生成安全的文件名
            filename = secure_filename(file.filename)
            
            # 生成唯一文件名（使用时间戳和随机ID）
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            unique_filename = f"{timestamp}_{str(uuid.uuid4().hex[:8])}_{filename}"
            
            # 确定保存路径
            year_month = datetime.now().strftime('%Y%m')
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], year_month)
            
            print(f"上传路径: {upload_path}")
            
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
            
            file_path = os.path.join(upload_path, unique_filename)
            
            # 保存文件
            file.save(file_path)
            print(f"文件已保存到: {file_path}")
            
            # 返回文件URL
            file_url = url_for('static', filename=f'uploads/{year_month}/{unique_filename}')
            print(f"图片URL: {file_url}")
            
            return jsonify({'url': file_url})
        else:
            print(f"不支持的文件类型: {file.filename}")
            return jsonify({'error': f'不支持的文件类型: {file.filename}'}), 400
    except Exception as e:
        print(f"图片上传异常: {str(e)}")
        return jsonify({'error': f'上传图片时发生错误: {str(e)}'}), 500

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/note/autosave', methods=['POST'])
@login_required
def autosave_note():
    note_id = request.form.get('note_id')
    title = request.form.get('title')
    content = request.form.get('content')
    csrf_token = request.form.get('csrf_token')
    
    if not note_id or not title or not content:
        return jsonify({'error': '参数不完整'}), 400
    
    # CSRF验证
    if not csrf_token or not validate_csrf_token(csrf_token):
        return jsonify({'error': 'CSRF验证失败'}), 403
    
    # 获取笔记
    note = NoteModel.get_by_id(note_id)
    if not note:
        return jsonify({'error': '笔记不存在'}), 404
    
    # 检查权限
    if note.user_id != current_user.id:
        return jsonify({'error': '无权修改此笔记'}), 403
    
    # 自动保存笔记
    if NoteModel.autosave(note_id, title, content, current_user.id):
        return jsonify({'success': True})
    else:
        return jsonify({'error': '保存失败'}), 500

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# 在文件最后添加这段代码，确保Vercel可以找到app实例
app.debug = False
# 确保应用可被Vercel识别
application = app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
