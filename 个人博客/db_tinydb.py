import os
import json
import uuid
import datetime
import hashlib
from datetime import datetime
from flask_login import UserMixin
from tinydb import TinyDB, Query, where
from tinydb.operations import set
from tinydb.table import Document
from werkzeug.security import generate_password_hash, check_password_hash
import shutil
import tempfile
import time

# 确保数据目录存在 - 使用临时目录确保有写入权限
DB_FOLDER = os.path.join(tempfile.gettempdir(), 'personal_blog_data')
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)
    print(f"创建数据目录: {DB_FOLDER}")

# 为不同实体创建不同的TinyDB数据库文件
USER_DB = os.path.join(DB_FOLDER, 'users.json')
CATEGORY_DB = os.path.join(DB_FOLDER, 'categories.json')
TAG_DB = os.path.join(DB_FOLDER, 'tags.json')
NOTE_DB = os.path.join(DB_FOLDER, 'notes.json')
NOTE_TAG_DB = os.path.join(DB_FOLDER, 'note_tags.json')
VERSION_DB = os.path.join(DB_FOLDER, 'versions.json')
HISTORY_DB = os.path.join(DB_FOLDER, 'history.json')

# 初始化数据库连接
db_users = TinyDB(USER_DB)
db_categories = TinyDB(CATEGORY_DB)
db_tags = TinyDB(TAG_DB)
db_notes = TinyDB(NOTE_DB)
db_note_tags = TinyDB(NOTE_TAG_DB)
db_versions = TinyDB(VERSION_DB)
db_history = TinyDB(HISTORY_DB)

# 定义查询对象
User = Query()
Category = Query()
Tag = Query()
Note = Query()
NoteTag = Query()
Version = Query()
History = Query()

# 辅助函数 - 获取当前ISO格式时间
def now():
    return datetime.now().isoformat()

# 辅助函数 - 转换ISO格式字符串为datetime对象
def iso_to_datetime(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except ValueError:
        return None

# 辅助函数 - 生成ID
def generate_id():
    return str(uuid.uuid4())

# 用户模型
class UserModel(UserMixin):
    def __init__(self, id, username, password_hash, created_at=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'password_hash': self.password_hash,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def create(cls, username, password):
        user_id = generate_id()
        password_hash = generate_password_hash(password)
        created_at = now()
        
        user_data = {
            'id': user_id,
            'username': username,
            'password_hash': password_hash,
            'created_at': created_at
        }
        
        db_users.insert(user_data)
        return cls(user_id, username, password_hash, created_at)
    
    @classmethod
    def get_by_id(cls, user_id):
        user = db_users.get(User.id == user_id)
        if not user:
            return None
        return cls(user['id'], user['username'], user['password_hash'], user['created_at'])
    
    @classmethod
    def get_by_username(cls, username):
        user = db_users.get(User.username == username)
        if not user:
            return None
        return cls(user['id'], user['username'], user['password_hash'], user['created_at'])

# 分类模型
class CategoryModel:
    def __init__(self, id, name, user_id, parent_id=None, order=0, created_at=None):
        self.id = id
        self.name = name
        self.user_id = user_id
        self.parent_id = parent_id
        self.order = order
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'user_id': self.user_id,
            'parent_id': self.parent_id,
            'order': self.order,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def create(cls, name, user_id, parent_id=None, order=0):
        category_id = generate_id()
        created_at = now()
        
        category_data = {
            'id': category_id,
            'name': name,
            'user_id': user_id,
            'parent_id': parent_id,
            'order': order,
            'created_at': created_at
        }
        
        db_categories.insert(category_data)
        return cls(category_id, name, user_id, parent_id, order, created_at)
    
    @classmethod
    def get_by_id(cls, category_id):
        category = db_categories.get(Category.id == category_id)
        if not category:
            return None
        return cls(
            category['id'], 
            category['name'], 
            category['user_id'], 
            category.get('parent_id'), 
            category.get('order', 0), 
            category['created_at']
        )
    
    @classmethod
    def get_all_by_user(cls, user_id):
        categories = db_categories.search(Category.user_id == user_id)
        # 按order排序
        categories.sort(key=lambda x: x.get('order', 0))
        return [cls(
            c['id'], 
            c['name'], 
            c['user_id'], 
            c.get('parent_id'), 
            c.get('order', 0), 
            c['created_at']
        ) for c in categories]
    
    @classmethod
    def update(cls, category_id, name=None, parent_id=None, order=None):
        category = db_categories.get(Category.id == category_id)
        if not category:
            return False
        
        updates = {}
        if name is not None:
            updates['name'] = name
        if parent_id is not None:
            updates['parent_id'] = parent_id
        if order is not None:
            updates['order'] = order
        
        if updates:
            db_categories.update(updates, Category.id == category_id)
            return True
        return False
    
    @classmethod
    def delete(cls, category_id):
        # 先获取该分类下的所有笔记，更新为无分类
        db_notes.update({'category_id': None}, Note.category_id == category_id)
        
        # 更新所有子分类的parent_id为None
        db_categories.update({'parent_id': None}, Category.parent_id == category_id)
        
        # 删除分类
        db_categories.remove(Category.id == category_id)
        return True

# 标签模型
class TagModel:
    def __init__(self, id, name, created_at=None):
        self.id = id
        self.name = name
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def create(cls, name):
        # 检查标签是否已存在
        existing = db_tags.get(Tag.name == name)
        if existing:
            return cls(existing['id'], existing['name'], existing['created_at'])
        
        tag_id = generate_id()
        created_at = now()
        
        tag_data = {
            'id': tag_id,
            'name': name,
            'created_at': created_at
        }
        
        db_tags.insert(tag_data)
        return cls(tag_id, name, created_at)
    
    @classmethod
    def get_by_id(cls, tag_id):
        tag = db_tags.get(Tag.id == tag_id)
        if not tag:
            return None
        return cls(tag['id'], tag['name'], tag['created_at'])
    
    @classmethod
    def get_by_name(cls, name):
        tag = db_tags.get(Tag.name == name)
        if not tag:
            return None
        return cls(tag['id'], tag['name'], tag['created_at'])
    
    @classmethod
    def get_all(cls):
        tags = db_tags.all()
        return [cls(t['id'], t['name'], t['created_at']) for t in tags]
    
    @classmethod
    def get_usage_counts(cls):
        """返回所有标签的使用次数"""
        tags = db_tags.all()
        result = {}
        
        for tag in tags:
            count = len(db_note_tags.search(NoteTag.tag_id == tag['id']))
            result[tag['id']] = count
        
        return result

# 笔记模型
class NoteModel:
    def __init__(self, id, title, content, user_id, category_id=None, created_at=None, 
                 updated_at=None, is_public=False):
        self.id = id
        self.title = title
        self.content = content
        self.user_id = user_id
        self.category_id = category_id
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
        self.updated_at = iso_to_datetime(updated_at) if updated_at else datetime.now()
        self.is_public = is_public
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'user_id': self.user_id,
            'category_id': self.category_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_public': self.is_public
        }
    
    @property
    def note_tags(self):
        """获取笔记关联的标签关系"""
        note_tags_data = db_note_tags.search(NoteTag.note_id == self.id)
        return [NoteTagModel(
            nt['id'], 
            nt['note_id'], 
            nt['tag_id'], 
            nt['created_at']
        ) for nt in note_tags_data]
    
    @property
    def tags(self):
        """获取笔记的所有标签"""
        note_tags_data = db_note_tags.search(NoteTag.note_id == self.id)
        tags = []
        for nt in note_tags_data:
            tag = db_tags.get(Tag.id == nt['tag_id'])
            if tag:
                tags.append(TagModel(tag['id'], tag['name'], tag['created_at']))
        return tags
    
    @property
    def category(self):
        """获取笔记的分类"""
        if not self.category_id:
            return None
        category = db_categories.get(Category.id == self.category_id)
        if not category:
            return None
        return CategoryModel(
            category['id'], 
            category['name'], 
            category['user_id'], 
            category.get('parent_id'), 
            category.get('order', 0), 
            category['created_at']
        )
    
    @property
    def author(self):
        """获取笔记的作者"""
        user = db_users.get(User.id == self.user_id)
        if not user:
            return None
        return UserModel(user['id'], user['username'], user['password_hash'], user['created_at'])
    
    @classmethod
    def create(cls, title, content, user_id, category_id=None, is_public=False):
        note_id = generate_id()
        created_at = now()
        updated_at = created_at
        
        note_data = {
            'id': note_id,
            'title': title,
            'content': content,
            'user_id': user_id,
            'category_id': category_id,
            'created_at': created_at,
            'updated_at': updated_at,
            'is_public': is_public
        }
        
        # 插入数据库
        db_notes.insert(note_data)
        
        # 创建历史记录
        HistoryModel.create(note_id, user_id, 'create', '创建笔记')
        
        # 添加初始版本
        version_number = 1
        VersionModel.create(note_id, content, version_number)
        
        # 返回笔记对象
        print(f"笔记创建成功: {note_id}")
        return cls(
            note_id, title, content, user_id, category_id, 
            created_at, updated_at, is_public
        )
    
    @classmethod
    def get_by_id(cls, note_id):
        note = db_notes.get(Note.id == note_id)
        if not note:
            return None
        return cls(
            note['id'], 
            note['title'], 
            note['content'], 
            note['user_id'], 
            note.get('category_id'), 
            note['created_at'], 
            note['updated_at'], 
            note.get('is_public', False)
        )
    
    @classmethod
    def get_all_by_user(cls, user_id, category_id=None, tag_id=None, search=None, date_range=None):
        # 基本查询条件
        User = Query()
        query = User.user_id == user_id
        
        # 添加额外过滤条件
        if category_id:
            query = (query) & (User.category_id == category_id)
        
        notes = db_notes.search(query)
        
        # 标签过滤
        if tag_id:
            note_ids = [nt['note_id'] for nt in db_note_tags.search(NoteTag.tag_id == tag_id)]
            notes = [note for note in notes if note['id'] in note_ids]
        
        # 搜索过滤
        if search:
            search = search.lower()
            filtered_notes = []
            for note in notes:
                if (search in note['title'].lower() or 
                    search in note['content'].lower()):
                    filtered_notes.append(note)
                else:
                    # 检查标签中是否包含搜索词
                    note_tags = db_note_tags.search(NoteTag.note_id == note['id'])
                    for nt in note_tags:
                        tag = db_tags.get(Tag.id == nt['tag_id'])
                        if tag and search in tag['name'].lower():
                            filtered_notes.append(note)
                            break
            notes = filtered_notes
        
        # 日期范围过滤
        if date_range:
            now = datetime.now()
            if date_range == 'week':
                # 最近一周
                start_date = (now - timedelta(days=7))
            elif date_range == 'month':
                # 最近一个月
                start_date = (now - timedelta(days=30))
            else:
                start_date = None
            
            if start_date:
                start_date_str = start_date.isoformat()
                notes = [note for note in notes if note['updated_at'] >= start_date_str]
        
        # 转换为对象
        result = [cls(
            note['id'], 
            note['title'], 
            note['content'], 
            note['user_id'], 
            note.get('category_id'), 
            note['created_at'], 
            note['updated_at'], 
            note.get('is_public', False)
        ) for note in notes]
        
        # 按更新时间排序，最新的在前
        result.sort(key=lambda x: x.updated_at, reverse=True)
        
        return result
    
    @classmethod
    def get_public_notes(cls, category_id=None, tag_id=None, search=None):
        # 基本查询条件
        query = Note.is_public == True
        
        # 添加额外过滤条件
        if category_id:
            query = (query) & (Note.category_id == category_id)
        
        notes = db_notes.search(query)
        
        # 标签过滤
        if tag_id:
            note_ids = [nt['note_id'] for nt in db_note_tags.search(NoteTag.tag_id == tag_id)]
            notes = [note for note in notes if note['id'] in note_ids]
        
        # 搜索过滤
        if search:
            search = search.lower()
            filtered_notes = []
            for note in notes:
                if (search in note['title'].lower() or 
                    search in note['content'].lower()):
                    filtered_notes.append(note)
                else:
                    # 检查标签中是否包含搜索词
                    note_tags = db_note_tags.search(NoteTag.note_id == note['id'])
                    for nt in note_tags:
                        tag = db_tags.get(Tag.id == nt['tag_id'])
                        if tag and search in tag['name'].lower():
                            filtered_notes.append(note)
                            break
            notes = filtered_notes
        
        # 转换为对象
        result = [cls(
            note['id'], 
            note['title'], 
            note['content'], 
            note['user_id'], 
            note.get('category_id'), 
            note['created_at'], 
            note['updated_at'], 
            note.get('is_public', False)
        ) for note in notes]
        
        # 按更新时间排序，最新的在前
        result.sort(key=lambda x: x.updated_at, reverse=True)
        
        return result
    
    @classmethod
    def update(cls, note_id, title=None, content=None, category_id=None, is_public=None, user_id=None):
        """更新笔记（创建历史记录和版本）"""
        note = db_notes.get(Note.id == note_id)
        if not note:
            return False
        
        # 权限检查
        if user_id and note['user_id'] != user_id:
            return False
        
        updates = {}
        if title is not None:
            updates['title'] = title
        if content is not None:
            updates['content'] = content
            # 创建一个新版本
            version_number = cls.get_last_version_number(note_id) + 1
            VersionModel.create(note_id, content, version_number, save_type='manual')
        if category_id is not None:
            updates['category_id'] = category_id
        if is_public is not None:
            updates['is_public'] = is_public
        
        if updates:
            updates['updated_at'] = now()
            db_notes.update(updates, Note.id == note_id)
            
            # 创建历史记录
            HistoryModel.create(note_id, note['user_id'], 'edit', '编辑笔记')
            
            return True
        
        return False
    
    @classmethod
    def delete(cls, note_id, user_id):
        # 先记录历史
        note = db_notes.get(Note.id == note_id)
        if note:
            HistoryModel.create(note_id, user_id, 'delete', f"删除笔记: {note.get('title', '')}")
            
            # 删除笔记标签关系
            db_note_tags.remove(NoteTag.note_id == note_id)
            
            # 删除笔记版本
            db_versions.remove(Version.note_id == note_id)
            
            # 删除笔记
            db_notes.remove(Note.id == note_id)
            return True
        return False
    
    @classmethod
    def set_tags(cls, note_id, tag_names):
        """设置笔记的标签（替换现有标签）"""
        # 先删除现有标签关系
        db_note_tags.remove(NoteTag.note_id == note_id)
        
        # 添加新标签
        for name in tag_names:
            name = name.strip()
            if name:
                # 创建或获取标签
                tag = TagModel.create(name)
                # 创建标签关系
                NoteTagModel.create(note_id, tag.id)
    
    @classmethod
    def get_versions(cls, note_id):
        """获取笔记的所有版本"""
        versions = db_versions.search(Version.note_id == note_id)
        versions.sort(key=lambda v: v['version_number'])
        return [VersionModel(
            v['id'],
            v['note_id'],
            v['content'],
            v['version_number'],
            v['created_at']
        ) for v in versions]
    
    @classmethod
    def get_history(cls, note_id):
        """获取笔记的历史记录"""
        history = db_history.search(History.note_id == note_id)
        history.sort(key=lambda h: h['created_at'], reverse=True)
        return [HistoryModel(
            h['id'],
            h['note_id'],
            h['user_id'],
            h['change_type'],
            h.get('details'),
            h['created_at']
        ) for h in history]
    
    @classmethod
    def get_last_version_number(cls, note_id):
        """获取笔记的最后版本号"""
        versions = db_versions.search(Version.note_id == note_id)
        if not versions:
            return 0
        return max(v['version_number'] for v in versions)
    
    @classmethod
    def autosave(cls, note_id, title, content, user_id):
        """自动保存笔记（不创建历史记录，但创建自动保存版本）"""
        note = db_notes.get(Note.id == note_id)
        if not note or note['user_id'] != user_id:
            return False
        
        # 检查内容是否有显著变化，避免频繁创建几乎相同的版本
        if note['content'] == content:
            # 仅更新时间戳，但不创建新版本
            db_notes.update({'updated_at': now()}, Note.id == note_id)
            return True
        
        updates = {
            'title': title,
            'content': content,
            'updated_at': now()
        }
        
        # 创建一个自动保存版本
        version_number = cls.get_last_version_number(note_id) + 1
        VersionModel.create(note_id, content, version_number, save_type='auto')
        
        db_notes.update(updates, Note.id == note_id)
        return True

# 笔记标签关系模型
class NoteTagModel:
    def __init__(self, id, note_id, tag_id, created_at=None):
        self.id = id
        self.note_id = note_id
        self.tag_id = tag_id
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'note_id': self.note_id,
            'tag_id': self.tag_id,
            'created_at': self.created_at.isoformat()
        }
    
    @property
    def tag(self):
        """获取关联的标签"""
        tag = db_tags.get(Tag.id == self.tag_id)
        if not tag:
            return None
        return TagModel(tag['id'], tag['name'], tag['created_at'])
    
    @property
    def note(self):
        """获取关联的笔记"""
        note = db_notes.get(Note.id == self.note_id)
        if not note:
            return None
        return NoteModel(
            note['id'], 
            note['title'], 
            note['content'], 
            note['user_id'], 
            note.get('category_id'), 
            note['created_at'], 
            note['updated_at'], 
            note.get('is_public', False)
        )
    
    @classmethod
    def create(cls, note_id, tag_id):
        # 检查是否已存在相同关系
        existing = db_note_tags.get((NoteTag.note_id == note_id) & (NoteTag.tag_id == tag_id))
        if existing:
            return cls(existing['id'], existing['note_id'], existing['tag_id'], existing['created_at'])
        
        note_tag_id = generate_id()
        created_at = now()
        
        note_tag_data = {
            'id': note_tag_id,
            'note_id': note_id,
            'tag_id': tag_id,
            'created_at': created_at
        }
        
        db_note_tags.insert(note_tag_data)
        return cls(note_tag_id, note_id, tag_id, created_at)

# 笔记版本模型
class VersionModel:
    def __init__(self, id, note_id, content, version_number, created_at=None, save_type='manual'):
        self.id = id
        self.note_id = note_id
        self.content = content
        self.version_number = version_number
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
        self.save_type = save_type  # 'auto' 或 'manual'
    
    def to_dict(self):
        return {
            'id': self.id,
            'note_id': self.note_id,
            'content': self.content,
            'version_number': self.version_number,
            'created_at': self.created_at.isoformat(),
            'save_type': self.save_type
        }
    
    @property
    def note(self):
        """获取关联的笔记"""
        note = db_notes.get(Note.id == self.note_id)
        if not note:
            return None
        return NoteModel(
            note['id'], 
            note['title'], 
            note['content'], 
            note['user_id'], 
            note.get('category_id'), 
            note['created_at'], 
            note['updated_at'], 
            note.get('is_public', False)
        )
    
    @classmethod
    def create(cls, note_id, content, version_number, save_type='manual'):
        version_id = generate_id()
        created_at = now()
        
        version_data = {
            'id': version_id,
            'note_id': note_id,
            'content': content,
            'version_number': version_number,
            'created_at': created_at,
            'save_type': save_type
        }
        
        db_versions.insert(version_data)
        return cls(version_id, note_id, content, version_number, created_at, save_type)
    
    @classmethod
    def get_by_id(cls, version_id):
        version = db_versions.get(Version.id == version_id)
        if not version:
            return None
        return cls(
            version['id'], 
            version['note_id'], 
            version['content'], 
            version['version_number'], 
            version['created_at']
        )

# 笔记历史模型
class HistoryModel:
    def __init__(self, id, note_id, user_id, change_type, details=None, created_at=None):
        self.id = id
        self.note_id = note_id
        self.user_id = user_id
        self.change_type = change_type
        self.details = details
        self.created_at = iso_to_datetime(created_at) if created_at else datetime.now()
    
    def to_dict(self):
        return {
            'id': self.id,
            'note_id': self.note_id,
            'user_id': self.user_id,
            'change_type': self.change_type,
            'details': self.details,
            'created_at': self.created_at.isoformat()
        }
    
    @property
    def note(self):
        """获取关联的笔记"""
        note = db_notes.get(Note.id == self.note_id)
        if not note:
            return None
        return NoteModel(
            note['id'], 
            note['title'], 
            note['content'], 
            note['user_id'], 
            note.get('category_id'), 
            note['created_at'], 
            note['updated_at'], 
            note.get('is_public', False)
        )
    
    @property
    def user(self):
        """获取关联的用户"""
        user = db_users.get(User.id == self.user_id)
        if not user:
            return None
        return UserModel(user['id'], user['username'], user['password_hash'], user['created_at'])
    
    @classmethod
    def create(cls, note_id, user_id, change_type, details=None):
        history_id = generate_id()
        created_at = now()
        
        history_data = {
            'id': history_id,
            'note_id': note_id,
            'user_id': user_id,
            'change_type': change_type,
            'details': details,
            'created_at': created_at
        }
        
        db_history.insert(history_data)
        return cls(history_id, note_id, user_id, change_type, details, created_at)

# 数据备份与恢复功能
def backup_data(user_id, backup_dir=None, category_id=None, date_from=None, date_to=None):
    """备份用户数据
    
    Args:
        user_id: 用户ID
        backup_dir: 备份文件路径，如果为None则使用临时目录
        category_id: 仅备份指定分类的笔记
        date_from: 开始日期，格式为YYYY-MM-DD
        date_to: 结束日期，格式为YYYY-MM-DD
    
    Returns:
        str: 备份文件路径
    """
    try:
        # 确保用户存在
        user = db_users.get(User.id == user_id)
        if not user:
            return None
        
        # 创建临时目录
        if backup_dir is None:
            import tempfile
            backup_dir = os.path.join(tempfile.gettempdir(), f'note_backup_{user_id}_{int(time.time())}')
            os.makedirs(backup_dir, exist_ok=True)
        elif not os.path.isdir(backup_dir):
            # 如果是文件路径，使用其作为备份文件路径
            backup_file = backup_dir
        else:
            # 创建备份文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'note_backup_{timestamp}.json')
        
        # 准备过滤条件
        note_filter = (Note.user_id == user_id)
        if category_id:
            note_filter &= (Note.category_id == category_id)
        
        # 获取笔记
        notes = db_notes.search(note_filter)
        
        # 按日期筛选
        if date_from or date_to:
            filtered_notes = []
            for note in notes:
                created_at = iso_to_datetime(note['created_at'])
                if date_from:
                    from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                    if created_at.date() < from_date:
                        continue
                if date_to:
                    to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                    if created_at.date() > to_date:
                        continue
                filtered_notes.append(note)
            notes = filtered_notes
        
        # 创建备份数据结构
        backup_data = {
            'metadata': {
                'version': '1.0',
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'username': user['username'],
                'note_count': len(notes)
            },
            'notes': notes,
            'categories': db_categories.search(Category.user_id == user_id)
        }
        
        # 获取笔记关联的标签
        note_ids = [note['id'] for note in notes]
        note_tags = db_note_tags.search(NoteTag.note_id.one_of(note_ids))
        
        # 获取关联的标签
        tag_ids = [nt['tag_id'] for nt in note_tags]
        tags = [tag for tag in db_tags.all() if tag['id'] in tag_ids]
        
        # 添加到备份数据
        backup_data['note_tags'] = note_tags
        backup_data['tags'] = tags
        
        # 备份版本
        versions = []
        for note_id in note_ids:
            note_versions = db_versions.search(Version.note_id == note_id)
            versions.extend(note_versions)
        
        backup_data['versions'] = versions
        
        # 备份历史记录
        histories = []
        for note_id in note_ids:
            note_histories = db_history.search(History.note_id == note_id)
            histories.extend(note_histories)
        
        backup_data['histories'] = histories
        
        # 写入备份文件
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=4)
        
        return backup_file
    except Exception as e:
        print(f"备份失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def restore_data(user_id, backup_file, restore_mode='add'):
    """从备份文件恢复数据
    
    Args:
        user_id: 用户ID
        backup_file: 备份文件路径
        restore_mode: 恢复模式，'add'仅添加新内容，'overwrite'覆盖现有内容
    
    Returns:
        tuple: (bool, str) 是否成功及消息
    """
    try:
        # 确保用户存在
        user = db_users.get(User.id == user_id)
        if not user:
            return False, "用户不存在"
        
        # 检查文件是否存在
        if not os.path.exists(backup_file):
            return False, f"备份文件不存在: {backup_file}"
            
        # 检查文件是否可读
        if not os.access(backup_file, os.R_OK):
            return False, f"无法读取备份文件: {backup_file}，请检查文件权限"
        
        # 读取备份文件
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
        except json.JSONDecodeError:
            return False, "备份文件格式无效，不是有效的JSON格式"
        except UnicodeDecodeError:
            return False, "备份文件编码错误，请确保文件为UTF-8编码"
        
        # 验证备份数据结构
        if not isinstance(backup_data, dict):
            return False, "备份文件内容格式不正确，缺少必要的数据结构"
            
        # 记录恢复操作
        print(f"开始为用户 {user_id} 恢复数据，模式: {restore_mode}")
        
        # 恢复分类
        restored_categories = 0
        if 'categories' in backup_data:
            for category in backup_data['categories']:
                # 检查是否只恢复新内容
                if restore_mode == 'add':
                    existing = db_categories.get((Category.name == category['name']) & (Category.user_id == user_id))
                    if existing:
                        continue
                
                # 确保分类归属当前用户
                category['user_id'] = user_id
                
                # 尝试插入或更新
                existing = db_categories.get(Category.id == category['id'])
                if existing:
                    db_categories.update(category, Category.id == category['id'])
                else:
                    db_categories.insert(category)
                restored_categories += 1
        
        # 恢复标签
        restored_tags = 0
        if 'tags' in backup_data:
            for tag in backup_data['tags']:
                existing = db_tags.get(Tag.name == tag['name'])
                if not existing:
                    db_tags.insert(tag)
                    restored_tags += 1
        
        # 恢复笔记
        restored_note_ids = []
        if 'notes' in backup_data:
            for note in backup_data['notes']:
                # 检查是否只恢复新内容
                if restore_mode == 'add':
                    existing = db_notes.get((Note.title == note['title']) & (Note.user_id == user_id))
                    if existing:
                        # 记录已存在的笔记ID，用于后续恢复笔记标签等
                        restored_note_ids.append((note['id'], existing['id']))
                        continue
                
                # 确保笔记归属当前用户
                note['user_id'] = user_id
                
                # 尝试插入或更新
                existing = db_notes.get(Note.id == note['id'])
                if existing and restore_mode == 'overwrite':
                    db_notes.update(note, Note.id == note['id'])
                else:
                    db_notes.insert(note)
                    restored_note_ids.append((note['id'], note['id']))
        
        # 创建ID映射
        id_map = dict(restored_note_ids)
        
        # 恢复笔记标签关系
        restored_note_tags = 0
        if 'note_tags' in backup_data:
            for note_tag in backup_data['note_tags']:
                old_note_id = note_tag['note_id']
                # 如果笔记ID在映射中，说明已恢复
                if old_note_id in id_map:
                    # 更新为新笔记ID
                    note_tag['note_id'] = id_map[old_note_id]
                    
                    # 检查是否已存在相同关系
                    existing = db_note_tags.get(
                        (NoteTag.note_id == note_tag['note_id']) & 
                        (NoteTag.tag_id == note_tag['tag_id'])
                    )
                    if not existing:
                        db_note_tags.insert(note_tag)
                        restored_note_tags += 1
        
        # 恢复版本
        restored_versions = 0
        if 'versions' in backup_data and restore_mode == 'overwrite':
            for version in backup_data['versions']:
                old_note_id = version['note_id']
                # 如果笔记ID在映射中，说明已恢复
                if old_note_id in id_map:
                    # 更新为新笔记ID
                    version['note_id'] = id_map[old_note_id]
                    
                    # 尝试插入新版本
                    existing = db_versions.get(Version.id == version['id'])
                    if not existing:
                        db_versions.insert(version)
                        restored_versions += 1
        
        # 恢复历史记录
        restored_histories = 0
        if 'histories' in backup_data and restore_mode == 'overwrite':
            for history in backup_data['histories']:
                old_note_id = history['note_id']
                # 如果笔记ID在映射中，说明已恢复
                if old_note_id in id_map:
                    # 更新为新笔记ID
                    history['note_id'] = id_map[old_note_id]
                    
                    # 尝试插入新历史记录
                    existing = db_history.get(History.id == history['id'])
                    if not existing:
                        db_history.insert(history)
                        restored_histories += 1
        
        # 记录恢复操作历史
        metadata = backup_data.get('metadata', {})
        details = f"从备份文件恢复{metadata.get('note_count', '未知数量的')}笔记，模式: {restore_mode}"
        
        # 创建全局历史记录
        if id_map:  # 首先检查id_map是否为空
            note_ids = set(id_map.values())  # 正确地创建一个集合
            for note_id in note_ids:  # 使用正确创建的集合进行迭代
                HistoryModel.create(
                    note_id=note_id,
                    user_id=user_id,
                    change_type='restore',
                    details=details
                )
        
        # 打印恢复统计信息
        restore_stats = f"恢复完成：{len(id_map)}个笔记, {restored_categories}个分类, {restored_tags}个标签, {restored_note_tags}个笔记标签关系, {restored_versions}个版本, {restored_histories}个历史记录"
        print(restore_stats)
        
        return True, f"已成功恢复 {len(id_map)} 个笔记"
    except Exception as e:
        print(f"恢复失败: {e}")
        import traceback
        traceback.print_exc()
        return False, f"恢复失败: {str(e)}"

# 创建默认分类
def create_default_categories(user_id):
    """为新用户创建默认分类"""
    defaults = [
        {'name': '未分类', 'order': 0},
        {'name': '日常笔记', 'order': 1},
        {'name': '工作', 'order': 2},
        {'name': '学习', 'order': 3}
    ]
    
    for item in defaults:
        CategoryModel.create(item['name'], user_id, None, item['order']) 